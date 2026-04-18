from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from wiki_mcp.schemas.domain_pack import (
    AttributeDefinition,
    DomainPack,
    EntityTypeDefinition,
    IdentityRule,
    MergePolicy,
    RelationTypeDefinition,
)
from wiki_mcp.schemas.domain_proposal import (
    DomainProposalAudit,
    DomainProposalBatch,
    DomainProposalFactDecision,
    DomainProposalIngestionResult,
    DomainProposalRelationDecision,
    DomainProposalRejection,
    DomainProposalWritePlan,
    ProposalEvidenceRef,
    ProposalIdentityHints,
)
from wiki_mcp.schemas.fact_record import FactRecord
from wiki_mcp.schemas.fact_relation import FactRelation
from wiki_mcp.schemas.ingestion_batch import IngestionBatch
from wiki_mcp.schemas.metadata_validation import ensure_scope_ref
from wiki_mcp.schemas.scope_ref import ScopeRef
from wiki_mcp.schemas.source_record import SourceRecord
from wiki_mcp.services.domain_contract_normalization import normalize_domain_proposal_batch
from wiki_mcp.services.domain_pack_registry import DomainPackRegistryError
from wiki_mcp.services.interfaces.core_ingestion import CoreIngestionService
from wiki_mcp.services.interfaces.domain_pack_registry import DomainPackRegistry
from wiki_mcp.services.interfaces.repositories import FactRepository

_SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass(slots=True)
class _ResolvedFactCandidate:
    proposal_id: str
    entity_type: str
    canonical_key: str
    fact_id: str
    attributes: dict[str, Any]
    evidence: list[ProposalEvidenceRef]
    merge_policy: MergePolicy
    source_proposal_ids: list[str] = field(default_factory=list)
    existing_record: FactRecord | None = None
    action: str = "create"


@dataclass(frozen=True, slots=True)
class _ResolvedEntityRef:
    canonical_key: str
    entity_type: str


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _slugify(value: str | None) -> str:
    if not value:
        return "unknown"
    stripped = value.strip().lower()
    normalized = _SLUG_RE.sub("-", stripped).strip("-")
    if normalized:
        return normalized
    return "text-" + hashlib.sha1(stripped.encode("utf-8")).hexdigest()[:12]


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


class DomainProposalIngestionGateway:
    """Validate proposal batches against the active pack and commit through fact ingestion."""

    def __init__(
        self,
        *,
        domain_pack_registry: DomainPackRegistry,
        fact_repository: FactRepository,
        core_ingestion_service: CoreIngestionService,
    ) -> None:
        self.domain_pack_registry = domain_pack_registry
        self.fact_repository = fact_repository
        self.core_ingestion_service = core_ingestion_service

    def validate_batch(
        self,
        batch: DomainProposalBatch,
    ) -> DomainProposalIngestionResult:
        return self.ingest_batch(batch, dry_run=True)

    def ingest_batch(
        self,
        batch: DomainProposalBatch,
        *,
        dry_run: bool = False,
    ) -> DomainProposalIngestionResult:
        batch = normalize_domain_proposal_batch(batch)
        audit = self._build_audit(batch, dry_run=dry_run)
        rejections: list[DomainProposalRejection] = []
        fact_decisions: list[DomainProposalFactDecision] = []
        relation_decisions: list[DomainProposalRelationDecision] = []
        records: list[FactRecord] = []
        relations: list[FactRelation] = []

        domain = self._as_non_empty_string(batch.get("domain"))
        producer = self._as_non_empty_string(batch.get("producer"))
        if domain is None:
            rejections.append(
                self._rejection(
                    code="missing_field",
                    message="DomainProposalBatch.domain must be a non-empty string.",
                    field="domain",
                )
            )
        if producer is None:
            rejections.append(
                self._rejection(
                    code="missing_field",
                    message="DomainProposalBatch.producer must be a non-empty string.",
                    field="producer",
                )
            )

        scope_ref: ScopeRef = {"scope": "shared"}
        raw_scope_ref = batch.get("scope_ref")
        if raw_scope_ref is not None:
            try:
                scope_ref = ensure_scope_ref(raw_scope_ref, label="DomainProposalBatch.scope_ref")
            except ValueError as exc:
                rejections.append(
                    self._rejection(
                        code="invalid_scope_ref",
                        message=str(exc),
                        field="scope_ref",
                    )
                )

        if domain is None or producer is None or rejections:
            return self._result(
                ok=False,
                committed=False,
                dry_run=dry_run,
                audit=audit,
                rejections=rejections,
                fact_decisions=fact_decisions,
                relation_decisions=relation_decisions,
                write_plan=self._build_write_plan([], []),
                records=records,
                relations=relations,
            )

        pack = self._resolve_active_pack(
            domain=domain,
            requested_pack_version=self._as_non_empty_string(batch.get("pack_version")),
            audit=audit,
            rejections=rejections,
        )
        if pack is None:
            return self._result(
                ok=False,
                committed=False,
                dry_run=dry_run,
                audit=audit,
                rejections=rejections,
                fact_decisions=fact_decisions,
                relation_decisions=relation_decisions,
                write_plan=self._build_write_plan([], []),
                records=records,
                relations=relations,
            )

        entity_types = pack.get("entity_types", {})
        relation_types = pack.get("relation_types", {})

        accepted_facts = self._evaluate_fact_proposals(
            batch=batch,
            entity_types=entity_types,
            scope_ref=scope_ref,
            rejections=rejections,
            fact_decisions=fact_decisions,
        )

        accepted_relations = self._evaluate_relation_proposals(
            batch=batch,
            entity_types=entity_types,
            relation_types=relation_types,
            scope_ref=scope_ref,
            audit=audit,
            accepted_facts=accepted_facts,
            rejections=rejections,
            relation_decisions=relation_decisions,
        )

        records = [self._candidate_to_record(candidate, domain=domain, scope_ref=scope_ref, audit=audit) for candidate in accepted_facts]
        relations = accepted_relations
        write_plan = self._build_write_plan(fact_decisions, relation_decisions)

        if rejections:
            return self._result(
                ok=False,
                committed=False,
                dry_run=dry_run,
                audit=audit,
                rejections=rejections,
                fact_decisions=fact_decisions,
                relation_decisions=relation_decisions,
                write_plan=write_plan,
                records=records,
                relations=relations,
            )

        if dry_run:
            return self._result(
                ok=True,
                committed=False,
                dry_run=True,
                audit=audit,
                rejections=[],
                fact_decisions=fact_decisions,
                relation_decisions=relation_decisions,
                write_plan=write_plan,
                records=records,
                relations=relations,
            )

        ingestion_batch: IngestionBatch = {
            "source": self._build_source(batch, audit),
            "records": records,
            "relations": relations,
            "validation": {
                "ok": True,
                "warnings": [],
                "errors": [],
            },
        }
        persisted = self.core_ingestion_service.ingest_batch(ingestion_batch)
        return self._result(
            ok=True,
            committed=True,
            dry_run=False,
            audit=audit,
            rejections=[],
            fact_decisions=fact_decisions,
            relation_decisions=relation_decisions,
            write_plan=write_plan,
            records=records,
            relations=relations,
            **persisted,
        )

    def _evaluate_fact_proposals(
        self,
        *,
        batch: DomainProposalBatch,
        entity_types: dict[str, EntityTypeDefinition],
        scope_ref: ScopeRef,
        rejections: list[DomainProposalRejection],
        fact_decisions: list[DomainProposalFactDecision],
    ) -> list[_ResolvedFactCandidate]:
        facts = batch.get("facts") or []
        seen_ids: set[str] = set()
        raw_candidates: list[_ResolvedFactCandidate] = []

        for index, proposal in enumerate(facts):
            proposal_id = self._as_non_empty_string(proposal.get("proposal_id"))
            if proposal_id is None:
                rejections.append(
                    self._rejection(
                        code="missing_field",
                        message="Fact proposal_id must be a non-empty string.",
                        field=f"facts[{index}].proposal_id",
                    )
                )
                continue
            if proposal_id in seen_ids:
                rejections.append(
                    self._rejection(
                        code="duplicate_proposal_id",
                        message=f"Fact proposal_id {proposal_id!r} appears more than once in the batch.",
                        proposal_id=proposal_id,
                        field="proposal_id",
                    )
                )
                continue
            seen_ids.add(proposal_id)

            domain = self._as_non_empty_string(proposal.get("domain"))
            if domain != batch["domain"]:
                rejections.append(
                    self._rejection(
                        code="proposal_domain_mismatch",
                        message=(
                            f"Fact proposal {proposal_id!r} targets domain {domain!r}, "
                            f"expected {batch['domain']!r}."
                        ),
                        proposal_id=proposal_id,
                        field="domain",
                    )
                )
                continue

            entity_type = self._as_non_empty_string(proposal.get("entity_type"))
            if entity_type is None or entity_type not in entity_types:
                rejections.append(
                    self._rejection(
                        code="unsupported_entity_type",
                        message=(
                            f"Fact proposal {proposal_id!r} uses unsupported entity_type "
                            f"{proposal.get('entity_type')!r}."
                        ),
                        proposal_id=proposal_id,
                        field="entity_type",
                    )
                )
                continue

            entity_definition = entity_types[entity_type]
            attributes = self._ensure_attributes(
                proposal_id=proposal_id,
                attributes=proposal.get("attributes"),
                definitions=entity_definition.get("attributes", {}),
                required=entity_definition.get("required_attributes", []),
                subject="fact",
                rejections=rejections,
            )
            evidence = self._ensure_evidence(
                proposal_id=proposal_id,
                evidence=proposal.get("evidence"),
                field="evidence",
                required=True,
                rejections=rejections,
            )
            if attributes is None or evidence is None:
                continue

            identity_hints = self._coerce_identity_hints(proposal.get("identity_hints"))
            canonical_key = self._resolve_canonical_key(
                proposal_id=proposal_id,
                entity_type=entity_type,
                attributes=attributes,
                identity_hints=identity_hints,
                identity_rule=entity_definition["identity"],
                rejections=rejections,
            )
            if canonical_key is None:
                continue

            raw_candidates.append(
                _ResolvedFactCandidate(
                    proposal_id=proposal_id,
                    entity_type=entity_type,
                    canonical_key=canonical_key,
                    fact_id=f"fact:{canonical_key}",
                    attributes=attributes,
                    evidence=evidence,
                    merge_policy=entity_definition["merge_policy"],
                    source_proposal_ids=[proposal_id],
                )
            )

        merged_candidates: list[_ResolvedFactCandidate] = []
        by_identity: dict[tuple[str, str, str, str | None, str | None], _ResolvedFactCandidate] = {}

        for candidate in raw_candidates:
            identity = (
                candidate.entity_type,
                candidate.canonical_key,
                scope_ref["scope"],
                scope_ref.get("tenant_id"),
                scope_ref.get("user_id"),
            )
            keeper = by_identity.get(identity)
            if keeper is None:
                by_identity[identity] = candidate
                merged_candidates.append(candidate)
                continue

            merged = self._merge_attribute_maps(
                current=keeper.attributes,
                incoming=candidate.attributes,
                merge_policy=keeper.merge_policy,
            )
            if merged is None:
                rejections.append(
                    self._rejection(
                        code="duplicate_fact_conflict",
                        message=(
                            f"Fact proposal {candidate.proposal_id!r} conflicts with another proposal "
                            f"for canonical_key {candidate.canonical_key!r}."
                        ),
                        proposal_id=candidate.proposal_id,
                        field="attributes",
                        details={"canonical_key": candidate.canonical_key},
                    )
                )
                continue

            keeper.attributes = merged
            keeper.evidence = self._merge_evidence(keeper.evidence, candidate.evidence)
            keeper.source_proposal_ids.append(candidate.proposal_id)
            fact_decisions.append(
                {
                    "proposal_id": candidate.proposal_id,
                    "entity_type": candidate.entity_type,
                    "canonical_key": candidate.canonical_key,
                    "fact_id": keeper.fact_id,
                    "action": "merged",
                    "merged_into_proposal_id": keeper.proposal_id,
                }
            )

        existing_records = self.fact_repository.get_by_canonical_keys(
            [candidate.canonical_key for candidate in merged_candidates],
            scope_ref,
        )
        existing_by_key: dict[str, FactRecord] = {}
        for record in existing_records:
            key = record["canonical_key"]
            if key in existing_by_key and existing_by_key[key]["id"] != record["id"]:
                rejections.append(
                    self._rejection(
                        code="existing_canonical_key_conflict",
                        message=(
                            f"Canonical key {key!r} already maps to multiple stored facts. "
                            "Manual repair is required before proposal ingestion."
                        ),
                        field="canonical_key",
                        details={"canonical_key": key},
                    )
                )
                continue
            existing_by_key[key] = record

        accepted: list[_ResolvedFactCandidate] = []
        for candidate in merged_candidates:
            existing = existing_by_key.get(candidate.canonical_key)
            if existing is None:
                accepted.append(candidate)
                fact_decisions.append(
                    {
                        "proposal_id": candidate.proposal_id,
                        "entity_type": candidate.entity_type,
                        "canonical_key": candidate.canonical_key,
                        "fact_id": candidate.fact_id,
                        "action": "create",
                        "details": {
                            "merged_proposal_ids": [
                                proposal_id
                                for proposal_id in candidate.source_proposal_ids
                                if proposal_id != candidate.proposal_id
                            ]
                        },
                    }
                )
                continue

            if existing["entity_type"] != candidate.entity_type:
                rejections.append(
                    self._rejection(
                        code="existing_fact_conflict",
                        message=(
                            f"Canonical key {candidate.canonical_key!r} already exists as entity_type "
                            f"{existing['entity_type']!r}, not {candidate.entity_type!r}."
                        ),
                        proposal_id=candidate.proposal_id,
                        field="entity_type",
                        details={"canonical_key": candidate.canonical_key, "existing_fact_id": existing["id"]},
                    )
                )
                continue

            merged_attributes = self._merge_attribute_maps(
                current=existing["attributes"],
                incoming=candidate.attributes,
                merge_policy=candidate.merge_policy,
                existing_record=existing,
            )
            if merged_attributes is None:
                rejections.append(
                    self._rejection(
                        code="existing_fact_conflict",
                        message=(
                            f"Fact proposal {candidate.proposal_id!r} conflicts with stored fact "
                            f"{existing['id']!r} for canonical_key {candidate.canonical_key!r}."
                        ),
                        proposal_id=candidate.proposal_id,
                        field="attributes",
                        details={"canonical_key": candidate.canonical_key, "existing_fact_id": existing["id"]},
                    )
                )
                continue

            candidate.fact_id = existing["id"]
            candidate.existing_record = existing
            candidate.attributes = merged_attributes
            candidate.action = "update" if merged_attributes != existing["attributes"] else "noop"
            accepted.append(candidate)
            fact_decisions.append(
                {
                    "proposal_id": candidate.proposal_id,
                    "entity_type": candidate.entity_type,
                    "canonical_key": candidate.canonical_key,
                    "fact_id": candidate.fact_id,
                    "action": candidate.action,
                    "details": {"existing_fact_id": existing["id"]},
                }
            )

        return accepted

    def _evaluate_relation_proposals(
        self,
        *,
        batch: DomainProposalBatch,
        entity_types: dict[str, EntityTypeDefinition],
        relation_types: dict[str, RelationTypeDefinition],
        scope_ref: ScopeRef,
        audit: DomainProposalAudit,
        accepted_facts: list[_ResolvedFactCandidate],
        rejections: list[DomainProposalRejection],
        relation_decisions: list[DomainProposalRelationDecision],
    ) -> list[FactRelation]:
        relations = batch.get("relations") or []
        accepted_fact_by_proposal_id: dict[str, _ResolvedFactCandidate] = {}
        accepted_fact_by_key: dict[str, _ResolvedFactCandidate] = {}
        for candidate in accepted_facts:
            accepted_fact_by_key[candidate.canonical_key] = candidate
            for proposal_id in candidate.source_proposal_ids:
                accepted_fact_by_proposal_id[proposal_id] = candidate

        seen_ids: set[str] = set()
        materialized: list[FactRelation] = []
        by_identity: dict[tuple[str, str, str, str, str | None, str | None], int] = {}

        for index, proposal in enumerate(relations):
            proposal_id = self._as_non_empty_string(proposal.get("proposal_id"))
            if proposal_id is None:
                rejections.append(
                    self._rejection(
                        code="missing_field",
                        message="Relation proposal_id must be a non-empty string.",
                        field=f"relations[{index}].proposal_id",
                    )
                )
                continue
            if proposal_id in seen_ids:
                rejections.append(
                    self._rejection(
                        code="duplicate_proposal_id",
                        message=f"Relation proposal_id {proposal_id!r} appears more than once in the batch.",
                        proposal_id=proposal_id,
                        field="proposal_id",
                    )
                )
                continue
            seen_ids.add(proposal_id)

            domain = self._as_non_empty_string(proposal.get("domain"))
            if domain != batch["domain"]:
                rejections.append(
                    self._rejection(
                        code="proposal_domain_mismatch",
                        message=(
                            f"Relation proposal {proposal_id!r} targets domain {domain!r}, "
                            f"expected {batch['domain']!r}."
                        ),
                        proposal_id=proposal_id,
                        field="domain",
                    )
                )
                continue

            relation_type = self._as_non_empty_string(proposal.get("relation_type"))
            if relation_type is None or relation_type not in relation_types:
                rejections.append(
                    self._rejection(
                        code="unsupported_relation_type",
                        message=(
                            f"Relation proposal {proposal_id!r} uses unsupported relation_type "
                            f"{proposal.get('relation_type')!r}."
                        ),
                        proposal_id=proposal_id,
                        field="relation_type",
                    )
                )
                continue

            relation_definition = relation_types[relation_type]
            attributes = self._ensure_attributes(
                proposal_id=proposal_id,
                attributes=proposal.get("attributes"),
                definitions=relation_definition.get("attributes", {}),
                required=[],
                subject="relation",
                rejections=rejections,
            )
            evidence = self._ensure_evidence(
                proposal_id=proposal_id,
                evidence=proposal.get("evidence"),
                field="evidence",
                required=relation_definition.get("evidence_policy", "optional") == "required",
                rejections=rejections,
            )
            if attributes is None or evidence is None:
                continue

            from_ref = self._resolve_entity_ref(
                proposal_id=proposal_id,
                ref=proposal.get("from_ref"),
                ref_label="from_ref",
                entity_types=entity_types,
                accepted_fact_by_proposal_id=accepted_fact_by_proposal_id,
                accepted_fact_by_key=accepted_fact_by_key,
                scope_ref=scope_ref,
                rejections=rejections,
            )
            to_ref = self._resolve_entity_ref(
                proposal_id=proposal_id,
                ref=proposal.get("to_ref"),
                ref_label="to_ref",
                entity_types=entity_types,
                accepted_fact_by_proposal_id=accepted_fact_by_proposal_id,
                accepted_fact_by_key=accepted_fact_by_key,
                scope_ref=scope_ref,
                rejections=rejections,
            )
            if from_ref is None or to_ref is None:
                continue

            if from_ref.entity_type not in relation_definition["from_entity_types"]:
                rejections.append(
                    self._rejection(
                        code="relation_endpoint_type_mismatch",
                        message=(
                            f"Relation proposal {proposal_id!r} cannot use from entity_type "
                            f"{from_ref.entity_type!r} for relation_type {relation_type!r}."
                        ),
                        proposal_id=proposal_id,
                        field="from_ref",
                        details={"allowed_entity_types": relation_definition["from_entity_types"]},
                    )
                )
                continue
            if to_ref.entity_type not in relation_definition["to_entity_types"]:
                rejections.append(
                    self._rejection(
                        code="relation_endpoint_type_mismatch",
                        message=(
                            f"Relation proposal {proposal_id!r} cannot use to entity_type "
                            f"{to_ref.entity_type!r} for relation_type {relation_type!r}."
                        ),
                        proposal_id=proposal_id,
                        field="to_ref",
                        details={"allowed_entity_types": relation_definition["to_entity_types"]},
                    )
                )
                continue

            relation: FactRelation = {
                "domain": batch["domain"],
                "relation_type": relation_type,
                "from_canonical_key": from_ref.canonical_key,
                "to_canonical_key": to_ref.canonical_key,
                "scope": scope_ref["scope"],
                **({"tenant_id": scope_ref["tenant_id"]} if "tenant_id" in scope_ref else {}),
                **({"user_id": scope_ref["user_id"]} if "user_id" in scope_ref else {}),
                "schema_version": audit["evaluated_pack_version"],
                "provenance": self._build_provenance(
                    existing=None,
                    evidence=evidence,
                    audit=audit,
                    producer=batch["producer"],
                ),
                **({"attributes": attributes} if attributes else {}),
            }
            identity = (
                relation_type,
                relation["from_canonical_key"],
                relation["to_canonical_key"],
                relation["scope"],
                relation.get("tenant_id"),
                relation.get("user_id"),
            )
            existing_index = by_identity.get(identity)
            if existing_index is not None:
                merged = self._merge_relation_attributes(
                    current=materialized[existing_index].get("attributes", {}),
                    incoming=attributes,
                )
                if merged is None:
                    rejections.append(
                        self._rejection(
                            code="duplicate_relation_conflict",
                            message=(
                                f"Relation proposal {proposal_id!r} conflicts with another proposal "
                                f"for {relation_type!r} between {from_ref.canonical_key!r} and "
                                f"{to_ref.canonical_key!r}."
                            ),
                            proposal_id=proposal_id,
                            field="attributes",
                        )
                    )
                    continue
                if merged:
                    materialized[existing_index]["attributes"] = merged
                relation_decisions.append(
                    {
                        "proposal_id": proposal_id,
                        "relation_type": relation_type,
                        "from_canonical_key": from_ref.canonical_key,
                        "to_canonical_key": to_ref.canonical_key,
                        "action": "merged",
                    }
                )
                continue

            by_identity[identity] = len(materialized)
            materialized.append(relation)
            relation_decisions.append(
                {
                    "proposal_id": proposal_id,
                    "relation_type": relation_type,
                    "from_canonical_key": from_ref.canonical_key,
                    "to_canonical_key": to_ref.canonical_key,
                    "action": "create",
                }
            )

        return materialized

    def _resolve_entity_ref(
        self,
        *,
        proposal_id: str,
        ref: Any,
        ref_label: str,
        entity_types: dict[str, EntityTypeDefinition],
        accepted_fact_by_proposal_id: dict[str, _ResolvedFactCandidate],
        accepted_fact_by_key: dict[str, _ResolvedFactCandidate],
        scope_ref: ScopeRef,
        rejections: list[DomainProposalRejection],
    ) -> _ResolvedEntityRef | None:
        if not isinstance(ref, Mapping):
            rejections.append(
                self._rejection(
                    code="missing_field",
                    message=f"{ref_label} must be a mapping.",
                    proposal_id=proposal_id,
                    field=ref_label,
                )
            )
            return None

        proposal_ref = self._as_non_empty_string(ref.get("proposal_id"))
        if proposal_ref is not None:
            candidate = accepted_fact_by_proposal_id.get(proposal_ref)
            if candidate is None:
                rejections.append(
                    self._rejection(
                        code="relation_endpoint_not_found",
                        message=(
                            f"Relation proposal {proposal_id!r} references unknown or rejected "
                            f"fact proposal {proposal_ref!r}."
                        ),
                        proposal_id=proposal_id,
                        field=ref_label,
                    )
                )
                return None
            return _ResolvedEntityRef(
                canonical_key=candidate.canonical_key,
                entity_type=candidate.entity_type,
            )

        entity_type = self._as_non_empty_string(ref.get("entity_type"))
        if entity_type is None or entity_type not in entity_types:
            rejections.append(
                self._rejection(
                    code="relation_endpoint_not_found",
                    message=(
                        f"Relation proposal {proposal_id!r} must provide either proposal_id "
                        f"or a resolvable entity_type for {ref_label}."
                    ),
                    proposal_id=proposal_id,
                    field=ref_label,
                )
            )
            return None

        entity_definition = entity_types[entity_type]
        attributes = (
            dict(ref["attributes"])
            if isinstance(ref.get("attributes"), Mapping)
            else {}
        )
        identity_hints = self._coerce_identity_hints(ref.get("identity_hints"))
        canonical_key = self._resolve_canonical_key(
            proposal_id=proposal_id,
            entity_type=entity_type,
            attributes=attributes,
            identity_hints=identity_hints,
            identity_rule=entity_definition["identity"],
            rejections=rejections,
            field=ref_label,
        )
        if canonical_key is None:
            return None

        in_batch = accepted_fact_by_key.get(canonical_key)
        if in_batch is not None:
            return _ResolvedEntityRef(
                canonical_key=in_batch.canonical_key,
                entity_type=in_batch.entity_type,
            )

        existing = self.fact_repository.get_by_canonical_keys([canonical_key], scope_ref)
        if not existing:
            rejections.append(
                self._rejection(
                    code="relation_endpoint_not_found",
                    message=(
                        f"Resolved {ref_label} canonical_key {canonical_key!r} does not exist in the "
                        "accepted batch or current canonical store."
                    ),
                    proposal_id=proposal_id,
                    field=ref_label,
                )
            )
            return None

        if existing[0]["entity_type"] != entity_type:
            rejections.append(
                self._rejection(
                    code="relation_endpoint_type_mismatch",
                    message=(
                        f"Resolved {ref_label} canonical_key {canonical_key!r} exists as "
                        f"{existing[0]['entity_type']!r}, not {entity_type!r}."
                    ),
                    proposal_id=proposal_id,
                    field=ref_label,
                )
            )
            return None

        return _ResolvedEntityRef(canonical_key=canonical_key, entity_type=entity_type)

    def _candidate_to_record(
        self,
        candidate: _ResolvedFactCandidate,
        *,
        domain: str,
        scope_ref: ScopeRef,
        audit: DomainProposalAudit,
    ) -> FactRecord:
        provenance = self._build_provenance(
            existing=candidate.existing_record.get("provenance") if candidate.existing_record else None,
            evidence=candidate.evidence,
            audit=audit,
            producer=audit["producer"],
        )
        record: FactRecord = {
            "id": candidate.fact_id,
            "domain": domain,
            "entity_type": candidate.entity_type,
            "canonical_key": candidate.canonical_key,
            "attributes": candidate.attributes,
            "scope": scope_ref["scope"],
            **({"tenant_id": scope_ref["tenant_id"]} if "tenant_id" in scope_ref else {}),
            **({"user_id": scope_ref["user_id"]} if "user_id" in scope_ref else {}),
            "schema_version": audit["evaluated_pack_version"],
            "provenance": provenance,
        }
        return record

    def _resolve_active_pack(
        self,
        *,
        domain: str,
        requested_pack_version: str | None,
        audit: DomainProposalAudit,
        rejections: list[DomainProposalRejection],
    ) -> DomainPack | None:
        try:
            pack = self.domain_pack_registry.get(domain)
        except DomainPackRegistryError as exc:
            rejections.append(
                self._rejection(
                    code=exc.code,
                    message=str(exc),
                    field="pack_version",
                    details={
                        "domain": exc.domain,
                        "pack_version": exc.pack_version,
                        "available_versions": exc.available_versions,
                    },
                )
            )
            return None

        evaluated_pack_version = pack["manifest"]["pack_version"]
        audit["evaluated_pack_version"] = evaluated_pack_version
        if requested_pack_version and requested_pack_version != evaluated_pack_version:
            rejections.append(
                self._rejection(
                    code="inactive_domain_pack_version",
                    message=(
                        f"Proposal batch requested pack_version {requested_pack_version!r}, "
                        f"but the active pack for domain {domain!r} is {evaluated_pack_version!r}."
                    ),
                    field="pack_version",
                    details={
                        "requested_pack_version": requested_pack_version,
                        "evaluated_pack_version": evaluated_pack_version,
                    },
                )
            )
        return pack

    def _ensure_attributes(
        self,
        *,
        proposal_id: str,
        attributes: Any,
        definitions: dict[str, AttributeDefinition],
        required: list[str],
        subject: str,
        rejections: list[DomainProposalRejection],
    ) -> dict[str, Any] | None:
        start_index = len(rejections)
        if attributes is None:
            candidate: dict[str, Any] = {}
        elif isinstance(attributes, Mapping):
            candidate = dict(attributes)
        else:
            rejections.append(
                self._rejection(
                    code="invalid_attribute_type",
                    message=f"{subject.capitalize()} proposal attributes must be a mapping.",
                    proposal_id=proposal_id,
                    field="attributes",
                )
            )
            return None

        for name in sorted(candidate):
            definition = definitions.get(name)
            if definition is None:
                rejections.append(
                    self._rejection(
                        code="unknown_attribute",
                        message=(
                            f"{subject.capitalize()} proposal {proposal_id!r} uses unknown attribute "
                            f"{name!r}."
                        ),
                        proposal_id=proposal_id,
                        field=f"attributes.{name}",
                    )
                )
                continue
            if not self._attribute_value_matches_definition(candidate[name], definition):
                rejections.append(
                    self._rejection(
                        code="invalid_attribute_type",
                        message=(
                            f"{subject.capitalize()} proposal {proposal_id!r} attribute {name!r} "
                            f"does not match declared type {definition['type']!r}."
                        ),
                        proposal_id=proposal_id,
                        field=f"attributes.{name}",
                    )
                )

        for name in required:
            if name not in candidate or _is_blank(candidate.get(name)):
                rejections.append(
                    self._rejection(
                        code="missing_required_attribute",
                        message=(
                            f"{subject.capitalize()} proposal {proposal_id!r} is missing required "
                            f"attribute {name!r}."
                        ),
                        proposal_id=proposal_id,
                        field=f"attributes.{name}",
                    )
                )

        if any(
            rejection.get("proposal_id") == proposal_id
            and str(rejection.get("field", "")).startswith("attributes")
            for rejection in rejections[start_index:]
        ):
            return None
        return candidate

    def _ensure_evidence(
        self,
        *,
        proposal_id: str,
        evidence: Any,
        field: str,
        required: bool,
        rejections: list[DomainProposalRejection],
    ) -> list[ProposalEvidenceRef] | None:
        start_index = len(rejections)
        if evidence is None:
            if required:
                rejections.append(
                    self._rejection(
                        code="invalid_evidence",
                        message=f"Proposal {proposal_id!r} requires at least one evidence item.",
                        proposal_id=proposal_id,
                        field=field,
                    )
                )
                return None
            return []
        if not isinstance(evidence, list):
            rejections.append(
                self._rejection(
                    code="invalid_evidence",
                    message=f"Proposal {proposal_id!r} evidence must be a list.",
                    proposal_id=proposal_id,
                    field=field,
                )
            )
            return None
        if required and not evidence:
            rejections.append(
                self._rejection(
                    code="invalid_evidence",
                    message=f"Proposal {proposal_id!r} requires at least one evidence item.",
                    proposal_id=proposal_id,
                    field=field,
                )
            )
            return None

        normalized: list[ProposalEvidenceRef] = []
        for index, item in enumerate(evidence):
            if not isinstance(item, Mapping):
                rejections.append(
                    self._rejection(
                        code="invalid_evidence",
                        message=f"Evidence item {index} for proposal {proposal_id!r} must be a mapping.",
                        proposal_id=proposal_id,
                        field=f"{field}[{index}]",
                    )
                )
                continue
            connector = self._as_non_empty_string(item.get("connector"))
            source_id = self._as_non_empty_string(item.get("source_id"))
            if connector is None or source_id is None:
                rejections.append(
                    self._rejection(
                        code="invalid_evidence",
                        message=(
                            f"Evidence item {index} for proposal {proposal_id!r} must include "
                            "connector and source_id."
                        ),
                        proposal_id=proposal_id,
                        field=f"{field}[{index}]",
                    )
                )
                continue
            normalized_item: ProposalEvidenceRef = {
                "connector": connector,
                "source_id": source_id,
            }
            pointer = self._as_non_empty_string(item.get("pointer"))
            if pointer is not None:
                normalized_item["pointer"] = pointer
            normalized.append(normalized_item)

        if required and not normalized:
            return None
        if any(
            rejection.get("proposal_id") == proposal_id
            and str(rejection.get("field", "")).startswith(field)
            for rejection in rejections[start_index:]
        ):
            return None
        return normalized

    def _resolve_canonical_key(
        self,
        *,
        proposal_id: str,
        entity_type: str,
        attributes: dict[str, Any],
        identity_hints: ProposalIdentityHints,
        identity_rule: IdentityRule,
        rejections: list[DomainProposalRejection],
        field: str = "identity_hints",
    ) -> str | None:
        if identity_rule["mode"] == "external_id":
            value = self._identity_value(
                identity_rule["field"],
                attributes=attributes,
                identity_hints=identity_hints,
            )
            if value is None:
                rejections.append(
                    self._rejection(
                        code="identity_field_missing",
                        message=(
                            f"Fact proposal {proposal_id!r} is missing identity value "
                            f"{identity_rule['field']!r}."
                        ),
                        proposal_id=proposal_id,
                        field=field,
                    )
                )
                return None
            prefix = self._as_non_empty_string(identity_rule.get("prefix")) or entity_type
            return f"{prefix}:{value}"

        if identity_rule["mode"] == "hint_priority":
            for strategy in identity_rule.get("strategies", []):
                hint_name = self._as_non_empty_string(strategy.get("hint"))
                if hint_name is None:
                    continue
                value = self._identity_value(
                    hint_name,
                    attributes=attributes,
                    identity_hints=identity_hints,
                )
                if value is None:
                    continue
                prefix = self._as_non_empty_string(strategy.get("prefix")) or entity_type
                normalized_value = self._normalize_identity_component(
                    value,
                    strategy.get("normalization", []),
                )
                if normalized_value:
                    return f"{prefix}:{normalized_value}"

            fallback = identity_rule.get("fallback", "reject")
            rejection_code = (
                "identity_manual_review_required"
                if fallback == "manual_review"
                else "identity_field_missing"
            )
            rejections.append(
                self._rejection(
                    code=rejection_code,
                    message=(
                        f"Fact proposal {proposal_id!r} could not resolve a stable identity for "
                        f"entity_type {entity_type!r} using the configured hint_priority rule."
                    ),
                    proposal_id=proposal_id,
                    field=field,
                )
            )
            return None

        values: list[str] = []
        for identity_field in identity_rule["fields"]:
            value = self._identity_value(
                identity_field,
                attributes=attributes,
                identity_hints=identity_hints,
            )
            if value is None:
                rejections.append(
                    self._rejection(
                        code="identity_field_missing",
                        message=(
                            f"Fact proposal {proposal_id!r} is missing identity value "
                            f"{identity_field!r}."
                        ),
                        proposal_id=proposal_id,
                        field=field,
                    )
                )
                return None
            values.append(self._normalize_identity_component(value, identity_rule.get("normalization", [])))

        prefix = self._as_non_empty_string(identity_rule.get("prefix")) or entity_type
        return f"{prefix}:{':'.join(values)}"

    def _identity_value(
        self,
        field: str,
        *,
        attributes: dict[str, Any],
        identity_hints: ProposalIdentityHints,
    ) -> str | None:
        hint = identity_hints.get(field)
        if isinstance(hint, str) and hint.strip():
            return hint.strip()
        value = attributes.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        return None

    def _normalize_identity_component(
        self,
        value: str,
        rules: list[str],
    ) -> str:
        normalized = value
        for rule in rules:
            if rule == "trim":
                normalized = normalized.strip()
            elif rule == "lowercase":
                normalized = normalized.lower()
            elif rule == "digits_only":
                normalized = re.sub(r"\D+", "", normalized)
            elif rule == "collapse_whitespace":
                normalized = " ".join(normalized.split())
            elif rule == "slugify":
                normalized = _slugify(normalized)
        return normalized.strip()

    def _attribute_value_matches_definition(
        self,
        value: Any,
        definition: AttributeDefinition,
    ) -> bool:
        if value is None:
            return bool(definition.get("nullable"))
        attr_type = definition["type"]
        if attr_type in {"string", "markdown", "url", "datetime"}:
            if not isinstance(value, str):
                return False
        elif attr_type == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                return False
        elif attr_type == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return False
        elif attr_type == "boolean":
            if not isinstance(value, bool):
                return False
        elif attr_type == "json":
            if not isinstance(value, (dict, list, str, int, float, bool)):
                return False
        if "enum" in definition and value not in definition["enum"]:
            return False
        return True

    def _merge_attribute_maps(
        self,
        *,
        current: dict[str, Any],
        incoming: dict[str, Any],
        merge_policy: MergePolicy,
        existing_record: FactRecord | None = None,
    ) -> dict[str, Any] | None:
        mode = merge_policy.get("mode", "upsert")
        strategy = merge_policy.get("conflict_strategy", "manual_review")
        source_timestamp_attribute = self._as_non_empty_string(
            merge_policy.get("source_timestamp_attribute")
        )

        merged = dict(current)
        for key, incoming_value in incoming.items():
            current_value = merged.get(key)
            if current_value == incoming_value or _is_blank(incoming_value):
                continue
            if _is_blank(current_value):
                if mode == "append_only" and existing_record is not None:
                    return None
                merged[key] = incoming_value
                continue
            if mode == "append_only":
                return None
            if strategy == "prefer_existing":
                continue
            if strategy == "manual_review":
                return None
            if strategy == "prefer_newer_source":
                if source_timestamp_attribute and existing_record is not None:
                    if not self._incoming_is_newer(
                        current=current,
                        incoming=incoming,
                        source_timestamp_attribute=source_timestamp_attribute,
                    ):
                        continue
                merged[key] = incoming_value
                continue
            merged[key] = incoming_value
        return merged

    def _incoming_is_newer(
        self,
        *,
        current: dict[str, Any],
        incoming: dict[str, Any],
        source_timestamp_attribute: str,
    ) -> bool:
        current_value = current.get(source_timestamp_attribute)
        incoming_value = incoming.get(source_timestamp_attribute)
        current_timestamp = self._parse_timestamp(current_value)
        incoming_timestamp = self._parse_timestamp(incoming_value)
        if current_timestamp is None or incoming_timestamp is None:
            return True
        return incoming_timestamp >= current_timestamp

    def _parse_timestamp(self, value: Any) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        candidate = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            return None

    def _merge_relation_attributes(
        self,
        *,
        current: dict[str, Any],
        incoming: dict[str, Any],
    ) -> dict[str, Any] | None:
        merged = dict(current)
        for key, value in incoming.items():
            if key not in merged or _is_blank(merged[key]):
                merged[key] = value
                continue
            if merged[key] != value:
                return None
        return merged

    def _merge_evidence(
        self,
        current: list[ProposalEvidenceRef],
        incoming: list[ProposalEvidenceRef],
    ) -> list[ProposalEvidenceRef]:
        by_identity: dict[tuple[str, str, str | None], ProposalEvidenceRef] = {}
        for item in [*current, *incoming]:
            identity = (item["connector"], item["source_id"], item.get("pointer"))
            by_identity[identity] = item
        return list(by_identity.values())

    def _build_audit(
        self,
        batch: DomainProposalBatch,
        *,
        dry_run: bool,
    ) -> DomainProposalAudit:
        payload_hash = hashlib.sha1(
            json.dumps(batch, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        batch_id = self._as_non_empty_string(batch.get("batch_id")) or f"proposal-batch:{payload_hash[:12]}"
        audit: DomainProposalAudit = {
            "batch_id": batch_id,
            "domain": str(batch.get("domain") or ""),
            "producer": str(batch.get("producer") or ""),
            "evaluated_at": _utc_now(),
            "content_hash": payload_hash,
            "dry_run": dry_run,
        }
        requested_pack_version = self._as_non_empty_string(batch.get("pack_version"))
        if requested_pack_version is not None:
            audit["requested_pack_version"] = requested_pack_version
        return audit

    def _build_source(
        self,
        batch: DomainProposalBatch,
        audit: DomainProposalAudit,
    ) -> SourceRecord:
        submitted_at = self._as_non_empty_string(batch.get("submitted_at")) or audit["evaluated_at"]
        body = (
            f"# Domain Proposal Batch\n\n"
            f"- batch_id: {audit['batch_id']}\n"
            f"- domain: {batch['domain']}\n"
            f"- producer: {batch['producer']}\n"
            f"- pack_version: {audit['evaluated_pack_version']}\n"
            f"- facts: {len(batch.get('facts') or [])}\n"
            f"- relations: {len(batch.get('relations') or [])}\n"
        )
        return {
            "source_id": audit["batch_id"],
            "connector": batch["producer"],
            "domain": batch["domain"],
            "title": f"Domain proposal batch {audit['batch_id']}",
            "body_markdown": body,
            "metadata": {
                "kind": "domain_proposal_batch",
                "producer": batch["producer"],
                "proposal_counts": {
                    "facts": len(batch.get("facts") or []),
                    "relations": len(batch.get("relations") or []),
                },
                "proposal_metadata": dict(batch.get("metadata") or {}),
                "proposal_audit": dict(audit),
            },
            "fetched_at": submitted_at,
            "content_hash": audit["content_hash"],
            "status": "validated",
        }

    def _build_provenance(
        self,
        *,
        existing: Mapping[str, Any] | None,
        evidence: list[ProposalEvidenceRef],
        audit: DomainProposalAudit,
        producer: str,
    ) -> dict[str, Any]:
        existing_map = dict(existing or {})
        source_ids = {
            str(source_id)
            for source_id in existing_map.get("source_ids", [])
            if isinstance(source_id, str) and source_id
        }
        source_ids.update(item["source_id"] for item in evidence)

        upstream_versions = {
            str(key): str(value)
            for key, value in dict(existing_map.get("upstream_versions") or {}).items()
        }
        upstream_versions["domain_pack"] = audit["evaluated_pack_version"]

        notes = [
            str(note)
            for note in existing_map.get("notes", [])
            if isinstance(note, str) and note
        ]
        audit_note = f"proposal_batch:{audit['batch_id']}"
        if audit_note not in notes:
            notes.append(audit_note)

        provenance = dict(existing_map)
        previous_audit = provenance.get("audit")
        if previous_audit and previous_audit != audit:
            history = list(provenance.get("audit_history") or [])
            history.append(previous_audit)
            provenance["audit_history"] = history
        provenance.update(
            {
                "source_ids": sorted(source_ids),
                "upstream_versions": upstream_versions,
                "generated_by": {
                    "kind": "system",
                    "provider": "domain_proposal_ingestion",
                },
                "generated_at": audit["evaluated_at"],
                "notes": notes,
                "audit": {
                    **audit,
                    "producer": producer,
                },
                "evidence": [dict(item) for item in evidence],
            }
        )
        return provenance

    def _build_write_plan(
        self,
        fact_decisions: list[DomainProposalFactDecision],
        relation_decisions: list[DomainProposalRelationDecision],
    ) -> DomainProposalWritePlan:
        facts_to_create = 0
        facts_to_update = 0
        facts_to_noop = 0
        for decision in fact_decisions:
            action = decision["action"]
            if action == "merged":
                continue
            if action == "update":
                facts_to_update += 1
            elif action == "noop":
                facts_to_noop += 1
            else:
                facts_to_create += 1
        return {
            "facts_to_create": facts_to_create,
            "facts_to_update": facts_to_update,
            "facts_to_noop": facts_to_noop,
            "relations_to_create": sum(
                1
                for decision in relation_decisions
                if decision["action"] == "create"
            ),
        }

    def _result(
        self,
        *,
        ok: bool,
        committed: bool,
        dry_run: bool,
        audit: DomainProposalAudit,
        rejections: list[DomainProposalRejection],
        fact_decisions: list[DomainProposalFactDecision],
        relation_decisions: list[DomainProposalRelationDecision],
        write_plan: DomainProposalWritePlan,
        records: list[FactRecord],
        relations: list[FactRelation],
        **persisted: Any,
    ) -> DomainProposalIngestionResult:
        return {
            "ok": ok,
            "committed": committed,
            "dry_run": dry_run,
            "audit": audit,
            "rejections": rejections,
            "fact_decisions": fact_decisions,
            "relation_decisions": relation_decisions,
            "write_plan": write_plan,
            "records": records,
            "relations": relations,
            **persisted,
        }

    def _rejection(
        self,
        *,
        code: str,
        message: str,
        proposal_id: str | None = None,
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> DomainProposalRejection:
        rejection: DomainProposalRejection = {
            "code": code,
            "message": message,
        }
        if proposal_id is not None:
            rejection["proposal_id"] = proposal_id
        if field is not None:
            rejection["field"] = field
        if details is not None:
            rejection["details"] = details
        return rejection

    def _as_non_empty_string(self, value: Any) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        return value.strip()

    def _coerce_identity_hints(self, value: Any) -> ProposalIdentityHints:
        if not isinstance(value, Mapping):
            return {}
        hints: ProposalIdentityHints = {}
        for key, item in value.items():
            if isinstance(key, str) and isinstance(item, str) and item.strip():
                hints[key] = item.strip()
        return hints
