from __future__ import annotations

from wiki_mcp.services.interpretation_projection import DefaultOutboxProjectionWorker


class StubOutboxRepository:
    def __init__(self) -> None:
        self.claim_calls: list[tuple[int, list[str] | None]] = []
        self.processed_ids: list[str] = []
        self.failed: list[tuple[str, str]] = []
        self.events = [
            {
                "id": "evt-1",
                "event_type": "fact_ingested",
                "aggregate_layer": "fact",
                "aggregate_id": "fact_snap:1",
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
                "id": "evt-2",
                "event_type": "fact_ingested",
                "aggregate_layer": "fact",
                "aggregate_id": "fact_snap:2",
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


class StubInterpretationProjectionService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def project_fact_event(self, event: dict[str, object]) -> dict[str, object]:
        self.calls.append(event["id"])
        if event["id"] == "evt-2":
            raise ValueError("broken payload")
        return {
            "fact_snapshot_id": event["aggregate_id"],
            "interpretation_snapshot_id": "interp_snap:1",
            "interpretation_ids": ["interp:1"],
            "emitted_outbox_event_ids": ["evt-3"],
        }


def test_worker_claims_fact_events_and_marks_results() -> None:
    outbox_repository = StubOutboxRepository()
    projection_service = StubInterpretationProjectionService()
    worker = DefaultOutboxProjectionWorker(
        outbox_repository=outbox_repository,
        interpretation_projection_service=projection_service,
    )

    results = worker.run_once(limit=2)

    assert outbox_repository.claim_calls == [(2, ["fact_ingested"])]
    assert projection_service.calls == ["evt-1", "evt-2"]
    assert outbox_repository.processed_ids == ["evt-1"]
    assert outbox_repository.failed == [("evt-2", "broken payload")]
    assert results == [
        {
            "fact_snapshot_id": "fact_snap:1",
            "interpretation_snapshot_id": "interp_snap:1",
            "interpretation_ids": ["interp:1"],
            "emitted_outbox_event_ids": ["evt-3"],
        }
    ]
