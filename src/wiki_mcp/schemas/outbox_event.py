from __future__ import annotations

from typing import Any, TypedDict


class OutboxEvent(TypedDict):
    """Outbox event envelope for asynchronous projection work."""

    event_type: str
    aggregate_layer: str
    aggregate_id: str
    payload: dict[str, Any]
