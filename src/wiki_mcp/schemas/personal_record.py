from __future__ import annotations

from typing import Any, TypedDict

from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.schemas.snapshot_ref import SnapshotRef


class PersonalRecord(TypedDict):
    """User-scoped Personal metadata record."""

    id: str
    domain: str
    kind: str
    title: str
    summary: str
    scope_ref: ScopeRef
    snapshot_ref: SnapshotRef
    profile_version: str
    body_path: str
    status: str
    schema_version: str
    provenance: dict[str, Any]
