from __future__ import annotations

from wiki_mcp.services.personal_stale_marking import DefaultPersonalStaleWorker


class StubOutboxRepository:
    def __init__(self) -> None:
        self.claim_calls: list[tuple[int, list[str] | None]] = []
        self.processed_ids: list[str] = []
        self.failed: list[tuple[str, str]] = []
        self.events = [
            {
                "id": "evt-2",
                "event_type": "interpretation_snapshot_published",
                "aggregate_layer": "interpretation",
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
                "id": "evt-3",
                "event_type": "interpretation_snapshot_published",
                "aggregate_layer": "interpretation",
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

    def mark_failed(self, event_id: str, error_message: str) -> None:
        self.failed.append((event_id, error_message))


class StubPersonalStaleMarkingService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def mark_from_interpretation_event(self, event: dict[str, object]) -> list[str]:
        self.calls.append(event["id"])
        if event["id"] == "evt-3":
            raise ValueError("cannot mark stale")
        return ["personal:plan-1"]


def test_worker_claims_interpretation_events_and_marks_results() -> None:
    outbox_repository = StubOutboxRepository()
    stale_service = StubPersonalStaleMarkingService()
    worker = DefaultPersonalStaleWorker(
        outbox_repository=outbox_repository,
        personal_stale_marking_service=stale_service,
    )

    results = worker.run_once(limit=2)

    assert outbox_repository.claim_calls == [(2, ["interpretation_snapshot_published"])]
    assert stale_service.calls == ["evt-2", "evt-3"]
    assert outbox_repository.processed_ids == ["evt-2"]
    assert outbox_repository.failed == [("evt-3", "cannot mark stale")]
    assert results == [["personal:plan-1"]]
