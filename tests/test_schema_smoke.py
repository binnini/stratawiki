from __future__ import annotations

from wiki_mcp.schemas import (
    INTERPRETATION_LIFECYCLE_STATUSES,
    INTERPRETATION_STATUS_PUBLISHED,
    FactRecord,
    InterpretationRecord,
    PersonalAnchor,
    PersonalRecord,
    Provenance,
    ScopeRef,
    SnapshotRef,
)


def test_shared_schema_examples_are_constructible() -> None:
    provenance: Provenance = {
        "source_ids": ["greenhouse:job:123"],
        "upstream_versions": {
            "fact_snapshot": "fact_snap_2026_04_17_0900",
            "profile_version": "profile_v7",
        },
        "generated_by": {
            "kind": "llm",
            "provider": "openai",
            "model": "gpt-5.4",
            "prompt_version": "interp.market_trend.v1",
        },
        "generated_at": "2026-04-17T09:00:00Z",
    }
    scope_ref: ScopeRef = {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"}
    snapshot_ref: SnapshotRef = {
        "fact_snapshot_id": "fact_snap_2026_04_17_0900",
        "interpretation_snapshot_id": "interp_snap_2026_04_17_0905",
        "profile_version": "profile_v7",
    }
    personal_anchors: list[PersonalAnchor] = [
        {"layer": "interpretation", "id": "interp:market_trend:123"},
        {"layer": "fact", "id": "fact:job_posting:123"},
    ]

    fact: FactRecord = {
        "id": "fact:job_posting:123",
        "layer": "fact",
        "domain": "recruiting",
        "entity_type": "job_posting",
        "canonical_key": "greenhouse:job:123",
        "attributes": {"title": "Backend Engineer"},
        "scope": "shared",
        "schema_version": "fact.v1",
        "status": "active",
        "version": 1,
        "created_at": "2026-04-17T09:00:00Z",
        "updated_at": "2026-04-17T09:00:00Z",
        "provenance": provenance,
    }
    interpretation: InterpretationRecord = {
        "id": "interp:market_trend:123",
        "layer": "interpretation",
        "domain": "recruiting",
        "family": "market_trend",
        "kind": "trend",
        "subject_type": "market_segment",
        "subject_id": "backend-japan-midlevel",
        "subject": {
            "type": "market_segment",
            "id": "backend-japan-midlevel",
            "label": "Backend Japan Midlevel",
        },
        "scope_ref": {"scope": "shared"},
        "schema_version": "interpretation.v2",
        "status": INTERPRETATION_STATUS_PUBLISHED,
        "confidence": 0.82,
        "fact_snapshot_id": snapshot_ref["fact_snapshot_id"],
        "computed_at": "2026-04-17T09:05:00Z",
        "expires_at": "2026-04-18T09:05:00Z",
        "title": "Production LLM experience preference is increasing",
        "claim": "Production LLM experience is increasingly preferred in this segment.",
        "summary": "Shared interpretation summary",
        "body": {"signals": [], "observations": [], "counterpoints": []},
        "evidence": [{"fact_id": fact["id"], "weight": 0.4, "role": "primary"}],
        "provenance": provenance,
        "render_hints": {"page_family": "market_trend", "page_key": "backend-japan-midlevel"},
    }
    personal: PersonalRecord = {
        "id": "personal:note:123",
        "layer": "personal",
        "domain": "recruiting",
        "kind": "query_answer",
        "title": "My recruiting summary",
        "summary": "A personalized recruiting summary",
        "scope_ref": scope_ref,
        "snapshot_ref": snapshot_ref,
        "profile_version": "profile_v7",
        "body_path": "personal/recruiting/summary.md",
        "anchors": personal_anchors,
        "status": "active",
        "schema_version": "personal.v1",
        "version": 1,
        "created_at": "2026-04-17T09:10:00Z",
        "updated_at": "2026-04-17T09:10:00Z",
        "provenance": provenance,
    }

    assert fact["layer"] == "fact"
    assert interpretation["status"] in INTERPRETATION_LIFECYCLE_STATUSES
    assert personal["snapshot_ref"]["profile_version"] == "profile_v7"


def test_interpretation_lifecycle_statuses_match_docs_order() -> None:
    assert INTERPRETATION_LIFECYCLE_STATUSES == (
        "proposed",
        "validated",
        "published",
        "stale",
        "superseded",
        "rejected",
        "deleted",
    )
