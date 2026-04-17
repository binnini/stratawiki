# 2026-04-15 Ingestion Flow

## Purpose
This note captures the current end-to-end ingestion path as it exists in code and architecture decisions.
It is intentionally practical and implementation-oriented.

## Current End-To-End Flow

1. External source system fetches raw provider data
2. External integration normalizes provider-specific responses into a domain-facing payload
3. StrataWiki external adapter converts that payload into a `SourceRecord`
4. Domain ingestion plugin converts the `SourceRecord` into:
   - `FactRecord[]`
   - `FactRelation[]`
   - `ValidationResult`
5. `CoreIngestionService` will orchestrate persistence and projection
6. Repository layer will persist canonical records and append outbox events
7. Worker path will later rebuild downstream interpretation/rendered state

## Current Concrete Example

The first concrete implementation path is:

- external WorkNet normalized recruiting payload
- `WorknetRecruitingExternalAdapter`
- `RecruitingSourceIngestionPlugin`
- future `CoreIngestionService`
- future repositories / outbox / snapshots

## Layer Responsibilities

### External integration
Owns:
- provider API calls
- provider-specific parsing
- source/domain-level normalization

Does not own:
- StrataWiki canonical facts
- StrataWiki snapshots
- StrataWiki outbox
- StrataWiki dependency graph

### StrataWiki external adapter
Owns:
- translation from external normalized payload to `SourceRecord`
- metadata packing
- readable markdown body rendering for the source envelope

Stops at:
- `SourceRecord`

### Domain ingestion plugin
Owns:
- source acceptance check
- source normalization inside the domain boundary
- first-pass fact decomposition
- relation extraction
- validation

Current recruiting decomposition is intentionally thin:
- `job_posting`
- `company`
- `job`
- `recruitment_section`

### Core ingestion service
Will own:
- plugin selection
- batch preparation
- repository writes
- snapshot publication
- outbox append
- ingestion result assembly

### Repository layer
Will own:
- PostgreSQL writes for canonical data
- PostgreSQL writes for snapshots/outbox/dependency metadata
- filesystem writes for rendered artifacts

## Why This Split Exists

The split is designed to avoid two bad outcomes:

1. External systems becoming tightly coupled to StrataWiki internals
2. StrataWiki core becoming tightly coupled to provider-specific response formats

The current boundary strategy is:

- external systems expose controlled intermediate payloads
- StrataWiki adapters translate into `SourceRecord`
- domain plugins translate into canonical fact envelopes
- repositories isolate physical storage

## Current Gaps

The flow is not complete yet.
The missing pieces are:

- `CoreIngestionService` implementation
- repository integration tests
- actual PostgreSQL schema and migrations
- snapshot publication implementation
- outbox event append and worker consumption
- interpretation rebuild path
- rendered page metadata + dependency update path

## Practical Rule

When extending ingestion, follow this rule:

- if a change is provider-specific, put it in the external integration or external adapter
- if a change is domain-semantic, put it in the domain plugin
- if a change is persistence/projection-related, put it in core services or repositories
