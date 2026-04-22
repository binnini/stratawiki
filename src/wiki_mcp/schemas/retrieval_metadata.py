from __future__ import annotations

from typing import Literal, TypedDict


class RetrievalMetadata(TypedDict):
    """Execution metadata recorded for one curated retrieval pass."""

    mode: Literal["curated"]
    layer_order: list[str]
    backend: str
    personal_search_policy: Literal["metadata_first_markdown_support"]
    personal_support_source: Literal["markdown_body_scan", "anchor_reverse_lookup", "none"]
    personal_anchor_status: Literal["present", "absent", "not_available"]
    interpretation_source: Literal["personal_anchors", "search_fallback", "none"]
    fact_source: Literal["interpretation_evidence", "personal_anchors", "search_fallback", "mixed", "none"]
    evidence_fact_limit: int
    graph_behavior: Literal["support_only"]
