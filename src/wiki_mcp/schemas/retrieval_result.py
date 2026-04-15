from __future__ import annotations

from typing import TypedDict

from wiki_mcp.schemas.snapshot_ref import SnapshotRef


class RetrievalResult(TypedDict):
    """Result envelope for retrieval orchestration across layers."""

    personal_ids: list[str]
    interpretation_ids: list[str]
    fact_ids: list[str]
    snapshot_ref: SnapshotRef
