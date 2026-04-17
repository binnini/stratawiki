from __future__ import annotations

from typing import Any, TypedDict

from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.schemas.snapshot_ref import SnapshotRef


class RenderedPageSummary(TypedDict):
    """Rendered page metadata used for read-side listing."""

    domain: str
    layer: str
    record_id: str
    path: str
    title: str
    scope_ref: ScopeRef
    snapshot_ref: SnapshotRef
    metadata: dict[str, Any]
