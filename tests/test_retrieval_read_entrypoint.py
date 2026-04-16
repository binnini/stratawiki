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
            "personal_records": [
                {
                    "id": "personal:plan-1",
                    "domain": "recruiting",
                    "kind": "career_plan",
                    "title": "Backend transition plan",
                    "summary": "Personal strategy summary",
                    "snapshot_ref": {
                        "fact_snapshot_id": "fact_snap:new",
                        "interpretation_snapshot_id": "interp_snap:new",
                        "profile_version": "profile-v2",
                    },
                }
            ],
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
                    "has_rendered_page": True,
                }
            ],
            "interpretation_records": [],
            "interpretation_explanations": [],
            "fact_records": [],
            "fact_explanations": [],
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
            "interpretation_pages": [],
            "fact_pages": [],
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
                    "has_rendered_page": True,
                }
            ],
            "personal_records": [
                {
                    "id": "personal:plan-1",
                    "domain": "recruiting",
                    "kind": "career_plan",
                    "title": "Backend transition plan",
                    "summary": "Personal strategy summary",
                    "snapshot_ref": {
                        "fact_snapshot_id": "fact_snap:new",
                        "interpretation_snapshot_id": "interp_snap:new",
                        "profile_version": "profile-v2",
                    },
                }
            ],
            "interpretation_explanations": [],
            "interpretation_records": [],
            "fact_explanations": [],
            "fact_records": [],
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
            "interpretation_pages": [],
            "fact_pages": [],
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
                "career_plan",
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
            INSERT INTO interp.record (
                id,
                domain,
                kind,
                subject_type,
                subject_id,
                scope,
                tenant_id,
                user_id,
                schema_version,
                status,
                confidence,
                computed_at,
                expires_at,
                body_json,
                provenance_json,
                render_hints_json,
                fact_snapshot_id
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s::jsonb, %s::jsonb, %s::jsonb, %s
            )
            """,
            (
                "interp:market-1",
                "recruiting",
                "market_summary",
                "career_path",
                "backend-transition",
                "shared",
                None,
                None,
                "v1",
                "active",
                0.9,
                "2026-04-16T00:00:00Z",
                None,
                '{"summary": "Shared market context"}',
                '{"source": "test"}',
                '{}',
                "fact_snap:shared",
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
    assert result["retrieval"]["personal_explanations"][0]["record_id"] == "personal:plan-1"
    assert result["retrieval"]["personal_records"][0] == {
        "id": "personal:plan-1",
        "domain": "recruiting",
        "kind": "career_plan",
        "title": "Backend transition plan",
        "summary": "Personal strategy summary",
        "snapshot_ref": {
            "fact_snapshot_id": "fact_snap:new",
            "interpretation_snapshot_id": "interp_snap:new",
            "profile_version": "profile-v2",
        },
    }
    assert result["retrieval"]["interpretation_records"][0] == {
        "id": "interp:market-1",
        "domain": "recruiting",
        "kind": "market_summary",
        "subject_type": "career_path",
        "subject_id": "backend-transition",
        "status": "active",
        "confidence": 0.9,
        "summary": "Shared market context",
    }
    assert result["retrieval"]["personal_pages"][0]["record_id"] == "personal:plan-1"
    assert result["retrieval"]["interpretation_pages"][0]["record_id"] == "interp:market-1"
    assert result["retrieval"]["snapshot_ref"]["fact_snapshot_id"] == "fact_snap:new"


def test_default_retrieval_read_entrypoint_discovers_canonical_only_personal_record(
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
                "personal:gap-1",
                "recruiting",
                "profile_gap_analysis",
                "Backend gap analysis",
                "Your strongest gaps are backend Python depth and production debugging evidence.",
                "user",
                "tenant-1",
                "user-1",
                "fact_snap:gap",
                "interp_snap:gap",
                "profile-v3",
                "wiki/personal/tenant-1/user-1/gap-1.md",
                "active",
                "v1",
                '{"source": "test"}',
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
        question="backend python depth",
    )

    assert result["ok"] is True
    assert result["retrieval"]["personal_ids"] == ["personal:gap-1"]
    assert result["retrieval"]["personal_pages"] == []
    assert result["retrieval"]["personal_records"] == [
        {
            "id": "personal:gap-1",
            "domain": "recruiting",
            "kind": "profile_gap_analysis",
            "title": "Backend gap analysis",
            "summary": "Your strongest gaps are backend Python depth and production debugging evidence.",
            "snapshot_ref": {
                "fact_snapshot_id": "fact_snap:gap",
                "interpretation_snapshot_id": "interp_snap:gap",
                "profile_version": "profile-v3",
            },
        }
    ]
    assert result["retrieval"]["personal_explanations"][0]["matched_fields"] == [
        "canonical_summary"
    ]
    assert result["retrieval"]["personal_explanations"][0]["has_rendered_page"] is False
    assert result["retrieval"]["snapshot_ref"] == {
        "fact_snapshot_id": "fact_snap:gap",
        "interpretation_snapshot_id": "interp_snap:gap",
        "profile_version": "profile-v3",
    }


def test_default_retrieval_read_entrypoint_uses_lexical_canonical_search_not_recent_only(
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
                "personal:recent-1",
                "recruiting",
                "weekly_action_plan",
                "Weekly admin notes",
                "Follow up on generic admin tasks and inbox cleanup.",
                "user",
                "tenant-1",
                "user-1",
                "fact_snap:recent",
                "interp_snap:recent",
                "profile-v4",
                "wiki/personal/tenant-1/user-1/recent.md",
                "active",
                "v1",
                '{"source": "test"}',
            ),
        )
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
                "personal:gap-1",
                "recruiting",
                "profile_gap_analysis",
                "Backend gap analysis",
                "Your strongest gaps are backend Python depth and production debugging evidence.",
                "user",
                "tenant-1",
                "user-1",
                "fact_snap:gap",
                "interp_snap:gap",
                "profile-v4",
                "wiki/personal/tenant-1/user-1/gap.md",
                "active",
                "v1",
                '{"source": "test"}',
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
        question="backend python depth",
    )

    assert result["retrieval"]["personal_ids"] == ["personal:gap-1"]
    assert result["retrieval"]["personal_pages"] == []
    assert result["retrieval"]["personal_explanations"][0]["match_type"] == "contains"
    assert result["retrieval"]["personal_explanations"][0]["has_rendered_page"] is False
    assert result["retrieval"]["snapshot_ref"] == {
        "fact_snapshot_id": "fact_snap:gap",
        "interpretation_snapshot_id": "interp_snap:gap",
        "profile_version": "profile-v4",
    }
