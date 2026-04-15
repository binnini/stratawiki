# External Ingestion Adapter Spec

## Purpose

This document defines how StrataWiki should integrate with an external ingestion system or API.

The goal is to avoid forcing StrataWiki to own every source-specific ingestion workflow while still preserving:

- canonical Fact control
- provenance
- snapshot publication
- outbox publication
- downstream propagation consistency

This document assumes that another project may already handle source fetching or even domain extraction, and that StrataWiki should consume those results through an adapter boundary.

## Core Position

StrataWiki should not directly depend on another project's internal data model.

Instead, it should integrate through an adapter or anti-corruption layer.

That means:

- external project contracts remain external
- StrataWiki contracts remain internal
- adapters translate between them

This is the safest way to preserve long-term system boundaries.

## Why an Adapter Layer Is Needed

Even if the external ingestion system is well-designed, it is optimized for its own assumptions.

If StrataWiki binds directly to those assumptions, the result is usually:

- external schema leakage into core StrataWiki models
- harder migration later
- tighter release coupling between projects
- weakened ownership of canonical identity and provenance rules

An adapter layer isolates these risks.

## Integration Levels

There are two main levels at which an external system can integrate with StrataWiki.

### Level 1: Source-Level Integration

The external system provides normalized source-like payloads.

StrataWiki then performs domain extraction itself.

External system responsibilities:

- source acquisition
- source cleanup
- raw or normalized payload delivery

StrataWiki responsibilities:

- `SourceRecord` mapping
- domain extraction into `FactRecord` and `FactRelation`
- validation
- canonical write
- snapshot and outbox publication

This makes the external system behave like an upstream `SourceAdapter`.

### Level 2: Batch-Level Integration

The external system provides payloads close to StrataWiki's ingestion contract.

For example, it may already provide:

- extracted entities
- extracted relations
- candidate canonical keys
- validation hints

StrataWiki responsibilities:

- adapt into `IngestionBatch`
- validate contract integrity
- canonical persistence
- snapshot and outbox publication

This makes the external system behave more like an upstream domain extraction service.

## Recommended Default

Prefer `Level 1` or a controlled intermediate form when possible.

Reason:

- it preserves StrataWiki control over domain extraction contracts
- it reduces coupling to another project's extraction semantics
- it keeps canonical identity and validation logic closer to StrataWiki

Use `Level 2` only when the external system already performs extraction that StrataWiki is willing to trust and stabilize around.

## Controlled Intermediate Form

In many cases the best approach is neither pure source-level nor fully batch-level.

A practical middle ground is:

- external system returns normalized domain payloads
- StrataWiki adapter converts them into `SourceRecord`, `FactRecord`, and `FactRelation`
- StrataWiki core remains the final authority for persistence and propagation

This gives flexibility without binding the core too tightly to raw upstream formats.

## Adapter Responsibilities

The adapter layer should be responsible for:

- calling the external ingestion API
- translating external payloads into StrataWiki contracts
- mapping external provenance into StrataWiki provenance fields
- normalizing external IDs and candidate canonical keys
- handling version mismatches between systems
- rejecting payloads that violate StrataWiki contract assumptions

The adapter layer should not be responsible for:

- publishing StrataWiki fact snapshots
- emitting StrataWiki outbox events
- deciding stale propagation policy
- bypassing StrataWiki validation and persistence paths

## Adapter Targets

An external adapter may target one of two internal contracts.

### Target A: `SourceRecord`

Use this when the external system behaves like a sophisticated source fetcher.

Example flow:

1. external system returns cleaned payload
2. adapter maps it to `SourceRecord`
3. StrataWiki domain plugin performs extraction
4. core ingestion persists the result

Best when:

- external system does not own canonical extraction semantics
- StrataWiki wants to keep extraction logic local

### Target B: `IngestionBatch`

Use this when the external system already produces domain extraction outputs compatible with StrataWiki's ingestion contract.

Example flow:

1. external system returns extracted domain payload
2. adapter maps it to `IngestionBatch`
3. core ingestion validates and persists the batch

Best when:

- external system already models entities and relations in a stable way
- StrataWiki is comfortable treating it as an upstream extraction provider

## Contract Translation Rules

### Source Identity

The adapter must preserve a stable source identity.

At minimum:

- external source ID
- external connector or provider name
- fetched time
- content hash or source version if available

### Provenance

The adapter must preserve enough provenance to answer:

- where did this data come from
- when was it fetched
- which external system produced it
- what upstream identifiers were involved

### Canonical Keys

If the external system provides canonical-like identifiers, the adapter may forward them as candidate canonical keys.

However, StrataWiki should remain the final authority on whether those keys are accepted as canonical internally.

### Schema Versioning

The adapter should carry both:

- external schema version if known
- internal StrataWiki schema version target

This is important when upstream systems evolve independently.

## Failure Modes

The adapter layer must expect mismatch and drift.

Typical failure cases:

- upstream payload missing required identity fields
- external schema changed without coordination
- candidate canonical keys conflict with internal rules
- relations reference entities not present in the same payload
- scope assumptions do not match StrataWiki expectations

Adapters should fail loudly and structurally rather than silently guessing.

## Scope and ACL Considerations

The adapter must not assume that all external payloads are globally shared.

If the upstream data is:

- tenant-specific
- user-specific
- partially restricted

then the adapter must map those constraints into StrataWiki scope fields explicitly.

At minimum, the adapter should be able to set:

- `scope`
- `tenant_id`
- `user_id` where applicable

The core should still validate that the resulting scope is internally consistent.

## Suggested Python Shape

The exact code can vary, but conceptually the adapter may look like this:

```python
class ExternalIngestionAdapter(Protocol):
    provider_name: str

    def fetch_external_payload(self, external_id: str) -> dict: ...

    def to_source_record(self, payload: dict) -> SourceRecord: ...

    def to_ingestion_batch(self, payload: dict) -> IngestionBatch: ...
```

Not every adapter needs both methods.

A source-level adapter may implement only:

- `fetch_external_payload`
- `to_source_record`

A batch-level adapter may implement:

- `fetch_external_payload`
- `to_ingestion_batch`

## Recommended V1 Rule

For version one:

- keep external integration behind adapters
- prefer source-level or controlled intermediate integration first
- treat StrataWiki as the authority for canonical persistence, snapshot publication, and propagation
- avoid allowing external projects to bypass StrataWiki's internal contracts

## Decision Guidance

Use source-level integration if:

- the external project is mainly a data collection system
- extraction semantics are not yet stable
- StrataWiki still wants control of domain extraction

Use batch-level integration if:

- the external project already performs stable domain extraction
- the entity and relation model is mature enough to trust
- the adapter can reliably map outputs into `IngestionBatch`

## Recommended Next Step

The next practical task should be one of these:

1. inspect the external ingestion API shape
2. decide whether the first integration target should be `SourceRecord` or `IngestionBatch`
3. create a minimal adapter protocol in code once the upstream payload shape is known

Until then, this document should be treated as the integration boundary policy.
