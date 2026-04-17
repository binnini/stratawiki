from __future__ import annotations

from wiki_mcp.adapters.llm import DeterministicLLMGateway
from wiki_mcp.services.interpretation_families import (
    InterpretationProposalContext,
    MarketTrendInterpretationBuilder,
)


def test_market_trend_builder_generates_llm_backed_proposal() -> None:
    builder = MarketTrendInterpretationBuilder(
        llm_gateway=DeterministicLLMGateway(
            provider="mock-provider",
            model="mock-model-v1",
            default_structured_output={
                "kind": "market_trend",
                "title": "Production LLM experience demand is rising",
                "claim": "Production LLM experience is increasingly requested in this segment.",
                "summary": "Shared demand is moving toward applied LLM delivery skills.",
                "body": {
                    "headline": "LLM delivery skills are showing up more often",
                    "thesis": "Employers increasingly prefer candidates who can ship LLM-backed systems.",
                    "signals": ["Multiple backend postings reference production AI work."],
                    "observations": ["Roles cluster around backend and platform work."],
                    "counterpoints": ["Some postings still prioritize general backend fundamentals."],
                },
            },
        )
    )

    proposal = builder.build_proposal(_proposal_context())

    assert proposal is not None
    assert proposal["family"] == "market_trend"
    assert proposal["kind"] == "market_trend"
    assert proposal["title"] == "Production LLM experience demand is rising"
    assert proposal["summary"] == "Shared demand is moving toward applied LLM delivery skills."
    assert proposal["confidence"] == 0.69
    assert proposal["computed_at"] == "2026-04-17T10:00:00Z"
    assert proposal["expires_at"] == "2026-04-18T10:00:00Z"
    assert proposal["render_hints"] == {
        "page_family": "market_trend",
        "page_key": "backend-japan-midlevel",
        "priority": "medium",
    }
    assert proposal["evidence"] == [
        {"fact_id": "fact:job:1", "weight": 0.5, "role": "primary"},
        {"fact_id": "fact:job:2", "weight": 0.5, "role": "supporting"},
    ]
    assert proposal["provenance"]["generated_by"]["provider"] == "mock-provider"
    assert proposal["provenance"]["generated_by"]["schema_name"] == "interpretation.market_trend"


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
                "attributes": {
                    "title": "Backend Engineer",
                    "summary": "Production AI systems experience preferred.",
                },
                "scope": "shared",
                "schema_version": "fact.v1",
                "provenance": {"source_ids": ["job:1"]},
            },
            {
                "id": "fact:job:2",
                "domain": "recruiting",
                "entity_type": "job_posting",
                "canonical_key": "job:2",
                "attributes": {
                    "title": "Platform Engineer",
                    "summary": "LLM feature delivery and evaluation background preferred.",
                },
                "scope": "shared",
                "schema_version": "fact.v1",
                "provenance": {"source_ids": ["job:2"]},
            },
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
