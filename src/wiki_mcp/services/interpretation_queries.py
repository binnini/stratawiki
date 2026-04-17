from __future__ import annotations

from wiki_mcp.schemas import (
    INTERPRETATION_STATUS_PUBLISHED,
    INTERPRETATION_STATUS_STALE,
    InterpretationRecord,
    ScopeRef,
)
from wiki_mcp.services.interfaces.repositories import InterpretationRepository


class InterpretationQueryService:
    """Minimal read surface for published interpretation records."""

    def __init__(self, *, interpretation_repository: InterpretationRepository) -> None:
        self.interpretation_repository = interpretation_repository

    def get_interpretation_record(
        self,
        *,
        record_id: str,
        scope_ref: ScopeRef,
        include_non_public: bool = False,
    ) -> InterpretationRecord | None:
        records = self.interpretation_repository.get_by_ids([record_id], scope_ref)
        if not records:
            return None
        record = records[0]
        if include_non_public or record["status"] in {
            INTERPRETATION_STATUS_PUBLISHED,
            INTERPRETATION_STATUS_STALE,
        }:
            return record
        return None

    def search_interpretations(
        self,
        *,
        domain: str,
        question: str,
        scope_ref: ScopeRef,
        limit: int = 10,
    ) -> list[InterpretationRecord]:
        query_tokens = [token for token in question.lower().split() if token]
        return self.interpretation_repository.search_for_retrieval(
            domain=domain,
            scope_ref=scope_ref,
            query_text=question.strip(),
            query_tokens=query_tokens,
            limit=limit,
        )
