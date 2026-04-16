from __future__ import annotations

from pathlib import Path

from psycopg import Connection

from wiki_mcp.services.personal_query_entrypoint import (
    DefaultPersonalQueryEntrypoint,
    build_default_personal_query_entrypoint,
)


class StubPersonalQueryService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def query_personal_knowledge(self, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        self.calls.append(kwargs)
        return (
            {
                "personal_ids": ["personal:plan-1"],
                "interpretation_ids": [],
                "fact_ids": [],
                "personal_pages": [],
                "interpretation_pages": [],
                "fact_pages": [],
                "personal_explanations": [],
                "interpretation_explanations": [],
                "fact_explanations": [],
            },
            {
                "answer_type": "personal_query_answer",
                "generation_strategy": "deterministic_summary_bundle_v1",
                "personal_family": "career_transition_plan",
                "question": kwargs["question"],
                "answer_summary": "Current career transition plan focus: Backend transition plan.",
                "answer_rationale": "Selected personal context first because the current layer order is personal -> interpretation -> fact.",
                "answer_markdown": "# Career Transition Plan\n",
                "recommended_actions": ["Prioritize the transition direction captured in backend transition plan."],
                "citations": [],
                "input_bundle": {
                    "question": kwargs["question"],
                    "scope_ref": kwargs["scope_ref"],
                    "personal_context": [],
                    "interpretation_context": [],
                    "fact_context": [],
                },
            },
        )


def test_personal_query_entrypoint_returns_authoritative_answer_envelope() -> None:
    service = StubPersonalQueryService()
    entrypoint = DefaultPersonalQueryEntrypoint(personal_query_service=service)

    result = entrypoint.query_personal_knowledge(
        domain="recruiting",
        question="How should I focus?",
        scope_ref={"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
    )

    assert service.calls == [
        {
            "domain": "recruiting",
            "question": "How should I focus?",
            "scope_ref": {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
            "profile_context": None,
        }
    ]
    assert result["ok"] is True
    assert result["projection"] == {
        "family": "answer",
        "kind": "personal_query",
        "scope": "user",
        "layers": ["personal", "interpretation", "fact"],
    }
    assert result["answer"]["answer_type"] == "personal_query_answer"
    assert result["answer"]["personal_family"] == "career_transition_plan"
    assert result["answer"]["answer_rationale"].startswith("Selected personal context first")
    assert result["answer"]["question"] == "How should I focus?"
    assert result["retrieval"]["personal_ids"] == ["personal:plan-1"]


def test_default_personal_query_entrypoint_loads_answer_from_postgres(
    postgres_connection: Connection[dict],
    tmp_path: Path,
) -> None:
    with postgres_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO personal.record (
                id,
                domain,
                kind,
                title,
                summary,
                scope,
                tenant_id,
                user_id,
                fact_snapshot_id,
                interpretation_snapshot_id,
                profile_version,
                body_path,
                status,
                schema_version,
                provenance_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                "personal:plan-1",
                "recruiting",
                "career_transition_plan",
                "Backend transition plan",
                "Personal strategy summary",
                "user",
                "tenant-1",
                "user-1",
                "fact_snap:new",
                "interp_snap:new",
                "profile-v2",
                "wiki/personal/tenant-1/user-1/plan-1.md",
                "active",
                "v1",
                '{"source": "test"}',
            ),
        )
        cursor.execute(
            """
            INSERT INTO graph.rendered_page (
                domain,
                layer,
                record_id,
                path,
                scope,
                tenant_id,
                user_id,
                fact_snapshot_id,
                interpretation_snapshot_id,
                profile_version,
                metadata_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                "recruiting",
                "personal",
                "personal:plan-1",
                "wiki/personal/tenant-1/user-1/plan-1.md",
                "user",
                "tenant-1",
                "user-1",
                "fact_snap:new",
                "interp_snap:new",
                "profile-v2",
                '{"title": "Backend transition plan"}',
            ),
        )
    postgres_connection.commit()

    entrypoint = build_default_personal_query_entrypoint(
        postgres_connection,
        render_root=tmp_path,
    )

    result = entrypoint.query_personal_context(
        domain="recruiting",
        tenant_id="tenant-1",
        user_id="user-1",
        question="backend transition plan",
    )

    assert result["ok"] is True
    assert result["projection"]["family"] == "answer"
    assert result["projection"]["kind"] == "personal_query"
    assert result["answer"]["personal_family"] == "career_transition_plan"
    assert result["answer"]["answer_summary"].startswith("Current career transition plan focus:")
    assert "## Recommended Actions" in result["answer"]["answer_markdown"]
    assert "Top match reason:" in result["answer"]["answer_rationale"]
    assert result["answer"]["input_bundle"]["personal_context"][0]["record_id"] == "personal:plan-1"
    assert result["retrieval"]["personal_ids"] == ["personal:plan-1"]
