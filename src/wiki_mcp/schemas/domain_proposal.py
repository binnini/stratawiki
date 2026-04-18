from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict

from wiki_mcp.schemas.fact_record import FactRecord
from wiki_mcp.schemas.fact_relation import FactRelation
from wiki_mcp.schemas.scope_ref import ScopeRef


class ProposalEvidenceRef(TypedDict):
    connector: str
    source_id: str
    pointer: NotRequired[str]


ProposalIdentityHints = dict[str, str]


class ProposalEntityRef(TypedDict, total=False):
    """Reference one entity proposal or an identity-resolvable entity surface."""

    proposal_id: str
    entity_type: str
    attributes: dict[str, Any]
    identity_hints: ProposalIdentityHints


class FactProposal(TypedDict, total=False):
    proposal_id: str
    domain: str
    entity_type: str
    attributes: dict[str, Any]
    identity_hints: ProposalIdentityHints
    evidence: list[ProposalEvidenceRef]


class RelationProposal(TypedDict, total=False):
    proposal_id: str
    domain: str
    relation_type: str
    from_ref: ProposalEntityRef
    to_ref: ProposalEntityRef
    attributes: dict[str, Any]
    evidence: list[ProposalEvidenceRef]


class DomainProposalBatch(TypedDict, total=False):
    batch_id: str
    domain: str
    pack_version: str
    producer: str
    scope_ref: ScopeRef
    submitted_at: str
    metadata: dict[str, Any]
    facts: list[FactProposal]
    relations: list[RelationProposal]


ProposalDecisionAction = Literal["create", "update", "noop", "merged"]


class DomainProposalAudit(TypedDict, total=False):
    batch_id: str
    domain: str
    producer: str
    requested_pack_version: str
    evaluated_pack_version: str
    evaluated_at: str
    content_hash: str
    dry_run: bool


class DomainProposalRejection(TypedDict, total=False):
    code: str
    message: str
    proposal_id: str
    field: str
    details: dict[str, Any]


class DomainProposalFactDecision(TypedDict, total=False):
    proposal_id: str
    entity_type: str
    canonical_key: str
    fact_id: str
    action: ProposalDecisionAction
    merged_into_proposal_id: str
    details: dict[str, Any]


class DomainProposalRelationDecision(TypedDict, total=False):
    proposal_id: str
    relation_type: str
    from_canonical_key: str
    to_canonical_key: str
    action: ProposalDecisionAction
    details: dict[str, Any]


class DomainProposalWritePlan(TypedDict):
    facts_to_create: int
    facts_to_update: int
    facts_to_noop: int
    relations_to_create: int


class DomainProposalIngestionResult(TypedDict, total=False):
    ok: bool
    committed: bool
    dry_run: bool
    audit: DomainProposalAudit
    rejections: list[DomainProposalRejection]
    fact_decisions: list[DomainProposalFactDecision]
    relation_decisions: list[DomainProposalRelationDecision]
    write_plan: DomainProposalWritePlan
    records: list[FactRecord]
    relations: list[FactRelation]
    fact_snapshot_id: str
    facts_created: int
    facts_updated: int
    relations_created: int
    affected_fact_ids: list[str]
    outbox_event_ids: list[str]
