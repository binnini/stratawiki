from __future__ import annotations

from typing import TypedDict

from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.schemas.snapshot_ref import SnapshotRef


class RenderedArtifact(TypedDict):
    """Readable rendered output generated from canonical layers."""

    domain: str
    layer: str
    record_id: str
    path: str
    title: str
    body_markdown: str
    scope_ref: ScopeRef
    snapshot_ref: SnapshotRef
