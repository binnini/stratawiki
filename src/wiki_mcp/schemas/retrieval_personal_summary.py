from __future__ import annotations

from typing import NotRequired, TypedDict

from wiki_mcp.schemas.snapshot_ref import SnapshotRef


class RetrievalPersonalSummary(TypedDict):
    """Retrieval-facing summary of a Personal record."""

    id: str
    domain: str
    kind: str
    title: str
    summary: str
    snapshot_ref: SnapshotRef
    path: NotRequired[str]
