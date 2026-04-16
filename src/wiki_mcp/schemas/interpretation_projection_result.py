from __future__ import annotations

from typing import TypedDict


class InterpretationProjectionResult(TypedDict):
    """Result of projecting one Fact outbox event into Interpretation state."""

    fact_snapshot_id: str
    interpretation_snapshot_id: str
    interpretation_ids: list[str]
    emitted_outbox_event_ids: list[str]
