from __future__ import annotations

from typing import Protocol

from wiki_mcp.schemas.fact_record import FactRecord
from wiki_mcp.schemas.fact_relation import FactRelation
from wiki_mcp.schemas.source_record import SourceRecord
from wiki_mcp.schemas.validation_result import ValidationResult


class DomainIngestionPlugin(Protocol):
    """Legacy source-driven decomposition contract kept for compatibility flows."""

    domain_name: str
    schema_version: str

    def accepts(self, source: SourceRecord) -> bool:
        """Return whether this plugin can process the provided source."""

    def normalize_source(self, source: SourceRecord) -> SourceRecord:
        """Apply domain-specific normalization to a common source envelope."""

    def extract_fact_records(self, source: SourceRecord) -> list[FactRecord]:
        """Extract canonical Fact records from a normalized source."""

    def extract_fact_relations(
        self,
        source: SourceRecord,
        records: list[FactRecord],
    ) -> list[FactRelation]:
        """Extract explicit Fact relations from a normalized source and extracted records."""

    def validate_batch(
        self,
        source: SourceRecord,
        records: list[FactRecord],
        relations: list[FactRelation],
    ) -> ValidationResult:
        """Validate extracted records and relations before core persistence."""
