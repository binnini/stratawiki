from __future__ import annotations

from wiki_mcp.services.personal_query import DefaultPersonalQueryService


class StubRetrievalService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def retrieve_for_query(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        return {
            "personal_ids": ["personal:plan-1"],
            "interpretation_ids": ["interp:market-1"],
            "fact_ids": ["fact:job-1"],
            "personal_explanations": [
                {
                    "layer": "personal",
                    "record_id": "personal:plan-1",
                    "score": 100,
                    "match_type": "exact",
                    "matched_fields": ["title"],
                    "profile_boost_applied": True,
                }
            ],
            "personal_records": [
                {
                    "id": "personal:plan-1",
                    "domain": "recruiting",
                    "kind": "career_plan",
                    "title": "Backend transition plan",
                    "summary": "Prioritize backend-focused applications this week.",
                    "snapshot_ref": {
                        "fact_snapshot_id": "fact_snap:new",
                        "interpretation_snapshot_id": "interp_snap:new",
                        "profile_version": "profile-v2",
                    },
                }
            ],
            "interpretation_explanations": [
                {
                    "layer": "interpretation",
                    "record_id": "interp:market-1",
                    "score": 64,
                    "match_type": "token_overlap",
                    "matched_fields": ["title", "path"],
                    "profile_boost_applied": False,
                }
            ],
            "interpretation_records": [
                {
                    "id": "interp:market-1",
                    "domain": "recruiting",
                    "kind": "market_summary",
                    "subject_type": "career_path",
                    "subject_id": "backend-transition",
                    "status": "active",
                    "confidence": 0.9,
                    "summary": "Backend hiring remains active for Python-heavy roles.",
                }
            ],
            "fact_explanations": [
                {
                    "layer": "fact",
                    "record_id": "fact:job-1",
                    "score": 32,
                    "match_type": "token_overlap",
                    "matched_fields": ["title"],
                    "profile_boost_applied": False,
                }
            ],
            "fact_records": [
                {
                    "id": "fact:job-1",
                    "domain": "recruiting",
                    "entity_type": "job_posting",
                    "canonical_key": "backend-engineer-seoul",
                    "scope": "shared",
                    "title": "Backend Engineer",
                }
            ],
            "personal_pages": [
                {
                    "domain": "recruiting",
                    "layer": "personal",
                    "record_id": "personal:plan-1",
                    "path": "wiki/personal/tenant-1/user-1/plan-1.md",
                    "title": "Backend transition plan",
                    "scope_ref": {
                        "scope": "user",
                        "tenant_id": "tenant-1",
                        "user_id": "user-1",
                    },
                    "snapshot_ref": {
                        "fact_snapshot_id": "fact_snap:new",
                        "interpretation_snapshot_id": "interp_snap:new",
                        "profile_version": "profile-v2",
                    },
                    "metadata": {"title": "Backend transition plan"},
                }
            ],
            "interpretation_pages": [
                {
                    "domain": "recruiting",
                    "layer": "interpretation",
                    "record_id": "interp:market-1",
                    "path": "wiki/shared/interpretation/backend-transition-market.md",
                    "title": "Backend transition market",
                    "scope_ref": {"scope": "shared"},
                    "snapshot_ref": {
                        "fact_snapshot_id": "fact_snap:new",
                        "interpretation_snapshot_id": "interp_snap:new",
                    },
                    "metadata": {"title": "Backend transition market"},
                }
            ],
            "fact_pages": [],
            "snapshot_ref": {
                "fact_snapshot_id": "fact_snap:new",
                "interpretation_snapshot_id": "interp_snap:new",
                "profile_version": "profile-v2",
            },
        }


def test_personal_query_service_builds_answer_bundle_on_retrieval_output() -> None:
    retrieval_service = StubRetrievalService()
    service = DefaultPersonalQueryService(retrieval_service=retrieval_service)

    retrieval, answer = service.query_personal_knowledge(
        domain="recruiting",
        question="How should I focus my backend transition?",
        scope_ref={"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
        profile_context={
            "user_id": "user-1",
            "tenant_id": "tenant-1",
            "domain": "recruiting",
            "profile_version": "profile-v2",
            "goals": ["transition"],
            "preferences": {"location": "Seoul"},
            "attributes": {"experience_years": 4},
        },
    )

    assert retrieval["personal_ids"] == ["personal:plan-1"]
    assert answer["answer_type"] == "personal_query_answer"
    assert answer["generation_strategy"] == "deterministic_summary_bundle_v1"
    assert answer["question"] == "How should I focus my backend transition?"
    assert answer["answer_summary"].startswith("Best current personal context:")
    assert "profile-version preference" in answer["answer_rationale"]
    assert "Rationale:" in answer["answer_markdown"]
    assert "## Personal Context" in answer["answer_markdown"]
    assert "## Shared Interpretation Context" in answer["answer_markdown"]
    assert answer["input_bundle"]["personal_context"][0] == {
        "layer": "personal",
        "record_id": "personal:plan-1",
        "title": "Backend transition plan",
        "summary": "Prioritize backend-focused applications this week.",
        "retrieval_score": 100,
        "match_reason": "exact match on title with profile-version preference",
        "matched_fields": ["title"],
        "path": "wiki/personal/tenant-1/user-1/plan-1.md",
    }
    assert answer["input_bundle"]["interpretation_context"][0]["record_id"] == "interp:market-1"
    assert answer["citations"][0]["record_id"] == "personal:plan-1"


def test_personal_query_service_returns_no_match_answer_when_retrieval_is_empty() -> None:
    class EmptyRetrievalService:
        def retrieve_for_query(self, **kwargs: object) -> dict[str, object]:
            return {
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

    service = DefaultPersonalQueryService(retrieval_service=EmptyRetrievalService())

    _, answer = service.query_personal_knowledge(
        domain="recruiting",
        question="Anything for me?",
        scope_ref={"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
    )

    assert answer["answer_summary"] == (
        "No matching personal, interpretation, or fact context was found."
    )
    assert answer["generation_strategy"] == "deterministic_summary_bundle_v1"
    assert answer["answer_rationale"] == (
        "No retrieval candidate cleared the current matching threshold."
    )
    assert answer["citations"] == []
