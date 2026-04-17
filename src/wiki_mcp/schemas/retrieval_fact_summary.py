from __future__ import annotations

from typing import NotRequired, TypedDict


class RetrievalFactSummary(TypedDict):
    """Retrieval-facing summary of a canonical Fact record."""

    id: str
    domain: str
    entity_type: str
    canonical_key: str
    scope: str
    fact_snapshot_id: NotRequired[str]
    title: NotRequired[str]
