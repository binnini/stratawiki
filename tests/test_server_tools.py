from __future__ import annotations

import json
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from wiki_mcp.adapters.llm import DeterministicLLMGateway
from wiki_mcp.cli import run_cli
from wiki_mcp.server import StrataWikiServer
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
            self.records[record["id"]] = dict(record)
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

    def search_by_anchors(
        self,
        *,
        domain: str,
        scope_ref: dict[str, Any],
        interpretation_ids: list[str],
        fact_ids: list[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        return []

    def save_record(self, record: dict[str, Any]) -> str:
        self.saved_records.append(dict(record))
        self.records[record["id"]] = dict(record)
        return str(record["id"])


class FakeProfileContextRepository:
    def __init__(self, profiles: list[dict[str, Any]] | None = None) -> None:
        self.profiles = {
            (profile["domain"], profile["tenant_id"], profile["user_id"]): dict(profile)
            for profile in (profiles or [])
        }

    def get_profile_context(self, domain: str, tenant_id: str, user_id: str) -> dict[str, Any]:
        key = (domain, tenant_id, user_id)
        if key not in self.profiles:
            raise KeyError(
                f"No profile context found for domain={domain!r}, tenant_id={tenant_id!r}, user_id={user_id!r}"
            )
        return dict(self.profiles[key])

    def save_profile_context(self, profile: dict[str, Any]) -> None:
        key = (profile["domain"], profile["tenant_id"], profile["user_id"])
        self.profiles[key] = dict(profile)


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
            return {
                "domain": domain,
                "layers": {
                    status_layer: dict(status)
                    for status_layer, status in self.status_by_layer.items()
                },
            }
        return dict(self.status_by_layer.get(layer) or {})


class FakeOutboxRepository:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def append_events(self, events: list[dict[str, Any]]) -> list[str]:
        stored_ids: list[str] = []
        for event in events:
            event_id = f"evt-{len(self.events) + 1}"
            stored = {
                "id": event_id,
                "event_type": event["event_type"],
                "aggregate_layer": event["aggregate_layer"],
                "aggregate_id": event["aggregate_id"],
                "payload": dict(event["payload"]),
                "status": "pending",
                "attempt_count": 0,
                "available_at": "2026-04-18T00:00:00Z",
                "claimed_at": None,
                "processed_at": None,
                "last_error": None,
                "idempotency_key": event.get("idempotency_key"),
            }
            self.events.append(stored)
            stored_ids.append(event_id)
        return stored_ids

    def get_event(self, event_id: str) -> dict[str, Any]:
        for stored in self.events:
            if stored["id"] == event_id:
                return dict(stored)
        raise KeyError(event_id)

    def claim_pending(
        self,
        *,
        limit: int,
        event_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        claimed: list[dict[str, Any]] = []
        for stored in self.events:
            if len(claimed) >= limit:
                break
            if stored["status"] != "pending":
                continue
            if event_types and stored["event_type"] not in event_types:
                continue
            stored["status"] = "claimed"
            stored["claimed_at"] = "2026-04-18T00:05:00Z"
            stored["attempt_count"] += 1
            claimed.append(dict(stored))
        return claimed

    def mark_processed(self, event_id: str) -> None:
        for stored in self.events:
            if stored["id"] == event_id:
                stored["status"] = "processed"
                stored["processed_at"] = "2026-04-18T00:10:00Z"
                stored["last_error"] = None
                return
        raise KeyError(event_id)

    def mark_failed(
        self,
        event_id: str,
        error_message: str,
        *,
        retryable: bool = True,
    ) -> None:
        for stored in self.events:
            if stored["id"] == event_id:
                stored["status"] = "pending" if retryable else "failed"
                stored["last_error"] = error_message
                return
        raise KeyError(event_id)


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
    domain_pack_registry: Any
    domain_pack_validator: Any
    domain_pack_compatibility_checker: Any
    domain_pack_review_audit_repository: Any
    domain_pack_approval_service: Any
    domain_proposal_ingestion_service: Any
    retrieval_service: Any
    personal_query_orchestrator: Any
    personal_query_service: Any
    interpretation_family_registry: Any
    interpretation_proposal_service: Any
    interpretation_publication_service: Any
    interpretation_query_service: Any

    def close(self) -> None:
        return None


def _external_pack() -> dict[str, Any]:
    return {
        "manifest": {
            "domain": "recruiting",
            "packVersion": "2026-04-18",
            "status": "active",
            "compatibility": {"minStrataWikiVersion": "0.2.0"},
            "owner": {"system": "jobs-wiki"},
        },
        "entityTypes": {
            "job_posting": {
                "name": "job_posting",
                "attributes": {
                    "title": {"type": "string"},
                    "summary": {"type": "markdown", "nullable": True},
                },
                "requiredAttributes": ["title"],
                "identity": {
                    "mode": "hint_priority",
                    "strategies": [{"hint": "source_id", "prefix": "job_posting"}],
                    "fallback": "reject",
                },
                "mergePolicy": {
                    "mode": "upsert",
                    "conflictStrategy": "prefer_newer_source",
                },
            },
            "company": {
                "name": "company",
                "attributes": {
                    "name": {"type": "string"},
                    "normalized_name": {"type": "string", "nullable": True},
                },
                "requiredAttributes": ["name"],
                "identity": {
                    "mode": "hint_priority",
                    "strategies": [
                        {
                            "hint": "normalized_name",
                            "prefix": "company",
                            "normalization": ["trim", "lowercase", "slugify"],
                        }
                    ],
                    "fallback": "reject",
                },
                "mergePolicy": {
                    "mode": "upsert",
                    "conflictStrategy": "manual_review",
                },
            },
        },
        "relationTypes": {
            "posted_by": {
                "name": "posted_by",
                "fromEntityTypes": ["job_posting"],
                "toEntityTypes": ["company"],
                "evidencePolicy": "required",
            }
        },
    }


def _external_batch() -> dict[str, Any]:
    return {
        "domain": "recruiting",
        "packVersion": "2026-04-18",
        "producer": "jobs-wiki.tests",
        "facts": [
            {
                "proposalId": "job_posting:worknet:EMP-2",
                "domain": "recruiting",
                "entityType": "job_posting",
                "attributes": {
                    "title": "Platform Backend Engineer",
                    "summary": "Production AI platform delivery",
                },
                "identityHints": {"source_id": "EMP-2"},
                "evidence": [
                    {
                        "connector": "worknet.open_recruitment",
                        "sourceId": "EMP-2",
                        "pointer": "posting",
                    }
                ],
            },
            {
                "proposalId": "company:name:jobswiki",
                "domain": "recruiting",
                "entityType": "company",
                "attributes": {
                    "name": "JobsWiki",
                    "normalized_name": "jobswiki",
                },
                "identityHints": {"normalized_name": "jobswiki"},
                "evidence": [
                    {
                        "connector": "worknet.open_recruitment",
                        "sourceId": "EMP-2",
                        "pointer": "company",
                    }
                ],
            },
        ],
        "relations": [
            {
                "proposalId": "relation:posted_by:job_posting:worknet:EMP-2:company:name:jobswiki",
                "domain": "recruiting",
                "relationType": "posted_by",
                "fromRef": {"proposalId": "job_posting:worknet:EMP-2"},
                "toRef": {"proposalId": "company:name:jobswiki"},
                "evidence": [
                    {
                        "connector": "worknet.open_recruitment",
                        "sourceId": "EMP-2",
                        "pointer": "company",
                    }
                ],
            }
        ],
    }


def build_fake_server(tmp_path: Path, *, profile_seeded: bool = True) -> StrataWikiServer:
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
        "interpretation_snapshot_id": "interp_snap:seed",
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
    profile_context_repository = FakeProfileContextRepository(
        [
            {
                "user_id": "user-1",
                "tenant_id": "tenant-1",
                "domain": "recruiting",
                "profile_version": "profile:v1",
                "goals": ["find backend roles"],
                "preferences": {"location": "jp"},
                "attributes": {"level": "mid"},
            }
        ]
        if profile_seeded
        else []
    )
    snapshot_repository = FakeSnapshotRepository()
    outbox_repository = FakeOutboxRepository()
    rendering_repository = FileSystemRenderingRepository(tmp_path)
    core_ingestion_service = DefaultCoreIngestionService(
        fact_repository=fact_repository,
        snapshot_repository=snapshot_repository,
        outbox_repository=outbox_repository,
    )
    domain_pack_registry = InMemoryDomainPackRegistry()
    domain_pack_validator = DefaultDomainPackValidator()
    domain_pack_compatibility_checker = DefaultDomainPackCompatibilityChecker()
    domain_pack_approval_service = DefaultDomainPackApprovalService(
        domain_pack_registry=domain_pack_registry,
        validator=domain_pack_validator,
        compatibility_checker=domain_pack_compatibility_checker,
    )
    report = domain_pack_approval_service.register_pack(_external_pack(), activate=True)
    assert report["ok"] is True
    domain_proposal_ingestion_service = DomainProposalIngestionGateway(
        domain_pack_registry=domain_pack_registry,
        fact_repository=fact_repository,
        core_ingestion_service=core_ingestion_service,
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
    interpretation_rendering_service = InterpretationRenderingService(
        interpretation_repository=interpretation_repository,
        rendering_repository=rendering_repository,
    )
    publication_service = InterpretationPublicationService(
        proposal_service=proposal_service,
        interpretation_repository=interpretation_repository,
        snapshot_repository=snapshot_repository,
        outbox_repository=outbox_repository,
        interpretation_rendering_service=interpretation_rendering_service,
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
        domain_pack_registry=domain_pack_registry,
        domain_pack_validator=domain_pack_validator,
        domain_pack_compatibility_checker=domain_pack_compatibility_checker,
        domain_pack_review_audit_repository=None,
        domain_pack_approval_service=domain_pack_approval_service,
        domain_proposal_ingestion_service=domain_proposal_ingestion_service,
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
        "validate_domain_proposal_batch",
        "ingest_domain_proposal_batch",
        "get_fact_record",
        "build_interpretation_snapshot",
        "get_interpretation_record",
        "list_interpretation_proposals",
        "validate_interpretation_proposal",
        "publish_interpretation_partition",
        "get_interpretation_proposal_status",
        "upsert_profile_context",
        "query_personal_knowledge",
        "get_snapshot_status",
        "get_cache_status",
        "get_job_status",
        "explain_result",
    ]
    tool_by_name = {tool.name: tool for tool in tools}
    assert tool_by_name["ingest_fact_batch"].contract_status == "legacy_transition"
    assert tool_by_name["ingest_fact_batch"].recommended_for_external_clients is False
    assert tool_by_name["validate_domain_proposal_batch"].contract_status == "preferred_external_write"
    assert tool_by_name["validate_domain_proposal_batch"].recommended_for_external_clients is True
    assert tool_by_name["ingest_domain_proposal_batch"].contract_status == "preferred_external_write"
    assert tool_by_name["ingest_domain_proposal_batch"].recommended_for_external_clients is True


def test_server_fact_and_personal_tools_work_on_happy_path(tmp_path: Path) -> None:
    server = build_fake_server(tmp_path)

    fact = server.call_tool(
        "get_fact_record",
        {"domain": "recruiting", "fact_id": "fact:job:1"},
    )
    interpretation = server.call_tool(
        "get_interpretation_record",
        {"domain": "recruiting", "interpretation_id": "interp:published:1"},
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
    assert interpretation["status"] == "ok"
    assert interpretation["record"]["interpretation_snapshot_id"] == "interp_snap:seed"
    assert answer["status"] == "ok"
    assert answer["interpretation_records_used"] == ["interp:published:1"]
    assert answer["fact_records_used"] == ["fact:job:1"]
    assert answer["provenance"]["profile_version"] == "profile:v1"


def test_server_profile_context_write_unblocks_personal_query(tmp_path: Path) -> None:
    server = build_fake_server(tmp_path, profile_seeded=False)

    try:
        server.call_tool(
            "query_personal_knowledge",
            {
                "domain": "recruiting",
                "tenant_id": "tenant-1",
                "user_id": "user-1",
                "question": "What should I focus on next?",
                "profile_version": "profile:v1",
                "model_profile": "balanced_default",
                "save": False,
            },
        )
    except KeyError as exc:
        assert "No profile context found" in str(exc)
    else:
        raise AssertionError("Expected query_personal_knowledge to fail before profile provisioning.")

    upsert = server.call_tool(
        "upsert_profile_context",
        {
            "domain": "recruiting",
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "profile_version": "profile:v1",
            "goals": ["find backend roles"],
            "preferences": {"location": "jp"},
            "attributes": {"level": "mid"},
        },
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
            "save": False,
        },
    )

    assert upsert["status"] == "ok"
    assert upsert["profile_context"]["profile_version"] == "profile:v1"
    assert answer["status"] == "ok"
    assert answer["provenance"]["profile_version"] == "profile:v1"


def test_server_personal_query_rejects_profile_version_mismatch_after_write(tmp_path: Path) -> None:
    server = build_fake_server(tmp_path, profile_seeded=False)
    server.call_tool(
        "upsert_profile_context",
        {
            "domain": "recruiting",
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "profile_version": "profile:v2",
            "goals": ["find backend roles"],
            "preferences": {"location": "jp"},
            "attributes": {"level": "mid"},
        },
    )

    try:
        server.call_tool(
            "query_personal_knowledge",
            {
                "domain": "recruiting",
                "tenant_id": "tenant-1",
                "user_id": "user-1",
                "question": "What should I focus on next?",
                "profile_version": "profile:v1",
                "model_profile": "balanced_default",
                "save": False,
            },
        )
    except ValueError as exc:
        assert str(exc) == "Requested profile_version does not match the current stored profile context."
    else:
        raise AssertionError("Expected query_personal_knowledge to reject a mismatched profile_version.")


def test_server_profile_context_write_rejects_invalid_shapes(tmp_path: Path) -> None:
    server = build_fake_server(tmp_path, profile_seeded=False)

    try:
        server.call_tool(
            "upsert_profile_context",
            {
                "domain": "recruiting",
                "tenant_id": "tenant-1",
                "user_id": "user-1",
                "profile_version": "profile:v1",
                "goals": "find backend roles",
                "preferences": {"location": "jp"},
                "attributes": {"level": "mid"},
            },
        )
    except ValueError as exc:
        assert str(exc) == "Profile context goals must be a list of strings."
    else:
        raise AssertionError("Expected upsert_profile_context to reject invalid goal shapes.")


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
    domain_snapshot = server.call_tool("get_snapshot_status", {"domain": "recruiting"})

    assert result["status"] == "ok"
    assert result["records_created"] == 1
    assert result["interpretation_snapshot"].startswith("interp_snap:recruiting:market_trend:")
    assert snapshot["status"] == "ok"
    assert snapshot["interpretation_snapshot"] == result["interpretation_snapshot"]
    assert domain_snapshot["status"] == "ok"
    assert domain_snapshot["fact_snapshot"] == "fact_snap:seed"
    assert domain_snapshot["interpretation_snapshot"] == result["interpretation_snapshot"]
    assert set(domain_snapshot["layers"]) == {"fact", "interpretation"}
    rendered_page = (
        tmp_path / "wiki" / "shared" / "interpretations" / "market_trend" / "backend-japan-midlevel.md"
    )
    assert rendered_page.exists()
    assert f"Interpretation Snapshot: `{result['interpretation_snapshot']}`" in rendered_page.read_text(
        encoding="utf-8"
    )


def test_server_interpretation_lifecycle_tools_cover_proposal_validation_and_publish(
    tmp_path: Path,
) -> None:
    server = build_fake_server(tmp_path)

    build = server.call_tool(
        "build_interpretation_snapshot",
        {
            "domain": "recruiting",
            "partition": {"family": "market_trends", "segment": "backend-japan-midlevel"},
            "fact_ids": ["fact:job:1"],
            "fact_snapshot": "fact_snap:seed",
            "model_profile": "balanced_default",
            "publish": False,
        },
    )
    proposals = server.call_tool(
        "list_interpretation_proposals",
        {
            "domain": "recruiting",
            "partition": {"family": "market_trends", "segment": "backend-japan-midlevel"},
        },
    )

    assert build["status"] == "ok"
    assert build["records_created"] == 1
    assert proposals["status"] == "ok"
    assert len(proposals["items"]) == 1
    proposal_id = proposals["items"][0]["proposal_id"]
    assert proposals["items"][0]["lifecycle_state"] == "proposed"
    assert proposals["items"][0]["review_state"] == "pending_validation"

    validated = server.call_tool(
        "validate_interpretation_proposal",
        {"domain": "recruiting", "proposal_id": proposal_id},
    )
    validated_status = server.call_tool(
        "get_interpretation_proposal_status",
        {"domain": "recruiting", "proposal_id": proposal_id},
    )
    publish = server.call_tool(
        "publish_interpretation_partition",
        {
            "domain": "recruiting",
            "partition": {"family": "market_trends", "segment": "backend-japan-midlevel"},
            "source_state": "validated",
        },
    )
    published_status = server.call_tool(
        "get_interpretation_proposal_status",
        {"domain": "recruiting", "proposal_id": proposal_id},
    )

    assert validated == {
        "status": "ok",
        "proposal_id": proposal_id,
        "ok": True,
        "validation_state": "validated",
        "review_state": "ready_to_publish",
        "errors": [],
    }
    assert validated_status["lifecycle_state"] == "validated"
    assert validated_status["review_state"] == "ready_to_publish"
    assert publish["status"] == "ok"
    assert publish["published_records"] == 1
    assert publish["published_proposal_ids"] == [proposal_id]
    assert publish["interpretation_snapshot"].startswith(
        "interp_snap:recruiting:market_trend:backend-japan-midlevel:"
    )
    assert published_status["lifecycle_state"] == "published"
    assert published_status["review_state"] == "published"
    assert published_status["interpretation_snapshot"] == publish["interpretation_snapshot"]


def test_server_publish_interpretation_partition_reports_missing_candidates(
    tmp_path: Path,
) -> None:
    server = build_fake_server(tmp_path)

    try:
        server.call_tool(
            "publish_interpretation_partition",
            {
                "domain": "recruiting",
                "partition": {"family": "market_trends", "segment": "backend-japan-midlevel"},
                "source_state": "validated",
            },
        )
    except KeyError as exc:
        assert "No interpretation proposals matched" in str(exc)
    else:
        raise AssertionError(
            "Expected publish_interpretation_partition to reject an empty validated partition."
        )


def test_server_get_cache_status_marks_personal_record_fresh(tmp_path: Path) -> None:
    server = build_fake_server(tmp_path)

    status = server.call_tool(
        "get_cache_status",
        {
            "domain": "recruiting",
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "record_id": "personal:1",
        },
    )

    assert status == {
        "status": "ok",
        "record_id": "personal:1",
        "cache_state": "fresh",
        "reason": "match",
        "current_snapshots": {
            "fact_snapshot": "fact_snap:seed",
            "interpretation_snapshot": "interp_snap:seed",
            "profile_version": "profile:v1",
        },
        "record_snapshots": {
            "fact_snapshot": "fact_snap:seed",
            "interpretation_snapshot": "interp_snap:seed",
            "profile_version": "profile:v1",
        },
    }


def test_server_get_cache_status_marks_snapshot_drift_stale(tmp_path: Path) -> None:
    server = build_fake_server(tmp_path)
    server.bootstrap.snapshot_repository.status_by_layer["interpretation"] = {
        "layer": "interpretation",
        "domain": "recruiting",
        "current_snapshot_id": "interp_snap:new",
        "fact_snapshot_id": "fact_snap:seed",
        "interpretation_snapshot_id": "interp_snap:new",
        "published_at": "2026-04-18T00:20:00Z",
    }

    status = server.call_tool(
        "get_cache_status",
        {
            "domain": "recruiting",
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "record_id": "personal:1",
        },
    )

    assert status["cache_state"] == "stale"
    assert status["reason"] == "interpretation_snapshot_changed"
    assert status["current_snapshots"]["interpretation_snapshot"] == "interp_snap:new"


def test_server_get_cache_status_marks_profile_drift_invalid(tmp_path: Path) -> None:
    server = build_fake_server(tmp_path)
    server.bootstrap.profile_context_repository.save_profile_context(
        {
            "domain": "recruiting",
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "profile_version": "profile:v2",
            "goals": ["switch into backend platform roles"],
            "preferences": {"location": "tokyo"},
            "attributes": {"level": "mid"},
        }
    )

    status = server.call_tool(
        "get_cache_status",
        {
            "domain": "recruiting",
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "record_id": "personal:1",
        },
    )

    assert status["cache_state"] == "invalid"
    assert status["reason"] == "profile_version_changed"
    assert status["current_snapshots"]["profile_version"] == "profile:v2"


def test_server_get_cache_status_marks_missing_record(tmp_path: Path) -> None:
    server = build_fake_server(tmp_path)

    status = server.call_tool(
        "get_cache_status",
        {
            "domain": "recruiting",
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "record_id": "personal:missing",
        },
    )

    assert status == {
        "status": "ok",
        "record_id": "personal:missing",
        "cache_state": "missing",
        "reason": "record_not_found",
        "current_snapshots": {
            "fact_snapshot": "fact_snap:seed",
            "interpretation_snapshot": "interp_snap:seed",
            "profile_version": "profile:v1",
        },
    }


def test_server_get_job_status_tracks_background_job_lifecycle(tmp_path: Path) -> None:
    server = build_fake_server(tmp_path)

    queued = server.call_tool(
        "build_interpretation_snapshot",
        {
            "domain": "recruiting",
            "partition": {"family": "market_trends", "segment": "backend-japan-midlevel"},
            "fact_ids": ["fact:job:1"],
            "fact_snapshot": "fact_snap:seed",
            "model_profile": "balanced_default",
            "publish": True,
            "execution_mode": "background",
        },
    )
    pending = server.call_tool("get_job_status", {"job_id": queued["job_id"]})
    worker = run_cli(
        ["worker", "--limit", "5"],
        server_factory=lambda **kwargs: server,
        runtime_validator=lambda **kwargs: {"status": "ok"},
        stdout=StringIO(),
        stderr=StringIO(),
    )
    processed = server.call_tool("get_job_status", {"job_id": queued["job_id"]})

    assert worker == 0
    assert pending["job"]["job_id"] == queued["job_id"]
    assert pending["job"]["state"] == "pending"
    assert pending["job"]["kind"] == "interpretation_build"
    assert pending["job"]["payload"]["partition"]["family"] == "market_trend"
    assert processed["job"]["state"] == "processed"
    assert processed["job"]["processed_at"] == "2026-04-18T00:10:00Z"
    assert processed["job"]["last_error"] is None


def test_server_explain_result_reports_personal_snapshot_drift_and_anchors(tmp_path: Path) -> None:
    server = build_fake_server(tmp_path)
    server.bootstrap.snapshot_repository.status_by_layer["interpretation"] = {
        "layer": "interpretation",
        "domain": "recruiting",
        "current_snapshot_id": "interp_snap:new",
        "fact_snapshot_id": "fact_snap:seed",
        "interpretation_snapshot_id": "interp_snap:new",
        "published_at": "2026-04-18T00:20:00Z",
    }

    explanation = server.call_tool(
        "explain_result",
        {
            "domain": "recruiting",
            "layer": "personal",
            "result_id": "personal:1",
            "tenant_id": "tenant-1",
            "user_id": "user-1",
        },
    )

    assert explanation["status"] == "ok"
    assert explanation["layer"] == "personal"
    assert explanation["explanation"]["change_reason"] == "interpretation_snapshot_changed"
    assert explanation["explanation"]["cache_state"] == "stale"
    assert explanation["explanation"]["anchors"] == ["interp:published:1", "fact:job:1"]
    assert explanation["explanation"]["based_on"] == {
        "fact_snapshot": "fact_snap:seed",
        "interpretation_snapshot": "interp_snap:seed",
        "profile_version": "profile:v1",
    }
    assert explanation["explanation"]["current_snapshots"]["interpretation_snapshot"] == "interp_snap:new"


def test_server_explain_result_reports_interpretation_publication_context(tmp_path: Path) -> None:
    server = build_fake_server(tmp_path)

    build = server.call_tool(
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
    published = server.bootstrap.interpretation_repository.list_records(
        domain="recruiting",
        scope_ref={"scope": "shared"},
        family="market_trend",
        subject_id="backend-japan-midlevel",
        statuses=["published"],
        limit=10,
    )[0]

    explanation = server.call_tool(
        "explain_result",
        {
            "domain": "recruiting",
            "layer": "interpretation",
            "result_id": published["id"],
        },
    )

    assert build["status"] == "ok"
    assert explanation["status"] == "ok"
    assert explanation["layer"] == "interpretation"
    assert explanation["explanation"]["change_reason"] == "current_result"
    assert explanation["explanation"]["lifecycle_state"] == "published"
    assert explanation["explanation"]["review_state"] == "published"
    assert explanation["explanation"]["anchors"] == ["fact:job:1"]
    assert explanation["explanation"]["based_on"]["fact_snapshot"] == "fact_snap:seed"
    assert (
        explanation["explanation"]["current_snapshots"]["interpretation_snapshot"]
        == build["interpretation_snapshot"]
    )


def test_server_validates_and_ingests_external_domain_proposals(tmp_path: Path) -> None:
    server = build_fake_server(tmp_path)

    dry_run = server.call_tool(
        "validate_domain_proposal_batch",
        {"batch": _external_batch()},
    )
    commit = server.call_tool(
        "ingest_domain_proposal_batch",
        {"batch": _external_batch()},
    )

    assert dry_run["ok"] is True
    assert dry_run["committed"] is False
    assert dry_run["audit"]["evaluated_pack_version"] == "2026-04-18"
    assert commit["ok"] is True
    assert commit["committed"] is True
    assert "fact:job_posting:EMP-2" in commit["affected_fact_ids"]


def test_server_can_queue_interpretation_build_for_worker_execution(tmp_path: Path) -> None:
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
            "execution_mode": "background",
        },
    )

    assert result == {
        "status": "queued",
        "execution_mode": "background",
        "job_id": "evt-1",
        "event_id": "evt-1",
        "event_type": "interpretation_snapshot_build_requested",
    }
    queued_event = server.bootstrap.outbox_repository.events[0]
    assert queued_event["event_type"] == "interpretation_snapshot_build_requested"
    assert queued_event["payload"]["partition"]["family"] == "market_trend"
    rendered_page = (
        tmp_path / "wiki" / "shared" / "interpretations" / "market_trend" / "backend-japan-midlevel.md"
    )
    assert rendered_page.exists() is False


def test_worker_cli_processes_queued_interpretation_build_jobs(tmp_path: Path) -> None:
    server = build_fake_server(tmp_path)
    queue_stdout = StringIO()
    queue_stderr = StringIO()

    queue_exit_code = run_cli(
        [
            "call",
            "build_interpretation_snapshot",
            "--args",
            json.dumps(
                {
                    "domain": "recruiting",
                    "partition": {
                        "family": "market_trends",
                        "segment": "backend-japan-midlevel",
                    },
                    "fact_ids": ["fact:job:1"],
                    "fact_snapshot": "fact_snap:seed",
                    "model_profile": "balanced_default",
                    "publish": True,
                    "execution_mode": "background",
                }
            ),
        ],
        server_factory=lambda **kwargs: server,
        stdout=queue_stdout,
        stderr=queue_stderr,
    )

    worker_stdout = StringIO()
    worker_stderr = StringIO()
    worker_exit_code = run_cli(
        ["worker", "--limit", "5"],
        server_factory=lambda **kwargs: server,
        runtime_validator=lambda **kwargs: {"status": "ok"},
        stdout=worker_stdout,
        stderr=worker_stderr,
    )

    queue_payload = json.loads(queue_stdout.getvalue())
    worker_payload = json.loads(worker_stdout.getvalue())

    assert queue_exit_code == 0
    assert queue_payload["status"] == "queued"
    assert worker_exit_code == 0
    assert worker_payload["status"] == "ok"
    assert worker_payload["claimed"] == 1
    assert worker_payload["processed"] == 1
    assert worker_payload["failed"] == 0
    assert worker_payload["jobs"][0]["job_id"] == queue_payload["job_id"]
    assert worker_payload["jobs"][0]["result"]["status"] == "ok"
    rendered_page = (
        tmp_path / "wiki" / "shared" / "interpretations" / "market_trend" / "backend-japan-midlevel.md"
    )
    assert rendered_page.exists()
    assert queue_stderr.getvalue() == ""
    assert worker_stderr.getvalue() == ""
