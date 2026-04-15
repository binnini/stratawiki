from __future__ import annotations

from typing import Protocol

from wiki_mcp.schemas.profile_context import ProfileContext
from wiki_mcp.schemas.retrieval_result import RetrievalResult
from wiki_mcp.schemas.scope_ref import ScopeRef


class RetrievalService(Protocol):
    """Layer-aware retrieval orchestration across Personal, Interpretation, and Fact."""

    def retrieve_for_query(
        self,
        domain: str,
        question: str,
        scope_ref: ScopeRef,
        profile_context: ProfileContext | None = None,
    ) -> RetrievalResult:
        """Resolve query context using the default layer order and scope rules."""
