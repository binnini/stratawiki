# Domain Pack and Schema Governance Spec

## Purpose

This document defines the current `Domain Pack` and schema-governance runtime in `StrataWiki`.

The goal is to move canonical domain semantics out of core Python code and into
registered, versioned artifacts that support:

- pack validation
- compatibility checking
- proposal ingestion
- pack-driven canonical key resolution

This document describes what is already implemented and what still remains open.

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
- approval-only registration and activation flow through the governance service
- a proposal-ingestion service for `DomainProposalBatch`
- dry-run evaluation, structured rejection responses, and pack-version audit metadata for proposal ingestion
- file-based pack artifact loading during bootstrap
- persisted review and activation audit records in an append-only filesystem store

The repository does not yet include:

- removal of the legacy source-driven recruiting ingestion path from the runtime
- richer pack lifecycle metadata beyond the active-version pointer plus review audit
- an operator-facing workflow beyond direct runtime APIs and JSONL audit records

## Architectural Position

`StrataWiki` now treats domain semantics as schema-governance artifacts rather than
as core-code assumptions.

The current runtime split is:

- source adapters still normalize raw inputs into `SourceRecord`
- external integration clients should prefer `DomainProposalBatch` validation and ingestion
- the existing recruiting ingestion plugin still decomposes normalized source into Facts for transition and internal source-driven use
- Domain Pack artifacts can be loaded and activated during bootstrap
- the Domain Pack registry, approval services, and proposal-ingestion service provide the runtime seam for pack-governed ingestion

This means the current source-driven ingestion path remains available while schema governance is being introduced incrementally, but it is no longer the preferred external write contract.

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

The default bootstrap context now exposes:

- the registry itself
- a Domain Pack validator
- a compatibility checker
- an approval service that can review or gate registration/activation
- a proposal-ingestion gateway
- bootstrap pack load reports
- a review-audit repository

When pack paths are configured, bootstrap can load, review, register, and optionally activate pack artifacts at startup.

The runtime may still start with an empty registry when no pack artifacts are configured.

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
4. introduce proposal ingestion against registered packs as the preferred external write path
5. reduce hardcoded recruiting semantics in the ingestion plugin

## Remaining Gaps

The following still remain open:

- a fully pack-driven replacement for the recruiting plugin decomposition path
- stronger pack lifecycle metadata for active, deprecated, and superseded versions
- richer operator-facing review tooling than the current persisted audit log

Those are the next schema-governance steps after the currently implemented approval, loading, and proposal-ingestion runtime plus the preferred external `DomainProposalBatch` contract.
