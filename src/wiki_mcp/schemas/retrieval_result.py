from __future__ import annotations

from typing import NotRequired, TypedDict

from wiki_mcp.schemas.retrieval_fact_summary import RetrievalFactSummary
from wiki_mcp.schemas.retrieval_interpretation_summary import (
    RetrievalInterpretationSummary,
)
from wiki_mcp.schemas.retrieval_match_explanation import RetrievalMatchExplanation
from wiki_mcp.schemas.retrieval_metadata import RetrievalMetadata
from wiki_mcp.schemas.retrieval_personal_summary import RetrievalPersonalSummary
from wiki_mcp.schemas.rendered_page_summary import RenderedPageSummary
from wiki_mcp.schemas.snapshot_ref import SnapshotRef


class RetrievalResult(TypedDict):
    """Result envelope for retrieval orchestration across layers."""

    personal_ids: list[str]
    interpretation_ids: list[str]
    fact_ids: list[str]
    personal_records: NotRequired[list[RetrievalPersonalSummary]]
    interpretation_records: NotRequired[list[RetrievalInterpretationSummary]]
    fact_records: NotRequired[list[RetrievalFactSummary]]
    personal_pages: NotRequired[list[RenderedPageSummary]]
    interpretation_pages: NotRequired[list[RenderedPageSummary]]
    fact_pages: NotRequired[list[RenderedPageSummary]]
    personal_explanations: NotRequired[list[RetrievalMatchExplanation]]
    interpretation_explanations: NotRequired[list[RetrievalMatchExplanation]]
    fact_explanations: NotRequired[list[RetrievalMatchExplanation]]
    retrieval_metadata: NotRequired[RetrievalMetadata]
    snapshot_ref: NotRequired[SnapshotRef]
