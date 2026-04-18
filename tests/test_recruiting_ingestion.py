from __future__ import annotations

from wiki_mcp.adapters.sources.worknet import WorknetRecruitingExternalAdapter
from wiki_mcp.domains.recruiting import RecruitingSourceIngestionPlugin


class StubWorknetRecruitingProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_recruiting_source(self, params: dict[str, object]) -> dict[str, object]:
        self.calls.append(params)
        return {
            "payloadVersion": "recruiting-source-payload/v1",
            "source": {
                "provider": "worknet",
                "kind": "open_recruitment",
                "sourceId": "EMP-1",
                "companySourceId": "COMP-1",
                "sourceUrl": "https://example.com/jobs/EMP-1",
                "mobileSourceUrl": "https://m.example.com/jobs/EMP-1",
                "fetchedAt": "2026-04-15T00:00:00.000Z",
                "contentHash": "hash-emp-1",
            },
            "posting": {
                "title": "백엔드 개발자",
                "companyName": "잡스위키",
                "companyType": "중견기업",
                "employmentType": "정규직",
                "startsAt": "2026-04-01",
                "closesAt": "2026-04-30",
                "summary": "플랫폼 API 개발",
                "applicationMethod": "홈페이지 접수",
                "requiredDocuments": "이력서, 포트폴리오",
                "acceptanceAnnouncement": "개별 안내",
                "inquiry": "recruit@example.com",
                "notes": "원격 근무 가능",
            },
            "company": {
                "sourceCompanyId": "COMP-1",
                "name": "잡스위키",
                "companyType": "중견기업",
                "homepageUrl": "https://jobswiki.example.com",
                "businessNumber": "123-45-67890",
                "summary": "채용 정보 플랫폼",
                "description": "개발자 중심의 채용 데이터 서비스를 운영합니다.",
                "mainBusiness": "채용 데이터 플랫폼",
                "logoUrl": "https://example.com/logo.png",
                "coordinates": {
                    "latitude": "37.0",
                    "longitude": "127.0",
                },
            },
            "jobs": [
                {
                    "sourceCode": "DEV-001",
                    "name": "백엔드 개발",
                }
            ],
            "recruitmentSections": [
                {
                    "title": "플랫폼팀",
                    "roleDescription": "API 설계 및 개발",
                    "selectionDescription": "코딩 테스트",
                    "location": "서울",
                    "careerRequirement": "3년 이상",
                    "educationRequirement": "대졸",
                    "otherRequirement": "Node.js 경험",
                    "openings": "2",
                    "note": "우대사항 있음",
                }
            ],
            "selectionSteps": [
                {
                    "name": "서류전형",
                    "schedule": "4월 2주",
                    "description": "서류 검토",
                    "note": "합격자 개별 통보",
                }
            ],
            "attachments": [
                {
                    "fileName": "guide.pdf",
                }
            ],
            "raw": {
                "openRecruitmentDetail": {"empSeqno": "EMP-1"},
            },
        }


def test_adapter_builds_source_record_from_external_payload() -> None:
    provider = StubWorknetRecruitingProvider()
    adapter = WorknetRecruitingExternalAdapter()

    source = adapter.fetch_source_record(
        provider,
        "EMP-1",
        auth_key="secret",
        include_raw=True,
    )

    assert len(provider.calls) == 1
    assert provider.calls[0]["sourceId"] == "EMP-1"
    assert provider.calls[0]["authKey"] == "secret"
    assert provider.calls[0]["includeRaw"] is True

    assert source["source_id"] == "EMP-1"
    assert source["connector"] == "worknet"
    assert source["domain"] == "recruiting"
    assert source["title"] == "백엔드 개발자"
    assert source["fetched_at"] == "2026-04-15T00:00:00.000Z"
    assert source["content_hash"] == "hash-emp-1"
    assert source["status"] == "active"
    assert "## Posting" in source["body_markdown"]
    assert "## Company" in source["body_markdown"]
    assert "## Selection Steps" in source["body_markdown"]
    assert source["metadata"]["payload_version"] == "recruiting-source-payload/v1"
    assert source["metadata"]["provider"] == "worknet"
    assert source["metadata"]["kind"] == "open_recruitment"
    assert source["metadata"]["company_source_id"] == "COMP-1"
    assert source["metadata"]["raw_included"] is True
    assert source["metadata"]["posting"]["company_name"] == "잡스위키"
    assert source["metadata"]["jobs"][0]["source_code"] == "DEV-001"
    assert source["metadata"]["attachments"][0]["file_name"] == "guide.pdf"


def test_plugin_extracts_docs_aligned_fact_records_and_relations() -> None:
    provider = StubWorknetRecruitingProvider()
    adapter = WorknetRecruitingExternalAdapter()
    plugin = RecruitingSourceIngestionPlugin()

    source = adapter.fetch_source_record(provider, "EMP-1")
    normalized = plugin.normalize_source(source)
    records = plugin.extract_fact_records(normalized)
    relations = plugin.extract_fact_relations(normalized, records)
    validation = plugin.validate_batch(normalized, records, relations)

    assert plugin.accepts(normalized) is True
    assert validation["ok"] is True
    assert validation["errors"] == []

    entity_types = {record["entity_type"] for record in records}
    assert entity_types == {"job_posting", "company", "role", "skill", "location"}

    record_by_type = {record["entity_type"]: record for record in records}
    posting = record_by_type["job_posting"]
    company = record_by_type["company"]
    role = record_by_type["role"]
    skill = record_by_type["skill"]
    location = record_by_type["location"]

    assert posting["canonical_key"] == "job_posting:EMP-1"
    assert posting["attributes"]["employment_type"] == "정규직"
    assert posting["attributes"]["source_url"] == "https://example.com/jobs/EMP-1"
    assert company["canonical_key"] == "company:COMP-1"
    assert company["attributes"]["normalized_name"] == "잡스위키"
    assert company["attributes"]["homepage_url"] == "https://jobswiki.example.com"
    assert role["canonical_key"] == "role:DEV-001"
    assert role["attributes"]["display_name"] == "백엔드 개발"
    assert skill["canonical_key"] == "skill:node-js"
    assert skill["attributes"]["name"] == "Node.js"
    assert location["canonical_key"] == "location:text-ea9858eeebb6"
    assert location["attributes"]["label"] == "서울"

    relation_types = {relation["relation_type"] for relation in relations}
    assert relation_types == {"posted_by", "has_role", "requires_skill", "located_in"}
    for relation in relations:
        assert relation["from_canonical_key"] == "job_posting:EMP-1"
        assert relation["scope"] == "shared"


def test_plugin_dedupes_repeated_skills_and_locations() -> None:
    provider = StubWorknetRecruitingProvider()
    adapter = WorknetRecruitingExternalAdapter()
    plugin = RecruitingSourceIngestionPlugin()

    source = adapter.fetch_source_record(provider, "EMP-1")
    source["metadata"]["recruitment_sections"].append(
        {
            "title": "플랫폼팀 복제",
            "role_description": "Node.js 운영 경험",
            "selection_description": None,
            "location": "서울",
            "career_requirement": None,
            "education_requirement": None,
            "other_requirement": "Node.js 경험",
            "openings": None,
            "note": None,
        }
    )

    normalized = plugin.normalize_source(source)
    records = plugin.extract_fact_records(normalized)
    relations = plugin.extract_fact_relations(normalized, records)

    location_records = [record for record in records if record["entity_type"] == "location"]
    skill_records = [record for record in records if record["entity_type"] == "skill"]
    located_relations = [relation for relation in relations if relation["relation_type"] == "located_in"]
    skill_relations = [relation for relation in relations if relation["relation_type"] == "requires_skill"]

    assert len(location_records) == 1
    assert len(skill_records) == 1
    assert len(located_relations) == 1
    assert len(skill_relations) == 1


def test_plugin_normalizes_multilingual_skill_aliases_to_shared_canonical_keys() -> None:
    provider = StubWorknetRecruitingProvider()
    adapter = WorknetRecruitingExternalAdapter()
    plugin = RecruitingSourceIngestionPlugin()

    source = adapter.fetch_source_record(provider, "EMP-1")
    source["metadata"]["posting"]["summary"] = "파이썬 기반 서비스와 React 운영 경험"
    source["metadata"]["posting"]["notes"] = "NodeJS, 노드 js 협업 경험 우대"
    source["metadata"]["recruitment_sections"][0]["other_requirement"] = "파이썬, 리액트, 노드JS 경험"

    normalized = plugin.normalize_source(source)
    records = plugin.extract_fact_records(normalized)
    relations = plugin.extract_fact_relations(normalized, records)

    skill_records = sorted(
        [record for record in records if record["entity_type"] == "skill"],
        key=lambda record: record["canonical_key"],
    )

    assert [record["canonical_key"] for record in skill_records] == [
        "skill:node-js",
        "skill:python",
        "skill:react",
    ]
    assert [record["attributes"]["name"] for record in skill_records] == [
        "Node.js",
        "Python",
        "React",
    ]
    assert len([relation for relation in relations if relation["relation_type"] == "requires_skill"]) == 3


def test_plugin_relations_inherit_scope_fields_from_posting_record() -> None:
    provider = StubWorknetRecruitingProvider()
    adapter = WorknetRecruitingExternalAdapter()
    plugin = RecruitingSourceIngestionPlugin()

    source = adapter.fetch_source_record(provider, "EMP-1")
    normalized = plugin.normalize_source(source)
    records = plugin.extract_fact_records(normalized)

    scoped_records = []
    for record in records:
        scoped_record = dict(record)
        scoped_record["scope"] = "user"
        scoped_record["tenant_id"] = "tenant-1"
        scoped_record["user_id"] = "user-1"
        scoped_records.append(scoped_record)

    relations = plugin.extract_fact_relations(normalized, scoped_records)

    assert relations
    for relation in relations:
        assert relation["scope"] == "user"
        assert relation["tenant_id"] == "tenant-1"
        assert relation["user_id"] == "user-1"
