from __future__ import annotations

from pathlib import Path

from psycopg import Connection

from wiki_mcp.schemas.profile_context import ProfileContext
from wiki_mcp.schemas.retrieval_read_result import RetrievalReadResult
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.services.page_read_entrypoint import DEFAULT_RENDER_ROOT
from wiki_mcp.services.page_reads import DefaultPageReadService
from wiki_mcp.services.retrieval import DefaultRetrievalService
from wiki_mcp.storage.filesystem.rendering import (
    FilesystemAndPostgresRenderingRepository,
)


class DefaultRetrievalReadEntrypoint:
    """Application-facing read authority for layered retrieval candidates."""

    projection_layers = ["personal", "interpretation", "fact"]

    def __init__(
        self,
        *,
        retrieval_service: DefaultRetrievalService,
    ) -> None:
        self.retrieval_service = retrieval_service

    def retrieve_for_query(
        self,
        *,
        domain: str,
        question: str,
        scope_ref: ScopeRef,
        profile_context: ProfileContext | None = None,
    ) -> RetrievalReadResult:
        retrieval = self.retrieval_service.retrieve_for_query(
            domain=domain,
            question=question,
            scope_ref=scope_ref,
            profile_context=profile_context,
        )
        return {
            "ok": True,
            "projection": {
                "family": "retrieval",
                "scope": scope_ref["scope"],
                "layers": self.projection_layers,
            },
            "read_model_state": "applied",
            "retrieval": retrieval,
        }

    def retrieve_personal_context(
        self,
        *,
        domain: str,
        tenant_id: str,
        user_id: str,
        question: str,
        profile_context: ProfileContext | None = None,
    ) -> RetrievalReadResult:
        return self.retrieve_for_query(
            domain=domain,
            question=question,
            scope_ref={
                "scope": "user",
                "tenant_id": tenant_id,
                "user_id": user_id,
            },
            profile_context=profile_context,
        )


def build_default_retrieval_read_entrypoint(
    connection: Connection[dict],
    *,
    render_root: str | Path = DEFAULT_RENDER_ROOT,
) -> DefaultRetrievalReadEntrypoint:
    page_read_service = DefaultPageReadService(
        rendering_repository=FilesystemAndPostgresRenderingRepository(
            render_root,
            connection,
        )
    )
    retrieval_service = DefaultRetrievalService(page_read_service=page_read_service)
    return DefaultRetrievalReadEntrypoint(retrieval_service=retrieval_service)
