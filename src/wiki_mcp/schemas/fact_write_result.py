from __future__ import annotations

from typing import TypedDict


class FactWriteResult(TypedDict):
    """Persistence summary for canonical Fact writes."""

    facts_created: int
    facts_updated: int
    relations_created: int
    affected_fact_ids: list[str]
