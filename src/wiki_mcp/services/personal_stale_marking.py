from __future__ import annotations

from datetime import UTC, datetime

from wiki_mcp.schemas.outbox_event import (
    InterpretationSnapshotPublishedPayload,
    OutboxEvent,
    OutboxEventRecord,
    PersonalRecordsMarkedStalePayload,
)
from wiki_mcp.schemas.personal_record import PersonalRecord
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.services.interfaces.repositories import (
    DependencyRepository,
    OutboxRepository,
    PersonalRepository,
)


class DefaultPersonalStaleMarkingService:
    """Marks dependent Personal records stale after interpretation refresh."""

    def __init__(
        self,
        *,
        dependency_repository: DependencyRepository,
        personal_repository: PersonalRepository,
        outbox_repository: OutboxRepository,
    ) -> None:
        self.dependency_repository = dependency_repository
        self.personal_repository = personal_repository
        self.outbox_repository = outbox_repository

    def mark_from_interpretation_event(
        self,
        event: OutboxEventRecord,
    ) -> list[str]:
        if event["event_type"] != "interpretation_snapshot_published":
            raise ValueError(
                "Unsupported outbox event type for personal stale marking: "
                f"{event['event_type']!r}."
            )

        payload = self._parse_payload(event["payload"])
        scope_ref = self._scope_ref_from_payload(payload)
        affected_personal_ids: list[str] = []

        for interpretation_id in payload["interpretation_ids"]:
            impact = self.dependency_repository.get_impact(
                payload["domain"],
                "interpretation",
                interpretation_id,
                scope_ref,
            )
            affected_personal_ids.extend(impact["affected_personal_ids"])

        unique_personal_ids = list(dict.fromkeys(affected_personal_ids))
        if not unique_personal_ids:
            return []

        personal_records = self.personal_repository.get_by_ids(
            unique_personal_ids,
            scope_ref,
        )
        stale_at = datetime.now(UTC).isoformat()
        updated_ids: list[str] = []

        for record in personal_records:
            updated_record = self._mark_record_stale(
                record,
                payload=payload,
                source_event_id=event["id"],
                stale_at=stale_at,
            )
            self.personal_repository.save_record(updated_record)
            updated_ids.append(updated_record["id"])

        self.outbox_repository.append_events(
            [
                self._build_personal_stale_event(
                    payload=payload,
                    source_event_id=event["id"],
                    personal_record_ids=updated_ids,
                )
            ]
        )
        return updated_ids

    def _parse_payload(
        self,
        payload: dict[str, object],
    ) -> InterpretationSnapshotPublishedPayload:
        required_keys = {
            "domain",
            "interpretation_kind",
            "fact_snapshot_id",
            "interpretation_snapshot_id",
            "interpretation_ids",
            "source_event_id",
            "scope",
        }
        missing_keys = sorted(key for key in required_keys if key not in payload)
        if missing_keys:
            raise ValueError(
                "interpretation_snapshot_published payload is missing required fields: "
                + ", ".join(missing_keys)
            )
        return payload  # type: ignore[return-value]

    def _scope_ref_from_payload(
        self,
        payload: InterpretationSnapshotPublishedPayload,
    ) -> ScopeRef:
        scope_ref: ScopeRef = {"scope": payload["scope"]}
        if "tenant_id" in payload:
            scope_ref["tenant_id"] = payload["tenant_id"]
        if "user_id" in payload:
            scope_ref["user_id"] = payload["user_id"]
        return scope_ref

    def _mark_record_stale(
        self,
        record: PersonalRecord,
        *,
        payload: InterpretationSnapshotPublishedPayload,
        source_event_id: str,
        stale_at: str,
    ) -> PersonalRecord:
        return {
            **record,
            "status": "stale",
            "provenance": {
                **record["provenance"],
                "stale_marker": {
                    "reason": "upstream_interpretation_snapshot_changed",
                    "stale_at": stale_at,
                    "source_event_id": source_event_id,
                    "fact_snapshot_id": payload["fact_snapshot_id"],
                    "interpretation_snapshot_id": payload["interpretation_snapshot_id"],
                    "triggering_interpretation_ids": payload["interpretation_ids"],
                },
            },
        }

    def _build_personal_stale_event(
        self,
        *,
        payload: InterpretationSnapshotPublishedPayload,
        source_event_id: str,
        personal_record_ids: list[str],
    ) -> OutboxEvent:
        event_payload: PersonalRecordsMarkedStalePayload = {
            "domain": payload["domain"],
            "fact_snapshot_id": payload["fact_snapshot_id"],
            "interpretation_snapshot_id": payload["interpretation_snapshot_id"],
            "personal_record_ids": personal_record_ids,
            "triggering_interpretation_ids": payload["interpretation_ids"],
            "source_event_id": source_event_id,
        }
        return {
            "event_type": "personal_records_marked_stale",
            "aggregate_layer": "personal",
            "aggregate_id": payload["interpretation_snapshot_id"],
            "idempotency_key": (
                "personal_records_marked_stale:"
                f"{payload['interpretation_snapshot_id']}"
            ),
            "payload": event_payload,
        }


class DefaultPersonalStaleWorker:
    """Small synchronous worker for Personal stale marking."""

    def __init__(
        self,
        *,
        outbox_repository: OutboxRepository,
        personal_stale_marking_service: DefaultPersonalStaleMarkingService,
    ) -> None:
        self.outbox_repository = outbox_repository
        self.personal_stale_marking_service = personal_stale_marking_service

    def run_once(self, *, limit: int = 10) -> list[list[str]]:
        claimed_events = self.outbox_repository.claim_pending(
            limit=limit,
            event_types=["interpretation_snapshot_published"],
        )
        results: list[list[str]] = []

        for event in claimed_events:
            try:
                result = self.personal_stale_marking_service.mark_from_interpretation_event(
                    event
                )
            except Exception as exc:
                self.outbox_repository.mark_failed(event["id"], str(exc))
                continue

            self.outbox_repository.mark_processed(event["id"])
            results.append(result)

        return results
