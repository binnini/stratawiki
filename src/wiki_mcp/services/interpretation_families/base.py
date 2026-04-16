from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from wiki_mcp.schemas.fact_record import FactRecord
from wiki_mcp.schemas.interpretation_record import InterpretationRecord
from wiki_mcp.schemas.outbox_event import FactIngestedPayload
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.schemas.snapshot_ref import SnapshotRef


@dataclass(frozen=True)
class InterpretationBuildContext:
    payload: FactIngestedPayload
    facts: list[FactRecord]
    scope_ref: ScopeRef
    source_event_id: str
    schema_version: str


class InterpretationFamilyBuilder(Protocol):
    family: str

    def build_record(
        self,
        context: InterpretationBuildContext,
    ) -> InterpretationRecord | None: ...

    def build_rendered_artifact(
        self,
        record: InterpretationRecord,
        *,
        snapshot_ref: SnapshotRef,
    ) -> dict[str, object]: ...
