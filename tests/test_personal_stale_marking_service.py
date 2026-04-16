from __future__ import annotations

from wiki_mcp.services.personal_stale_marking import (
    DefaultPersonalStaleMarkingService,
)


class StubDependencyRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, dict[str, str]]] = []

    def get_impact(
        self,
        domain: str,
        layer: str,
        record_id: str,
        scope_ref: dict[str, str],
    ) -> dict[str, list[str]]:
        self.calls.append((domain, layer, record_id, scope_ref))
        return {
            "affected_interpretation_ids": [],
            "affected_rendered_paths": [],
            "affected_personal_ids": ["personal:plan-1"],
        }


class StubPersonalRepository:
    def __init__(self) -> None:
        self.saved_records: list[dict[str, object]] = []
        self.load_calls: list[tuple[list[str], dict[str, str]]] = []

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
                "title": "Plan",
                "summary": "Summary",
                "scope_ref": {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
                "snapshot_ref": {
                    "fact_snapshot_id": "fact_snap:old",
                    "interpretation_snapshot_id": "interp_snap:old",
                    "profile_version": "profile-v1",
                },
                "profile_version": "profile-v1",
                "body_path": "wiki/personal/plan.md",
                "status": "active",
                "schema_version": "v1",
                "provenance": {"source": "test"},
            }
        ]

    def save_record(self, record: dict[str, object]) -> str:
        self.saved_records.append(record)
        return record["id"]


class StubOutboxRepository:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, object]]] = []

    def append_events(self, events: list[dict[str, object]]) -> list[str]:
        self.calls.append(events)
        return ["evt-stale-1"]


def test_mark_from_interpretation_event_marks_personal_records_stale() -> None:
    dependency_repository = StubDependencyRepository()
    personal_repository = StubPersonalRepository()
    outbox_repository = StubOutboxRepository()
    service = DefaultPersonalStaleMarkingService(
        dependency_repository=dependency_repository,
        personal_repository=personal_repository,
        outbox_repository=outbox_repository,
    )

    updated_ids = service.mark_from_interpretation_event(
        {
            "id": "evt-2",
            "event_type": "interpretation_snapshot_published",
            "aggregate_layer": "interpretation",
            "aggregate_id": "interp_snap:new",
            "payload": {
                "domain": "recruiting",
                "interpretation_kind": "company_hiring_pattern",
                "fact_snapshot_id": "fact_snap:new",
                "interpretation_snapshot_id": "interp_snap:new",
                "interpretation_ids": ["interp:company_hiring_pattern:company-name:jobswiki"],
                "source_event_id": "evt-1",
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

    assert updated_ids == ["personal:plan-1"]
    assert dependency_repository.calls == [
        (
            "recruiting",
            "interpretation",
            "interp:company_hiring_pattern:company-name:jobswiki",
            {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
        )
    ]
    saved_record = personal_repository.saved_records[0]
    assert saved_record["status"] == "stale"
    assert saved_record["snapshot_ref"]["interpretation_snapshot_id"] == "interp_snap:old"
    assert saved_record["provenance"]["stale_marker"]["interpretation_snapshot_id"] == "interp_snap:new"
    assert outbox_repository.calls[0][0]["event_type"] == "personal_records_marked_stale"


def test_mark_from_interpretation_event_rejects_incomplete_payload() -> None:
    service = DefaultPersonalStaleMarkingService(
        dependency_repository=StubDependencyRepository(),
        personal_repository=StubPersonalRepository(),
        outbox_repository=StubOutboxRepository(),
    )

    try:
        service.mark_from_interpretation_event(
            {
                "id": "evt-2",
                "event_type": "interpretation_snapshot_published",
                "aggregate_layer": "interpretation",
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
            "Expected ValueError for incomplete interpretation_snapshot_published payload"
        )
