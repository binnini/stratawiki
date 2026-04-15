# Technology Decision Memo

## Purpose

This document is a working decision memo for the first implementation of StrataWiki.

It is intentionally not the final technical architecture.

The goal is to:
- identify which technical choices must be made early
- separate immediate decisions from deferred decisions
- define evaluation criteria for each decision
- provide a concrete starting stack for the first vertical slice
- make later revision explicit rather than accidental

This document should be refined through implementation, not treated as frozen from day one.

## Decision Philosophy

StrataWiki should avoid two common mistakes:

- under-designing core storage and state boundaries
- overbuilding infrastructure before the first useful end-to-end slice works

Therefore, technology choices should follow these principles:

- prefer the simplest technology that matches the current layer model
- optimize for correctness and inspectability first
- delay expensive infrastructure until the problem is proven
- choose technologies that preserve migration options
- keep canonical storage separate from rendered views

## Service and Database Position

StrataWiki should be treated as a separate knowledge backend service.

That implies:

- PostgreSQL is a separate infrastructure dependency
- StrataWiki owns schema and migrations
- a separate WAS may consume StrataWiki but should not absorb its canonical data lifecycle logic

## What Must Be Decided Early

These choices affect the entire implementation and should be settled before substantial coding begins.

### 1. Primary implementation language and packaging

Questions:
- continue with Python or not
- how to structure packaging and project bootstrap
- how to model schemas and interfaces

Current working assumption:
- Python 3.11+
- `pyproject.toml`
- package source under `src/`

Why it matters:
- affects all adapter, MCP, and schema work

### 2. Fact canonical store

Questions:
- PostgreSQL
- SQLite for early prototyping
- document store instead of RDBMS

Why it matters:
- Fact is the canonical observed layer
- dedupe, identity, and relation integrity depend on this choice

### 3. Interpretation canonical store

Questions:
- PostgreSQL JSONB
- MongoDB
- another document-oriented store

Why it matters:
- Interpretation is flexible, versioned, and relation-heavy
- the wrong choice can make either mutation or retrieval awkward

### 4. Personal metadata and rendered storage

Questions:
- user metadata in PostgreSQL
- markdown bodies on filesystem
- object storage for rendered outputs later

Why it matters:
- Personal outputs must be readable, scoped, and stale-aware

### 5. Projection and background job mechanism

Questions:
- outbox plus worker
- cron or scheduled jobs
- lightweight queue
- event broker later

Why it matters:
- Fact to Interpretation and Interpretation to Personal are asynchronous by design

### 6. Graph and dependency storage approach

Questions:
- relational reverse dependency tables plus derived graph artifacts
- dedicated graph database
- mixed model

Why it matters:
- retrieval expansion and invalidation routing depend on this choice

### 7. Retrieval indexing approach

Questions:
- lexical only initially
- embeddings from day one
- hybrid lexical plus vector

Why it matters:
- query quality and cost profile depend heavily on this decision

### 8. ACL and scope enforcement model

Questions:
- application-level filtering only
- database-level row filtering for some layers
- how to represent `shared`, `tenant`, and `user` scope consistently

Why it matters:
- multi-user safety depends on it

## What Should Be Deferred

These decisions are important, but should not block the first implementation slice.

- Kafka or heavyweight event bus adoption
- dedicated vector database
- dedicated graph database
- multi-region deployment
- warehouse or OLAP replica
- advanced observability stack
- high-complexity workflow orchestration

These should be revisited only if first-slice constraints prove they are needed.

## Decision Criteria

Each technology choice should be judged against the same criteria.

### Correctness

- does it preserve layer boundaries clearly
- does it support provenance and snapshot traceability
- does it make stale or invalid state understandable

### Operational Simplicity

- how many moving pieces does it introduce
- how hard is it to run locally and in early production
- how hard is it to debug

### Evolution Cost

- can we migrate away later
- does it lock us into one query model too early
- does it support schema evolution without major rewrites

### Performance Profile

- is it acceptable for the first vertical slice
- does it support incremental scaling
- does it fit the expected read/write pattern of the layer

### Multi-User Fitness

- does it work with shared plus tenant plus user scope
- does it support access filtering safely
- does it work with snapshot-aware caching and invalidation

## Current Baseline Recommendation

The following choices are now the active implementation baseline for version one.

### Runtime

- Python 3.11+
- `pyproject.toml`
- package structure under `src/wiki_mcp/`

### Fact Layer

- PostgreSQL
- SQLite is not the assumed canonical store for StrataWiki

Reasoning:
- Fact needs normalization, identity control, relations, and replayability

### Interpretation Canonical Layer

- PostgreSQL JSONB for version one
- MongoDB remains a later migration option if interpretation storage becomes the primary bottleneck

### Personal Layer

- profile and metadata in PostgreSQL
- rendered markdown bodies on the filesystem initially
- object storage remains a later option if needed

### Projection Mechanism

- outbox plus worker
- scheduled jobs may exist for support tasks, but the primary projection model is outbox plus worker
- do not adopt heavyweight broker infrastructure yet

### Graph and Dependency

- explicit reverse dependency indexes in PostgreSQL plus derived graph artifacts
- do not require a dedicated graph database in version one

### Retrieval

- structured filtering plus lexical retrieval
- add embeddings only if query evidence shows lexical retrieval is insufficient
- prefer hybrid search only after query logs justify it

## Confirmed Version-One Decisions

The following choices are now confirmed for version one.

- Fact store: PostgreSQL
- Interpretation canonical store: PostgreSQL JSONB
- Personal metadata store: PostgreSQL
- Personal rendered body: filesystem markdown
- Projection mechanism: outbox plus worker
- Graph and dependency storage: PostgreSQL reverse dependency indexes plus derived graph artifacts
- Retrieval indexing: structured filtering plus lexical retrieval
- ACL enforcement: application-level scope enforcement
- Ingestion structure: core pipeline plus domain ingestion interface
- Migration tooling: Alembic
- Postgres driver baseline: psycopg
- Local DB bootstrap baseline: `docker compose` + `alembic upgrade head`

## Current Implementation Note

The current repository now contains the first concrete PostgreSQL baseline.

Implemented pieces include:

- Alembic configuration and initial migration
- logical schemas for `fact`, `interp`, `personal`, `ops`, and `graph`
- initial envelope-first tables for v1
- snapshot pointer plus snapshot publication history
- worker-friendly outbox table
- local PostgreSQL bootstrap via `docker-compose.yml` and scripts

This does not mean all storage policy is finalized.
It means the structural storage baseline is now implemented and can be validated against real repository behavior.

## Deferred or Revisit-Later Decisions

These remain intentionally open for later phases.

- MongoDB as a future Interpretation store migration target
- object storage for rendered Personal bodies
- embeddings or hybrid retrieval
- dedicated graph database
- storage-level RLS hardening
- heavyweight event bus adoption
- normalized domain-specific canonical tables beyond the current envelope-first baseline
- final status taxonomy for interpretation, personal, and outbox flows

## Revisit Triggers

A technology choice should be reconsidered when one of these happens.

### Fact Store Revisit Trigger

- dedupe and relation management become awkward enough to slow core development
- scope filtering needs stronger guarantees than the current store can provide

### Interpretation Store Revisit Trigger

- interpretation updates are too expensive or too rigid
- rendering and retrieval need richer indexing than the chosen store supports well

### Projection Mechanism Revisit Trigger

- outbox plus worker becomes operationally unreliable under load
- dependency routing latency becomes unacceptable

### Retrieval Revisit Trigger

- query logs show lexical retrieval misses key relevant records too often
- user-facing quality depends on semantic expansion not achievable with current indexing

### Graph Storage Revisit Trigger

- dependency traversal or impact analysis becomes too slow with current indexes
- graph maintenance cost outweighs the benefit of derived graph artifacts

## Decision Order Status

The initial technology decision sequence has been completed for version one:

1. Fact store: decided
2. Interpretation canonical store: decided
3. Personal metadata and rendered storage: decided
4. projection mechanism: decided
5. graph and dependency storage: decided
6. retrieval indexing strategy: decided
7. ACL enforcement boundaries: decided
8. migration and bootstrap baseline: decided

## First Slice Constraint

All technical decisions should be tested against one question:

Can this choice help us deliver the first recruiting vertical slice quickly without blocking later evolution?

The first slice should cover:
- one source connector
- recruiting Fact ingest
- one Interpretation family
- one Personal strategy flow
- one dependency impact path

If a technology does not materially help that slice, it should probably be deferred.

## Status

This memo is active and incomplete.

It should be updated as decisions are discussed and as implementation reveals constraints that were not obvious during design.
