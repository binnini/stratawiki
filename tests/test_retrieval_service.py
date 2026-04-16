from __future__ import annotations

from wiki_mcp.services.retrieval import DefaultRetrievalService


class StubPageReadService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_page(self, **kwargs: object) -> dict[str, object] | None:
        raise AssertionError("get_page should not be called in retrieval tests")

    def list_pages(self, **kwargs: object) -> list[dict[str, object]]:
        self.calls.append(kwargs)

        layer = kwargs["layer"]
        scope_ref = kwargs["scope_ref"]
        if layer == "personal":
            assert scope_ref == {
                "scope": "user",
                "tenant_id": "tenant-1",
                "user_id": "user-1",
            }
            return [
                {
                    "domain": "recruiting",
                    "layer": "personal",
                    "record_id": "personal:plan-1",
                    "path": "wiki/personal/tenant-1/user-1/backend-transition-plan.md",
                    "title": "Backend Transition Plan",
                    "scope_ref": scope_ref,
                    "snapshot_ref": {
                        "fact_snapshot_id": "fact_snap:personal",
                        "interpretation_snapshot_id": "interp_snap:personal",
                        "profile_version": "profile-v2",
                    },
                    "metadata": {"title": "Backend Transition Plan"},
                },
                {
                    "domain": "recruiting",
                    "layer": "personal",
                    "record_id": "personal:notes-1",
                    "path": "wiki/personal/tenant-1/user-1/weekly-notes.md",
                    "title": "Weekly Notes",
                    "scope_ref": scope_ref,
                    "snapshot_ref": {
                        "fact_snapshot_id": "fact_snap:personal:other",
                        "interpretation_snapshot_id": "interp_snap:personal:other",
                        "profile_version": "profile-v1",
                    },
                    "metadata": {"title": "Weekly Notes"},
                },
            ]

        if layer == "interpretation":
            assert scope_ref == {"scope": "shared"}
            return [
                {
                    "domain": "recruiting",
                    "layer": "interpretation",
                    "record_id": "interp:backend-transition-market",
                    "path": "wiki/shared/interpretation/backend-transition-market.md",
                    "title": "Backend Transition Market",
                    "scope_ref": scope_ref,
                    "snapshot_ref": {
                        "fact_snapshot_id": "fact_snap:shared",
                        "interpretation_snapshot_id": "interp_snap:shared",
                    },
                    "metadata": {"title": "Backend Transition Market"},
                }
            ]

        if layer == "fact":
            assert scope_ref == {"scope": "shared"}
            return [
                {
                    "domain": "recruiting",
                    "layer": "fact",
                    "record_id": "fact:job-posting-1",
                    "path": "wiki/shared/fact/backend-transition-evidence.md",
                    "title": "Backend Transition Evidence",
                    "scope_ref": scope_ref,
                    "snapshot_ref": {"fact_snapshot_id": "fact_snap:evidence"},
                    "metadata": {"title": "Backend Transition Evidence"},
                }
            ]

        raise AssertionError(f"Unexpected layer {layer!r}")


class StubPersonalRepository:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_by_ids(self, ids: list[str], scope_ref: dict[str, str]) -> list[dict[str, object]]:
        self.calls.append({"ids": ids, "scope_ref": scope_ref})
        return [
            {
                "id": "personal:plan-1",
                "domain": "recruiting",
                "kind": "career_plan",
                "title": "Backend Transition Plan",
                "summary": "Personal strategy summary",
                "scope_ref": scope_ref,
                "snapshot_ref": {
                    "fact_snapshot_id": "fact_snap:personal",
                    "interpretation_snapshot_id": "interp_snap:personal",
                    "profile_version": "profile-v2",
                },
                "profile_version": "profile-v2",
                "body_path": "wiki/personal/tenant-1/user-1/backend-transition-plan.md",
                "status": "active",
                "schema_version": "v1",
                "provenance": {"source": "test"},
            }
        ]


class StubInterpretationRepository:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_by_ids(self, ids: list[str], scope_ref: dict[str, str]) -> list[dict[str, object]]:
        self.calls.append({"ids": ids, "scope_ref": scope_ref})
        return [
            {
                "id": "interp:backend-transition-market",
                "domain": "recruiting",
                "kind": "market_summary",
                "subject_type": "career_path",
                "subject_id": "backend-transition",
                "scope_ref": scope_ref,
                "schema_version": "v1",
                "status": "active",
                "confidence": 0.9,
                "computed_at": "2026-04-16T00:00:00Z",
                "expires_at": None,
                "body": {"summary": "Shared market context"},
                "provenance": {"source": "test"},
                "render_hints": {},
            }
        ]


class StubFactRepository:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_by_ids(self, ids: list[str], scope_ref: dict[str, str]) -> list[dict[str, object]]:
        self.calls.append({"ids": ids, "scope_ref": scope_ref})
        return [
            {
                "id": "fact:job-posting-1",
                "domain": "recruiting",
                "entity_type": "job_posting",
                "canonical_key": "job_posting:backend-transition-1",
                "attributes": {"title": "Backend Transition Evidence"},
                "scope": scope_ref["scope"],
                "schema_version": "v1",
                "provenance": {"source": "test"},
            }
        ]


def test_retrieval_service_prefers_layer_order_and_merges_snapshot_from_personal() -> None:
    personal_repository = StubPersonalRepository()
    interpretation_repository = StubInterpretationRepository()
    fact_repository = StubFactRepository()
    service = DefaultRetrievalService(
        page_read_service=StubPageReadService(),
        personal_repository=personal_repository,
        interpretation_repository=interpretation_repository,
        fact_repository=fact_repository,
    )

    result = service.retrieve_for_query(
        domain="recruiting",
        question="Backend Transition Plan",
        scope_ref={"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
        profile_context={
            "user_id": "user-1",
            "tenant_id": "tenant-1",
            "domain": "recruiting",
            "profile_version": "profile-v2",
            "goals": ["transition"],
            "preferences": {},
            "attributes": {},
        },
    )

    assert result["personal_ids"] == ["personal:plan-1"]
    assert result["interpretation_ids"] == ["interp:backend-transition-market"]
    assert result["fact_ids"] == ["fact:job-posting-1"]
    assert result["personal_explanations"] == [
        {
            "layer": "personal",
            "record_id": "personal:plan-1",
            "rank": 1,
            "score": 100,
            "match_type": "exact",
            "matched_fields": ["title"],
            "matched_token_count": 3,
            "profile_boost_applied": False,
        }
    ]
    assert result["interpretation_explanations"][0]["record_id"] == "interp:backend-transition-market"
    assert result["interpretation_explanations"][0]["rank"] == 1
    assert result["interpretation_explanations"][0]["match_type"] == "token_overlap"
    assert set(result["interpretation_explanations"][0]["matched_fields"]) == {
        "record_id",
        "title",
        "path",
    }
    assert result["interpretation_explanations"][0]["score"] > 0
    assert result["interpretation_explanations"][0]["matched_token_count"] > 0
    assert result["fact_explanations"][0]["record_id"] == "fact:job-posting-1"
    assert result["fact_explanations"][0]["rank"] == 1
    assert result["fact_explanations"][0]["match_type"] == "token_overlap"
    assert set(result["fact_explanations"][0]["matched_fields"]) == {"title", "path"}
    assert result["fact_explanations"][0]["score"] > 0
    assert result["fact_explanations"][0]["matched_token_count"] > 0
    assert result["personal_records"] == [
        {
            "id": "personal:plan-1",
            "domain": "recruiting",
            "kind": "career_plan",
            "title": "Backend Transition Plan",
            "summary": "Personal strategy summary",
            "snapshot_ref": {
                "fact_snapshot_id": "fact_snap:personal",
                "interpretation_snapshot_id": "interp_snap:personal",
                "profile_version": "profile-v2",
            },
        }
    ]
    assert result["interpretation_records"] == [
        {
            "id": "interp:backend-transition-market",
            "domain": "recruiting",
            "kind": "market_summary",
            "subject_type": "career_path",
            "subject_id": "backend-transition",
            "status": "active",
            "confidence": 0.9,
            "summary": "Shared market context",
        }
    ]
    assert result["fact_records"] == [
        {
            "id": "fact:job-posting-1",
            "domain": "recruiting",
            "entity_type": "job_posting",
            "canonical_key": "job_posting:backend-transition-1",
            "scope": "shared",
            "title": "Backend Transition Evidence",
        }
    ]
    assert result["personal_pages"][0]["record_id"] == "personal:plan-1"
    assert result["interpretation_pages"][0]["record_id"] == "interp:backend-transition-market"
    assert result["fact_pages"][0]["record_id"] == "fact:job-posting-1"
    assert result["snapshot_ref"] == {
        "fact_snapshot_id": "fact_snap:personal",
        "interpretation_snapshot_id": "interp_snap:personal",
        "profile_version": "profile-v2",
    }
    assert personal_repository.calls == [
        {
            "ids": ["personal:plan-1"],
            "scope_ref": {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
        }
    ]
    assert interpretation_repository.calls == [
        {
            "ids": ["interp:backend-transition-market"],
            "scope_ref": {"scope": "shared"},
        }
    ]
    assert fact_repository.calls == [
        {
            "ids": ["fact:job-posting-1"],
            "scope_ref": {"scope": "shared"},
        }
    ]


def test_retrieval_service_matches_exact_record_id_lookup() -> None:
    service = DefaultRetrievalService(page_read_service=StubPageReadService())

    result = service.retrieve_for_query(
        domain="recruiting",
        question="personal:plan-1",
        scope_ref={"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
    )

    assert result["personal_ids"] == ["personal:plan-1"]
    assert result["personal_pages"][0]["record_id"] == "personal:plan-1"
    assert result["personal_explanations"][0]["match_type"] == "exact"
    assert result["personal_explanations"][0]["rank"] == 1
    assert result["interpretation_ids"] == []
    assert result["interpretation_pages"] == []
    assert result["interpretation_explanations"] == []
    assert result["fact_ids"] == []
    assert result["fact_pages"] == []
    assert result["fact_explanations"] == []
    assert result["snapshot_ref"]["fact_snapshot_id"] == "fact_snap:personal"


def test_retrieval_service_orders_hydrated_records_by_matched_ids() -> None:
    class OrderedPageReadService:
        def get_page(self, **kwargs: object) -> dict[str, object] | None:
            raise AssertionError("get_page should not be called in retrieval tests")

        def list_pages(self, **kwargs: object) -> list[dict[str, object]]:
            layer = kwargs["layer"]
            if layer != "personal":
                return []
            return [
                {
                    "domain": "recruiting",
                    "layer": "personal",
                    "record_id": "personal:b",
                    "path": "wiki/personal/b.md",
                    "title": "Backend plan beta",
                    "scope_ref": kwargs["scope_ref"],
                    "snapshot_ref": {"fact_snapshot_id": "fact_snap:new"},
                    "metadata": {"title": "Backend plan beta"},
                },
                {
                    "domain": "recruiting",
                    "layer": "personal",
                    "record_id": "personal:a",
                    "path": "wiki/personal/a.md",
                    "title": "Backend plan alpha",
                    "scope_ref": kwargs["scope_ref"],
                    "snapshot_ref": {"fact_snapshot_id": "fact_snap:new"},
                    "metadata": {"title": "Backend plan alpha"},
                },
            ]

    class OutOfOrderPersonalRepository:
        def get_by_ids(self, ids: list[str], scope_ref: dict[str, str]) -> list[dict[str, object]]:
            return [
                {
                    "id": "personal:a",
                    "domain": "recruiting",
                    "kind": "notes",
                    "title": "A",
                    "summary": "A",
                    "scope_ref": scope_ref,
                    "snapshot_ref": {"fact_snapshot_id": "fact_snap:new"},
                    "profile_version": "profile-v1",
                    "body_path": "wiki/personal/a.md",
                    "status": "active",
                    "schema_version": "v1",
                    "provenance": {},
                },
                {
                    "id": "personal:b",
                    "domain": "recruiting",
                    "kind": "notes",
                    "title": "B",
                    "summary": "B",
                    "scope_ref": scope_ref,
                    "snapshot_ref": {"fact_snapshot_id": "fact_snap:new"},
                    "profile_version": "profile-v1",
                    "body_path": "wiki/personal/b.md",
                    "status": "active",
                    "schema_version": "v1",
                    "provenance": {},
                },
            ]

    service = DefaultRetrievalService(
        page_read_service=OrderedPageReadService(),
        personal_repository=OutOfOrderPersonalRepository(),
        layer_result_limit=2,
    )

    result = service.retrieve_for_query(
        domain="recruiting",
        question="backend plan",
        scope_ref={"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
    )

    assert result["personal_ids"] == ["personal:b", "personal:a"]
    assert [item["record_id"] for item in result["personal_explanations"]] == [
        "personal:b",
        "personal:a",
    ]
    assert [record["id"] for record in result["personal_records"]] == [
        "personal:b",
        "personal:a",
    ]
    assert result["personal_records"][0]["title"] == "B"


class EmptyPageReadService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_page(self, **kwargs: object) -> dict[str, object] | None:
        raise AssertionError("get_page should not be called in retrieval tests")

    def list_pages(self, **kwargs: object) -> list[dict[str, object]]:
        self.calls.append(kwargs)
        return []


def test_retrieval_service_returns_empty_result_without_snapshot_when_no_match() -> None:
    page_read_service = EmptyPageReadService()
    service = DefaultRetrievalService(page_read_service=page_read_service)

    result = service.retrieve_for_query(
        domain="recruiting",
        question="missing topic",
        scope_ref={"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
    )

    assert result == {
        "personal_ids": [],
        "interpretation_ids": [],
        "fact_ids": [],
        "personal_pages": [],
        "interpretation_pages": [],
        "fact_pages": [],
        "personal_explanations": [],
        "interpretation_explanations": [],
        "fact_explanations": [],
    }
    assert page_read_service.calls == [
        {
            "domain": "recruiting",
            "scope_ref": {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
            "layer": "personal",
            "limit": 50,
        },
        {
            "domain": "recruiting",
            "scope_ref": {"scope": "shared"},
            "layer": "interpretation",
            "limit": 50,
        },
        {
            "domain": "recruiting",
            "scope_ref": {"scope": "shared"},
            "layer": "fact",
            "limit": 50,
        },
    ]


def test_retrieval_service_returns_empty_result_for_blank_query() -> None:
    page_read_service = EmptyPageReadService()
    service = DefaultRetrievalService(page_read_service=page_read_service)

    result = service.retrieve_for_query(
        domain="recruiting",
        question="   ",
        scope_ref={"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
    )

    assert result == {
        "personal_ids": [],
        "interpretation_ids": [],
        "fact_ids": [],
        "personal_pages": [],
        "interpretation_pages": [],
        "fact_pages": [],
        "personal_explanations": [],
        "interpretation_explanations": [],
        "fact_explanations": [],
    }
    assert page_read_service.calls == []
