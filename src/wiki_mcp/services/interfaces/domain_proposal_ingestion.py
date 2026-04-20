from __future__ import annotations

from typing import Protocol

from wiki_mcp.schemas.domain_proposal import (
    DomainProposalBatch,
    DomainProposalIngestionResult,
)


class DomainProposalIngestionService(Protocol):
    """Pack-governed ingestion contract for proposal batches."""

    def validate_batch(
        self,
        batch: DomainProposalBatch,
    ) -> DomainProposalIngestionResult:
        """Evaluate one proposal batch without persisting canonical writes."""

    def ingest_batch(
        self,
        batch: DomainProposalBatch,
        *,
        dry_run: bool = False,
    ) -> DomainProposalIngestionResult:
        """Evaluate one proposal batch and optionally persist accepted writes."""
