from __future__ import annotations

from typing import NotRequired, TypedDict

from wiki_mcp.schemas.ingestion_error import IngestionError
from wiki_mcp.schemas.ingestion_result import IngestionResult
from wiki_mcp.schemas.source_record import SourceRecord
from wiki_mcp.schemas.validation_result import ValidationResult


class IngestionExecutionResult(TypedDict):
    """Application-facing result envelope for one ingestion attempt."""

    ok: bool
    source: NotRequired[SourceRecord]
    plugin_name: NotRequired[str]
    validation: NotRequired[ValidationResult]
    ingestion_result: NotRequired[IngestionResult]
    error: NotRequired[IngestionError]
