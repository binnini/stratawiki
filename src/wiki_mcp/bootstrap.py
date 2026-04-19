from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import psycopg

from wiki_mcp.adapters.llm import build_llm_gateway_router_from_env
from wiki_mcp.demo import build_demo_llm_gateway, build_demo_runtime
from wiki_mcp.services import (
    DefaultDomainPackApprovalService,
    DefaultDomainPackCompatibilityChecker,
    DefaultDomainPackValidator,
    DomainProposalIngestionGateway,
    InMemoryDomainPackRegistry,
    InterpretationProposalService,
    InterpretationPublicationService,
    InterpretationQueryService,
    InterpretationRenderingService,
    PersonalKnowledgeQueryService,
    PersonalQueryOrchestrator,
)
from wiki_mcp.services.core_ingestion import DefaultCoreIngestionService
from wiki_mcp.services.domain_pack_artifacts import load_and_register_domain_packs
from wiki_mcp.services.interpretation_families import (
    InterpretationFamilyRegistry,
    MarketTrendInterpretationBuilder,
)
from wiki_mcp.services.retrieval import CuratedRetrievalService
from wiki_mcp.storage.filesystem import (
    FileSystemDomainPackReviewAuditRepository,
    FileSystemRenderingRepository,
)
from wiki_mcp.storage.postgres.repositories import (
    PostgresFactRepository,
    PostgresInterpretationRepository,
    PostgresOutboxRepository,
    PostgresPersonalRepository,
    PostgresProfileContextRepository,
    PostgresSnapshotRepository,
)

DEFAULT_DATABASE_URL = "postgresql://stratawiki:stratawiki@localhost:5432/stratawiki"


@dataclass(slots=True)
class BootstrapContext:
    """Runtime bootstrap context for the current MVP slice."""

    connection: Any
    owns_connection: bool = False
    render_root: Path | None = None
    fact_repository: Any | None = None
    interpretation_repository: Any | None = None
    personal_repository: Any | None = None
    profile_context_repository: Any | None = None
    snapshot_repository: Any | None = None
    outbox_repository: Any | None = None
    rendering_repository: Any | None = None
    llm_gateway: Any | None = None
    core_ingestion_service: Any | None = None
    domain_pack_registry: Any | None = None
    domain_pack_validator: Any | None = None
    domain_pack_compatibility_checker: Any | None = None
    domain_pack_review_audit_repository: Any | None = None
    domain_pack_approval_service: Any | None = None
    domain_proposal_ingestion_service: Any | None = None
    domain_pack_load_reports: list[dict[str, Any]] | None = None
    retrieval_service: Any | None = None
    personal_query_orchestrator: Any | None = None
    personal_query_service: Any | None = None
    interpretation_family_registry: Any | None = None
    interpretation_proposal_service: Any | None = None
    interpretation_publication_service: Any | None = None
    interpretation_rendering_service: Any | None = None
    interpretation_query_service: Any | None = None

    def close(self) -> None:
        connection = self.connection
        if self.owns_connection and hasattr(connection, "closed") and not connection.closed:
            connection.close()


def resolve_database_url(database_url: str | None = None) -> str:
    return database_url or os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL


def connect_postgres(database_url: str | None = None) -> Any:
    import psycopg
    from psycopg.rows import dict_row

    resolved_url = resolve_database_url(database_url)
    psycopg_url = resolved_url.replace("+psycopg", "", 1)
    return psycopg.connect(psycopg_url, row_factory=dict_row)


def bootstrap_application(
    *,
    connection: Any | None = None,
    database_url: str | None = None,
    render_root: str | Path = "data",
    demo_mode: bool = False,
    seed_path: str | Path | None = None,
    domain_pack_paths: list[str | Path] | None = None,
    active_domain_pack_versions: dict[str, str] | None = None,
) -> BootstrapContext:
    if demo_mode:
        runtime = build_demo_runtime(render_root=render_root, seed_path=seed_path)
        domain_proposal_ingestion_service = DomainProposalIngestionGateway(
            domain_pack_registry=runtime["domain_pack_registry"],
            fact_repository=runtime["fact_repository"],
            core_ingestion_service=runtime["core_ingestion_service"],
        )
        domain_pack_load_reports = load_and_register_domain_packs(
            approval_service=runtime["domain_pack_approval_service"],
            domain_pack_paths=domain_pack_paths,
            active_domain_pack_versions=active_domain_pack_versions,
        )
        return BootstrapContext(
            connection=connection or object(),
            owns_connection=False,
            render_root=Path(render_root),
            fact_repository=runtime["fact_repository"],
            interpretation_repository=runtime["interpretation_repository"],
            personal_repository=runtime["personal_repository"],
            profile_context_repository=runtime["profile_context_repository"],
            snapshot_repository=runtime["snapshot_repository"],
            outbox_repository=runtime["outbox_repository"],
            rendering_repository=runtime["rendering_repository"],
            llm_gateway=runtime["llm_gateway"],
            core_ingestion_service=runtime["core_ingestion_service"],
            domain_pack_registry=runtime["domain_pack_registry"],
            domain_pack_validator=runtime["domain_pack_validator"],
            domain_pack_compatibility_checker=runtime["domain_pack_compatibility_checker"],
            domain_pack_review_audit_repository=runtime["domain_pack_review_audit_repository"],
            domain_pack_approval_service=runtime["domain_pack_approval_service"],
            domain_proposal_ingestion_service=domain_proposal_ingestion_service,
            domain_pack_load_reports=domain_pack_load_reports,
            retrieval_service=runtime["retrieval_service"],
            personal_query_orchestrator=runtime["personal_query_orchestrator"],
            personal_query_service=runtime["personal_query_service"],
            interpretation_family_registry=runtime["interpretation_family_registry"],
            interpretation_proposal_service=runtime["interpretation_proposal_service"],
            interpretation_publication_service=runtime["interpretation_publication_service"],
            interpretation_query_service=runtime["interpretation_query_service"],
        )

    owns_connection = connection is None
    resolved_connection = connection or connect_postgres(database_url)
    fact_repository = PostgresFactRepository(resolved_connection)
    interpretation_repository = PostgresInterpretationRepository(resolved_connection)
    personal_repository = PostgresPersonalRepository(resolved_connection)
    profile_context_repository = PostgresProfileContextRepository(resolved_connection)
    snapshot_repository = PostgresSnapshotRepository(resolved_connection)
    outbox_repository = PostgresOutboxRepository(resolved_connection)
    rendering_repository = FileSystemRenderingRepository(render_root)
    llm_gateway = build_llm_gateway_router_from_env(
        default_gateway=build_demo_llm_gateway(),
    )
    core_ingestion_service = DefaultCoreIngestionService(
        fact_repository=fact_repository,
        snapshot_repository=snapshot_repository,
        outbox_repository=outbox_repository,
    )
    domain_pack_registry = InMemoryDomainPackRegistry()
    domain_pack_validator = DefaultDomainPackValidator()
    domain_pack_compatibility_checker = DefaultDomainPackCompatibilityChecker()
    domain_pack_review_audit_repository = FileSystemDomainPackReviewAuditRepository(
        Path(render_root) / "domain-pack-reviews.jsonl"
    )
    domain_pack_approval_service = DefaultDomainPackApprovalService(
        domain_pack_registry=domain_pack_registry,
        validator=domain_pack_validator,
        compatibility_checker=domain_pack_compatibility_checker,
        review_audit_repository=domain_pack_review_audit_repository,
    )
    domain_proposal_ingestion_service = DomainProposalIngestionGateway(
        domain_pack_registry=domain_pack_registry,
        fact_repository=fact_repository,
        core_ingestion_service=core_ingestion_service,
    )
    domain_pack_load_reports = load_and_register_domain_packs(
        approval_service=domain_pack_approval_service,
        domain_pack_paths=domain_pack_paths,
        active_domain_pack_versions=active_domain_pack_versions,
    )
    retrieval_service = CuratedRetrievalService(
        fact_repository=fact_repository,
        interpretation_repository=interpretation_repository,
        personal_repository=personal_repository,
        rendering_repository=rendering_repository,
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
    interpretation_rendering_service = InterpretationRenderingService(
        interpretation_repository=interpretation_repository,
        rendering_repository=rendering_repository,
    )
    interpretation_publication_service = InterpretationPublicationService(
        proposal_service=interpretation_proposal_service,
        interpretation_repository=interpretation_repository,
        snapshot_repository=snapshot_repository,
        outbox_repository=outbox_repository,
        interpretation_rendering_service=interpretation_rendering_service,
    )
    interpretation_query_service = InterpretationQueryService(
        interpretation_repository=interpretation_repository,
    )
    return BootstrapContext(
        connection=resolved_connection,
        owns_connection=owns_connection,
        render_root=Path(render_root),
        fact_repository=fact_repository,
        interpretation_repository=interpretation_repository,
        personal_repository=personal_repository,
        profile_context_repository=profile_context_repository,
        snapshot_repository=snapshot_repository,
        outbox_repository=outbox_repository,
        rendering_repository=rendering_repository,
        llm_gateway=llm_gateway,
        core_ingestion_service=core_ingestion_service,
        domain_pack_registry=domain_pack_registry,
        domain_pack_validator=domain_pack_validator,
        domain_pack_compatibility_checker=domain_pack_compatibility_checker,
        domain_pack_review_audit_repository=domain_pack_review_audit_repository,
        domain_pack_approval_service=domain_pack_approval_service,
        domain_proposal_ingestion_service=domain_proposal_ingestion_service,
        domain_pack_load_reports=domain_pack_load_reports,
        retrieval_service=retrieval_service,
        personal_query_orchestrator=personal_query_orchestrator,
        personal_query_service=personal_query_service,
        interpretation_family_registry=interpretation_family_registry,
        interpretation_proposal_service=interpretation_proposal_service,
        interpretation_publication_service=interpretation_publication_service,
        interpretation_rendering_service=interpretation_rendering_service,
        interpretation_query_service=interpretation_query_service,
    )
