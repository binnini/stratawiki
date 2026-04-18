from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wiki_mcp.adapters.llm import DeterministicLLMGateway
from wiki_mcp.server import StrataWikiServer
from wiki_mcp.services import (
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


class FakeFactRepository:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {
            "fact:job:1": {
                "id": "fact:job:1",
                "domain": "recruiting",
                "entity_type": "job_posting",
                "canonical_key": "job:1",
                "scope": "shared",
                "schema_version": "fact.v1",
                "attributes": {
                    "title": "Backend Engineer",
                    "summary": "Production AI systems experience preferred.",
                },
                "fact_snapshot_id": "fact_snap:seed",
                "provenance": {"source_ids": ["job:1"]},
            }
        }
        self.relations: list[dict[str, Any]] = []

    def get_by_ids(self, ids: list[str], scope_ref: dict[str, Any]) -> list[dict[str, Any]]:
        return [dict(self.records[record_id]) for record_id in ids if record_id in self.records]

    def get_by_canonical_keys(
        self,
        canonical_keys: list[str],
        scope_ref: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return [
            dict(record)
            for record in self.records.values()
            if record["canonical_key"] in canonical_keys
        ]

    def search_for_retrieval(self, **_: Any) -> list[dict[str, Any]]:
        return [dict(self.records["fact:job:1"])]

    def write_facts(
        self,
        records: list[dict[str, Any]],
        relations: list[dict[str, Any]],
        *,
        fact_snapshot_id: str,
    ) -> dict[str, Any]:
        for record in records:
            persisted = dict(record)
            persisted["fact_snapshot_id"] = fact_snapshot_id
            self.records[persisted["id"]] = persisted
        self.relations.extend(relations)
        return {
            "facts_created": len(records),
            "facts_updated": 0,
            "relations_created": len(relations),
            "affected_fact_ids": [record["id"] for record in records],
        }


class FakeInterpretationRepository:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    def get_by_ids(self, ids: list[str], scope_ref: dict[str, Any]) -> list[dict[str, Any]]:
        return [dict(self.records[record_id]) for record_id in ids if record_id in self.records]

    def list_records(
        self,
        *,
        domain: str,
        scope_ref: dict[str, Any],
        family: str | None = None,
        kind: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
        statuses: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        for record in self.records.values():
            if record["domain"] != domain:
                continue
            if family is not None and record.get("family") != family:
                continue
            if kind is not None and record.get("kind") != kind:
                continue
            if subject_type is not None and record.get("subject_type") != subject_type:
                continue
            if subject_id is not None and record.get("subject_id") != subject_id:
                continue
            if statuses and record.get("status") not in statuses:
                continue
            matches.append(dict(record))
        return matches[:limit]

    def search_for_retrieval(self, **_: Any) -> list[dict[str, Any]]:
        return [
            dict(record)
            for record in self.records.values()
            if record.get("status") in {"published", "stale"}
        ]

    def save_records(
        self,
        records: list[dict[str, Any]],
        snapshot_ref: dict[str, Any],
    ) -> list[str]:
        for record in records:
            persisted = dict(record)
            persisted.pop("interpretation_snapshot_id", None)
            self.records[persisted["id"]] = persisted
        return [record["id"] for record in records]


class FakePersonalRepository:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {
            "personal:1": {
                "id": "personal:1",
                "domain": "recruiting",
                "kind": "plan",
                "title": "Existing plan",
                "summary": "Anchored to shared context",
                "scope_ref": {"scope": "user", "tenant_id": "tenant-1", "user_id": "user-1"},
                "snapshot_ref": {
                    "fact_snapshot_id": "fact_snap:seed",
                    "interpretation_snapshot_id": "interp_snap:seed",
                    "profile_version": "profile:v1",
                },
                "profile_version": "profile:v1",
                "body_path": "wiki/users/user-1/plans/existing.md",
                "status": "active",
                "schema_version": "personal.v1",
                "provenance": {"generated_by": {"kind": "user"}},
                "body": {
                    "anchors": [
                        {"layer": "interpretation", "id": "interp:published:1"},
                        {"layer": "fact", "id": "fact:job:1"},
                    ]
                },
            }
        }
        self.saved_records: list[dict[str, Any]] = []

    def get_by_ids(self, ids: list[str], scope_ref: dict[str, Any]) -> list[dict[str, Any]]:
        return [dict(self.records[record_id]) for record_id in ids if record_id in self.records]

    def search_for_retrieval(self, **_: Any) -> list[dict[str, Any]]:
        return [dict(self.records["personal:1"])]

    def save_record(self, record: dict[str, Any]) -> str:
        self.saved_records.append(dict(record))
        self.records[record["id"]] = dict(record)
        return str(record["id"])


class FakeProfileContextRepository:
    def get_profile_context(self, domain: str, tenant_id: str, user_id: str) -> dict[str, Any]:
        return {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "domain": domain,
            "profile_version": "profile:v1",
            "goals": ["find backend roles"],
            "preferences": {"location": "jp"},
            "attributes": {"level": "mid"},
        }


class FakeSnapshotRepository:
    def __init__(self) -> None:
        self.published: list[tuple[str, str, dict[str, Any]]] = []
        self.status_by_layer: dict[str, dict[str, Any]] = {
            "fact": {
                "layer": "fact",
                "domain": "recruiting",
                "current_snapshot_id": "fact_snap:seed",
                "fact_snapshot_id": "fact_snap:seed",
                "published_at": "2026-04-18T00:00:00Z",
            },
            "interpretation": {
                "layer": "interpretation",
                "domain": "recruiting",
                "current_snapshot_id": "interp_snap:seed",
                "fact_snapshot_id": "fact_snap:seed",
                "interpretation_snapshot_id": "interp_snap:seed",
                "published_at": "2026-04-18T00:10:00Z",
            },
        }

    def publish_snapshot(self, layer: str, domain: str, snapshot_ref: dict[str, Any]) -> str:
        self.published.append((layer, domain, dict(snapshot_ref)))
        snapshot_id = snapshot_ref.get("interpretation_snapshot_id") or snapshot_ref["fact_snapshot_id"]
        self.status_by_layer[layer] = {
            "layer": layer,
            "domain": domain,
            "current_snapshot_id": snapshot_id,
            "fact_snapshot_id": snapshot_ref["fact_snapshot_id"],
            **(
                {"interpretation_snapshot_id": snapshot_ref["interpretation_snapshot_id"]}
                if "interpretation_snapshot_id" in snapshot_ref
                else {}
            ),
            **({"profile_version": snapshot_ref["profile_version"]} if "profile_version" in snapshot_ref else {}),
            "published_at": "2026-04-18T01:00:00Z",
        }
        return str(snapshot_id)

    def get_snapshot_status(self, *, layer: str | None = None, domain: str) -> dict[str, Any] | None:
        if layer is None:
            return dict(self.status_by_layer["fact"])
        return dict(self.status_by_layer.get(layer) or {})


class FakeOutboxRepository:
    def append_events(self, events: list[dict[str, Any]]) -> list[str]:
        return [f"evt-{index}" for index, _ in enumerate(events, start=1)]


@dataclass(slots=True)
class FakeBootstrap:
    connection: Any
    fact_repository: Any
    interpretation_repository: Any
    personal_repository: Any
    profile_context_repository: Any
    snapshot_repository: Any
    outbox_repository: Any
    rendering_repository: Any
    core_ingestion_service: Any
    retrieval_service: Any
    personal_query_orchestrator: Any
    personal_query_service: Any
    interpretation_family_registry: Any
    interpretation_proposal_service: Any
    interpretation_publication_service: Any
    interpretation_query_service: Any

    def close(self) -> None:
        return None


def build_fake_server(tmp_path: Path) -> StrataWikiServer:
    fact_repository = FakeFactRepository()
    interpretation_repository = FakeInterpretationRepository()
    interpretation_repository.records["interp:published:1"] = {
        "id": "interp:published:1",
        "layer": "interpretation",
        "domain": "recruiting",
        "family": "market_trend",
        "kind": "market_trend",
        "subject_type": "market_segment",
        "subject_id": "backend-japan-midlevel",
        "scope_ref": {"scope": "shared"},
        "schema_version": "interpretation.v2",
        "status": "published",
        "confidence": 0.82,
        "fact_snapshot_id": "fact_snap:seed",
        "computed_at": "2026-04-18T00:00:00Z",
        "expires_at": "2026-04-19T00:00:00Z",
        "title": "Demand is rising",
        "claim": "Production AI demand is rising.",
        "summary": "Demand is rising for backend roles with production AI exposure.",
        "body": {"signals": ["llm"], "observations": [], "counterpoints": []},
        "evidence": [{"fact_id": "fact:job:1", "weight": 1.0, "role": "primary"}],
        "provenance": {"generated_by": {"kind": "llm"}},
        "render_hints": {"page_family": "market_trend"},
    }
    personal_repository = FakePersonalRepository()
    profile_context_repository = FakeProfileContextRepository()
    snapshot_repository = FakeSnapshotRepository()
    outbox_repository = FakeOutboxRepository()
    rendering_repository = FileSystemRenderingRepository(tmp_path)
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
    orchestrator = PersonalQueryOrchestrator(retrieval_service=retrieval_service)
    llm_gateway = DeterministicLLMGateway(
        provider="mock",
        model="mock-model-v1",
        default_text="## Strategy\n\nFocus on backend roles that mention production AI systems.",
        default_structured_output={
            "kind": "market_trend",
            "title": "Production AI demand is rising",
            "claim": "Production AI experience is increasingly requested.",
            "summary": "Backend hiring is tilting toward production AI delivery.",
            "body": {
                "headline": "Demand is rising",
                "thesis": "Employers increasingly ask for production AI experience.",
                "signals": ["Backend roles mention production AI systems."],
                "observations": ["Signals cluster in backend roles."],
                "counterpoints": [],
            },
        },
    )
    personal_query_service = PersonalKnowledgeQueryService(
        orchestrator=orchestrator,
        llm_gateway=llm_gateway,
        personal_repository=personal_repository,
        rendering_repository=rendering_repository,
    )
    family_registry = InterpretationFamilyRegistry(
        [MarketTrendInterpretationBuilder(llm_gateway=llm_gateway)]
    )
    proposal_service = InterpretationProposalService(
        family_registry=family_registry,
        interpretation_repository=interpretation_repository,
        fact_repository=fact_repository,
    )
    publication_service = InterpretationPublicationService(
        proposal_service=proposal_service,
        interpretation_repository=interpretation_repository,
        snapshot_repository=snapshot_repository,
    )
    query_service = InterpretationQueryService(
        interpretation_repository=interpretation_repository,
    )
    bootstrap = FakeBootstrap(
        connection=object(),
        fact_repository=fact_repository,
        interpretation_repository=interpretation_repository,
        personal_repository=personal_repository,
        profile_context_repository=profile_context_repository,
        snapshot_repository=snapshot_repository,
        outbox_repository=outbox_repository,
        rendering_repository=rendering_repository,
        core_ingestion_service=core_ingestion_service,
        retrieval_service=retrieval_service,
        personal_query_orchestrator=orchestrator,
        personal_query_service=personal_query_service,
        interpretation_family_registry=family_registry,
        interpretation_proposal_service=proposal_service,
        interpretation_publication_service=publication_service,
        interpretation_query_service=query_service,
    )
    return StrataWikiServer(bootstrap=bootstrap)  # type: ignore[arg-type]


def test_server_lists_mvp_tools(tmp_path: Path) -> None:
    server = build_fake_server(tmp_path)

    tools = server.list_tools()

    assert [tool.name for tool in tools] == [
        "ingest_fact_batch",
        "get_fact_record",
        "build_interpretation_snapshot",
        "get_interpretation_record",
        "query_personal_knowledge",
        "get_snapshot_status",
    ]


def test_server_fact_and_personal_tools_work_on_happy_path(tmp_path: Path) -> None:
    server = build_fake_server(tmp_path)

    fact = server.call_tool(
        "get_fact_record",
        {"domain": "recruiting", "fact_id": "fact:job:1"},
    )
    answer = server.call_tool(
        "query_personal_knowledge",
        {
            "domain": "recruiting",
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "question": "What should I focus on next?",
            "profile_version": "profile:v1",
            "model_profile": "balanced_default",
            "save": True,
        },
    )

    assert fact["status"] == "ok"
    assert fact["record"]["id"] == "fact:job:1"
    assert answer["status"] == "ok"
    assert answer["interpretation_records_used"] == ["interp:published:1"]
    assert answer["fact_records_used"] == ["fact:job:1"]
    assert answer["provenance"]["profile_version"] == "profile:v1"


def test_server_builds_interpretation_and_reads_snapshot_status(tmp_path: Path) -> None:
    server = build_fake_server(tmp_path)

    result = server.call_tool(
        "build_interpretation_snapshot",
        {
            "domain": "recruiting",
            "partition": {"family": "market_trends", "segment": "backend-japan-midlevel"},
            "fact_ids": ["fact:job:1"],
            "fact_snapshot": "fact_snap:seed",
            "model_profile": "balanced_default",
            "publish": True,
        },
    )
    snapshot = server.call_tool(
        "get_snapshot_status",
        {"domain": "recruiting", "partition": {"family": "market_trends"}},
    )

    assert result["status"] == "ok"
    assert result["records_created"] == 1
    assert result["interpretation_snapshot"].startswith("interp_snap:recruiting:market_trend:")
    assert snapshot["status"] == "ok"
    assert snapshot["interpretation_snapshot"] == result["interpretation_snapshot"]
