from __future__ import annotations

from wiki_mcp.services.retrieval import DefaultRetrievalService
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
                    "rank": 1,
                    "score": 100,
                    "match_type": "exact",
                    "matched_fields": ["title"],
                    "matched_token_count": 3,
                    "profile_boost_applied": True,
                }
            ],
            "personal_records": [
                {
                    "id": "personal:plan-1",
                    "domain": "recruiting",
                    "kind": "career_transition_plan",
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
                    "rank": 1,
                    "score": 64,
                    "match_type": "token_overlap",
                    "matched_fields": ["title", "path"],
                    "matched_token_count": 2,
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
                    "rank": 1,
                    "score": 32,
                    "match_type": "token_overlap",
                    "matched_fields": ["title"],
                    "matched_token_count": 1,
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
    assert answer["personal_family"] == "career_transition_plan"
    assert answer["answer_rationale_items"][0]["category"] == "selection"
    assert answer["answer_rationale_items"][1]["category"] == "ranking"
    assert answer["question"] == "How should I focus my backend transition?"
    assert answer["answer_summary"].startswith("Current career transition plan focus:")
    assert "profile-version preference" in answer["answer_rationale"]
    assert "## Recommended Actions" in answer["answer_markdown"]
    assert "## Market Signals" in answer["answer_markdown"]
    assert answer["recommended_actions"][0].startswith("Prioritize the transition direction")
    assert answer["input_bundle"]["personal_context"][0] == {
        "layer": "personal",
        "record_id": "personal:plan-1",
        "title": "Backend transition plan",
        "summary": "Prioritize backend-focused applications this week.",
        "kind": "career_transition_plan",
        "retrieval_rank": 1,
        "retrieval_score": 100,
        "matched_token_count": 3,
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
    assert "personal_family" not in answer
    assert answer["answer_rationale"] == (
        "No retrieval candidate cleared the current matching threshold."
    )
    assert answer["answer_rationale_items"][0]["category"] == "selection"
    assert answer["citations"] == []


def test_personal_query_service_builds_profile_gap_analysis_family_answer() -> None:
    class ProfileGapRetrievalService:
        def retrieve_for_query(self, **kwargs: object) -> dict[str, object]:
            return {
                "personal_ids": ["personal:gap-1"],
                "interpretation_ids": ["interp:market-1"],
                "fact_ids": [],
                "personal_explanations": [
                    {
                        "layer": "personal",
                        "record_id": "personal:gap-1",
                        "rank": 1,
                        "score": 80,
                        "match_type": "contains",
                        "matched_fields": ["title"],
                        "matched_token_count": 2,
                        "profile_boost_applied": False,
                    }
                ],
                "personal_records": [
                    {
                        "id": "personal:gap-1",
                        "domain": "recruiting",
                        "kind": "profile_gap_analysis",
                        "title": "Backend profile gap analysis",
                        "summary": "Your strongest gaps are backend project signaling and production Python depth.",
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
                        "rank": 1,
                        "score": 32,
                        "match_type": "token_overlap",
                        "matched_fields": ["title"],
                        "matched_token_count": 1,
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
                        "summary": "Python-heavy backend hiring remains active.",
                    }
                ],
                "fact_explanations": [],
                "fact_records": [],
                "personal_pages": [
                    {
                        "domain": "recruiting",
                        "layer": "personal",
                        "record_id": "personal:gap-1",
                        "path": "wiki/personal/tenant-1/user-1/gap-1.md",
                        "title": "Backend profile gap analysis",
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
                        "metadata": {"title": "Backend profile gap analysis"},
                    }
                ],
                "interpretation_pages": [],
                "fact_pages": [],
                "snapshot_ref": {
                    "fact_snapshot_id": "fact_snap:new",
                    "interpretation_snapshot_id": "interp_snap:new",
                    "profile_version": "profile-v2",
                },
            }

    service = DefaultPersonalQueryService(retrieval_service=ProfileGapRetrievalService())

    _, answer = service.query_personal_knowledge(
        domain="recruiting",
        question="What are my backend gaps?",
        scope_ref={"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
        profile_context={
            "user_id": "user-1",
            "tenant_id": "tenant-1",
            "domain": "recruiting",
            "profile_version": "profile-v2",
            "goals": ["transition_to_backend", "improve_signaling"],
            "preferences": {},
            "attributes": {"experience_years": 3},
        },
    )

    assert answer["personal_family"] == "profile_gap_analysis"
    assert answer["answer_summary"].startswith("Current profile gap focus:")
    assert answer["recommended_actions"][0].startswith("Turn the main gap described")
    assert "## Gap-Closing Actions" in answer["answer_markdown"]
    assert answer["answer_rationale_items"][1]["category"] == "ranking"


def test_personal_query_service_builds_weekly_action_plan_family_answer() -> None:
    class WeeklyActionRetrievalService:
        def retrieve_for_query(self, **kwargs: object) -> dict[str, object]:
            return {
                "personal_ids": ["personal:weekly-1"],
                "interpretation_ids": ["interp:market-1"],
                "fact_ids": ["fact:job-1"],
                "personal_explanations": [
                    {
                        "layer": "personal",
                        "record_id": "personal:weekly-1",
                        "rank": 1,
                        "score": 80,
                        "match_type": "contains",
                        "matched_fields": ["title"],
                        "matched_token_count": 2,
                        "profile_boost_applied": False,
                    }
                ],
                "personal_records": [
                    {
                        "id": "personal:weekly-1",
                        "domain": "recruiting",
                        "kind": "weekly_action_plan",
                        "title": "Backend weekly action plan",
                        "summary": "Focus this week on applications, Python refresh, and one portfolio improvement.",
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
                        "rank": 1,
                        "score": 32,
                        "match_type": "token_overlap",
                        "matched_fields": ["title"],
                        "matched_token_count": 1,
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
                        "summary": "Backend demand is still active this week.",
                    }
                ],
                "fact_explanations": [
                    {
                        "layer": "fact",
                        "record_id": "fact:job-1",
                        "rank": 1,
                        "score": 32,
                        "match_type": "token_overlap",
                        "matched_fields": ["title"],
                        "matched_token_count": 1,
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
                        "record_id": "personal:weekly-1",
                        "path": "wiki/personal/tenant-1/user-1/weekly-1.md",
                        "title": "Backend weekly action plan",
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
                        "metadata": {"title": "Backend weekly action plan"},
                    }
                ],
                "interpretation_pages": [],
                "fact_pages": [],
                "snapshot_ref": {
                    "fact_snapshot_id": "fact_snap:new",
                    "interpretation_snapshot_id": "interp_snap:new",
                    "profile_version": "profile-v2",
                },
            }

    service = DefaultPersonalQueryService(retrieval_service=WeeklyActionRetrievalService())

    _, answer = service.query_personal_knowledge(
        domain="recruiting",
        question="What should I do this week?",
        scope_ref={"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
    )

    assert answer["personal_family"] == "weekly_action_plan"
    assert answer["answer_summary"].startswith("Current weekly action focus:")
    assert answer["recommended_actions"][0].startswith("Execute the top weekly priority")
    assert "## This Week" in answer["answer_markdown"]
    assert answer["answer_rationale_items"][1]["category"] == "ranking"


def test_personal_query_service_selection_reflects_canonical_retrieval_ranking() -> None:
    class CanonicalSummaryPageReadService:
        def get_page(self, **kwargs: object) -> dict[str, object] | None:
            raise AssertionError("get_page should not be called in personal query tests")

        def list_pages(self, **kwargs: object) -> list[dict[str, object]]:
            if kwargs["layer"] == "personal":
                return [
                    {
                        "domain": "recruiting",
                        "layer": "personal",
                        "record_id": "personal:weekly-1",
                        "path": "wiki/personal/tenant-1/user-1/execution-notes.md",
                        "title": "Execution Notes",
                        "scope_ref": kwargs["scope_ref"],
                        "snapshot_ref": {
                            "fact_snapshot_id": "fact_snap:new",
                            "interpretation_snapshot_id": "interp_snap:new",
                            "profile_version": "profile-v2",
                        },
                        "metadata": {"title": "Execution Notes"},
                    },
                    {
                        "domain": "recruiting",
                        "layer": "personal",
                        "record_id": "personal:gap-1",
                        "path": "wiki/personal/tenant-1/user-1/career-notes.md",
                        "title": "Career Notes",
                        "scope_ref": kwargs["scope_ref"],
                        "snapshot_ref": {
                            "fact_snapshot_id": "fact_snap:new",
                            "interpretation_snapshot_id": "interp_snap:new",
                            "profile_version": "profile-v2",
                        },
                        "metadata": {"title": "Career Notes"},
                    },
                ]
            return []

    class CanonicalSummaryPersonalRepository:
        def get_by_ids(self, ids: list[str], scope_ref: dict[str, str]) -> list[dict[str, object]]:
            return [
                {
                    "id": "personal:weekly-1",
                    "domain": "recruiting",
                    "kind": "weekly_action_plan",
                    "title": "Execution Notes",
                    "summary": "Weekly admin follow-up and generic applications.",
                    "scope_ref": scope_ref,
                    "snapshot_ref": {
                        "fact_snapshot_id": "fact_snap:new",
                        "interpretation_snapshot_id": "interp_snap:new",
                        "profile_version": "profile-v2",
                    },
                    "profile_version": "profile-v2",
                    "body_path": "wiki/personal/tenant-1/user-1/execution-notes.md",
                    "status": "active",
                    "schema_version": "v1",
                    "provenance": {},
                },
                {
                    "id": "personal:gap-1",
                    "domain": "recruiting",
                    "kind": "profile_gap_analysis",
                    "title": "Career Notes",
                    "summary": "Your strongest gaps are backend Python depth and production debugging evidence.",
                    "scope_ref": scope_ref,
                    "snapshot_ref": {
                        "fact_snapshot_id": "fact_snap:new",
                        "interpretation_snapshot_id": "interp_snap:new",
                        "profile_version": "profile-v2",
                    },
                    "profile_version": "profile-v2",
                    "body_path": "wiki/personal/tenant-1/user-1/career-notes.md",
                    "status": "active",
                    "schema_version": "v1",
                    "provenance": {},
                },
            ]

        def list_for_retrieval(
            self,
            *,
            domain: str,
            scope_ref: dict[str, str],
            limit: int,
        ) -> list[dict[str, object]]:
            return []

    retrieval_service = DefaultRetrievalService(
        page_read_service=CanonicalSummaryPageReadService(),
        personal_repository=CanonicalSummaryPersonalRepository(),
    )
    service = DefaultPersonalQueryService(retrieval_service=retrieval_service)

    _, answer = service.query_personal_knowledge(
        domain="recruiting",
        question="backend python depth",
        scope_ref={"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
        profile_context={
            "user_id": "user-1",
            "tenant_id": "tenant-1",
            "domain": "recruiting",
            "profile_version": "profile-v2",
            "goals": ["transition_to_backend"],
            "preferences": {},
            "attributes": {},
        },
    )

    assert answer["personal_family"] == "profile_gap_analysis"
    assert answer["input_bundle"]["personal_context"][0]["record_id"] == "personal:gap-1"
    assert answer["input_bundle"]["personal_context"][0]["matched_fields"] == [
        "canonical_summary"
    ]
    assert answer["answer_summary"].startswith("Current profile gap focus:")


def test_personal_query_service_uses_canonical_only_personal_candidate_for_family_selection() -> None:
    class EmptyPageReadService:
        def get_page(self, **kwargs: object) -> dict[str, object] | None:
            raise AssertionError("get_page should not be called in personal query tests")

        def list_pages(self, **kwargs: object) -> list[dict[str, object]]:
            return []

    class CanonicalOnlyPersonalRepository:
        def get_by_ids(self, ids: list[str], scope_ref: dict[str, str]) -> list[dict[str, object]]:
            return []

        def list_for_retrieval(
            self,
            *,
            domain: str,
            scope_ref: dict[str, str],
            limit: int,
        ) -> list[dict[str, object]]:
            return [
                {
                    "id": "personal:gap-1",
                    "domain": "recruiting",
                    "kind": "profile_gap_analysis",
                    "title": "Backend gap analysis",
                    "summary": "Your strongest gaps are backend Python depth and production debugging evidence.",
                    "scope_ref": scope_ref,
                    "snapshot_ref": {
                        "fact_snapshot_id": "fact_snap:new",
                        "interpretation_snapshot_id": "interp_snap:new",
                        "profile_version": "profile-v2",
                    },
                    "profile_version": "profile-v2",
                    "body_path": "wiki/personal/tenant-1/user-1/gap-1.md",
                    "status": "active",
                    "schema_version": "v1",
                    "provenance": {},
                }
            ]

    retrieval_service = DefaultRetrievalService(
        page_read_service=EmptyPageReadService(),
        personal_repository=CanonicalOnlyPersonalRepository(),
    )
    service = DefaultPersonalQueryService(retrieval_service=retrieval_service)

    _, answer = service.query_personal_knowledge(
        domain="recruiting",
        question="backend python depth",
        scope_ref={"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
    )

    assert answer["personal_family"] == "profile_gap_analysis"
    assert answer["input_bundle"]["personal_context"][0]["record_id"] == "personal:gap-1"
    assert "path" not in answer["input_bundle"]["personal_context"][0]
    assert answer["input_bundle"]["personal_context"][0]["matched_fields"] == [
        "canonical_summary"
    ]
    assert answer["answer_summary"].startswith("Current profile gap focus:")
