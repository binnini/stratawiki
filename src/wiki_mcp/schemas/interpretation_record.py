from __future__ import annotations

from typing import Any, NotRequired, TypedDict

from wiki_mcp.schemas.interpretation_lifecycle import InterpretationLifecycleStatus
from wiki_mcp.schemas.provenance import Provenance
from wiki_mcp.schemas.scope_ref import ScopeRef


class InterpretationRecord(TypedDict):
    """Canonical shared Interpretation record envelope."""

    id: str
    layer: NotRequired[str]
    domain: str
    family: NotRequired[str]
    kind: str
    subject_type: str
    subject_id: str
    subject_label: NotRequired[str]
    subject: NotRequired[dict[str, str]]
    scope_ref: ScopeRef
    schema_version: str
    status: InterpretationLifecycleStatus
    confidence: float
    fact_snapshot_id: str
    computed_at: str
    expires_at: str | None
    interpretation_snapshot_id: NotRequired[str]
    created_at: NotRequired[str]
    updated_at: NotRequired[str]
    version: NotRequired[int]
    title: NotRequired[str]
    claim: NotRequired[str]
    summary: NotRequired[str]
    body: dict[str, Any]
    evidence: NotRequired[list[dict[str, Any]]]
    relations: NotRequired[list[dict[str, Any]]]
    freshness: NotRequired[dict[str, Any]]
    confidence_detail: NotRequired[dict[str, float]]
    provenance: Provenance
    render_hints: dict[str, Any]
