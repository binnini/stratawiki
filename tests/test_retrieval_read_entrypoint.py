from __future__ import annotations

from pathlib import Path

from psycopg import Connection

from wiki_mcp.services.retrieval_read_entrypoint import (
    DefaultRetrievalReadEntrypoint,
    build_default_retrieval_read_entrypoint,
)


class StubRetrievalService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def retrieve_for_query(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        return {
            "personal_ids": ["personal:plan-1"],
            "interpretation_ids": ["interp:market-1"],
            "fact_ids": ["fact:job-1"],
            "snapshot_ref": {
                "fact_snapshot_id": "fact_snap:new",
                "interpretation_snapshot_id": "interp_snap:new",
                "profile_version": "profile-v2",
            },
        }


def test_retrieval_read_entrypoint_returns_authoritative_envelope() -> None:
    retrieval_service = StubRetrievalService()
    entrypoint = DefaultRetrievalReadEntrypoint(retrieval_service=retrieval_service)

    result = entrypoint.retrieve_for_query(
        domain="recruiting",
        question="backend transition plan",
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

    assert retrieval_service.calls == [
        {
            "domain": "recruiting",
            "question": "backend transition plan",
            "scope_ref": {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
            "profile_context": {
                "user_id": "user-1",
                "tenant_id": "tenant-1",
                "domain": "recruiting",
                "profile_version": "profile-v2",
                "goals": ["transition"],
                "preferences": {},
                "attributes": {},
            },
        }
    ]
    assert result == {
        "ok": True,
        "projection": {
            "family": "retrieval",
            "scope": "user",
            "layers": ["personal", "interpretation", "fact"],
        },
        "read_model_state": "applied",
        "retrieval": {
            "personal_ids": ["personal:plan-1"],
            "interpretation_ids": ["interp:market-1"],
            "fact_ids": ["fact:job-1"],
            "snapshot_ref": {
                "fact_snapshot_id": "fact_snap:new",
                "interpretation_snapshot_id": "interp_snap:new",
                "profile_version": "profile-v2",
            },
        },
    }


def test_retrieval_read_entrypoint_wraps_personal_scope() -> None:
    retrieval_service = StubRetrievalService()
    entrypoint = DefaultRetrievalReadEntrypoint(retrieval_service=retrieval_service)

    result = entrypoint.retrieve_personal_context(
        domain="recruiting",
        tenant_id="tenant-1",
        user_id="user-1",
        question="backend transition plan",
    )

    assert retrieval_service.calls[0]["scope_ref"] == {
        "scope": "user",
        "tenant_id": "tenant-1",
        "user_id": "user-1",
    }
    assert result["projection"]["scope"] == "user"


def test_default_retrieval_read_entrypoint_loads_candidates_from_postgres(
    postgres_connection: Connection[dict],
    tmp_path: Path,
) -> None:
    with postgres_connection.cursor() as cursor:
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
                "interpretation",
                "interp:market-1",
                "wiki/shared/interpretation/backend-transition-market.md",
                "shared",
                None,
                None,
                "fact_snap:shared",
                "interp_snap:shared",
                None,
                '{"title": "Backend transition market"}',
            ),
        )
    postgres_connection.commit()

    entrypoint = build_default_retrieval_read_entrypoint(
        postgres_connection,
        render_root=tmp_path,
    )

    result = entrypoint.retrieve_personal_context(
        domain="recruiting",
        tenant_id="tenant-1",
        user_id="user-1",
        question="backend transition",
    )

    assert result["ok"] is True
    assert result["projection"] == {
        "family": "retrieval",
        "scope": "user",
        "layers": ["personal", "interpretation", "fact"],
    }
    assert result["read_model_state"] == "applied"
    assert result["retrieval"]["personal_ids"] == ["personal:plan-1"]
    assert result["retrieval"]["interpretation_ids"] == ["interp:market-1"]
    assert result["retrieval"]["snapshot_ref"]["fact_snapshot_id"] == "fact_snap:new"
