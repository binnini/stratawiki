# StrataWiki Architecture Checkpoint

## Context

This note summarizes the current architecture, technical decisions, and code-boundary work completed so far for StrataWiki.

It is a working checkpoint, not an official design document.

Official project documentation remains in `docs/`.

## Current Direction

StrataWiki is positioned as a separate knowledge backend service.

It is not:

- just a database
- just an MCP wrapper
- just a markdown wiki

It is a multi-layer knowledge system with:

- canonical Fact storage
- canonical Interpretation storage
- user-scoped Personal outputs
- rendered markdown views
- graph and dependency support
- snapshot and invalidation logic

The intended deployment relationship is:

- a separate WAS or product backend for user-facing product APIs and orchestration
- StrataWiki as the knowledge backend
- PostgreSQL as a separate infrastructure dependency owned by StrataWiki at the schema and migration level

## Core Philosophy

The system is based on an adapted LLM Wiki pattern.

The key philosophy remains:

- knowledge should compound over time
- synthesis should persist
- good answers should become durable artifacts
- humans curate direction, LLMs help maintain knowledge structure

The major adaptation is:

- markdown is not the only source of truth
- markdown is the readable layer of a larger system

## Confirmed Layer Model

The architecture is fixed around three semantic layers.

### Fact

- canonical observed data
- normalized and deduplicated
- strongest source of truth in the system

### Interpretation

- shared derived meaning from Facts
- canonical storage plus rendered shared wiki views
- versioned and refreshable

### Personal

- user-scoped strategy, notes, plans, and cached outputs
- metadata in canonical storage
- readable bodies rendered to markdown

## Confirmed Version-One Technical Decisions

The following choices have been confirmed for version one.

- runtime: Python 3.11+
- Fact store: PostgreSQL
- Interpretation canonical store: PostgreSQL JSONB
- Personal metadata store: PostgreSQL
- Personal rendered body: filesystem markdown
- projection model: outbox + worker
- graph and dependency storage: PostgreSQL reverse dependency indexes + derived graph artifacts
- retrieval indexing: structured filtering + lexical search
- ACL enforcement: application-level scope enforcement
- ingestion structure: core pipeline + domain ingestion interface

The current migration stance is:

- MongoDB remains a possible later migration target for Interpretation if document ergonomics become the primary bottleneck
- embeddings and hybrid retrieval remain deferred
- dedicated graph DB remains deferred
- storage-level RLS remains deferred

## PostgreSQL Structure

The PostgreSQL structure is fixed conceptually as:

- `fact`
- `interp`
- `personal`
- `ops`
- `graph`

The intent is:

- one PostgreSQL database
- multiple logical schemas
- clear ownership boundaries inside one datastore

This keeps v1 operationally simple while preserving future migration boundaries.

## Internal Boundaries Now Recognized

The architecture should remain internally layered even if it is not physically split into many services yet.

Primary boundaries:

- core vs domain plugins
- canonical vs rendered
- retrieval vs dependency
- synchronous request path vs asynchronous projection path
- MCP interface vs internal service interface

Secondary boundaries:

- profile/context
- search backend adapters
- rendering subsystem

## Ingestion Strategy

The ingestion design is now clarified.

The system should not fully outsource ingestion.

Instead:

- core owns ingestion orchestration, persistence, snapshot publication, outbox events, and propagation triggers
- domain plugins own normalization, fact extraction, relation extraction, canonical key logic, and validation

There is also a new external integration stance:

- StrataWiki should not bind directly to another project's internal ingestion model
- another system should integrate through an adapter boundary
- preferred integration target is a domain-normalized payload, not raw API payload and not StrataWiki-internal canonical record formats

## External Ingestion Status

An existing external project path was reviewed:

- `/home/yebin/projects/Jobs-Wiki/packages/integrations/worknet`

Current judgment:

- it is a strong low-level or intermediate integration layer
- it is not yet a StrataWiki `DomainIngestionPlugin`
- it is best treated as a source-level or controlled-intermediate provider

Recommended direction for the external project:

- keep low-level WorkNet adapter/client structure
- add a domain-facing normalized recruiting payload provider above it
- let StrataWiki adapt that payload into `SourceRecord` or `IngestionBatch`

## Code Boundaries Added So Far

The codebase now has thin interface boundaries for the main architectural seams.

### Schema envelopes

Added or clarified:

- `SourceRecord`
- `FactRecord`
- `FactRelation`
- `ValidationResult`
- `IngestionBatch`
- `IngestionResult`
- `ScopeRef`
- `SnapshotRef`
- `RetrievalResult`
- `DependencyImpact`
- `RenderedArtifact`
- `ProfileContext`
- `InterpretationRecord`
- `PersonalRecord`
- `OutboxEvent`
- `FactWriteResult`

### Service interfaces

Added:

- `DomainIngestionPlugin`
- `CoreIngestionService`
- `RetrievalService`
- `DependencyService`
- `RenderingService`
- `ProfileContextService`

### Repository interfaces

Added:

- `FactRepository`
- `InterpretationRepository`
- `PersonalRepository`
- `ProfileContextRepository`
- `RenderingRepository`
- `SnapshotRepository`
- `OutboxRepository`
- `DependencyRepository`

These boundaries are intentionally thin. The goal was to freeze architecture seams before implementing the first real domain flow.

## Current Retrieval Model

The current retrieval order is fixed conceptually as:

- Personal
- Interpretation
- Fact

This means:

- user-specific context is preferred first
- shared interpretation provides reusable meaning
- Fact is used for grounding and evidence

This is the default retrieval philosophy for user-facing requests.

## Current Propagation Model

The current downstream propagation order is:

- Fact change
- Interpretation stale marking or rebuild
- Personal stale marking or refresh on access

The system should prefer:

- dependency-aware stale marking
- selective recomputation
- outbox-driven asynchronous work
- family or segment scoped interpretation snapshots where possible

## Docs vs Dev Wiki

Current policy:

- `docs/` contains official design and implementation documentation
- `dev-wiki/` contains working notes, logs, experiments, and temporary architecture traces

At the moment, the `docs/` set still looks appropriate as official project docs.
No document is currently being downgraded back into `dev-wiki/`.

## What Has Not Been Done Yet

Still not implemented:

- actual Postgres repositories
- actual core service implementations
- actual MCP tool implementations
- actual recruiting plugin implementation
- actual external ingestion adapter implementation
- actual database migrations or DDL

The system is now at the point where implementation can begin with less architectural ambiguity.

## Suggested Next Actions

Recommended next steps:

1. implement core service skeletons using the current repository interfaces
2. inspect the external recruiting/worknet payload shape in more detail
3. define the external normalized recruiting payload contract
4. build the first domain adapter into StrataWiki
5. start the first end-to-end vertical slice from ingestion to personal retrieval

## Open Questions

- what exact shape should the external recruiting normalized payload take
- should the first adapter target `SourceRecord` or `IngestionBatch`
- how should snapshot IDs be generated and persisted in v1
- what minimum DDL is needed to support the first end-to-end slice without over-modeling early
