# PostgreSQL Schema Structure

## Purpose

This document defines the PostgreSQL schema structure currently implemented for StrataWiki version one.

The goal is still not to finalize domain-specific normalized tables.

The implemented baseline focuses on:

- generic Fact envelopes in PostgreSQL
- Interpretation canonical records in PostgreSQL JSONB
- Personal metadata in PostgreSQL
- outbox and snapshot operations in PostgreSQL
- graph dependency indexes and rendered page metadata in PostgreSQL

Detailed domain-level normalized tables remain deferred until the domain ingestion interface is exercised with real source data.

## Current Implementation Status

A repository-owned PostgreSQL baseline now exists in the StrataWiki repo.

Current implementation assets:

- `alembic/`
- `alembic.ini`
- initial migration under `alembic/versions/`
- `docker-compose.yml` for local PostgreSQL
- `scripts/bootstrap_db.sh`
- `scripts/db_upgrade.sh`
- `db/README.md`

This means the structural schema approach is no longer only conceptual. A concrete initial migration now defines the version-one storage baseline.

## Guiding Principle

StrataWiki uses:

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

## Implemented Logical Schemas

The implemented version-one structure is:

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

### Implemented Tables

- `fact.record_envelopes`
- `fact.relation_envelopes`

### Current Design

The implemented baseline is envelope-first.

`fact.record_envelopes` currently stores:

- canonical fact identity
- `domain`
- `entity_type`
- `canonical_key`
- explicit scope metadata
- `schema_version`
- `attributes_json`
- `provenance_json`
- timestamps

`fact.relation_envelopes` currently stores:

- domain-neutral relation envelopes
- relation natural key components
- explicit scope metadata
- `schema_version`
- `attributes_json`
- `provenance_json`
- timestamps

### Scope Rule

Both implemented `fact` tables now support:

- `scope`
- `tenant_id`
- `user_id`

Initial data may still be mostly `shared`, but the schema is now multiscoped from day one.

### Notes

The exact domain entities remain intentionally deferred until the domain ingestion interface is in place and real source data has been reviewed.

## `interp` Schema

### Purpose

The `interp` schema stores canonical shared Interpretation records.

This layer represents derived meaning from Facts.

### Implemented Tables

- `interp.record`

### Current Design

The current implementation uses a hybrid structure:

- stable filterable fields as relational columns
- flexible interpretation content in JSONB

`interp.record` currently includes:

- envelope fields such as `domain`, `kind`, `subject_type`, `subject_id`
- explicit scope metadata
- `schema_version`, `status`, `confidence`
- `computed_at`, `expires_at`
- `body_json`
- `provenance_json`
- `render_hints_json`
- `fact_snapshot_id`
- timestamps

### Notes

Row-level `interpretation_snapshot_id` is intentionally not required in `interp.record`.
Publication lineage is handled in `ops`.

## `personal` Schema

### Purpose

The `personal` schema stores user-scoped metadata and profile state.

This is not the same as rendered markdown output.

### Implemented Tables

- `personal.record`
- `personal.profile_context`

### Current Design

`personal.record` currently stores:

- one personal metadata record per id
- explicit scope metadata
- snapshot tuple references
- `body_path`
- `status`
- `schema_version`
- `provenance_json`
- timestamps

`personal.profile_context` currently stores:

- `domain`
- `tenant_id`
- `user_id`
- `profile_version`
- `goals_json`
- `preferences_json`
- `attributes_json`
- timestamps

A unique key on `(domain, tenant_id, user_id)` is part of the implemented baseline.

### Notes

Personal markdown remains valuable, but it is treated as a readable artifact rather than the only state store.

## `ops` Schema

### Purpose

The `ops` schema stores operational state required for asynchronous projection and system coordination.

### Implemented Tables

- `ops.snapshot_pointer`
- `ops.snapshot_publication`
- `ops.outbox_event`

### Current Design

`ops.snapshot_pointer` stores the current published snapshot pointer.

`ops.snapshot_publication` stores minimal publication history and reproducibility lineage.

`ops.outbox_event` is implemented as a worker-friendly outbox table with:

- UUID primary key
- optional `idempotency_key`
- event metadata
- `status`
- `attempt_count`
- scheduling and processing timestamps
- `last_error`
- retry state derived from `status`, `attempt_count`, and `available_at`

The current repository behavior uses:

- `pending` for ready or requeued work
- `claimed` while one worker owns the event
- `processed` after successful completion
- `failed` for terminal failures
- exponential backoff for retryable failures until the max-attempt limit

### Notes

The `ops` schema is now part of the concrete baseline and should not be treated as an afterthought.

## `graph` Schema

### Purpose

The `graph` schema stores graph-adjacent operational structures.

This does not make PostgreSQL the canonical semantic graph store.

Instead, this schema exists to support:

- dependency reverse indexes
- impact analysis
- rendered page metadata lookup

### Implemented Tables

- `graph.dependency_edge`
- `graph.rendered_page`

### Current Design

`graph.dependency_edge` prioritizes reverse lookup and downstream impact routing.

`graph.rendered_page` is currently implemented as a single-table design for both shared and personal rendered artifacts, distinguished by `layer`.

The rendered page table includes:

- `domain`
- `layer`
- `record_id`
- `path`
- explicit scope metadata
- snapshot metadata
- optional `metadata_json`
- timestamps

Current Personal regeneration now rewrites the filesystem artifact and upserts
the matching `graph.rendered_page` row so downstream impact lookup and future
read paths share the same rendered-page metadata.

## Cross-Schema Design Rules

These rules now apply to the implemented baseline.

### 1. Scope Must Be Explicit

Any record that participates in retrieval, rendering, or graph traversal should be able to express:

- `shared`
- `tenant`
- `user`

The implemented baseline uses `text + check constraint`, not PostgreSQL enum.

### 2. Snapshot References Must Be First-Class

Snapshot lineage should not live only in logs or derived explanations.

The current baseline uses:

- record-level snapshot references where appropriate
- `ops.snapshot_pointer` for current pointers
- `ops.snapshot_publication` for minimal publication history

### 3. Schema Versions Must Be Stored

Because the system is expected to evolve, record families retain a `schema_version` where appropriate.

### 4. Domain Normalization Remains Deferred

The current migration intentionally does not create recruiting-final or source-specific normalized tables.

The initial schema is deliberately envelope-first.
