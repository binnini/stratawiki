from __future__ import annotations

from typing import Any, NotRequired, TypedDict

from wiki_mcp.schemas.personal_anchor import PersonalAnchor
from wiki_mcp.schemas.provenance import Provenance
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.schemas.snapshot_ref import SnapshotRef


class PersonalRecord(TypedDict):
    """User-scoped Personal metadata record."""

    id: str
    layer: NotRequired[str]
    domain: str
    kind: str
    title: str
    summary: str
    scope_ref: ScopeRef
    snapshot_ref: SnapshotRef
    profile_version: str
    path: str
    subspace: NotRequired[str]
    asset_refs: NotRequired[list[str]]
    content_hash: NotRequired[str]
    body: NotRequired[dict[str, Any] | str]
    anchors: NotRequired[list[PersonalAnchor]]
    status: str
    schema_version: str
    created_at: NotRequired[str]
    updated_at: NotRequired[str]
    version: NotRequired[int]
    provenance: Provenance
