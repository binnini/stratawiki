from __future__ import annotations

from pathlib import Path

from psycopg import Connection

from wiki_mcp.schemas.personal_query_read_result import PersonalQueryReadResult
from wiki_mcp.schemas.profile_context import ProfileContext
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.services.page_read_entrypoint import DEFAULT_RENDER_ROOT
from wiki_mcp.services.page_reads import DefaultPageReadService
from wiki_mcp.services.personal_query import DefaultPersonalQueryService
from wiki_mcp.services.retrieval import DefaultRetrievalService
from wiki_mcp.storage.filesystem.rendering import (
    FilesystemAndPostgresRenderingRepository,
)
from wiki_mcp.storage.postgres.repositories import (
    PostgresFactRepository,
    PostgresInterpretationRepository,
    PostgresPersonalRepository,
)


class DefaultPersonalQueryEntrypoint:
    """Application-facing answer slice built on top of retrieval candidates."""

    projection_layers = ["personal", "interpretation", "fact"]

    def __init__(
        self,
        *,
        personal_query_service: DefaultPersonalQueryService,
    ) -> None:
        self.personal_query_service = personal_query_service

    def query_personal_knowledge(
        self,
        *,
        domain: str,
        question: str,
        scope_ref: ScopeRef,
        profile_context: ProfileContext | None = None,
    ) -> PersonalQueryReadResult:
        retrieval, answer = self.personal_query_service.query_personal_knowledge(
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
            "answer": answer,
            "retrieval": retrieval,
        }

    def query_personal_context(
        self,
        *,
        domain: str,
        tenant_id: str,
        user_id: str,
        question: str,
        profile_context: ProfileContext | None = None,
    ) -> PersonalQueryReadResult:
        return self.query_personal_knowledge(
            domain=domain,
            question=question,
            scope_ref={
                "scope": "user",
                "tenant_id": tenant_id,
                "user_id": user_id,
            },
            profile_context=profile_context,
        )


def build_default_personal_query_entrypoint(
    connection: Connection[dict],
    *,
    render_root: str | Path = DEFAULT_RENDER_ROOT,
) -> DefaultPersonalQueryEntrypoint:
    page_read_service = DefaultPageReadService(
        rendering_repository=FilesystemAndPostgresRenderingRepository(
            render_root,
            connection,
        )
    )
    retrieval_service = DefaultRetrievalService(
        page_read_service=page_read_service,
        fact_repository=PostgresFactRepository(connection),
        interpretation_repository=PostgresInterpretationRepository(connection),
        personal_repository=PostgresPersonalRepository(connection),
    )
    return DefaultPersonalQueryEntrypoint(
        personal_query_service=DefaultPersonalQueryService(
            retrieval_service=retrieval_service,
        )
    )
