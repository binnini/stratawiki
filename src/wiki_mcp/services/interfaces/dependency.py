from __future__ import annotations

from typing import Protocol

from wiki_mcp.schemas.dependency_impact import DependencyImpact
from wiki_mcp.schemas.scope_ref import ScopeRef


class DependencyService(Protocol):
    """Dependency lookup and impact analysis for invalidation and refresh routing."""

    def get_impact(
        self,
        domain: str,
        layer: str,
        record_id: str,
        scope_ref: ScopeRef,
    ) -> DependencyImpact:
        """Return downstream artifacts affected by a changed canonical record."""
