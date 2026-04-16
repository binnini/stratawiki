from __future__ import annotations

from typing import Any, TypedDict

from wiki_mcp.schemas.scope_ref import ScopeRef


class InterpretationRecord(TypedDict):
    """Canonical shared Interpretation record envelope."""

    id: str
    domain: str
    kind: str
    subject_type: str
    subject_id: str
    scope_ref: ScopeRef
    schema_version: str
    status: str
    confidence: float
    fact_snapshot_id: str
    computed_at: str
    expires_at: str | None
    body: dict[str, Any]
    provenance: dict[str, Any]
    render_hints: dict[str, Any]
