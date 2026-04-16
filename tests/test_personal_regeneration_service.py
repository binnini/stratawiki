from __future__ import annotations

from pathlib import Path

from wiki_mcp.services.personal_regeneration import (
    DefaultPersonalRegenerationService,
)


class StubPersonalRepository:
    def __init__(self) -> None:
        self.load_calls: list[tuple[list[str], dict[str, str]]] = []
        self.saved_records: list[dict[str, object]] = []

    def get_by_ids(
        self,
        ids: list[str],
        scope_ref: dict[str, str],
    ) -> list[dict[str, object]]:
        self.load_calls.append((ids, scope_ref))
        return [
            {
                "id": "personal:plan-1",
                "domain": "recruiting",
                "kind": "career_transition_plan",
                "title": "Backend transition plan",
                "summary": "Old summary",
                "scope_ref": {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
                "snapshot_ref": {
                    "fact_snapshot_id": "fact_snap:old",
                    "interpretation_snapshot_id": "interp_snap:old",
                    "profile_version": "profile-v1",
                },
                "profile_version": "profile-v1",
                "body_path": "wiki/personal/tenant-1/user-1/plan-1.md",
                "status": "stale",
                "schema_version": "v1",
                "provenance": {"source": "test"},
            }
        ]

    def save_record(self, record: dict[str, object]) -> str:
        self.saved_records.append(record)
        return record["id"]


class StubProfileContextRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def get_profile_context(
        self,
        domain: str,
        tenant_id: str,
        user_id: str,
    ) -> dict[str, object]:
        self.calls.append((domain, tenant_id, user_id))
        return {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "domain": domain,
            "profile_version": "profile-v2",
            "goals": ["transition_to_backend", "move_to_tokyo"],
            "preferences": {"pace": "steady"},
            "attributes": {"experience_years": 3},
        }


class StubInterpretationRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, str]]] = []

    def get_by_ids(
        self,
        ids: list[str],
        scope_ref: dict[str, str],
    ) -> list[dict[str, object]]:
        self.calls.append((ids, scope_ref))
        return [
            {
                "id": "interp:company_hiring_pattern:company-name:jobswiki",
                "domain": "recruiting",
                "kind": "company_hiring_pattern",
                "subject_type": "company",
                "subject_id": "company-name:jobswiki",
                "scope_ref": scope_ref,
                "schema_version": "v1",
                "status": "active",
                "confidence": 0.6,
                "computed_at": "2026-04-16T00:00:00Z",
                "expires_at": None,
                "body": {"summary": "JobsWiki is actively hiring for backend roles."},
                "provenance": {"source_event_id": "evt-1"},
                "render_hints": {},
            }
        ]


class StubRenderingRepository:
    def __init__(self) -> None:
        self.artifacts: list[dict[str, object]] = []

    def write_artifact(self, artifact: dict[str, object]) -> str:
        self.artifacts.append(artifact)
        return str(Path("/tmp") / artifact["path"])


class StubOutboxRepository:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, object]]] = []

    def append_events(self, events: list[dict[str, object]]) -> list[str]:
        self.calls.append(events)
        return ["evt-regenerated-1"]


def test_regenerate_from_stale_event_refreshes_personal_record_and_artifact() -> None:
    personal_repository = StubPersonalRepository()
    profile_context_repository = StubProfileContextRepository()
    interpretation_repository = StubInterpretationRepository()
    rendering_repository = StubRenderingRepository()
    outbox_repository = StubOutboxRepository()
    service = DefaultPersonalRegenerationService(
        personal_repository=personal_repository,
        profile_context_repository=profile_context_repository,
        interpretation_repository=interpretation_repository,
        rendering_repository=rendering_repository,
        outbox_repository=outbox_repository,
    )

    regenerated_ids = service.regenerate_from_stale_event(
        {
            "id": "evt-3",
            "event_type": "personal_records_marked_stale",
            "aggregate_layer": "personal",
            "aggregate_id": "interp_snap:new",
            "payload": {
                "domain": "recruiting",
                "fact_snapshot_id": "fact_snap:new",
                "interpretation_snapshot_id": "interp_snap:new",
                "personal_record_ids": ["personal:plan-1"],
                "triggering_interpretation_ids": [
                    "interp:company_hiring_pattern:company-name:jobswiki"
                ],
                "source_event_id": "evt-2",
                "scope": "user",
                "tenant_id": "tenant-1",
                "user_id": "user-1",
            },
            "status": "claimed",
            "attempt_count": 1,
            "available_at": "2026-04-16T00:00:00Z",
            "claimed_at": None,
            "processed_at": None,
            "last_error": None,
            "idempotency_key": None,
        }
    )

    assert regenerated_ids == ["personal:plan-1"]
    saved_record = personal_repository.saved_records[0]
    assert saved_record["status"] == "active"
    assert saved_record["snapshot_ref"] == {
        "fact_snapshot_id": "fact_snap:new",
        "interpretation_snapshot_id": "interp_snap:new",
        "profile_version": "profile-v2",
    }
    assert saved_record["profile_version"] == "profile-v2"
    assert "Refreshed career transition plan" in saved_record["summary"]
    assert saved_record["provenance"]["regeneration"]["source_event_id"] == "evt-3"
    assert profile_context_repository.calls == [("recruiting", "tenant-1", "user-1")]
    assert interpretation_repository.calls == [
        (
            ["interp:company_hiring_pattern:company-name:jobswiki"],
            {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
        )
    ]
    assert rendering_repository.artifacts[0]["path"] == "wiki/personal/tenant-1/user-1/plan-1.md"
    assert "## Shared Interpretations" in rendering_repository.artifacts[0]["body_markdown"]
    assert outbox_repository.calls[0][0]["event_type"] == "personal_records_regenerated"


def test_regenerate_from_stale_event_rejects_incomplete_payload() -> None:
    service = DefaultPersonalRegenerationService(
        personal_repository=StubPersonalRepository(),
        profile_context_repository=StubProfileContextRepository(),
        interpretation_repository=StubInterpretationRepository(),
        rendering_repository=StubRenderingRepository(),
        outbox_repository=StubOutboxRepository(),
    )

    try:
        service.regenerate_from_stale_event(
            {
                "id": "evt-3",
                "event_type": "personal_records_marked_stale",
                "aggregate_layer": "personal",
                "aggregate_id": "interp_snap:new",
                "payload": {"domain": "recruiting"},
                "status": "claimed",
                "attempt_count": 1,
                "available_at": "2026-04-16T00:00:00Z",
                "claimed_at": None,
                "processed_at": None,
                "last_error": None,
                "idempotency_key": None,
            }
        )
    except ValueError as exc:
        assert "missing required fields" in str(exc)
    else:
        raise AssertionError(
            "Expected ValueError for incomplete personal_records_marked_stale payload"
        )
