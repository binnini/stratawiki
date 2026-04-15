# PostgreSQL Schema Structure

## Purpose

This document defines the recommended PostgreSQL schema structure for StrataWiki version one.

The goal is not to finalize domain-specific tables yet.

Instead, this document fixes the structural database approach for the confirmed version-one stack:

- Fact in PostgreSQL
- Interpretation canonical in PostgreSQL JSONB
- Personal metadata in PostgreSQL
- outbox and snapshot operations in PostgreSQL
- graph dependency indexes in PostgreSQL

Detailed domain-level table design should be added later after the domain ingestion interface is implemented and real data is inspected.

## Guiding Principle

StrataWiki should use:

- one PostgreSQL database
- multiple logical PostgreSQL schemas

This gives the project:

- operational simplicity
- clear layer boundaries
- easier migrations
- better ownership separation
- a clean path for later extraction if one layer moves to another storage system

## Why Multiple PostgreSQL Schemas

A single flat schema would work technically, but it would weaken conceptual boundaries.

StrataWiki has distinct concerns:

- canonical observed data
- canonical derived meaning
- user-scoped metadata
- projection operations
- dependency indexes and graph artifacts

These should not be mixed arbitrarily.

Logical PostgreSQL schemas provide a clean separation without requiring multiple databases.

## Recommended Logical Schemas

The recommended version-one structure is:

- `fact`
- `interp`
- `personal`
- `ops`
- `graph`

Each schema corresponds to a distinct responsibility.

## `fact` Schema

### Purpose

The `fact` schema stores canonical observed data.

This is the strongest source-of-truth layer in StrataWiki.

### Responsibilities

- canonical entities
- observed attributes
- explicit fact relations
- source snapshots
- deduplication support
- canonical identity resolution
- merge and supersession history

### Design Style

This schema should be relational and normalized where it matters.

Recommended characteristics:

- typed tables
- foreign keys where appropriate
- unique or canonical keys where needed
- explicit relation tables for many-to-many links
- version and status fields

### Notes

The exact domain entities are intentionally deferred until the domain ingestion interface is in place and real source data has been reviewed.

## `interp` Schema

### Purpose

The `interp` schema stores canonical shared Interpretation records.

This layer represents derived meaning from Facts.

### Responsibilities

- interpretation records
- interpretation-to-interpretation relations
- evidence references
- family or segment snapshot publication
- interpretation status and freshness
- render hints and provenance

### Design Style

This schema should use a hybrid structure:

- stable filterable fields as relational columns
- flexible interpretation content in JSONB

Recommended characteristics:

- envelope columns for high-value indexed fields
- JSONB body for interpretation payloads
- explicit relation tables where reverse lookup matters
- snapshot tables for publishable interpretation partitions

### Notes

This schema is intentionally designed so that Interpretation could later migrate to a NoSQL document store without changing the higher-level contracts.

## `personal` Schema

### Purpose

The `personal` schema stores user-scoped metadata and profile state.

This is not the same as rendered markdown output.

### Responsibilities

- user profiles
- profile versions
- personal record metadata
- anchor references into upper layers
- stale and invalid states
- rendered body paths
- provenance and snapshot references

### Design Style

This schema should be relational first.

The readable body of a Personal artifact should not be treated as the primary operational record.

Recommended characteristics:

- one record for personal metadata
- one or more anchor tables for upstream references
- explicit scope, tenant, and user fields
- snapshot tuple references
- rendered file path fields rather than storing all content inline by default

### Notes

Personal markdown remains valuable, but it is treated as a readable artifact rather than the only state store.

## `ops` Schema

### Purpose

The `ops` schema stores operational state required for asynchronous projection and system coordination.

### Responsibilities

- outbox events
- worker coordination
- snapshot pointers
- rebuild jobs
- cache metadata
- projection state

### Design Style

This schema should be small, explicit, and operationally oriented.

Recommended characteristics:

- append-friendly event tables
- retry and processing status fields
- job lifecycle fields
- current snapshot pointer tables
- lightweight cache bookkeeping where needed

### Notes

This schema is critical to the outbox-plus-worker model and should not be treated as an afterthought.

## `graph` Schema

### Purpose

The `graph` schema stores graph-adjacent operational structures.

This does not make PostgreSQL the canonical semantic graph store.

Instead, this schema exists to support:

- dependency reverse indexes
- semantic edge projections
- rendered page source tracking
- impact analysis

### Responsibilities

- dependency edges
- semantic edges
- rendered page metadata
- rendered page source mappings

### Design Style

This schema should prioritize reverse lookup and impact routing over graph-theory elegance.

Recommended characteristics:

- explicit edge tables
- layer and scope metadata on edges
- tables optimized for downstream impact lookup
- no requirement for a dedicated graph database in version one

## Cross-Schema Design Rules

These rules apply across all schemas.

### 1. Scope Must Be Explicit

Any record that participates in retrieval, rendering, or graph traversal should be able to express:

- `shared`
- `tenant`
- `user`

This means scope metadata must be available where needed, not inferred indirectly.

### 2. Snapshot References Must Be First-Class

Snapshot lineage should not live only in logs or derived explanations.

Relevant records should reference:

- fact snapshot
- interpretation snapshot
- profile version

where applicable.

### 3. Schema Versions Must Be Stored

Because the system is expected to evolve, records or record families should retain a `schema_version` where appropriate.

This is especially important for:

- Interpretation
- Personal metadata
- render pipelines
- migration logic

### 4. Filterable Fields Should Not Hide Inside JSONB

JSONB is useful, but the most important filter keys should remain as regular relational columns.

Typical examples:

- domain
- kind
- status
- scope
- tenant_id
- user_id
- subject_type
- subject_id
- snapshot references
- freshness timestamps

### 5. Reverse Lookup Matters More Than Perfect Normalization

StrataWiki depends heavily on:

- stale marking
- invalidation routing
- impact analysis
- provenance inspection

Therefore, relation and dependency tables should be designed for efficient reverse lookup, not only forward modeling purity.

## Recommended V1 Philosophy per Schema

### `fact`

- strongly structured
- relational first
- canonical and conservative

### `interp`

- hybrid structured plus document style
- JSONB-friendly
- optimized for flexible derived knowledge

### `personal`

- relational metadata
- markdown body stored separately on filesystem
- optimized for user scope and refreshability

### `ops`

- explicit operational state
- small but critical

### `graph`

- dependency routing first
- semantic projection second

## What Is Deliberately Deferred

This document does not yet fix:

- exact domain entity tables
- exact domain-specific relation tables
- exact indexes by table
- exact partitioning strategy
- exact migration tooling

These should be added later when:

- the domain ingestion interface is defined
- real source payloads are inspected
- the first domain slice is implemented

## Recommended Next Step

The next database-oriented design task should be one of these:

1. define the domain ingestion interface
2. inspect real domain source payloads
3. draft minimum viable DDL for the first domain slice

The schema structure above should be treated as fixed scaffolding for those later steps.
