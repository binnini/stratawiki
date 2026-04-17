from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class FactIngestedPayload(TypedDict):
    """Payload emitted after one canonical fact batch is committed."""

    domain: str
    source_id: str
    connector: str
    fact_snapshot_id: str
    affected_fact_ids: list[str]
    affected_entity_types: list[str]
    scope: str
    tenant_id: NotRequired[str]
    user_id: NotRequired[str]
    facts_created: int
    facts_updated: int
    relations_created: int


class InterpretationSnapshotPublishedPayload(TypedDict):
    """Payload emitted after a shared interpretation snapshot is published."""

    domain: str
    interpretation_kind: str
    fact_snapshot_id: str
    interpretation_snapshot_id: str
    interpretation_ids: list[str]
    source_event_id: str
    scope: str
    tenant_id: NotRequired[str]
    user_id: NotRequired[str]


class PersonalRecordsMarkedStalePayload(TypedDict):
    """Payload emitted after Personal records are marked stale."""

    domain: str
    fact_snapshot_id: str
    interpretation_snapshot_id: str
    personal_record_ids: list[str]
    triggering_interpretation_ids: list[str]
    source_event_id: str
    scope: str
    tenant_id: NotRequired[str]
    user_id: NotRequired[str]


class PersonalRecordsRegeneratedPayload(TypedDict):
    """Payload emitted after stale Personal records are regenerated."""

    domain: str
    fact_snapshot_id: str
    interpretation_snapshot_id: str
    profile_version: str
    personal_record_ids: list[str]
    source_event_id: str
    scope: str
    tenant_id: NotRequired[str]
    user_id: NotRequired[str]


class OutboxEventRecord(TypedDict):
    """Stored outbox event claimed by a worker."""

    id: str
    event_type: str
    aggregate_layer: str
    aggregate_id: str
    payload: dict[str, Any]
    status: str
    attempt_count: int
    available_at: str
    claimed_at: str | None
    processed_at: str | None
    last_error: str | None
    idempotency_key: str | None


class OutboxEvent(TypedDict):
    """Outbox event envelope for asynchronous projection work."""

    event_type: str
    aggregate_layer: str
    aggregate_id: str
    payload: dict[str, Any]
    idempotency_key: NotRequired[str]
