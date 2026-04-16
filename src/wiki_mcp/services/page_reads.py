from __future__ import annotations

from wiki_mcp.schemas.rendered_page import RenderedPage
from wiki_mcp.schemas.rendered_page_summary import RenderedPageSummary
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.services.interfaces.repositories import RenderingRepository


class DefaultPageReadService:
    """Read-side service for rendered shared and personal pages."""

    def __init__(self, *, rendering_repository: RenderingRepository) -> None:
        self.rendering_repository = rendering_repository

    def get_page(
        self,
        *,
        domain: str,
        layer: str,
        record_id: str,
        scope_ref: ScopeRef,
    ) -> RenderedPage | None:
        return self.rendering_repository.get_page(
            domain=domain,
            layer=layer,
            record_id=record_id,
            scope_ref=scope_ref,
        )

    def list_pages(
        self,
        *,
        domain: str,
        scope_ref: ScopeRef,
        layer: str | None = None,
        limit: int = 20,
    ) -> list[RenderedPageSummary]:
        return self.rendering_repository.list_pages(
            domain=domain,
            scope_ref=scope_ref,
            layer=layer,
            limit=limit,
        )
