from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

from wiki_mcp.schemas.page_read_error import PageReadError
from wiki_mcp.schemas.rendered_page import RenderedPage


class PageReadResult(TypedDict):
    """Application-facing result envelope for one rendered page read."""

    ok: bool
    read_model_state: Literal["applied", "not_applicable"]
    page: NotRequired[RenderedPage]
    error: NotRequired[PageReadError]
