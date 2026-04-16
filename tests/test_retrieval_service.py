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


def test_retrieval_service_prefers_layer_order_and_merges_snapshot_from_personal() -> None:
    service = DefaultRetrievalService(page_read_service=StubPageReadService())

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

    assert result == {
        "personal_ids": ["personal:plan-1"],
        "interpretation_ids": ["interp:backend-transition-market"],
        "fact_ids": ["fact:job-posting-1"],
        "personal_pages": [
            {
                "domain": "recruiting",
                "layer": "personal",
                "record_id": "personal:plan-1",
                "path": "wiki/personal/tenant-1/user-1/backend-transition-plan.md",
                "title": "Backend Transition Plan",
                "scope_ref": {
                    "scope": "user",
                    "tenant_id": "tenant-1",
                    "user_id": "user-1",
                },
                "snapshot_ref": {
                    "fact_snapshot_id": "fact_snap:personal",
                    "interpretation_snapshot_id": "interp_snap:personal",
                    "profile_version": "profile-v2",
                },
                "metadata": {"title": "Backend Transition Plan"},
            }
        ],
        "interpretation_pages": [
            {
                "domain": "recruiting",
                "layer": "interpretation",
                "record_id": "interp:backend-transition-market",
                "path": "wiki/shared/interpretation/backend-transition-market.md",
                "title": "Backend Transition Market",
                "scope_ref": {"scope": "shared"},
                "snapshot_ref": {
                    "fact_snapshot_id": "fact_snap:shared",
                    "interpretation_snapshot_id": "interp_snap:shared",
                },
                "metadata": {"title": "Backend Transition Market"},
            }
        ],
        "fact_pages": [
            {
                "domain": "recruiting",
                "layer": "fact",
                "record_id": "fact:job-posting-1",
                "path": "wiki/shared/fact/backend-transition-evidence.md",
                "title": "Backend Transition Evidence",
                "scope_ref": {"scope": "shared"},
                "snapshot_ref": {"fact_snapshot_id": "fact_snap:evidence"},
                "metadata": {"title": "Backend Transition Evidence"},
            }
        ],
        "snapshot_ref": {
            "fact_snapshot_id": "fact_snap:personal",
            "interpretation_snapshot_id": "interp_snap:personal",
            "profile_version": "profile-v2",
        },
    }


def test_retrieval_service_matches_exact_record_id_lookup() -> None:
    service = DefaultRetrievalService(page_read_service=StubPageReadService())

    result = service.retrieve_for_query(
        domain="recruiting",
        question="personal:plan-1",
        scope_ref={"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
    )

    assert result["personal_ids"] == ["personal:plan-1"]
    assert result["personal_pages"][0]["record_id"] == "personal:plan-1"
    assert result["interpretation_ids"] == []
    assert result["interpretation_pages"] == []
    assert result["fact_ids"] == []
    assert result["fact_pages"] == []
    assert result["snapshot_ref"]["fact_snapshot_id"] == "fact_snap:personal"


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
    }
    assert page_read_service.calls == []
