from __future__ import annotations

from typing import TypedDict

from wiki_mcp.schemas.page_read_model_state import PageReadModelState
from wiki_mcp.schemas.retrieval_projection_ref import RetrievalProjectionRef
from wiki_mcp.schemas.retrieval_result import RetrievalResult


class RetrievalReadResult(TypedDict):
    """Application-facing result envelope for retrieval candidate reads."""

    ok: bool
    projection: RetrievalProjectionRef
    read_model_state: PageReadModelState
    retrieval: RetrievalResult
