from __future__ import annotations

from typing import Literal, TypedDict


class RetrievalMetadata(TypedDict):
    """Execution metadata recorded for one curated retrieval pass."""

    mode: Literal["curated"]
    layer_order: list[str]
    backend: str
    personal_anchor_status: Literal["present", "absent", "not_available"]
    interpretation_source: Literal["personal_anchors", "search_fallback", "none"]
    fact_source: Literal["interpretation_evidence", "search_fallback", "mixed", "none"]
    evidence_fact_limit: int
