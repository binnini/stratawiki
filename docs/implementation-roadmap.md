# Implementation Roadmap

## Purpose

This document replaces the earlier migration-focused plan with a roadmap aligned to the current three-layer MCP architecture.

The earlier plan assumed a relatively direct conversion of a local LLM Wiki repository into MCP tools.

The current direction is broader:

- multi-user
- three-layer storage
- snapshot-aware derivation
- graph-based dependency routing
- bounded LLM orchestration and retrieval
- domain-plugin extensibility

This roadmap focuses on implementation order rather than repository migration mechanics.

## Guiding Principles

- stabilize core contracts before broadening integrations
- prefer one thin vertical slice over many partial subsystems
- separate canonical storage from rendered markdown early
- introduce LLM abstraction early, not as a late add-on
- design for explainability and invalidation from the beginning
- treat deployment and operator visibility as architectural constraints
- avoid premature infrastructure complexity

## Cross-Cutting Workstreams

The following workstreams cut across multiple phases and should be treated as first-class implementation concerns rather than optional follow-up tasks.

### Retrieval and Orchestration

This workstream includes:

- curated retrieval
- exploratory retrieval
- graph-backed retrieval
- markdown-search-backed retrieval
- context compaction
- provider-agnostic LLM orchestration

This workstream becomes relevant as early as `Interpretation` generation and should be implemented incrementally across phases rather than deferred until the end.

### Operator Tooling

This workstream includes:

- proposal review and publish visibility
- snapshot status inspection
- cache and stale inspection
- graph and dependency inspection
- job status and failure inspection
- explainability tools

This workstream should grow alongside shared interpretation and cache adoption.

### Deployment and Runtime Readiness

This workstream includes:

- process topology assumptions
- worker and scheduler compatibility
- durable versus ephemeral state separation
- background job execution model
- runtime observability baselines

See `docs/deployment-and-operations-spec.md` for the runtime constraints view.

## Implementation Quick Reference

| Area | Primary owner | Early reference spec |
|---|---|---|
| Fact write authority | program | `docs/three-layer-data-model-spec.md` |
| Interpretation lifecycle | LLM generation plus program validation | `docs/interpretation-schema-and-lifecycle-spec.md` |
| Retrieval mode policy | retrieval and orchestration layer | `docs/llm-orchestration-and-retrieval-spec.md` |
| Graph traversal and impact | graph layer | `docs/graph-index-and-propagation-spec.md` |
| Cache key and stale policy | cache and snapshot layer | `docs/cache-invalidation-consistency-spec.md` |
| Runtime topology | deployment and operations | `docs/deployment-and-operations-spec.md` |

## Phase 1: Core Contracts and LLM Interface

Objective:

- lock the architectural seams before building adapters or UI-facing features

Deliverables:

- three-layer data model primitives
- snapshot tuple model
- schema versioning policy
- shared scope model: shared, tenant, user
- MCP tool contract baseline
- provider-agnostic LLM gateway contract
- retrieval mode baseline
- interpretation lifecycle baseline

Implementation tasks:

- define Fact, Interpretation, Personal record interfaces
- define profile model
- define provenance model
- define graph node and edge metadata
- define structured error model
- define LLM gateway interface
- define prompt and schema version metadata policy
- define curated versus exploratory retrieval contract

Exit criteria:

- tool and data contracts are stable enough to code against

Depends on:

- no prior phase

Primary specs:

- `docs/three-layer-data-model-spec.md`
- `docs/llm-orchestration-and-retrieval-spec.md`
- `docs/mcp-tool-contract-spec.md`

## Phase 2: Canonical Fact Slice

Objective:

- implement the first reliable canonical write path

Deliverables:

- source normalization pipeline
- Fact persistence
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

Exit criteria:

- facts can be ingested, deduped, queried, and versioned

Depends on:

- Phase 1 contracts and schema baselines

Primary specs:

- `docs/three-layer-data-model-spec.md`
- `docs/mcp-architecture.md`

## Phase 3: Interpretation Canonical Layer

Objective:

- establish the shared derived meaning layer

Deliverables:

- interpretation record store
- interpretation family partitions
- interpretation snapshot publishing
- interpretation proposal and publish lifecycle
- first LLM-backed interpretation generation path

Implementation tasks:

- build one interpretation family end-to-end
- attach evidence references to facts
- attach confidence and freshness metadata
- implement build-and-swap or family-scoped publish
- implement proposal validation and promotion rules
- implement a minimal worker-compatible interpretation generation flow

Recommended initial interpretation families:

- market_trend
- skill_gap_pattern
- regional_opportunity_summary

Exit criteria:

- shared interpretations can be generated and refreshed independently of Personal

Depends on:

- Phase 1 contracts
- Phase 2 Fact slice

Primary specs:

- `docs/interpretation-schema-and-lifecycle-spec.md`
- `docs/llm-orchestration-and-retrieval-spec.md`

## Phase 4: Retrieval and Orchestration Slice

Objective:

- establish the first end-to-end retrieval and LLM orchestration path

Deliverables:

- curated retrieval flow
- retrieval backend abstraction
- context compaction pipeline
- first bounded exploratory retrieval path

Implementation tasks:

- implement `Personal -> Interpretation -> Fact` curated retrieval
- define graph versus markdown-search backend interfaces
- implement context compaction before generation
- implement exploratory retrieval authorization and limits
- attach retrieval mode and backend metadata to outputs

Exit criteria:

- at least one user-facing generation path works through a stable retrieval and orchestration layer

Depends on:

- Phase 1 contracts
- Phase 2 Fact slice
- Phase 3 Interpretation lifecycle and generation

Primary specs:

- `docs/llm-orchestration-and-retrieval-spec.md`
- `docs/graph-index-and-propagation-spec.md`
- `docs/mcp-tool-contract-spec.md`

## Phase 5: Rendered Shared Wiki Views

Objective:

- restore readable wiki-like exploration without making markdown the sole source of truth

Deliverables:

- shared markdown rendering pipeline
- rendered page metadata
- snapshot-aware page output

Implementation tasks:

- render shared interpretation pages
- attach render provenance
- generate page paths by family and segment
- support read access through MCP

Exit criteria:

- shared insight can be consumed as human-readable wiki pages

Depends on:

- Phase 3 Interpretation publication model

Primary specs:

- `docs/interpretation-schema-and-lifecycle-spec.md`
- `docs/mcp-architecture.md`

## Phase 6: Personal Layer

Objective:

- implement user-scoped strategy and note generation

Deliverables:

- profile storage
- personal record storage
- anchor model
- personal markdown rendering

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

Exit criteria:

- user-scoped strategy generation works with clear upstream references

Depends on:

- Phase 3 Interpretation layer
- Phase 4 Retrieval and orchestration
- Phase 5 rendered shared views where needed

Primary specs:

- `docs/three-layer-data-model-spec.md`
- `docs/llm-orchestration-and-retrieval-spec.md`

## Phase 7: Graph and Dependency Routing

Objective:

- make retrieval expansion and invalidation precise

Deliverables:

- semantic graph
- dependency reverse index
- impact analysis tools

Implementation tasks:

- create graph node and edge builders
- implement dependency reverse index
- implement `get_dependency_impact`
- implement graph neighbor inspection
- ensure scope-aware filtering

Exit criteria:

- the system can explain and route downstream impact of upstream changes

Depends on:

- Phase 3 Interpretation records
- Phase 4 retrieval abstractions

Primary specs:

- `docs/graph-index-and-propagation-spec.md`
- `docs/mcp-architecture.md`

## Phase 8: Cache, Snapshot, and Retrieval Optimization

Objective:

- control compute cost and stale state explicitly

Deliverables:

- cache key model
- stale versus invalid states
- cache inspection tools
- snapshot status inspection
- retrieval cache strategy
- markdown-search cache strategy if markdown retrieval is enabled

Implementation tasks:

- implement retrieval cache
- implement personal answer cache
- implement rendered page cache
- implement graph traversal or graph summary cache as needed
- implement markdown-search cache if markdown retrieval is enabled
- implement `get_cache_status`
- implement `get_snapshot_status`

Exit criteria:

- the system can answer whether outputs are fresh, stale, or invalid

Depends on:

- Phase 3 Interpretation snapshots
- Phase 4 retrieval metadata
- Phase 7 graph and dependency routing

Primary specs:

- `docs/cache-invalidation-consistency-spec.md`
- `docs/llm-orchestration-and-retrieval-spec.md`

## Phase 9: ACL and Multi-Tenant Hardening

Objective:

- make scope boundaries enforceable across all layers

Deliverables:

- shared, tenant, and user scope enforcement
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

Depends on:

- all prior read and write paths being available

Primary specs:

- `docs/three-layer-data-model-spec.md`
- `docs/graph-index-and-propagation-spec.md`
- `docs/mcp-tool-contract-spec.md`

## Phase 10: Operator Tooling and Operational Visibility

Objective:

- make the system operable and inspectable by humans

Deliverables:

- proposal review visibility
- snapshot and cache inspection views
- job status visibility
- explainability inspection tools
- graph and dependency inspection views

Implementation tasks:

- expose proposal review and publish status
- expose job and worker status
- expose snapshot and cache inspection flows
- expose explanation metadata for changed outputs
- expose graph and dependency inspection tools for operators

Exit criteria:

- an operator can understand what changed, what is stale, what is running, and what is safe to publish

Depends on:

- Phase 3 lifecycle
- Phase 7 dependency routing
- Phase 8 cache and snapshot status

Primary specs:

- `docs/deployment-and-operations-spec.md`
- `docs/cache-invalidation-consistency-spec.md`
- `docs/mcp-tool-contract-spec.md`

## Phase 11: Deployment and Runtime Readiness

Objective:

- ensure the system is deployable without changing its core architecture

Deliverables:

- server, worker, and scheduler compatible runtime boundaries
- durable versus ephemeral state policy
- background job execution baseline
- runtime observability baseline

Implementation tasks:

- separate request path and background path assumptions
- validate worker-compatible interpretation and graph jobs
- validate runtime state placement assumptions
- validate observability requirements for jobs, snapshots, caches, and indexes

Exit criteria:

- the system can run in a minimal multi-process deployment model without architectural redesign

Depends on:

- background-capable work from phases 3, 7, and 8
- operator visibility from phase 10

Primary specs:

- `docs/deployment-and-operations-spec.md`

## Phase 12: Domain Plugin Generalization

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

1. scaffold the repository around the current docs
2. implement the recruiting Fact slice
3. implement one interpretation family and its rendered page
4. implement one personal query flow with anchors
5. implement one dependency impact tool
