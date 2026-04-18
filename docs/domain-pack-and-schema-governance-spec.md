# Domain Pack and Schema Governance Spec

## Purpose

This document defines the current `Domain Pack` foundation in `StrataWiki`.

The goal is to move canonical domain semantics out of core Python code and into
registered, versioned artifacts that can later support:

- pack validation
- compatibility checking
- proposal ingestion
- pack-driven canonical key resolution

This document describes the foundation that now exists in the repository.
It does not claim that the full proposal-ingestion architecture is complete.

## Current Status

The repository now includes:

- a minimal `DomainPack` contract
- a `DomainPackRegistry` interface
- a default in-memory registry implementation
- runtime lookup by `domain + pack_version`
- explicit errors for missing packs and unsupported versions
- a dedicated Domain Pack validator with structured validation reports
- a compatibility checker with structured upgrade reports
- manual-review classification for non-breaking but operator-sensitive pack upgrades
- an approval service that evaluates candidate packs before registration or activation
- a proposal-ingestion service for `DomainProposalBatch`
- dry-run evaluation, structured rejection responses, and pack-version audit metadata for proposal ingestion

The repository does not yet include:

- file-based pack loading
- a bootstrapped proposal-ingestion path as the default runtime write surface
- durable pack-registration audit storage
- active or deprecated lifecycle metadata beyond one active-version pointer

## Architectural Position

`StrataWiki` now treats domain semantics as schema-governance artifacts rather than
as core-code assumptions.

The current runtime split is:

- source adapters still normalize raw inputs into `SourceRecord`
- the existing recruiting ingestion plugin still decomposes normalized source into Facts
- the new Domain Pack registry, approval services, and proposal-ingestion service provide the runtime seam for pack-governed ingestion

This means the current source-driven ingestion path remains valid while schema governance is being introduced incrementally.

## Domain Pack Contract

The minimal `DomainPack` contract is intentionally small.

### Manifest

The manifest identifies one pack artifact and its compatibility envelope.

Required fields:

- `domain`
- `pack_version`
- `compatibility.min_stratawiki_version`
- `owner.system`

Optional fields:

- `compatibility.max_stratawiki_version`
- `owner.team`

### Entity Types

Each entity type definition describes one canonical entity surface.

Required fields:

- `name`
- `attributes`
- `required_attributes`
- `identity`
- `merge_policy`

Optional fields:

- `description`

### Relation Types

Each relation type definition describes one canonical relation surface.

Required fields:

- `name`
- `from_entity_types`
- `to_entity_types`

Optional fields:

- `description`
- `attributes`
- `cardinality`
- `evidence_policy`

### Identity Rules

The current contract supports two identity modes:

- `external_id`
- `composite`

`external_id` uses one source field and an optional prefix.

`composite` uses:

- `fields`
- `prefix`
- optional `normalization` rules

### Merge Policy

The current merge policy describes how canonical conflicts should be handled.

Required fields:

- `mode`
- `conflict_strategy`

Optional fields:

- `source_timestamp_attribute`

### Projection Hints

Projection hints are read-side metadata only.
They do not define canonical truth.

Supported fields:

- `default_title_attribute`
- `searchable_attributes`
- `default_families`

## Registry Contract

The registry interface currently supports:

- `register(pack, activate=False)`
- `get(domain, pack_version=None)`
- `has(domain, pack_version=None)`
- `list_versions(domain)`
- `get_active_version(domain)`
- `set_active_version(domain, pack_version)`

Default lookup behavior resolves the active version for a domain.

Explicit version lookup resolves a specific registered artifact.

## Error Model

The current registry layer defines three explicit errors.

### `domain_pack_not_registered`

Raised when no pack exists for a domain.

### `unsupported_domain_pack_version`

Raised when a domain exists but the requested version is not registered.

### `domain_pack_version_already_registered`

Raised when the same `domain + pack_version` pair is registered twice.

## Runtime Integration

The default bootstrap context now exposes a `domain_pack_registry`.

This keeps the registry reachable from future services without forcing the current MVP ingestion path to migrate all at once.

At the moment, the registry is initialized empty.
Real domain-pack artifacts are expected to be registered by future bootstrap or integration code.

The runtime bootstrap now exposes:

- the registry itself
- a Domain Pack validator
- a compatibility checker
- an approval service that can review or gate registration/activation

Compatibility reports now distinguish between:

- `auto_pass`
- `manual_review`
- `auto_block`

This allows additive but operator-sensitive changes to be registered without
becoming the active pack until an explicit activation review is attached.

## Relationship to Existing Domain Code

The current recruiting ingestion path is still code-driven.

That is a temporary state, not the desired long-term ownership model.

The intended migration path is:

1. keep `SourceRecord` ingestion working
2. define and register a recruiting `DomainPack`
3. add validator and compatibility checks
4. introduce proposal ingestion against registered packs
5. reduce hardcoded recruiting semantics in the ingestion plugin

## Out of Scope for This Foundation

The following are intentionally deferred:

- proposal ingestion against registered packs as the default runtime write path
- durable audit trails for pack registration

Those concerns belong to the next schema-governance steps after the contract and registry foundation.
