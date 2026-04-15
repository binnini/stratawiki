# Implementation Roadmap

## Purpose

This document replaces the earlier migration-focused plan with a roadmap aligned to the current three-layer MCP architecture.

The earlier plan assumed a relatively direct conversion of a local LLM Wiki repository into MCP tools.

The current direction is broader:

- multi-user
- three-layer storage
- snapshot-aware derivation
- graph-based dependency routing
- domain-plugin extensibility

This roadmap focuses on implementation order rather than repository migration mechanics.

## Guiding Principles

- stabilize core contracts before broadening integrations
- prefer one thin vertical slice over many partial subsystems
- separate canonical storage from rendered markdown early
- design for explainability and invalidation from the beginning
- avoid premature infrastructure complexity

## Current Status Snapshot

A concrete PostgreSQL storage baseline now exists in the repository.

Completed baseline items:

- Alembic migration setup
- initial PostgreSQL logical schemas
- envelope-first Fact storage tables
- Interpretation canonical table baseline
- Personal metadata table baseline
- snapshot pointer and publication tables
- worker-friendly outbox table
- dependency edge and rendered page metadata tables
- local PostgreSQL bootstrap via Docker Compose and scripts

This means Phase 1 and the storage-heavy portion of Phase 2 now have an executable baseline rather than only design documents.

## Phase 1: Core Contracts

Objective:

- lock the architectural seams before building adapters or UI-facing features

Deliverables:

- three-layer data model primitives
- snapshot tuple model
- schema versioning policy
- shared scope model: shared, tenant, user
- MCP tool contract baseline

Implementation tasks:

- define Fact, Interpretation, Personal record interfaces
- define profile model
- define provenance model
- define graph node and edge metadata
- define structured error model

Status:

- largely complete at the contract level
- Postgres repository contracts are now wired to an initial DB baseline

Exit criteria:

- tool and data contracts are stable enough to code against

## Phase 2: Canonical Fact Slice

Objective:

- implement the first reliable canonical write path

Deliverables:

- source normalization pipeline
- PostgreSQL-backed Fact persistence
- dedupe logic
- fact snapshot publishing

Implementation tasks:

- implement `SourceRecord`
- build one source connector
- implement canonical Fact write path
- add relation persistence
- publish fact snapshot metadata

Recommended initial domain:

- recruiting

Recommended first fact entities:

- job_posting
- company
- role
- skill
- location

Status:

- envelope-first Fact persistence baseline now exists
- fact snapshot publication storage baseline now exists
- source-specific canonicalization and write orchestration remain to be implemented

Exit criteria:

- facts can be ingested, deduped, queried, and versioned

## Phase 3: Interpretation Canonical Layer

Objective:

- establish the shared derived meaning layer

Deliverables:

- PostgreSQL JSONB-backed interpretation record store
- interpretation family partitions
- interpretation snapshot publishing

Implementation tasks:

- build one interpretation family end-to-end
- attach evidence references to facts
- attach confidence and freshness metadata
- implement build-and-swap or family-scoped publish

Recommended initial interpretation families:

- market_trend
- skill_gap_pattern
- regional_opportunity_summary

Status:

- interpretation canonical storage baseline now exists
- family-level generation and refresh logic remain to be implemented

Exit criteria:

- shared interpretations can be generated and refreshed independently of Personal

## Phase 4: Rendered Shared Wiki Views

Objective:

- restore readable wiki-like exploration without making markdown the sole source of truth

Deliverables:

- shared markdown rendering pipeline
- rendered page metadata
- snapshot-aware page output
- filesystem-backed rendered output

Implementation tasks:

- render shared interpretation pages
- attach render provenance
- generate page paths by family and segment
- support read access through MCP

Status:

- rendered page metadata storage baseline now exists in PostgreSQL
- rendering pipeline itself remains to be implemented

Exit criteria:

- shared insight can be consumed as human-readable wiki pages

## Phase 5: Personal Layer

Objective:

- implement user-scoped strategy and note generation

Deliverables:

- PostgreSQL-backed profile storage
- PostgreSQL-backed personal metadata storage
- anchor model
- filesystem markdown rendering for personal outputs

Implementation tasks:

- define profile schema
- implement `query_personal_knowledge`
- implement `create_personal_plan`
- persist anchors and based-on snapshot tuples
- add stale markers for personal outputs

Recommended first personal record families:

- career_transition_plan
- profile_gap_analysis
- weekly_action_plan

Status:

- profile context and personal metadata storage baseline now exist
- personal generation and stale-state behavior remain to be implemented

Exit criteria:

- user-scoped strategy generation works with clear upstream references

## Phase 6: Graph and Dependency Routing

Objective:

- make retrieval expansion and invalidation precise

Deliverables:

- semantic graph artifacts
- PostgreSQL-backed dependency reverse index
- impact analysis tools

Implementation tasks:

- create graph node and edge builders
- implement dependency reverse index
- implement `get_dependency_impact`
- implement graph neighbor inspection
- ensure scope-aware filtering

Status:

- dependency edge and impact lookup storage baseline now exist
- graph builders and richer routing semantics remain to be implemented

Exit criteria:

- the system can explain and route downstream impact of upstream changes

## Phase 7: Cache and Snapshot Operations

Objective:

- control compute cost and stale state explicitly

Deliverables:

- cache key model
- stale versus invalid states
- cache inspection tools
- snapshot status inspection
- outbox plus worker projection flow

Implementation tasks:

- implement retrieval cache
- implement personal answer cache
- implement rendered page cache
- implement `get_cache_status`
- implement `get_snapshot_status`

Status:

- snapshot pointer/publication storage and outbox storage now exist
- worker flow, cache policies, and inspection tools remain to be implemented

Exit criteria:

- the system can answer whether outputs are fresh, stale, or invalid

## Phase 8: ACL and Multi-Tenant Hardening

Objective:

- make scope boundaries enforceable across all layers

Deliverables:

- shared, tenant, and user scope enforcement at the application layer
- retrieval filtering
- graph traversal filtering
- provenance filtering

Implementation tasks:

- add access checks to all MCP tools
- enforce scope at graph traversal time
- enforce scope at render retrieval time
- ensure personal caches never leak cross-user state

Exit criteria:

- scope is enforced end-to-end, not just at page rendering

## Phase 9: Domain Plugin Generalization

Objective:

- prove the core is reusable beyond recruiting

Deliverables:

- domain plugin contract
- one second domain stub or pilot

Implementation tasks:

- extract domain-specific schemas into plugin modules
- extract rendering templates by domain
- extract freshness defaults by domain
- define plugin registration path

Possible second domains:

- finance
- health and habit coaching

Exit criteria:

- the core no longer has recruiting assumptions baked into its architecture

## Recommended First Vertical Slice

Do not start with all three layers at full depth.

Recommended initial thin slice:

1. recruiting domain
2. one source connector
3. Fact ingest for job postings
4. one interpretation family
5. one personal strategy output
6. one dependency impact path

This is enough to validate:

- storage separation
- snapshot derivation
- stale handling
- user-facing usefulness

## Deferred Until Needed

These are useful, but should not block the first implementation:

- heavy event brokers
- complex multi-region deployment
- many external connectors
- rich graph visualization UI
- generalized analytics warehouse

## Success Criteria

The roadmap is functionally successful when:

- a fact change can be ingested and versioned
- a shared interpretation can be rebuilt from facts
- a personal plan can be generated from personal plus shared context
- graph or dependency lookup can explain downstream impact
- stale and invalid states are inspectable
- access scope is enforced consistently

## Recommended Immediate Next Build Steps

1. run and verify `alembic upgrade head` against local PostgreSQL
2. add repository-level smoke tests for Postgres persistence paths
3. implement the recruiting Fact slice on top of the envelope-first schema
4. implement one interpretation family and its rendered page
