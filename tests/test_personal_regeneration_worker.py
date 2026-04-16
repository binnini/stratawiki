from __future__ import annotations

from wiki_mcp.services.personal_regeneration import DefaultPersonalRegenerationWorker


class StubOutboxRepository:
    def __init__(self) -> None:
        self.claim_calls: list[tuple[int, list[str] | None]] = []
        self.processed_ids: list[str] = []
        self.failed: list[tuple[str, str, bool]] = []
        self.events = [
            {
                "id": "evt-4",
                "event_type": "personal_records_marked_stale",
                "aggregate_layer": "personal",
                "aggregate_id": "interp_snap:1",
                "payload": {"domain": "recruiting"},
                "status": "claimed",
                "attempt_count": 1,
                "available_at": "2026-04-16T00:00:00Z",
                "claimed_at": None,
                "processed_at": None,
                "last_error": None,
                "idempotency_key": None,
            },
            {
                "id": "evt-5",
                "event_type": "personal_records_marked_stale",
                "aggregate_layer": "personal",
                "aggregate_id": "interp_snap:2",
                "payload": {"domain": "recruiting"},
                "status": "claimed",
                "attempt_count": 1,
                "available_at": "2026-04-16T00:00:00Z",
                "claimed_at": None,
                "processed_at": None,
                "last_error": None,
                "idempotency_key": None,
            },
        ]

    def claim_pending(
        self,
        *,
        limit: int,
        event_types: list[str] | None = None,
    ) -> list[dict[str, object]]:
        self.claim_calls.append((limit, event_types))
        return self.events[:limit]

    def mark_processed(self, event_id: str) -> None:
        self.processed_ids.append(event_id)

    def mark_failed(
        self,
        event_id: str,
        error_message: str,
        *,
        retryable: bool = True,
    ) -> None:
        self.failed.append((event_id, error_message, retryable))


class StubPersonalRegenerationService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def regenerate_from_stale_event(self, event: dict[str, object]) -> list[str]:
        self.calls.append(event["id"])
        if event["id"] == "evt-5":
            raise RuntimeError("temporary outage")
        return ["personal:plan-1"]


class ValueErrorPersonalRegenerationService:
    def regenerate_from_stale_event(self, event: dict[str, object]) -> list[str]:
        raise ValueError("bad payload")



def test_worker_claims_personal_stale_events_and_marks_results() -> None:
    outbox_repository = StubOutboxRepository()
    regeneration_service = StubPersonalRegenerationService()
    worker = DefaultPersonalRegenerationWorker(
        outbox_repository=outbox_repository,
        personal_regeneration_service=regeneration_service,
    )

    results = worker.run_once(limit=2)

    assert outbox_repository.claim_calls == [(2, ["personal_records_marked_stale"])]
    assert regeneration_service.calls == ["evt-4", "evt-5"]
    assert outbox_repository.processed_ids == ["evt-4"]
    assert outbox_repository.failed == [("evt-5", "temporary outage", True)]
    assert results == [["personal:plan-1"]]



def test_worker_marks_value_errors_as_terminal_failures() -> None:
    outbox_repository = StubOutboxRepository()
    worker = DefaultPersonalRegenerationWorker(
        outbox_repository=outbox_repository,
        personal_regeneration_service=ValueErrorPersonalRegenerationService(),
    )

    results = worker.run_once(limit=1)

    assert outbox_repository.processed_ids == []
    assert outbox_repository.failed == [("evt-4", "bad payload", False)]
    assert results == []
