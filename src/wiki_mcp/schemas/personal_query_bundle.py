from __future__ import annotations

from typing import Any, NotRequired, TypedDict

from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.schemas.snapshot_ref import SnapshotRef


class PersonalQueryBundleItem(TypedDict):
    """One answer-generation context item derived from retrieval results."""

    layer: str
    record_id: str
    title: str
    summary: str
    kind: NotRequired[str]
    retrieval_rank: NotRequired[int]
    retrieval_score: NotRequired[int]
    matched_token_count: NotRequired[int]
    match_reason: NotRequired[str]
    matched_fields: NotRequired[list[str]]
    has_rendered_page: NotRequired[bool]
    path: NotRequired[str]


class PersonalQueryBundle(TypedDict):
    """Thin answer-generation bundle assembled on top of retrieval output."""

    question: str
    scope_ref: ScopeRef
    snapshot_ref: NotRequired[SnapshotRef]
    profile_context: NotRequired[dict[str, Any]]
    personal_context: list[PersonalQueryBundleItem]
    interpretation_context: list[PersonalQueryBundleItem]
    fact_context: list[PersonalQueryBundleItem]
