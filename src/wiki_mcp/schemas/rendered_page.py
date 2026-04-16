from __future__ import annotations

from typing import Any, TypedDict

from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.schemas.snapshot_ref import SnapshotRef


class RenderedPage(TypedDict):
    """Readable rendered page metadata plus markdown body."""

    domain: str
    layer: str
    record_id: str
    path: str
    title: str
    scope_ref: ScopeRef
    snapshot_ref: SnapshotRef
    metadata: dict[str, Any]
    body_markdown: str
