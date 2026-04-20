from __future__ import annotations

from wiki_mcp.services import (
    DefaultDomainPackApprovalService,
    DefaultDomainPackCompatibilityChecker,
    DefaultDomainPackValidator,
    InMemoryDomainPackRegistry,
)
from wiki_mcp.storage.memory import InMemoryDomainPackReviewAuditRepository


def _valid_pack(pack_version: str = "2026-04-18") -> dict[str, object]:
    return {
        "manifest": {
            "domain": "recruiting",
            "pack_version": pack_version,
            "compatibility": {
                "min_stratawiki_version": "0.1.0",
            },
            "owner": {
                "system": "jobs-wiki",
                "team": "career-knowledge",
            },
        },
        "entity_types": {
            "job_posting": {
                "name": "job_posting",
                "attributes": {
                    "title": {"type": "string"},
                    "summary": {"type": "markdown", "nullable": True},
                    "updated_at": {"type": "datetime", "nullable": True},
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
                    "source_timestamp_attribute": "updated_at",
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
                "cardinality": "many_to_many",
                "evidence_policy": "required",
            }
        },
        "projection_hints": {
            "default_title_attribute": {
                "job_posting": "title",
                "company": "name",
            },
            "searchable_attributes": {
                "job_posting": ["title", "summary"],
                "company": ["name"],
            },
            "default_families": ["opportunity", "company"],
        },
    }


def test_validator_accepts_structurally_valid_pack() -> None:
    validator = DefaultDomainPackValidator()

    report = validator.validate(_valid_pack())

    assert report["ok"] is True
    assert report["errors"] == []
    assert report["warnings"] == []


def test_validator_accepts_jobs_wiki_style_external_pack_shape() -> None:
    validator = DefaultDomainPackValidator()
    external_pack = {
        "manifest": {
            "domain": "recruiting",
            "packVersion": "2026-04-18",
            "status": "draft",
            "compatibility": {
                "minStrataWikiVersion": "0.2.0",
            },
            "owner": {
                "system": "jobs-wiki",
            },
            "sourceProfiles": ["worknet.open_recruitment"],
        },
        "proposalSurface": {
            "accepts": {"factProposal": True, "relationProposal": True},
            "strictUnknownAttributes": True,
            "batchMode": "atomic",
        },
        "entityTypes": {
            "job_posting": {
                "name": "job_posting",
                "attributes": {
                    "title": {"type": "string"},
                    "summary": {"type": "markdown", "nullable": True},
                    "opens_at": {"type": "datetime", "nullable": True},
                    "closes_at": {"type": "datetime", "nullable": True},
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
            }
        },
        "relationTypes": {},
        "projectionHints": {
            "defaultTitleAttribute": {"job_posting": "title"},
            "searchableAttributes": {"job_posting": ["title", "summary"]},
            "summaryAttributes": {"job_posting": ["summary"]},
            "temporalAttributes": {"job_posting": {"start": "opens_at", "end": "closes_at"}},
            "defaultFamilyByEntityType": {"job_posting": "opportunity"},
        },
    }

    report = validator.validate(external_pack)

    assert report["ok"] is True
    assert report["errors"] == []


def test_validator_rejects_unknown_fields_and_malformed_definitions() -> None:
    validator = DefaultDomainPackValidator()
    pack = {
        "manifest": {
            "domain": "recruiting",
            "pack_version": "2026-04-18",
            "compatibility": {},
            "owner": {
                "system": "jobs-wiki",
            },
        },
        "entity_types": {
            "job_posting": {
                "name": "job_posting",
                "attributes": {
                    "title": {"type": "string"},
                },
                "required_attributes": ["title", "status"],
                "identity": {
                    "mode": "external_id",
                    "field": "bad_identity_field",
                },
                "merge_policy": {
                    "mode": "upsert",
                    "conflict_strategy": "prefer_newer_source",
                    "source_timestamp_attribute": "title",
                },
                "unexpected": True,
            }
        },
        "relation_types": {
            "posted_by": {
                "name": "posted_by",
                "from_entity_types": ["job_posting"],
                "to_entity_types": ["company"],
                "cardinality": "invalid",
                "extra": "nope",
            }
        },
        "projection_hints": {
            "default_title_attribute": {"job_posting": "missing_attr"},
        },
        "proposal_surface": {"factProposal": True},
    }

    report = validator.validate(pack)

    assert report["ok"] is False
    codes = {issue["code"] for issue in report["errors"]}
    assert "unknown_field" in codes
    assert "missing_required_field" in codes
    assert "unknown_required_attribute" in codes
    assert "unknown_identity_field" in codes
    assert "invalid_merge_timestamp_attribute" in codes
    assert "unknown_relation_endpoint" in codes
    assert "invalid_relation_cardinality" in codes
    assert "invalid_projection_hint" in codes


def test_compatibility_checker_detects_breaking_changes() -> None:
    checker = DefaultDomainPackCompatibilityChecker()
    active_pack = _valid_pack("2026-04-18")
    candidate_pack = _valid_pack("2026-05-01")
    candidate_pack["entity_types"]["job_posting"]["identity"] = {
        "mode": "external_id",
        "field": "external_id",
        "prefix": "posting",
    }
    candidate_pack["entity_types"]["job_posting"]["required_attributes"] = [
        "title",
        "summary",
    ]
    candidate_pack["entity_types"]["organization"] = {
        "name": "organization",
        "attributes": {
            "name": {"type": "string"},
        },
        "required_attributes": ["name"],
        "identity": {
            "mode": "composite",
            "fields": ["name"],
            "prefix": "organization",
        },
        "merge_policy": {
            "mode": "upsert",
            "conflict_strategy": "manual_review",
        },
    }
    candidate_pack["relation_types"]["posted_by"]["to_entity_types"] = ["organization"]
    candidate_pack["relation_types"]["posted_by"]["cardinality"] = "one_to_one"

    report = checker.compare(active_pack=active_pack, candidate_pack=candidate_pack)

    assert report["compatible"] is False
    assert report["review_required"] is False
    assert report["migration_required"] is True
    assert report["recommended_action"] == "auto_block"
    codes = {issue["code"] for issue in report["issues"]}
    assert "canonical_key_rule_changed" in codes
    assert "required_attributes_strengthened" in codes
    assert "relation_endpoints_changed" in codes
    assert "relation_cardinality_changed" in codes
    assert len(report["breaking_changes"]) >= 4


def test_compatibility_checker_allows_additive_optional_changes() -> None:
    checker = DefaultDomainPackCompatibilityChecker()
    active_pack = _valid_pack("2026-04-18")
    candidate_pack = _valid_pack("2026-05-01")
    candidate_pack["entity_types"]["company"]["attributes"]["linkedin_url"] = {
        "type": "url",
        "nullable": True,
    }

    report = checker.compare(active_pack=active_pack, candidate_pack=candidate_pack)

    assert report["compatible"] is True
    assert report["review_required"] is False
    assert report["migration_required"] is False
    assert report["recommended_action"] == "auto_pass"
    assert report["issues"] == []


def test_compatibility_checker_flags_manual_review_for_endpoint_expansion_and_cardinality_relaxation() -> None:
    checker = DefaultDomainPackCompatibilityChecker()
    active_pack = _valid_pack("2026-04-18")
    candidate_pack = _valid_pack("2026-05-01")
    candidate_pack["entity_types"]["organization"] = {
        "name": "organization",
        "attributes": {
            "name": {"type": "string"},
        },
        "required_attributes": ["name"],
        "identity": {
            "mode": "composite",
            "fields": ["name"],
            "prefix": "organization",
        },
        "merge_policy": {
            "mode": "upsert",
            "conflict_strategy": "manual_review",
        },
    }
    candidate_pack["relation_types"]["posted_by"]["to_entity_types"] = [
        "company",
        "organization",
    ]
    candidate_pack["relation_types"]["posted_by"]["cardinality"] = "many_to_many"
    active_pack["relation_types"]["posted_by"]["cardinality"] = "one_to_many"

    report = checker.compare(active_pack=active_pack, candidate_pack=candidate_pack)

    assert report["compatible"] is True
    assert report["review_required"] is True
    assert report["migration_required"] is False
    assert report["recommended_action"] == "manual_review"
    codes = {issue["code"] for issue in report["review_required_issues"]}
    assert "relation_endpoints_expanded" in codes
    assert "relation_cardinality_changed" in codes
    assert all(issue["decision"] == "manual_review" for issue in report["review_required_issues"])


def test_approval_service_blocks_invalid_pack_registration() -> None:
    registry = InMemoryDomainPackRegistry()
    approval_service = DefaultDomainPackApprovalService(domain_pack_registry=registry)
    invalid_pack = _valid_pack()
    invalid_pack["entity_types"]["job_posting"]["required_attributes"] = ["missing"]

    report = approval_service.register_pack(invalid_pack, activate=True)

    assert report["ok"] is False
    assert report["registered"] is False
    assert registry.has("recruiting", "2026-04-18") is False


def test_approval_service_blocks_activation_for_breaking_candidate() -> None:
    registry = InMemoryDomainPackRegistry([_valid_pack("2026-04-18")])
    registry.set_active_version_approved("recruiting", "2026-04-18")
    approval_service = DefaultDomainPackApprovalService(domain_pack_registry=registry)
    candidate_pack = _valid_pack("2026-05-01")
    candidate_pack["entity_types"]["job_posting"]["identity"] = {
        "mode": "external_id",
        "field": "external_id",
        "prefix": "posting",
    }

    report = approval_service.register_pack(candidate_pack, activate=True)

    assert report["ok"] is False
    assert report["activation_safe"] is False
    assert report["recommended_action"] == "auto_block"
    assert report["compatibility"]["compatible"] is False
    assert registry.has("recruiting", "2026-05-01") is False


def test_approval_service_can_register_incompatible_version_without_activation() -> None:
    registry = InMemoryDomainPackRegistry([_valid_pack("2026-04-18")])
    registry.set_active_version_approved("recruiting", "2026-04-18")
    approval_service = DefaultDomainPackApprovalService(domain_pack_registry=registry)
    candidate_pack = _valid_pack("2026-05-01")
    candidate_pack["entity_types"]["job_posting"]["identity"] = {
        "mode": "external_id",
        "field": "external_id",
        "prefix": "posting",
    }

    report = approval_service.register_pack(candidate_pack, activate=False)

    assert report["ok"] is True
    assert report["registered"] is True
    assert report["activated"] is False
    assert report["compatibility"]["compatible"] is False
    assert registry.has("recruiting", "2026-05-01") is True


def test_approval_service_blocks_activation_when_manual_review_is_required() -> None:
    registry = InMemoryDomainPackRegistry([_valid_pack("2026-04-18")])
    registry.set_active_version_approved("recruiting", "2026-04-18")
    approval_service = DefaultDomainPackApprovalService(domain_pack_registry=registry)
    candidate_pack = _valid_pack("2026-05-01")
    candidate_pack["entity_types"]["organization"] = {
        "name": "organization",
        "attributes": {
            "name": {"type": "string"},
        },
        "required_attributes": ["name"],
        "identity": {
            "mode": "composite",
            "fields": ["name"],
            "prefix": "organization",
        },
        "merge_policy": {
            "mode": "upsert",
            "conflict_strategy": "manual_review",
        },
    }
    candidate_pack["relation_types"]["posted_by"]["to_entity_types"] = [
        "company",
        "organization",
    ]

    report = approval_service.register_pack(candidate_pack, activate=True)

    assert report["ok"] is False
    assert report["activation_safe"] is False
    assert report["review_required"] is True
    assert report["recommended_action"] == "manual_review"
    assert registry.has("recruiting", "2026-05-01") is False


def test_approval_service_allows_review_required_activation_with_review_audit() -> None:
    registry = InMemoryDomainPackRegistry([_valid_pack("2026-04-18")])
    registry.set_active_version_approved("recruiting", "2026-04-18")
    approval_service = DefaultDomainPackApprovalService(domain_pack_registry=registry)
    candidate_pack = _valid_pack("2026-05-01")
    candidate_pack["entity_types"]["organization"] = {
        "name": "organization",
        "attributes": {
            "name": {"type": "string"},
        },
        "required_attributes": ["name"],
        "identity": {
            "mode": "composite",
            "fields": ["name"],
            "prefix": "organization",
        },
        "merge_policy": {
            "mode": "upsert",
            "conflict_strategy": "manual_review",
        },
    }
    candidate_pack["relation_types"]["posted_by"]["to_entity_types"] = [
        "company",
        "organization",
    ]

    report = approval_service.register_pack(
        candidate_pack,
        activate=True,
        review_audit={
            "reviewed_by": "operator-1",
            "reviewed_at": "2026-04-18T12:00:00Z",
            "decision_reason": "Producer and read-side consumers are ready for additive endpoint expansion.",
            "migration_plan_ref": "runbook://pack-2026-05-01",
            "approved_for_activation": True,
        },
    )

    assert report["ok"] is True


def test_approval_service_persists_durable_audit_records() -> None:
    registry = InMemoryDomainPackRegistry([_valid_pack("2026-04-18")])
    registry.set_active_version_approved("recruiting", "2026-04-18")
    audit_repository = InMemoryDomainPackReviewAuditRepository()
    approval_service = DefaultDomainPackApprovalService(
        domain_pack_registry=registry,
        review_audit_repository=audit_repository,
    )
    candidate_pack = _valid_pack("2026-05-01")

    report = approval_service.register_pack(
        candidate_pack,
        activate=False,
        review_audit={
            "reviewed_by": "operator-1",
            "reviewed_at": "2026-04-18T12:00:00Z",
            "decision_reason": "Safe additive pack registration.",
        },
    )

    assert report["ok"] is True
    assert "audit_record_id" in report
    assert len(audit_repository.records) == 1
    stored = audit_repository.records[0]
    assert stored["action"] == "register_pack"
    assert stored["requested_activation"] is False
    assert stored["report"]["candidate_pack_version"] == "2026-05-01"
    assert report["registered"] is True
    assert report["activated"] is False
    assert report["activation_safe"] is True
    assert report["review_required"] is False
    assert report["review_audit"]["reviewed_by"] == "operator-1"
    assert "approved_for_activation" not in report["review_audit"]
    assert registry.has("recruiting", "2026-05-01") is True
