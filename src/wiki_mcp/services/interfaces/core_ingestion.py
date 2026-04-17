from __future__ import annotations

from typing import Protocol

from wiki_mcp.schemas.ingestion_batch import IngestionBatch
from wiki_mcp.schemas.ingestion_result import IngestionResult
from wiki_mcp.schemas.source_record import SourceRecord
from wiki_mcp.services.interfaces.domain_ingestion import DomainIngestionPlugin


class CoreIngestionService(Protocol):
    """Core orchestration contract for turning normalized sources into persisted Facts."""

    def prepare_batch(
        self,
        source: SourceRecord,
        plugin: DomainIngestionPlugin,
    ) -> IngestionBatch:
        """Run domain normalization, extraction, and validation without persistence."""

    def ingest_batch(self, batch: IngestionBatch) -> IngestionResult:
        """Persist a validated batch, publish a Fact snapshot, and emit outbox events."""

    def ingest_source(
        self,
        source: SourceRecord,
        plugin: DomainIngestionPlugin,
    ) -> IngestionResult:
        """Convenience method for prepare-plus-persist orchestration."""
