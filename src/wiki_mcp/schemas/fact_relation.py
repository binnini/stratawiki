from __future__ import annotations

from typing import Any, NotRequired, TypedDict

from wiki_mcp.schemas.provenance import Provenance
from wiki_mcp.schemas.scope_ref import ScopeValue

class FactRelation(TypedDict):
    """Domain-neutral envelope for canonical Fact relations."""

    domain: str
    relation_type: str
    from_canonical_key: str
    to_canonical_key: str
    scope: ScopeValue
    tenant_id: NotRequired[str]
    user_id: NotRequired[str]
    schema_version: str
    provenance: Provenance
    attributes: NotRequired[dict[str, Any]]
