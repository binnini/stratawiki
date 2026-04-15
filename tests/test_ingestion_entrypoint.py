from __future__ import annotations

from psycopg import Connection

from wiki_mcp.services.ingestion_entrypoint import (
    DefaultIngestionEntrypoint,
    build_default_ingestion_entrypoint,
)


class StubCoreIngestionService:
    def __init__(self, *, validation_ok: bool = True) -> None:
        self.validation_ok = validation_ok
        self.prepare_calls: list[tuple[dict[str, object], object]] = []
        self.ingest_calls: list[dict[str, object]] = []

    def prepare_batch(
        self,
        source: dict[str, object],
        plugin: object,
    ) -> dict[str, object]:
        self.prepare_calls.append((source, plugin))
        return {
            "source": source,
            "records": [],
            "relations": [],
            "validation": {
                "ok": self.validation_ok,
                "warnings": ["warn-1"] if not self.validation_ok else [],
                "errors": ["bad-batch"] if not self.validation_ok else [],
            },
        }

    def ingest_batch(self, batch: dict[str, object]) -> dict[str, object]:
        self.ingest_calls.append(batch)
        return {
            "fact_snapshot_id": "fact_snap:test",
            "facts_created": 1,
            "facts_updated": 0,
            "relations_created": 0,
            "affected_fact_ids": ["fact:1"],
            "outbox_event_ids": ["evt-1"],
        }


class AcceptingPlugin:
    def accepts(self, source: dict[str, object]) -> bool:
        return source["domain"] == "recruiting"


class OtherPlugin:
    def accepts(self, source: dict[str, object]) -> bool:
        return source["domain"] == "other"


class StubWorknetRecruitingProvider:
    def get_recruiting_source(self, params: dict[str, object]) -> dict[str, object]:
        return {
            "payloadVersion": "recruiting-source-payload/v1",
            "source": {
                "provider": "worknet",
                "kind": "open_recruitment",
                "sourceId": params["sourceId"],
                "companySourceId": "COMP-1",
                "sourceUrl": "https://example.com/jobs/EMP-1",
                "mobileSourceUrl": "https://m.example.com/jobs/EMP-1",
                "fetchedAt": "2026-04-16T00:00:00.000Z",
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
            "jobs": [{"sourceCode": "DEV-001", "name": "백엔드 개발"}],
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
            "selectionSteps": [],
            "attachments": [],
            "raw": None,
        }


def _source(domain: str = "recruiting") -> dict[str, object]:
    return {
        "source_id": "EMP-1",
        "connector": "worknet",
        "domain": domain,
        "title": "Backend Engineer",
        "body_markdown": "test",
        "metadata": {},
        "fetched_at": "2026-04-16T00:00:00Z",
        "content_hash": "hash-1",
        "status": "active",
    }


def test_ingestion_entrypoint_returns_plugin_not_found_error() -> None:
    entrypoint = DefaultIngestionEntrypoint(
        core_ingestion_service=StubCoreIngestionService(),
        plugins=[OtherPlugin()],
    )

    result = entrypoint.ingest_source(_source())

    assert result["ok"] is False
    assert result["error"]["code"] == "plugin_not_found"


def test_ingestion_entrypoint_returns_validation_failure_without_persisting() -> None:
    core_service = StubCoreIngestionService(validation_ok=False)
    entrypoint = DefaultIngestionEntrypoint(
        core_ingestion_service=core_service,
        plugins=[AcceptingPlugin()],
    )

    result = entrypoint.ingest_source(_source())

    assert result["ok"] is False
    assert result["plugin_name"] == "AcceptingPlugin"
    assert result["validation"]["ok"] is False
    assert result["error"]["code"] == "validation_failed"
    assert core_service.ingest_calls == []


def test_default_ingestion_entrypoint_ingests_worknet_source_into_postgres(
    postgres_connection: Connection[dict],
) -> None:
    entrypoint = build_default_ingestion_entrypoint(postgres_connection)

    result = entrypoint.ingest_worknet_source(
        StubWorknetRecruitingProvider(),
        "EMP-1",
        include_raw=True,
    )

    assert result["ok"] is True
    assert result["plugin_name"] == "RecruitingSourceIngestionPlugin"
    assert result["ingestion_result"]["facts_created"] == 4
    assert result["ingestion_result"]["relations_created"] == 3

    with postgres_connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS count FROM fact.record_envelopes")
        fact_count = cursor.fetchone()["count"]
        cursor.execute("SELECT COUNT(*) AS count FROM ops.snapshot_pointer")
        snapshot_pointer_count = cursor.fetchone()["count"]
        cursor.execute("SELECT COUNT(*) AS count FROM ops.outbox_event")
        outbox_count = cursor.fetchone()["count"]

    assert fact_count == 4
    assert snapshot_pointer_count == 1
    assert outbox_count == 1
