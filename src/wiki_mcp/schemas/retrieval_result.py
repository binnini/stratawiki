from __future__ import annotations

from typing import NotRequired, TypedDict

from wiki_mcp.schemas.fact_record import FactRecord
from wiki_mcp.schemas.interpretation_record import InterpretationRecord
from wiki_mcp.schemas.personal_record import PersonalRecord
from wiki_mcp.schemas.rendered_page_summary import RenderedPageSummary
from wiki_mcp.schemas.snapshot_ref import SnapshotRef


class RetrievalResult(TypedDict):
    """Result envelope for retrieval orchestration across layers."""

    personal_ids: list[str]
    interpretation_ids: list[str]
    fact_ids: list[str]
    personal_records: NotRequired[list[PersonalRecord]]
    interpretation_records: NotRequired[list[InterpretationRecord]]
    fact_records: NotRequired[list[FactRecord]]
    personal_pages: NotRequired[list[RenderedPageSummary]]
    interpretation_pages: NotRequired[list[RenderedPageSummary]]
    fact_pages: NotRequired[list[RenderedPageSummary]]
    snapshot_ref: NotRequired[SnapshotRef]
