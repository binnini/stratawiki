from __future__ import annotations

from typing import Literal, TypedDict

from wiki_mcp.schemas.rendered_page_summary import RenderedPageSummary


class PageListResult(TypedDict):
    """Application-facing result envelope for rendered page listing."""

    ok: bool
    read_model_state: Literal["applied"]
    pages: list[RenderedPageSummary]
