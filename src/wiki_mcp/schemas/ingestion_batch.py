from __future__ import annotations

from typing import TypedDict

from wiki_mcp.schemas.fact_record import FactRecord
from wiki_mcp.schemas.fact_relation import FactRelation
from wiki_mcp.schemas.source_record import SourceRecord
from wiki_mcp.schemas.validation_result import ValidationResult


class IngestionBatch(TypedDict):
    """Validated extraction output returned by a domain plugin before persistence."""

    source: SourceRecord
    records: list[FactRecord]
    relations: list[FactRelation]
    validation: ValidationResult
