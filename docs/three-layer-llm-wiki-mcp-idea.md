# 3-Layer LLM Wiki MCP Server Idea

## Purpose

This document captures a product and architecture idea for a multi-user MCP server built around a three-layer knowledge model:

- Fact
- Interpretation
- Personal

The target use case is broader than a single domain. The initial domain may be recruiting and job strategy, but the system should be extensible to other domains without changing its core architecture.

The central design question is:

How can a shared LLM Wiki evolve into a multi-user, domain-flexible MCP server without inheriting all the weaknesses of a markdown-only system?

## Architectural Position

This architecture should be understood as:

- CQRS-inspired rather than strict textbook CQRS
- tiered storage rather than a single persistence model
- snapshot-aware rather than globally ACID across every layer and store

The system separates canonical write-oriented state from rendered read-oriented views and user-scoped overlays.

## Core Thesis

The original LLM Wiki pattern works well for:

- local knowledge accumulation
- human-readable summaries
- agent-managed cross-linking
- synthesis over a manageable corpus

However, once the system becomes:

- multi-user
- partially personalized
- connector-driven
- cache-heavy
- mutation-prone

it starts behaving less like a local note system and more like a data platform.

At that point, one storage strategy is not enough.

The recommended approach is to separate the system into three semantic layers:

- `Fact`: what has been observed
- `Interpretation`: what the observed data appears to mean
- `Personal`: what matters to a specific user, goal, or context

## Why Three Layers

Without explicit layers, several problems get mixed together:

- raw facts get polluted by recommendations
- user-specific judgments leak into shared knowledge
- derived insights are hard to revise without damaging source truth
- markdown pages become both storage and rendering, which creates scaling problems

The three-layer split solves different classes of problems:

- `Fact` provides reproducibility and canonical grounding
- `Interpretation` provides reusable shared meaning
- `Personal` provides individualized strategy, notes, and prioritization

It also limits blast radius:

- shared truth does not need to be rewritten every time user strategy changes
- user strategy does not need to mutate shared interpretation records
- derived shared meaning can be refreshed without rewriting canonical fact storage

## Layer 1: Fact

### Definition

Fact is the canonical record of what the system has observed from sources.

Fact is not:

- a recommendation
- a user-specific strategy
- a trend claim
- an opinionated summary

Fact is:

- normalized source data
- entities and attributes extracted with strong provenance
- timestamps, status, identity, and structural relationships

### What Lives in Fact

Examples across domains:

- recruiting: job posting, company, skill, compensation range, location, application requirement
- finance: transaction, account, instrument, price event, filing, balance snapshot
- health: symptom report, lab result, intervention event, medication record, device reading

### Storage Direction

Fact should usually be stored in an RDBMS or another strongly structured canonical store.

The reason is not necessarily high-frequency OLTP. Even in low-frequency batch domains such as recruiting, Fact still benefits from:

- canonical identifiers
- deduplication
- referential integrity
- snapshot history
- predictable reprocessing
- analytical querying

### Trade-Off

Benefits:

- stable source of truth
- easier dedupe and identity resolution
- better provenance
- easier re-derivation of higher layers
- cleaner constraints and joins

Costs:

- more schema work
- slower iteration than dumping everything to markdown
- harder for end users to inspect directly

### Design Principle

If the answer to "can this be recomputed from sources?" is yes, it is often a Fact or a derivation from Fact, not a Personal artifact.

### Operational Note

Fact is the best candidate for stronger transactional guarantees, but this does not imply that every domain requires OLTP-style latency.

In slower batch-oriented domains such as recruiting, the main reasons to keep a structured Fact layer are:

- normalization
- identity control
- deduplication
- reliable re-derivation
- provenance

## Layer 2: Interpretation

### Definition

Interpretation is the shared, derived meaning of Facts.

This is the layer where the system says:

- what patterns appear to be happening
- what relationships matter
- what tradeoffs emerge
- what tensions or contradictions exist

Interpretation is shared knowledge, not yet user-specific advice.

### What Lives in Interpretation

Examples:

- recruiting: "Mid-level backend roles increasingly prefer production LLM experience"
- finance: "Small-cap volatility increased after earnings misses across the sector"
- health: "Poor sleep appears correlated with late caffeine and missed exercise windows"

Interpretation should also include:

- evidence references
- confidence
- freshness
- supporting and opposing relations
- provenance for how the interpretation was produced

### Two Viable Designs

There are two main ways to store Interpretation:

- markdown or LLM Wiki pages
- canonical NoSQL records

#### Interpretation as LLM Wiki

Benefits:

- human-readable
- naturally explorable through links
- better for direct insight consumption
- good substrate for downstream personal synthesis

Costs:

- expensive CRUD
- hard concurrent mutation
- duplication risk
- weak transactional guarantees
- poor token efficiency if used directly as primary query context

#### Interpretation as NoSQL Canonical Store

Benefits:

- easier partial updates
- easier versioning and status changes
- easier relation metadata and confidence tracking
- better for caching and incremental recomputation

Costs:

- less directly readable to users
- less "discoverable" than a wiki
- requires rendering or serialization for user-facing exploration

### Recommended Direction

Use a hybrid model:

- `Interpretation canonical`: store in NoSQL or another flexible structured store
- `Interpretation rendered`: generate markdown or wiki views for direct reading

This resolves the main trade-off:

- the canonical form supports operations
- the rendered form supports understanding

### Design Principle

Interpretation should be mutable, inspectable, and regenerable.

That makes it a poor fit for markdown-only storage as the primary system of record, but a strong fit for markdown as a presentation layer.

### Operational Note

Interpretation should usually be refreshed through asynchronous projection rather than in-place synchronous mutation across multiple stores.

That does not require Kafka on day one, but it does require some projection mechanism such as:

- outbox-driven jobs
- queue-based recomputation
- scheduled batch refresh
- polling-based projection rebuilds

## Layer 3: Personal

### Definition

Personal is the user-scoped layer.

This layer is specific to:

- a person
- a team
- a goal
- a time horizon
- a preference profile

It contains applied strategy rather than shared meaning.

### What Lives in Personal

Examples:

- recruiting: interview preparation strategy for a user transitioning from data analyst to backend engineer
- finance: a user-specific watchlist strategy and risk reminders
- health: a personalized habit plan based on symptoms, schedule, and tolerance

Personal may include:

- user notes
- user goals
- ranked priorities
- generated plans
- cached strategy trees
- user-specific syntheses

### Storage Direction

Personal is a good fit for LLM Wiki style storage, provided that it is user-scoped and treated as an overlay rather than a mutation of shared knowledge.

Benefits:

- highly readable
- useful as a strategic notebook
- easy to expose directly to users
- good fit for agent-assisted iteration

Costs:

- requires strong access control
- easily becomes stale if not linked to upstream invalidation
- can accumulate redundant strategy pages and cached answers

### Design Principle

Personal should never be the only place where shared facts or shared interpretations live.

Personal should derive from shared layers, not replace them.

### Retrieval Principle

Personal should reference upper layers through anchors and snapshot tuples rather than by copying large amounts of shared content into user pages.

In practice, the default retrieval path is usually:

- Personal
- Interpretation
- Fact

## Why Markdown-Only Breaks Down in Multi-User Systems

The original LLM Wiki assumes relatively simple local ownership.

In a multi-user MCP setting, markdown-only storage creates familiar database problems:

- lost updates
- duplicate entities
- broken references
- stale derived pages
- low token efficiency
- poor cache invalidation
- weak concurrency control
- difficult delete and merge behavior

This does not mean markdown is useless. It means markdown should no longer be the only storage primitive.

## Graph and Indexing Position

Graph should not be treated as a visualization artifact only.

In a multi-layer MCP system, graph acts as:

- a semantic navigation layer
- a dependency tracking layer
- a retrieval expansion layer
- a provenance navigation layer

The graph is not the canonical source of truth for Facts, Interpretations, or Personal records. It is a cross-layer index and dependency system built on top of them.

## Suggested Storage Model

### Fact

- primary storage: RDBMS
- optional rendered outputs: summary pages, audit pages, source pages

### Interpretation

- primary storage: NoSQL or document-oriented canonical store
- optional rendered outputs: shared wiki pages and domain dashboards

### Personal

- primary storage: user-scoped LLM Wiki pages plus profile metadata store
- optional cache: retrieval and answer caches keyed by profile version and upstream snapshot

## Multi-User Concerns

A production MCP server for this architecture must handle:

- shared base knowledge
- tenant-scoped or organization-scoped overlays
- user-private overlays
- profile-aware caching
- versioned interpretation snapshots
- invalidation when Fact changes
- invalidation when user profile changes
- explainability of why a recommendation changed

This is significantly more demanding than a single-user wiki.

## Expected Technical Challenges

The architecture is technically feasible, but several operational risks should be assumed up front.

### Cross-Store Synchronization

Fact, Interpretation, and Personal will often live in different storage systems.

This implies:

- asynchronous projection work
- snapshot publication
- stale marking rather than global synchronous recomputation

### Invalidation Cascades

One changed Fact can affect:

- multiple Interpretation records
- multiple rendered shared pages
- many Personal strategy pages and answer caches

This makes dependency granularity and lazy regeneration important design concerns.

### Snapshot Lag

Build-and-swap interpretation refresh protects reader consistency, but it also introduces freshness lag.

The system should therefore prefer partitioned or family-level refreshes over monolithic global rebuilds where possible.

### Multi-Tenant Access Control

If users or tenants share upper layers while keeping Personal data private, access control must apply consistently to:

- retrieval
- graph traversal
- rendering
- provenance lookups

### Schema Evolution

Because Facts, Interpretations, prompts, and renderers all evolve, the system must treat versioning as a first-class concern.

At minimum:

- record schema versions
- prompt and template versions
- compatibility-aware renderers
- migration rules for stale records

## Trade-Off Summary

### Fact in RDBMS

Strengths:

- structure
- replayability
- dedupe
- canonical identity
- strong provenance

Weaknesses:

- less readable
- more modeling effort

### Interpretation in LLM Wiki

Strengths:

- readable
- navigable
- insight-friendly

Weaknesses:

- weak CRUD
- expensive updates
- poor concurrency characteristics

### Interpretation in NoSQL

Strengths:

- flexible schema
- versionable
- operationally easier
- better for shared mutable derived knowledge

Weaknesses:

- weaker direct user readability
- needs a rendering strategy

### Personal in LLM Wiki

Strengths:

- natural fit for strategy, notes, and personalized plans
- good user experience
- easy to iterate with agents

Weaknesses:

- needs invalidation
- can bloat quickly
- requires good privacy boundaries

## Implementation Direction

The system should be implemented as an MCP server with a domain-neutral core, registered domain-pack artifacts, and domain-specific modules where code is still needed.

### Core Responsibilities

- source ingestion
- canonical IDs and provenance
- fact extraction and normalization
- interpretation generation
- personalization synthesis
- rendering to markdown
- caching and invalidation
- tool-level access control

### Domain Modules Should Provide

- fact schema definitions
- interpretation templates
- entity taxonomy
- domain-specific validation rules
- freshness rules
- domain-specific render templates

## Proposed MCP Capability Areas

- source sync and fetch
- fact ingest
- interpretation build and refresh
- personal plan generation
- wiki page render and retrieval
- graph build
- validation and invalidation
- explainability and provenance lookup

## Domain Example 1: Recruiting and Job Strategy

### Fact

- job postings
- companies
- skills
- role families
- locations
- compensation ranges
- language and visa requirements
- source snapshots

### Interpretation

- market trends by role, region, and seniority
- skill demand shifts
- hiring pattern comparisons
- role-transition difficulty estimates
- common portfolio signals and hiring frictions

Canonical storage direction:

- fact in RDBMS
- interpretation in NoSQL
- rendered shared market wiki pages from interpretation records

### Personal

- user transition strategy
- weekly application plans
- gap analysis against target roles
- interview prep trees
- portfolio recommendations

Rendered as user-scoped wiki pages and cached strategy views.

## Domain Example 2: Personal Finance Guidance

### Fact

- transactions
- accounts
- holdings
- price events
- recurring expenses
- income events

### Interpretation

- spending pattern summaries
- category drift and anomaly detection
- savings pressure trends
- concentration risk summaries
- event-driven portfolio observations

### Personal

- budget adjustment plans
- watchlist notes
- user-specific risk reminders
- monthly action plans

This domain may need stronger privacy, auditability, and more structured policy handling than recruiting.

## Domain Example 3: Health and Habit Coaching

### Fact

- sleep logs
- exercise events
- symptom reports
- medication records
- biometrics
- food or caffeine events

### Interpretation

- probable correlations
- routine stability patterns
- adherence summaries
- possible trigger clusters
- intervention-response patterns

### Personal

- user-specific daily routines
- experiment plans
- symptom management notes
- personalized reminders and strategy trees

This domain requires stronger safety boundaries and caution around recommendation generation.

## Design Decision on Domain Flexibility

The architecture should not hard-code recruiting assumptions into the core.

Recommended split:

- domain-neutral MCP core
- domain-pack artifacts plus domain-owned packages

The core should know how to:

- store and relate layers
- render wiki views
- manage caches
- route LLM calls

The domain module should know:

- what Fact looks like
- what Interpretation means
- what Personal strategies are allowed to generate

## Recommended Position

The most balanced design is:

- `Fact` as structured canonical data
- `Interpretation canonical` as structured derived data
- `Interpretation rendered` as shared wiki output
- `Personal` as user-scoped LLM Wiki output backed by profile metadata and invalidation rules

This preserves what is good about LLM Wiki while avoiding making markdown carry the full burden of a multi-user knowledge system.

## Open Questions

- How much of Interpretation should be pre-rendered versus rendered on demand?
- Should Personal pages be append-only, periodically compacted, or regenerated from profile snapshots?
- How should cross-user caching be partitioned when shared interpretation is stable but user strategy differs?
- What retention and deletion policies should apply to stale personal syntheses?
- Which domains justify stronger transactional guarantees than eventual consistency?

## Next Step

The next design document should specify:

- a concrete data model for all three layers
- cache and invalidation rules
- consistency expectations
- MCP tool contracts for shared and user-scoped operations

For graph, indexing, and propagation details, see the dedicated graph specification document rather than overloading this idea doc with operational mechanics.
