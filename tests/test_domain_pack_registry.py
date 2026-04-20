from __future__ import annotations

import pytest

from wiki_mcp.services.domain_pack_registry import (
    DomainPackApprovalRequiredError,
    DomainPackNotRegisteredError,
    DomainPackVersionAlreadyRegisteredError,
    InMemoryDomainPackRegistry,
    UnsupportedDomainPackVersionError,
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
                "team": "career-knowledge",
            },
        },
        "entity_types": {
            "job_posting": {
                "name": "job_posting",
                "attributes": {
                    "title": {
                        "type": "string",
                    },
                    "source_url": {
                        "type": "url",
                        "nullable": True,
                    },
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
                    "name": {
                        "type": "string",
                    }
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
                "job_posting": ["title"],
                "company": ["name"],
            },
            "default_families": ["opportunity", "company"],
        },
    }


def test_registry_registers_and_resolves_by_domain_and_version() -> None:
    registry = InMemoryDomainPackRegistry()
    v1 = _pack("2026-04-18")
    v2 = _pack("2026-05-01")

    registry.register_approved(v1, activate=True)
    registry.register_approved(v2, activate=True)

    assert registry.get_active_version("recruiting") == "2026-05-01"
    assert registry.list_versions("recruiting") == ["2026-04-18", "2026-05-01"]
    assert registry.get("recruiting")["manifest"]["pack_version"] == "2026-05-01"
    assert registry.get("recruiting", "2026-04-18")["manifest"]["pack_version"] == "2026-04-18"
    assert registry.has("recruiting", "2026-05-01") is True


def test_registry_can_switch_active_version() -> None:
    registry = InMemoryDomainPackRegistry([_pack("2026-04-18"), _pack("2026-05-01")])

    registry.set_active_version_approved("recruiting", "2026-04-18")

    assert registry.get("recruiting")["manifest"]["pack_version"] == "2026-04-18"

    registry.set_active_version_approved("recruiting", "2026-05-01")

    assert registry.get("recruiting")["manifest"]["pack_version"] == "2026-05-01"


def test_registry_raises_clear_error_for_unregistered_domain() -> None:
    registry = InMemoryDomainPackRegistry()

    with pytest.raises(DomainPackNotRegisteredError) as exc_info:
        registry.get("recruiting")

    assert exc_info.value.code == "domain_pack_not_registered"
    assert exc_info.value.domain == "recruiting"


def test_registry_raises_clear_error_for_unsupported_version() -> None:
    registry = InMemoryDomainPackRegistry([_pack("2026-04-18")])

    with pytest.raises(UnsupportedDomainPackVersionError) as exc_info:
        registry.get("recruiting", "2026-06-01")

    assert exc_info.value.code == "unsupported_domain_pack_version"
    assert exc_info.value.pack_version == "2026-06-01"
    assert exc_info.value.available_versions == ["2026-04-18"]


def test_registry_rejects_duplicate_registration() -> None:
    registry = InMemoryDomainPackRegistry([_pack("2026-04-18")])

    with pytest.raises(DomainPackVersionAlreadyRegisteredError) as exc_info:
        registry.register_approved(_pack("2026-04-18"))

    assert exc_info.value.code == "domain_pack_version_already_registered"


def test_registry_blocks_public_registration_and_activation_paths() -> None:
    registry = InMemoryDomainPackRegistry([_pack("2026-04-18")])

    with pytest.raises(DomainPackApprovalRequiredError) as register_exc:
        registry.register(_pack("2026-05-01"))

    with pytest.raises(DomainPackApprovalRequiredError) as activate_exc:
        registry.set_active_version("recruiting", "2026-04-18")

    assert register_exc.value.code == "domain_pack_approval_required"
    assert activate_exc.value.code == "domain_pack_approval_required"
