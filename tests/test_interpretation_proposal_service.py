from __future__ import annotations

from typing import Any

from wiki_mcp.services.interpretation_families import (
    InterpretationFamilyRegistry,
    InterpretationProposalContext,
)
from wiki_mcp.services.interpretation_proposals import InterpretationProposalService


class StubInterpretationBuilder:
    family = "market_trend"

    def build_proposal(self, context: InterpretationProposalContext) -> dict[str, Any] | None:
        return {
            "id": "interp:proposal:1",
            "kind": "trend",
            "claim": "Production LLM experience preference is increasing.",
            "summary": "Demand is trending upward.",
            "confidence": 0.82,
            "computed_at": "2026-04-17T10:00:00Z",
            "expires_at": None,
            "body": {"signals": ["llm"]},
            "evidence": [{"fact_id": "fact:job:1", "weight": 0.7, "role": "primary"}],
            "provenance": dict(context.provenance),
            "render_hints": {"page_family": context.family},
        }


class FakeInterpretationRepository:
    def __init__(self, records: dict[str, dict[str, Any]] | None = None) -> None:
        self.records = dict(records or {})
        self.saved_batches: list[tuple[list[dict[str, Any]], dict[str, Any]]] = []

    def get_by_ids(
        self,
        ids: list[str],
        scope_ref: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return [
            dict(self.records[record_id])
            for record_id in ids
            if record_id in self.records
        ]

    def search_for_retrieval(self, **_: Any) -> list[dict[str, Any]]:
        return []

    def save_records(
        self,
        records: list[dict[str, Any]],
        snapshot_ref: dict[str, Any],
    ) -> list[str]:
        self.saved_batches.append(([dict(record) for record in records], dict(snapshot_ref)))
        for record in records:
            self.records[record["id"]] = dict(record)
        return [record["id"] for record in records]


class FakeFactRepository:
    def __init__(self, facts: list[dict[str, Any]]) -> None:
        self.facts = {fact["id"]: dict(fact) for fact in facts}

    def get_by_ids(
        self,
        ids: list[str],
        scope_ref: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return [dict(self.facts[fact_id]) for fact_id in ids if fact_id in self.facts]

    def get_by_canonical_keys(self, canonical_keys: list[str], scope_ref: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    def search_for_retrieval(self, **_: Any) -> list[dict[str, Any]]:
        return []

    def write_facts(self, records: list[dict[str, Any]], relations: list[dict[str, Any]], *, fact_snapshot_id: str) -> dict[str, Any]:
        return {}


def _proposal_context() -> InterpretationProposalContext:
    return InterpretationProposalContext(
        domain="recruiting",
        family="market_trend",
        subject_type="market_segment",
        subject_id="backend-japan-midlevel",
        scope_ref={"scope": "shared"},
        fact_snapshot_id="fact_snap:1",
        schema_version="interpretation.v2",
        facts=[
            {
                "id": "fact:job:1",
                "domain": "recruiting",
                "entity_type": "job_posting",
                "canonical_key": "job:1",
                "attributes": {"title": "Backend Engineer"},
                "scope": "shared",
                "schema_version": "fact.v1",
                "provenance": {"source_ids": ["job:1"]},
            }
        ],
        provenance={
            "generated_by": {
                "kind": "llm",
                "provider": "openai",
                "model": "gpt-5.4",
                "prompt_version": "interp.market_trend.v1",
            },
            "generated_at": "2026-04-17T10:00:00Z",
        },
    )


def _fact_repository() -> FakeFactRepository:
    return FakeFactRepository(
        [
            {
                "id": "fact:job:1",
                "domain": "recruiting",
                "entity_type": "job_posting",
                "canonical_key": "job:1",
                "attributes": {"title": "Backend Engineer"},
                "scope": "shared",
                "schema_version": "fact.v1",
                "provenance": {"source_ids": ["job:1"]},
            }
        ]
    )


def test_create_proposals_persists_proposed_interpretations() -> None:
    interpretation_repository = FakeInterpretationRepository()
    service = InterpretationProposalService(
        family_registry=InterpretationFamilyRegistry([StubInterpretationBuilder()]),
        interpretation_repository=interpretation_repository,
        fact_repository=_fact_repository(),
    )

    proposals = service.create_proposals(_proposal_context())

    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal["status"] == "proposed"
    assert proposal["family"] == "market_trend"
    assert proposal["subject_id"] == "backend-japan-midlevel"
    assert proposal["fact_snapshot_id"] == "fact_snap:1"
    saved_records, snapshot_ref = interpretation_repository.saved_batches[0]
    assert saved_records[0]["status"] == "proposed"
    assert snapshot_ref == {"fact_snapshot_id": "fact_snap:1"}


def test_validate_proposal_promotes_to_validated_when_evidence_exists() -> None:
    interpretation_repository = FakeInterpretationRepository(
        {
            "interp:proposal:1": {
                "id": "interp:proposal:1",
                "layer": "interpretation",
                "domain": "recruiting",
                "family": "market_trend",
                "kind": "trend",
                "subject_type": "market_segment",
                "subject_id": "backend-japan-midlevel",
                "scope_ref": {"scope": "shared"},
                "schema_version": "interpretation.v2",
                "status": "proposed",
                "confidence": 0.82,
                "fact_snapshot_id": "fact_snap:1",
                "computed_at": "2026-04-17T10:00:00Z",
                "expires_at": None,
                "claim": "Production LLM experience preference is increasing.",
                "summary": "Demand is trending upward.",
                "body": {"signals": ["llm"]},
                "evidence": [{"fact_id": "fact:job:1", "weight": 0.7, "role": "primary"}],
                "provenance": {"generated_by": {"kind": "llm"}},
                "render_hints": {"page_family": "market_trend"},
            }
        }
    )
    service = InterpretationProposalService(
        family_registry=InterpretationFamilyRegistry(),
        interpretation_repository=interpretation_repository,
        fact_repository=_fact_repository(),
    )

    result = service.validate_proposal(
        proposal_id="interp:proposal:1",
        scope_ref={"scope": "shared"},
    )

    assert result["ok"] is True
    assert result["status"] == "validated"
    assert result["errors"] == []
    assert interpretation_repository.records["interp:proposal:1"]["status"] == "validated"


def test_validate_proposal_rejects_missing_evidence_fact_with_structured_error() -> None:
    interpretation_repository = FakeInterpretationRepository(
        {
            "interp:proposal:missing-fact": {
                "id": "interp:proposal:missing-fact",
                "layer": "interpretation",
                "domain": "recruiting",
                "family": "market_trend",
                "kind": "trend",
                "subject_type": "market_segment",
                "subject_id": "backend-japan-midlevel",
                "scope_ref": {"scope": "shared"},
                "schema_version": "interpretation.v2",
                "status": "proposed",
                "confidence": 0.82,
                "fact_snapshot_id": "fact_snap:1",
                "computed_at": "2026-04-17T10:00:00Z",
                "expires_at": None,
                "claim": "Production LLM experience preference is increasing.",
                "summary": "Demand is trending upward.",
                "body": {"signals": ["llm"]},
                "evidence": [{"fact_id": "fact:job:missing", "weight": 0.7, "role": "primary"}],
                "provenance": {"generated_by": {"kind": "llm"}},
                "render_hints": {"page_family": "market_trend"},
            }
        }
    )
    service = InterpretationProposalService(
        family_registry=InterpretationFamilyRegistry(),
        interpretation_repository=interpretation_repository,
        fact_repository=_fact_repository(),
    )

    result = service.validate_proposal(
        proposal_id="interp:proposal:missing-fact",
        scope_ref={"scope": "shared"},
    )

    assert result["ok"] is False
    assert result["status"] == "rejected"
    assert result["errors"][0]["code"] == "evidence_fact_not_found"
    assert result["errors"][0]["details"] == {"fact_id": "fact:job:missing"}
    assert interpretation_repository.records["interp:proposal:missing-fact"]["status"] == "rejected"
