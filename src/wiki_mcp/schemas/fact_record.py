from __future__ import annotations

from typing import Any, NotRequired, TypedDict

from wiki_mcp.schemas.provenance import Provenance
from wiki_mcp.schemas.scope_ref import ScopeValue


class FactRecord(TypedDict):
    """Domain-neutral envelope for canonical Fact records."""

    id: str
    layer: NotRequired[str]
    domain: str
    entity_type: str
    canonical_key: str
    attributes: dict[str, Any]
    scope: ScopeValue
    fact_snapshot_id: NotRequired[str]
    tenant_id: NotRequired[str]
    user_id: NotRequired[str]
    created_at: NotRequired[str]
    updated_at: NotRequired[str]
    version: NotRequired[int]
    schema_version: str
    status: NotRequired[str]
    provenance: Provenance
