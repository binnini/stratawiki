from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

DomainAttributeType = Literal[
    "string",
    "markdown",
    "datetime",
    "url",
    "integer",
    "number",
    "boolean",
    "json",
]
IdentityNormalizationRule = Literal[
    "trim",
    "lowercase",
    "slugify",
    "digits_only",
    "collapse_whitespace",
]
RelationCardinality = Literal["one_to_one", "one_to_many", "many_to_many"]
EvidencePolicy = Literal["required", "optional"]
MergeMode = Literal["upsert", "append_only"]
MergeConflictStrategy = Literal[
    "prefer_newer_source",
    "prefer_existing",
    "manual_review",
]
DomainPackStatus = Literal[
    "draft",
    "approved",
    "active",
    "deprecated",
    "archived",
    "closed",
]
ProposalBatchMode = Literal["atomic", "best_effort"]


class _DomainPackCompatibilityOptional(TypedDict, total=False):
    max_stratawiki_version: str


class DomainPackCompatibility(_DomainPackCompatibilityOptional):
    min_stratawiki_version: str


class _DomainPackOwnerOptional(TypedDict, total=False):
    team: str


class DomainPackOwner(_DomainPackOwnerOptional):
    system: str


class _DomainPackManifestOptional(TypedDict, total=False):
    status: DomainPackStatus
    source_profiles: list[str]


class DomainPackManifest(_DomainPackManifestOptional):
    """Top-level metadata that identifies one registered pack artifact."""

    domain: str
    pack_version: str
    compatibility: DomainPackCompatibility
    owner: DomainPackOwner


class _AttributeDefinitionOptional(TypedDict, total=False):
    description: str
    enum: list[str]
    nullable: bool


class AttributeDefinition(_AttributeDefinitionOptional):
    """Minimal attribute contract for entity and relation definitions."""

    type: DomainAttributeType


class _ExternalIdIdentityRuleOptional(TypedDict, total=False):
    prefix: str


class ExternalIdIdentityRule(_ExternalIdIdentityRuleOptional):
    mode: Literal["external_id"]
    field: str


class CompositeIdentityRule(TypedDict):
    mode: Literal["composite"]
    fields: list[str]
    prefix: str
    normalization: NotRequired[list[IdentityNormalizationRule]]


class _HintPriorityStrategyOptional(TypedDict, total=False):
    prefix: str
    normalization: list[IdentityNormalizationRule]
    description: str


class HintPriorityStrategy(_HintPriorityStrategyOptional):
    hint: str


class HintPriorityIdentityRule(TypedDict):
    mode: Literal["hint_priority"]
    strategies: list[HintPriorityStrategy]
    fallback: Literal["reject", "manual_review"]


IdentityRule = ExternalIdIdentityRule | CompositeIdentityRule | HintPriorityIdentityRule


class _MergePolicyOptional(TypedDict, total=False):
    source_timestamp_attribute: str


class MergePolicy(_MergePolicyOptional):
    mode: MergeMode
    conflict_strategy: MergeConflictStrategy


class _EntityTypeDefinitionOptional(TypedDict, total=False):
    description: str


class EntityTypeDefinition(_EntityTypeDefinitionOptional):
    name: str
    attributes: dict[str, AttributeDefinition]
    required_attributes: list[str]
    identity: IdentityRule
    merge_policy: MergePolicy


class _RelationTypeDefinitionOptional(TypedDict, total=False):
    description: str
    attributes: dict[str, AttributeDefinition]
    cardinality: RelationCardinality
    evidence_policy: EvidencePolicy


class RelationTypeDefinition(_RelationTypeDefinitionOptional):
    name: str
    from_entity_types: list[str]
    to_entity_types: list[str]


class ProjectionTemporalWindow(TypedDict, total=False):
    start: str
    end: str


class ProjectionHints(TypedDict, total=False):
    """Read-side hints that should not affect canonical truth decisions."""

    default_title_attribute: dict[str, str]
    searchable_attributes: dict[str, list[str]]
    default_families: list[str]
    summary_attributes: dict[str, list[str]]
    temporal_attributes: dict[str, ProjectionTemporalWindow]
    default_family_by_entity_type: dict[str, str]


class ProposalSurfaceAccepts(TypedDict, total=False):
    fact_proposal: bool
    relation_proposal: bool


class ProposalSurface(TypedDict, total=False):
    accepts: ProposalSurfaceAccepts
    strict_unknown_attributes: bool
    batch_mode: ProposalBatchMode


class _DomainPackOptional(TypedDict, total=False):
    projection_hints: ProjectionHints
    proposal_surface: ProposalSurface


class DomainPack(_DomainPackOptional):
    """Minimal versioned domain artifact consumed by schema governance services."""

    manifest: DomainPackManifest
    entity_types: dict[str, EntityTypeDefinition]
    relation_types: dict[str, RelationTypeDefinition]
