from __future__ import annotations

from typing import TypedDict

from wiki_mcp.schemas.page_read_model_state import PageReadModelState
from wiki_mcp.schemas.personal_query_answer import PersonalQueryAnswer
from wiki_mcp.schemas.retrieval_projection_ref import RetrievalProjectionRef
from wiki_mcp.schemas.retrieval_result import RetrievalResult


class PersonalQueryReadResult(TypedDict):
    """Application-facing result envelope for the first personal query slice."""

    ok: bool
    projection: RetrievalProjectionRef
    read_model_state: PageReadModelState
    answer: PersonalQueryAnswer
    retrieval: RetrievalResult
