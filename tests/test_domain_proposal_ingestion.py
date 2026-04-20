from __future__ import annotations

from wiki_mcp.schemas.domain_proposal import DomainProposalBatch
from wiki_mcp.services import (
    DomainProposalIngestionGateway,
    InMemoryDomainPackRegistry,
)
from wiki_mcp.services.core_ingestion import DefaultCoreIngestionService
from wiki_mcp.storage.memory import (
    InMemoryFactRepository,
    InMemoryOutboxRepository,
    InMemorySnapshotRepository,
)


def _pack(pack_version: str) -> dict[str, object]:
    return {
        "manifest": {
            "domain": "recruiting",
            "pack_version": pack_version,
            "compatibility": {
                "min_stratawiki_version": "0.1.0",
            },
            "owner": {
                "system": "jobs-wiki",
            },
        },
        "entity_types": {
            "job_posting": {
                "name": "job_posting",
                "attributes": {
                    "title": {"type": "string"},
                    "summary": {"type": "markdown", "nullable": True},
                },
                "required_attributes": ["title"],
                "identity": {
                    "mode": "external_id",
                    "field": "source_id",
                    "prefix": "job_posting",
                },
                "merge_policy": {
                    "mode": "upsert",
                    "conflict_strategy": "prefer_newer_source",
                },
            },
            "company": {
                "name": "company",
                "attributes": {
                    "name": {"type": "string"},
                    "homepage_url": {"type": "url", "nullable": True},
                },
                "required_attributes": ["name"],
                "identity": {
                    "mode": "composite",
                    "fields": ["name"],
                    "prefix": "company",
                    "normalization": ["trim", "lowercase", "slugify"],
                },
                "merge_policy": {
                    "mode": "upsert",
                    "conflict_strategy": "manual_review",
                },
            },
        },
        "relation_types": {
            "posted_by": {
                "name": "posted_by",
                "from_entity_types": ["job_posting"],
                "to_entity_types": ["company"],
                "attributes": {},
                "evidence_policy": "required",
            }
        },
    }


def _service(*, active_pack_version: str = "2026-04-18") -> tuple[
    DomainProposalIngestionGateway,
    InMemoryFactRepository,
    InMemorySnapshotRepository,
    InMemoryOutboxRepository,
]:
    fact_repository = InMemoryFactRepository()
    snapshot_repository = InMemorySnapshotRepository()
    outbox_repository = InMemoryOutboxRepository()
    core_ingestion_service = DefaultCoreIngestionService(
        fact_repository=fact_repository,
        snapshot_repository=snapshot_repository,
        outbox_repository=outbox_repository,
    )
    registry = InMemoryDomainPackRegistry([_pack("2026-04-01"), _pack(active_pack_version)])
    registry.set_active_version_approved("recruiting", active_pack_version)
    service = DomainProposalIngestionGateway(
        domain_pack_registry=registry,
        fact_repository=fact_repository,
        core_ingestion_service=core_ingestion_service,
    )
    return service, fact_repository, snapshot_repository, outbox_repository


def _valid_batch() -> DomainProposalBatch:
    return {
        "batch_id": "batch-1",
        "domain": "recruiting",
        "producer": "jobs-wiki",
        "facts": [
            {
                "proposal_id": "fact:posting",
                "domain": "recruiting",
                "entity_type": "job_posting",
                "attributes": {
                    "title": "Backend Engineer",
                    "summary": "Production AI delivery role",
                },
                "identity_hints": {
                    "source_id": "EMP-1",
                },
                "evidence": [
                    {
                        "connector": "worknet",
                        "source_id": "EMP-1",
                        "pointer": "/posting/title",
                    }
                ],
            },
            {
                "proposal_id": "fact:company",
                "domain": "recruiting",
                "entity_type": "company",
                "attributes": {
                    "name": "JobsWiki",
                    "homepage_url": "https://jobswiki.example.com",
                },
                "evidence": [
                    {
                        "connector": "worknet",
                        "source_id": "EMP-1",
                        "pointer": "/company",
                    }
                ],
            },
        ],
        "relations": [
            {
                "proposal_id": "rel:posted_by",
                "domain": "recruiting",
                "relation_type": "posted_by",
                "from_ref": {"proposal_id": "fact:posting"},
                "to_ref": {"proposal_id": "fact:company"},
                "evidence": [
                    {
                        "connector": "worknet",
                        "source_id": "EMP-1",
                        "pointer": "/company",
                    }
                ],
            }
        ],
    }


def test_validate_batch_uses_active_pack_and_returns_dry_run_plan() -> None:
    service, _, _, _ = _service(active_pack_version="2026-04-18")

    result = service.validate_batch(_valid_batch())

    assert result["ok"] is True
    assert result["committed"] is False
    assert result["dry_run"] is True
    assert result["audit"]["evaluated_pack_version"] == "2026-04-18"
    assert result["write_plan"] == {
        "facts_to_create": 2,
        "facts_to_update": 0,
        "facts_to_noop": 0,
        "relations_to_create": 1,
    }
    fact_by_proposal = {
        decision["proposal_id"]: decision for decision in result["fact_decisions"]
    }
    assert fact_by_proposal["fact:posting"]["canonical_key"] == "job_posting:EMP-1"
    assert fact_by_proposal["fact:company"]["canonical_key"] == "company:jobswiki"


def test_ingest_batch_commits_valid_batch_through_core_write_path() -> None:
    service, fact_repository, snapshot_repository, outbox_repository = _service()

    result = service.ingest_batch(_valid_batch())

    assert result["ok"] is True
    assert result["committed"] is True
    assert result["facts_created"] == 2
    assert result["relations_created"] == 1
    assert "fact:job_posting:EMP-1" in result["affected_fact_ids"]
    assert fact_repository.records["fact:job_posting:EMP-1"]["canonical_key"] == "job_posting:EMP-1"
    assert fact_repository.records["fact:company:jobswiki"]["attributes"]["name"] == "JobsWiki"
    assert snapshot_repository.get_snapshot_status(domain="recruiting") is not None
    assert outbox_repository.events[0]["event_type"] == "fact_ingested"


def test_ingest_batch_rejects_structured_invalid_proposal() -> None:
    service, fact_repository, snapshot_repository, outbox_repository = _service()
    batch = _valid_batch()
    batch["facts"][0]["attributes"]["unexpected"] = "value"

    result = service.ingest_batch(batch)

    assert result["ok"] is False
    assert result["committed"] is False
    assert result["rejections"][0]["code"] == "unknown_attribute"
    assert not fact_repository.records
    assert snapshot_repository.get_snapshot_status(domain="recruiting") is None
    assert outbox_repository.events == []


def test_validate_batch_rejects_non_active_pack_version() -> None:
    service, _, _, _ = _service(active_pack_version="2026-04-18")
    batch = _valid_batch()
    batch["pack_version"] = "2026-04-01"

    result = service.validate_batch(batch)

    assert result["ok"] is False
    assert result["committed"] is False
    assert result["rejections"][0]["code"] == "inactive_domain_pack_version"
    assert result["audit"]["evaluated_pack_version"] == "2026-04-18"


def test_ingest_batch_detects_existing_manual_review_conflict() -> None:
    service, fact_repository, _, _ = _service()
    fact_repository.records["fact:company:jobswiki"] = {
        "id": "fact:company:jobswiki",
        "domain": "recruiting",
        "entity_type": "company",
        "canonical_key": "company:jobswiki",
        "attributes": {
            "name": "JobsWiki",
            "homepage_url": "https://old.example.com",
        },
        "scope": "shared",
        "schema_version": "2026-04-18",
        "provenance": {"source_ids": ["EMP-0"]},
    }
    batch = _valid_batch()

    result = service.ingest_batch(batch)

    assert result["ok"] is False
    assert result["committed"] is False
    assert any(
        rejection["code"] == "existing_fact_conflict"
        and rejection.get("proposal_id") == "fact:company"
        for rejection in result["rejections"]
    )


def test_validate_batch_marks_existing_fact_as_update_in_write_plan() -> None:
    service, fact_repository, _, _ = _service()
    fact_repository.records["fact:job_posting:EMP-1"] = {
        "id": "fact:job_posting:EMP-1",
        "domain": "recruiting",
        "entity_type": "job_posting",
        "canonical_key": "job_posting:EMP-1",
        "attributes": {
            "title": "Backend Engineer",
            "summary": "Old summary",
        },
        "scope": "shared",
        "schema_version": "2026-04-18",
        "provenance": {"source_ids": ["EMP-0"]},
    }

    result = service.validate_batch(_valid_batch())

    assert result["ok"] is True
    assert result["write_plan"] == {
        "facts_to_create": 1,
        "facts_to_update": 1,
        "facts_to_noop": 0,
        "relations_to_create": 1,
    }
    decisions = {
        decision["proposal_id"]: decision["action"] for decision in result["fact_decisions"]
    }
    assert decisions["fact:posting"] == "update"
    assert decisions["fact:company"] == "create"


def test_relation_identity_ref_requires_batch_or_existing_target() -> None:
    service, _, _, _ = _service()
    batch = _valid_batch()
    batch["relations"][0]["to_ref"] = {
        "entity_type": "company",
        "attributes": {"name": "Missing Company"},
    }

    result = service.validate_batch(batch)

    assert result["ok"] is False
    assert any(
        rejection["code"] == "relation_endpoint_not_found"
        and rejection.get("proposal_id") == "rel:posted_by"
        for rejection in result["rejections"]
    )
