"""Core domain services."""

from wiki_mcp.services.core_ingestion import DefaultCoreIngestionService
from wiki_mcp.services.ingestion_entrypoint import (
    DefaultIngestionEntrypoint,
    build_default_ingestion_entrypoint,
    connect_postgres,
)

__all__ = [
    "DefaultCoreIngestionService",
    "DefaultIngestionEntrypoint",
    "build_default_ingestion_entrypoint",
    "connect_postgres",
]
