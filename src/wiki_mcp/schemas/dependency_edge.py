from __future__ import annotations

from typing import Any, NotRequired, TypedDict

from wiki_mcp.schemas.scope_ref import ScopeRef


class DependencyEdge(TypedDict):
    """Dependency edge written into the reverse-impact index."""

    domain: str
    from_layer: str
    from_id: str
    to_layer: str
    to_id: str
    scope_ref: ScopeRef
    edge_type: NotRequired[str]
    attributes: NotRequired[dict[str, Any]]
