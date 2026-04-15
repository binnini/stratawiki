# Domain Ingestion Interface Spec

## Purpose

This document defines the domain ingestion interface for StrataWiki.

The goal is to support many domains without forcing the core system to understand domain-specific semantics.

The interface should be:

- thin
- stable
- domain-extensible
- compatible with the existing three-layer architecture
- compatible with the confirmed version-one technology baseline

This document focuses on the ingestion boundary only.

It does not define:

- interpretation builders
- personalization logic
- rendering rules outside ingestion outputs

## Core Principle

StrataWiki should not push ingestion completely outside the system.

Instead, it should split ingestion into two parts:

- `core ingestion orchestration`
- `domain-specific ingestion logic`

The core should own:

- source lifecycle orchestration
- provenance handling
- dedupe hooks
- Fact persistence coordination
- outbox publication
- snapshot publication
- downstream propagation triggers

The domain plugin should own:

- source normalization
- entity extraction
- relation extraction
- domain-specific validation
- domain-specific canonical key strategy

## Why This Interface Exists

Different domains will produce very different shapes of data.

Examples:

- recruiting: job postings, companies, roles, skills, locations
- finance: transactions, holdings, instruments, price events
- health: symptoms, biometrics, interventions, routines

Trying to unify these into one rich universal schema too early would make the core brittle.

Instead, the core should only require a common ingestion contract.

## Interface Boundaries

### What the Core Must Know

The core must know only enough to:

- identify a source
- normalize provenance
- receive Fact records
- receive Fact relations
- validate batch structure
- write canonical data
- publish snapshots and events

### What the Core Must Not Assume

The core must not assume:

- specific domain entity types
- fixed domain relation types
- a universal ontology
- one canonical extraction strategy for every domain

## Ingestion Flow

The ingestion pipeline should follow this high-level flow.

1. fetch raw source from a connector
2. normalize it into a common source envelope
3. pass the normalized source to the domain ingestion plugin
4. receive Fact records and Fact relations
5. validate batch structure and invariants
6. persist records through the core persistence path
7. publish fact snapshot metadata
8. emit outbox events for downstream projection

The domain interface lives mostly in steps 3 and 4.

## Common Source Envelope

Every connector should produce a `SourceRecord` before domain extraction begins.

Example:

```json
{
  "source_id": "greenhouse:job:abc123",
  "connector": "greenhouse",
  "domain": "recruiting",
  "title": "Backend Engineer",
  "body_markdown": "Normalized markdown or extracted text",
  "metadata": {
    "source_url": "https://..."
  },
  "fetched_at": "2026-04-15T10:00:00Z",
  "content_hash": "sha256:...",
  "status": "active"
}
```

The domain plugin should not need to know how the external connector works.

## Domain Plugin Contract

The domain ingestion plugin should expose a thin contract.

### Required Responsibilities

- normalize domain-specific source structure if needed
- extract Fact records
- extract Fact relations
- define or compute canonical keys
- validate domain-level extraction output

### Recommended Interface Shape

Conceptually:

```python
class DomainIngestionPlugin(Protocol):
    domain_name: str
    schema_version: str

    def accepts(self, source: SourceRecord) -> bool: ...

    def normalize_source(self, source: SourceRecord) -> SourceRecord: ...

    def extract_fact_records(self, source: SourceRecord) -> list[FactRecord]: ...

    def extract_fact_relations(
        self,
        source: SourceRecord,
        records: list[FactRecord],
    ) -> list[FactRelation]: ...

    def validate_batch(
        self,
        source: SourceRecord,
        records: list[FactRecord],
        relations: list[FactRelation],
    ) -> ValidationResult: ...
```
```

This is not a final language-level API, but it captures the intended structure.

## FactRecord Envelope

The domain plugin should return Fact records in a generic envelope.

Example:

```json
{
  "id": "job_posting_123",
  "domain": "recruiting",
  "entity_type": "job_posting",
  "canonical_key": "greenhouse:posting:abc123",
  "attributes": {
    "title": "Backend Engineer",
    "seniority": "mid"
  },
  "scope": "shared",
  "schema_version": "recruiting.fact.v1",
  "provenance": {
    "source_id": "greenhouse:job:abc123"
  }
}
```

This envelope is intentionally minimal.

The domain-specific shape belongs inside:

- `entity_type`
- `attributes`
- `schema_version`

## FactRelation Envelope

The domain plugin should also return explicit Fact relations.

Example:

```json
{
  "domain": "recruiting",
  "relation_type": "requires_skill",
  "from_canonical_key": "greenhouse:posting:abc123",
  "to_canonical_key": "skill:python",
  "attributes": {},
  "schema_version": "recruiting.fact_relation.v1",
  "provenance": {
    "source_id": "greenhouse:job:abc123"
  }
}
```

A domain relation should not be hidden only inside nested JSON if reverse lookup matters later.

## ValidationResult

The domain plugin should provide structured validation output.

Example:

```json
{
  "ok": true,
  "warnings": [],
  "errors": []
}
```

Validation can cover:

- missing canonical keys
- invalid entity types
- relations referencing missing records
- impossible field combinations
- schema-version mismatches

## Core Responsibilities After Extraction

After the domain plugin returns records and relations, the core should take over.

The core is responsible for:

- dedupe and canonical write orchestration
- relation persistence
- source snapshot tracking
- fact snapshot publication
- outbox event creation
- stale marking and downstream routing hooks

This division is important.

The domain plugin should not directly write to all downstream layers.

## Canonical Keys

The domain plugin should define enough information for canonical identity resolution.

In some domains, canonical identity can be obvious.

In others, it may require a domain-specific normalization strategy.

The core should require a `canonical_key` field, but should not dictate how every domain computes it.

## Scope Rules

The domain plugin should return scope-aware outputs where needed.

Typical default:

- Fact outputs are usually `shared`

But some domains may require tenant-scoped Facts.

The ingestion interface should allow the plugin to set:

- `scope`
- `tenant_id`
- `user_id` when appropriate

The core should validate that these fields are internally consistent.

## Domain Extensibility

This interface should support multiple domains because it is thin.

It does not require domains to share:

- entity taxonomies
- relation names
- extraction logic
- field-level schemas

It requires only that they share:

- source envelope
- Fact record envelope
- Fact relation envelope
- validation result shape
- provenance contract

## What Is Deliberately Not Included

The domain ingestion interface does not include:

- interpretation generation
- personal relevance ranking
- rendering decisions
- query-time retrieval ranking
- contradiction resolution logic beyond ingestion validation

Those should exist in separate interfaces or service layers.

## Recommended V1 Rule

For version one:

- keep the ingestion interface thin
- keep domain semantics in the domain plugin
- keep write orchestration in the core
- avoid putting interpretation or personalization behavior into ingestion too early

## Open Questions for Later

These are intentionally deferred until after first implementation.

- should domains expose explicit dedupe hints in addition to canonical keys
- should bulk extraction support partial-failure batches or all-or-nothing validation
- should domain plugins be pure code modules only, or partly declarative through config
- should some domains support multiple ingestion profiles for the same source type

## Recommended Next Step

The next implementation-facing task should be one of these:

1. define the Python protocol or abstract base classes for `DomainIngestionPlugin`
2. define the core ingestion service interface that consumes domain plugin output
3. draft the first recruiting ingestion plugin against real source payloads

The ingestion contract in this document should be treated as the stable starting point for those tasks.
