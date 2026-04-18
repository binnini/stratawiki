from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wiki_mcp.adapters.llm import DeterministicLLMGateway
from wiki_mcp.services import (
    DefaultDomainPackApprovalService,
    DefaultDomainPackCompatibilityChecker,
    DefaultDomainPackValidator,
    InMemoryDomainPackRegistry,
    InterpretationProposalService,
    InterpretationPublicationService,
    InterpretationQueryService,
    PersonalKnowledgeQueryService,
    PersonalQueryOrchestrator,
)
from wiki_mcp.services.core_ingestion import DefaultCoreIngestionService
from wiki_mcp.services.interpretation_families import (
    InterpretationFamilyRegistry,
    MarketTrendInterpretationBuilder,
)
from wiki_mcp.services.retrieval import CuratedRetrievalService
from wiki_mcp.storage.filesystem import FileSystemRenderingRepository
from wiki_mcp.storage.memory import (
    InMemoryFactRepository,
    InMemoryInterpretationRepository,
    InMemoryOutboxRepository,
    InMemoryPersonalRepository,
    InMemoryProfileContextRepository,
    InMemorySnapshotRepository,
)


DEFAULT_DEMO_SEED_PATH = Path("examples/demo/mvp-seed.json")


@dataclass(frozen=True, slots=True)
class DemoSeed:
    raw: dict[str, Any]

    @property
    def profiles(self) -> list[dict[str, Any]]:
        return list(self.raw.get("profiles") or [])

    @property
    def source_records(self) -> list[dict[str, Any]]:
        return list(self.raw.get("source_records") or [])

    @property
    def demo_query(self) -> dict[str, Any]:
        return dict(self.raw.get("demo_query") or {})

    @property
    def demo_partition(self) -> dict[str, Any]:
        return dict(self.raw.get("demo_partition") or {})


def load_demo_seed(seed_path: str | Path | None = None) -> DemoSeed:
    path = Path(seed_path or DEFAULT_DEMO_SEED_PATH)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Demo seed at {path} must decode to an object.")
    return DemoSeed(raw=raw)


def build_demo_runtime(*, render_root: str | Path, seed_path: str | Path | None = None) -> dict[str, Any]:
    seed = load_demo_seed(seed_path)
    fact_repository = InMemoryFactRepository()
    interpretation_repository = InMemoryInterpretationRepository()
    personal_repository = InMemoryPersonalRepository()
    profile_context_repository = InMemoryProfileContextRepository(
        {
            (profile["domain"], profile["tenant_id"], profile["user_id"]): dict(profile)
            for profile in seed.profiles
        }
    )
    snapshot_repository = InMemorySnapshotRepository()
    outbox_repository = InMemoryOutboxRepository()
    rendering_repository = FileSystemRenderingRepository(render_root)
    llm_gateway = DeterministicLLMGateway(
        provider="mock",
        model="deterministic-demo-v1",
        default_text=(
            "## Strategy\n\n"
            "Focus on backend roles that explicitly mention platform, API, and production AI delivery work.\n\n"
            "## Next Steps\n\n"
            "- Prioritize postings that mention applied LLM or AI systems.\n"
            "- Emphasize backend execution, APIs, and shipping experience.\n"
            "- Build application materials around production-facing impact.\n"
        ),
        default_structured_output={
            "kind": "market_trend",
            "title": "Production AI delivery demand is rising",
            "claim": "Backend roles increasingly prefer candidates who can ship production AI systems.",
            "summary": "Hiring signals are tilting toward backend candidates with practical AI delivery experience.",
            "body": {
                "headline": "Production AI experience is showing up more often",
                "thesis": "Employers want backend engineers who can translate AI capability into production systems.",
                "signals": [
                    "Job summaries mention production AI, API delivery, and platform integration."
                ],
                "observations": [
                    "Demand is clustering around backend and platform responsibilities."
                ],
                "counterpoints": [
                    "Core backend fundamentals remain the baseline requirement."
                ]
            }
        },
    )
    core_ingestion_service = DefaultCoreIngestionService(
        fact_repository=fact_repository,
        snapshot_repository=snapshot_repository,
        outbox_repository=outbox_repository,
    )
    retrieval_service = CuratedRetrievalService(
        fact_repository=fact_repository,
        interpretation_repository=interpretation_repository,
        personal_repository=personal_repository,
    )
    personal_query_orchestrator = PersonalQueryOrchestrator(retrieval_service=retrieval_service)
    personal_query_service = PersonalKnowledgeQueryService(
        orchestrator=personal_query_orchestrator,
        llm_gateway=llm_gateway,
        personal_repository=personal_repository,
        rendering_repository=rendering_repository,
    )
    interpretation_family_registry = InterpretationFamilyRegistry(
        [MarketTrendInterpretationBuilder(llm_gateway=llm_gateway)]
    )
    interpretation_proposal_service = InterpretationProposalService(
        family_registry=interpretation_family_registry,
        interpretation_repository=interpretation_repository,
        fact_repository=fact_repository,
    )
    interpretation_publication_service = InterpretationPublicationService(
        proposal_service=interpretation_proposal_service,
        interpretation_repository=interpretation_repository,
        snapshot_repository=snapshot_repository,
    )
    interpretation_query_service = InterpretationQueryService(
        interpretation_repository=interpretation_repository,
    )
    domain_pack_registry = InMemoryDomainPackRegistry()
    domain_pack_validator = DefaultDomainPackValidator()
    domain_pack_compatibility_checker = DefaultDomainPackCompatibilityChecker()
    domain_pack_approval_service = DefaultDomainPackApprovalService(
        domain_pack_registry=domain_pack_registry,
        validator=domain_pack_validator,
        compatibility_checker=domain_pack_compatibility_checker,
    )
    return {
        "seed": seed,
        "fact_repository": fact_repository,
        "interpretation_repository": interpretation_repository,
        "personal_repository": personal_repository,
        "profile_context_repository": profile_context_repository,
        "snapshot_repository": snapshot_repository,
        "outbox_repository": outbox_repository,
        "rendering_repository": rendering_repository,
        "llm_gateway": llm_gateway,
        "core_ingestion_service": core_ingestion_service,
        "domain_pack_registry": domain_pack_registry,
        "domain_pack_validator": domain_pack_validator,
        "domain_pack_compatibility_checker": domain_pack_compatibility_checker,
        "domain_pack_approval_service": domain_pack_approval_service,
        "retrieval_service": retrieval_service,
        "personal_query_orchestrator": personal_query_orchestrator,
        "personal_query_service": personal_query_service,
        "interpretation_family_registry": interpretation_family_registry,
        "interpretation_proposal_service": interpretation_proposal_service,
        "interpretation_publication_service": interpretation_publication_service,
        "interpretation_query_service": interpretation_query_service,
    }
