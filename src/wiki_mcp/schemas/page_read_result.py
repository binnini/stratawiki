from __future__ import annotations

from typing import NotRequired, TypedDict

from wiki_mcp.schemas.page_read_error import PageReadError
from wiki_mcp.schemas.page_projection_ref import PageProjectionRef
from wiki_mcp.schemas.page_read_model_state import PageReadModelState
from wiki_mcp.schemas.rendered_page import RenderedPage


class PageReadResult(TypedDict):
    """Application-facing result envelope for one rendered page read."""

    ok: bool
    projection: PageProjectionRef
    read_model_state: PageReadModelState
    page: NotRequired[RenderedPage]
    error: NotRequired[PageReadError]
