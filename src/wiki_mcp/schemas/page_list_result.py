from __future__ import annotations

from typing import TypedDict

from wiki_mcp.schemas.page_projection_ref import PageProjectionRef
from wiki_mcp.schemas.page_read_model_state import PageReadModelState
from wiki_mcp.schemas.rendered_page_summary import RenderedPageSummary


class PageListResult(TypedDict):
    """Application-facing result envelope for rendered page listing."""

    ok: bool
    projection: PageProjectionRef
    read_model_state: PageReadModelState
    pages: list[RenderedPageSummary]
