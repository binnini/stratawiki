from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from wiki_mcp.schemas.fact_record import FactRecord
from wiki_mcp.schemas.interpretation_record import InterpretationRecord
from wiki_mcp.schemas.scope_ref import ScopeRef


@dataclass(frozen=True)
class InterpretationProposalContext:
    """Input context for family-scoped interpretation proposal generation."""

    domain: str
    family: str | None
    subject_type: str
    subject_id: str
    scope_ref: ScopeRef
    fact_snapshot_id: str
    schema_version: str
    facts: list[FactRecord]
    provenance: dict[str, object]
    subject: dict[str, str] | None = None


class InterpretationFamilyBuilder(Protocol):
    """Family-scoped proposal builder.

    Builders should produce proposal-shaped interpretation records that will
    later be validated and promoted by the interpretation lifecycle layer.
    """

    family: str

    def build_proposal(
        self,
        context: InterpretationProposalContext,
    ) -> InterpretationRecord | None: ...
