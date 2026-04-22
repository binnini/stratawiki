from __future__ import annotations

from typing import Protocol

from wiki_mcp.schemas.ingestion_batch import IngestionBatch
from wiki_mcp.schemas.ingestion_result import IngestionResult
from wiki_mcp.schemas.source_record import SourceRecord
from wiki_mcp.services.interfaces.domain_ingestion import DomainIngestionPlugin


class CoreIngestionService(Protocol):
    """Core canonical Fact write contract plus a legacy source/plugin seam."""

    def prepare_legacy_source_batch(
        self,
        source: SourceRecord,
        plugin: DomainIngestionPlugin,
    ) -> IngestionBatch:
        """Compatibility path for `SourceRecord -> DomainIngestionPlugin` normalization."""

    def prepare_batch(
        self,
        source: SourceRecord,
        plugin: DomainIngestionPlugin,
    ) -> IngestionBatch:
        """Compatibility alias for preparing one legacy normalized-source batch."""

    def ingest_batch(self, batch: IngestionBatch) -> IngestionResult:
        """Persist a validated canonical batch, publish a Fact snapshot, and emit outbox events."""

    def ingest_legacy_source(
        self,
        source: SourceRecord,
        plugin: DomainIngestionPlugin,
    ) -> IngestionResult:
        """Compatibility path for persisting one normalized source through a plugin."""

    def ingest_source(
        self,
        source: SourceRecord,
        plugin: DomainIngestionPlugin,
    ) -> IngestionResult:
        """Compatibility alias for prepare-plus-persist legacy source ingestion."""
