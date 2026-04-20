"""PostgreSQL-backed repository implementations."""

from wiki_mcp.storage.postgres.repositories import (
    PostgresDependencyRepository,
    PostgresFactRepository,
    PostgresInterpretationPublicationRepository,
    PostgresInterpretationRepository,
    PostgresOutboxRepository,
    PostgresPersonalAssetRepository,
    PostgresPersonalRepository,
    PostgresProfileContextRepository,
    PostgresSnapshotRepository,
)

__all__ = [
    "PostgresDependencyRepository",
    "PostgresFactRepository",
    "PostgresInterpretationPublicationRepository",
    "PostgresInterpretationRepository",
    "PostgresOutboxRepository",
    "PostgresPersonalAssetRepository",
    "PostgresPersonalRepository",
    "PostgresProfileContextRepository",
    "PostgresSnapshotRepository",
]
