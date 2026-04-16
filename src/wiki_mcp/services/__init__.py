"""Core domain services."""

from wiki_mcp.services.core_ingestion import DefaultCoreIngestionService
from wiki_mcp.services.ingestion_entrypoint import (
    DefaultIngestionEntrypoint,
    build_default_ingestion_entrypoint,
    connect_postgres,
)
from wiki_mcp.services.interpretation_projection import (
    DefaultInterpretationProjectionService,
    DefaultOutboxProjectionWorker,
)
from wiki_mcp.services.personal_stale_marking import (
    DefaultPersonalStaleMarkingService,
    DefaultPersonalStaleWorker,
)

__all__ = [
    "DefaultCoreIngestionService",
    "DefaultIngestionEntrypoint",
    "DefaultInterpretationProjectionService",
    "DefaultOutboxProjectionWorker",
    "DefaultPersonalStaleMarkingService",
    "DefaultPersonalStaleWorker",
    "build_default_ingestion_entrypoint",
    "connect_postgres",
]
