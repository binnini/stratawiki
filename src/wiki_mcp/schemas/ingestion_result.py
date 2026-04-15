from __future__ import annotations

from typing import TypedDict


class IngestionResult(TypedDict):
    """Core ingestion result after canonical persistence and snapshot publication."""

    fact_snapshot_id: str
    facts_created: int
    facts_updated: int
    relations_created: int
    affected_fact_ids: list[str]
    outbox_event_ids: list[str]
