from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from wiki_mcp.services.ingestion_entrypoint import (
    DefaultIngestionEntrypoint,
    build_default_ingestion_entrypoint,
)
from wiki_mcp.services.page_read_entrypoint import (
    DEFAULT_RENDER_ROOT,
    DefaultPageReadEntrypoint,
)
from wiki_mcp.services.page_reads import DefaultPageReadService
from wiki_mcp.services.personal_query import DefaultPersonalQueryService
from wiki_mcp.services.personal_query_entrypoint import DefaultPersonalQueryEntrypoint
from wiki_mcp.services.retrieval import DefaultRetrievalService
from wiki_mcp.services.retrieval_read_entrypoint import DefaultRetrievalReadEntrypoint
from wiki_mcp.storage.postgres.repositories import (
    PostgresFactRepository,
    PostgresInterpretationRepository,
    PostgresPersonalRepository,
)
from wiki_mcp.storage.filesystem.rendering import (
    FilesystemAndPostgresRenderingRepository,
)


DEFAULT_DATABASE_URL = "postgresql://stratawiki:stratawiki@localhost:5432/stratawiki"


@dataclass(slots=True)
class ApplicationEntrypoints:
    """Bundled application-facing entrypoints used by server bootstrap."""

    ingestion: DefaultIngestionEntrypoint
    page_reads: DefaultPageReadEntrypoint
    retrieval_reads: DefaultRetrievalReadEntrypoint
    personal_queries: DefaultPersonalQueryEntrypoint


@dataclass(slots=True)
class BootstrapContext:
    """Runtime bootstrap context for the current thin server slice."""

    connection: psycopg.Connection[dict]
    entrypoints: ApplicationEntrypoints
    owns_connection: bool = False

    def close(self) -> None:
        if self.owns_connection and not self.connection.closed:
            self.connection.close()


def resolve_database_url(database_url: str | None = None) -> str:
    return database_url or os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL


def connect_postgres(database_url: str | None = None) -> psycopg.Connection[dict]:
    resolved_url = resolve_database_url(database_url)
    psycopg_url = resolved_url.replace("+psycopg", "", 1)
    return psycopg.connect(psycopg_url, row_factory=dict_row)


def build_application_entrypoints(
    connection: psycopg.Connection[dict],
    *,
    render_root: str | Path = DEFAULT_RENDER_ROOT,
) -> ApplicationEntrypoints:
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
    return ApplicationEntrypoints(
        ingestion=build_default_ingestion_entrypoint(connection),
        page_reads=DefaultPageReadEntrypoint(
            page_read_service=page_read_service,
        ),
        retrieval_reads=DefaultRetrievalReadEntrypoint(
            retrieval_service=retrieval_service
        ),
        personal_queries=DefaultPersonalQueryEntrypoint(
            personal_query_service=DefaultPersonalQueryService(
                retrieval_service=retrieval_service,
            )
        ),
    )


def bootstrap_application(
    *,
    connection: psycopg.Connection[dict] | None = None,
    database_url: str | None = None,
    render_root: str | Path = DEFAULT_RENDER_ROOT,
) -> BootstrapContext:
    owns_connection = connection is None
    resolved_connection = connection or connect_postgres(database_url)
    return BootstrapContext(
        connection=resolved_connection,
        entrypoints=build_application_entrypoints(
            resolved_connection,
            render_root=render_root,
        ),
        owns_connection=owns_connection,
    )
