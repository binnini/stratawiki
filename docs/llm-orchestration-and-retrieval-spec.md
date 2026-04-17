# LLM Orchestration and Retrieval Spec

## Purpose

This document defines how LLMs should read from, write to, and reason over the three-layer StrataWiki system.

It is intended to clarify:

- LLM ownership boundaries
- retrieval modes and tool autonomy
- when graph traversal is allowed
- when markdown search tools such as `qmd` are useful
- how to balance content integrity, creativity, latency, and token efficiency

This document complements:

- `docs/mcp-architecture.md`
- `docs/three-layer-data-model-spec.md`
- `docs/graph-index-and-propagation-spec.md`
- `docs/cache-invalidation-consistency-spec.md`
- `docs/mcp-tool-contract-spec.md`

## Design Position

This system should not treat the LLM as:

- the canonical owner of all data
- an unrestricted database client
- a free-form writer of authoritative graph state

This system should treat the LLM as:

- the primary generator of `Interpretation`
- the primary author of user-facing `Personal` outputs
- a bounded explorer over graph and rendered knowledge artifacts
- a proposal generator whose outputs are validated before promotion into authoritative stores

## Design Goals

- preserve canonical integrity in `Fact`
- allow high-creativity synthesis in `Interpretation`
- allow high-utility personalization in `Personal`
- support both curated retrieval and exploratory retrieval
- make graph access explicit, bounded, and scope-safe
- keep markdown search optional and modular
- improve latency and token efficiency through retrieval discipline

## Non-Goals

- giving the LLM unrestricted write access to canonical truth
- making markdown the only retrieval backend
- requiring `qmd` or any specific search engine
- forcing all user requests through agentic graph exploration

## LLM Ownership Boundary

### `Fact`

`Fact` remains code-owned and authoritative.

LLM may:

- assist with extraction from normalized source records
- summarize fact sets for downstream use
- suggest candidate relations or anomalies

LLM may not:

- directly publish canonical Fact records
- decide dedupe or merge outcomes
- authoritatively mutate canonical identity or dependency state

Program responsibilities:

- source normalization
- Fact persistence
- canonical key management
- dedupe and merge
- relation persistence
- snapshot publishing

### `Interpretation`

`Interpretation` is the primary LLM-authored shared knowledge layer.

LLM may:

- synthesize trends, opportunities, risks, and comparisons
- summarize evidence into reusable shared pages
- propose semantic relations between interpretations
- create candidate new insight families or hypotheses

Program responsibilities:

- evidence validation
- provenance attachment
- snapshot attachment
- schema and status validation
- confidence and freshness calculation
- promotion from proposal to published interpretation

### `Personal`

`Personal` is the primary user-facing LLM-authored layer.

LLM may:

- interpret user intent
- compose personalized plans, notes, and answer pages
- update existing personal pages
- file useful query results back into the personal workspace

Program responsibilities:

- scope enforcement
- profile version lookup
- upstream snapshot binding
- stale and invalid status tracking
- persistence and access control

### Graph and Dependency State

Graph access is split between semantic exploration and operational authority.

LLM may:

- read graph-backed retrieval results
- request bounded semantic exploration
- propose semantic relations

LLM may not:

- write dependency edges directly
- bypass scope rules
- override stale or invalid status

Program responsibilities:

- graph traversal filtering
- dependency reverse index maintenance
- dependency edge writes
- impact analysis
- stale propagation

## Retrieval Modes

The system should support two retrieval modes.

### 1. Curated Retrieval Mode

This should be the default mode.

Flow:

1. Program interprets the request at a high level.
2. Program retrieves candidates from `Personal`, then `Interpretation`, then `Fact`.
3. Program filters by scope, snapshot validity, and freshness policy.
4. Program compacts the context.
5. LLM generates the final answer or document update.

Use cases:

- ordinary personal Q&A
- standard plan generation
- shared interpretation rendering
- low-latency user interactions

Advantages:

- low latency
- lower token usage
- stronger integrity guarantees
- easier caching

### 2. Exploratory Retrieval Mode

This should be used only when the request is open-ended or requires novel synthesis beyond the pre-packed context.

Flow:

1. Program authorizes exploratory mode.
2. LLM uses bounded graph or markdown-search tools.
3. Program enforces scope, hop, and result limits.
4. Exploration results are compacted.
5. LLM produces a proposal, synthesis, or filed result.

Use cases:

- novel cross-cutting insight generation
- open-ended research questions
- schema-misaligned user prompts
- interpretation linting and health checks

Guardrails:

- read-only
- scope-aware
- hop-limited
- result-count limited
- stale-aware
- tool-budget limited

## Retrieval Backends

Retrieval should be backend-agnostic at the orchestration level.

The system may use:

- graph traversal
- markdown search
- canonical store queries
- lexical search
- embedding search
- cache-assisted retrieval

No single backend should be mandatory for every layer.

## Graph Retrieval Strategy

Graph should be the preferred backend when the task requires:

- multi-hop semantic expansion
- evidence tracing
- cross-layer traversal
- contradiction or support inspection
- impact or dependency analysis

Typical graph-driven retrieval patterns:

- `Personal -> Interpretation -> Fact`
- `Interpretation -> evidence Facts`
- `Interpretation -> related Interpretations`
- `Personal -> anchored shared pages`

Graph access should be wrapped in bounded MCP tools rather than exposed as arbitrary raw graph queries.

## Markdown Search Strategy

Markdown search tools such as `qmd` are optional retrieval accelerators for rendered wiki artifacts.

They are most useful when:

- rendered pages become numerous
- page-local lexical or hybrid search becomes a bottleneck
- the LLM benefits from quick retrieval of page snippets before deeper graph expansion

They are less useful for:

- canonical Fact identity work
- dependency propagation
- authoritative stale or invalid decisions

`qmd` or similar search should be treated as a retrieval module, not a system-of-record component.

## Layer-Specific Retrieval Policy

### `Fact`

Preferred backends:

- canonical DB queries
- relation indexes
- optional lexical or embedding search

Graph use:

- evidence traversal
- subject expansion

Markdown search use:

- generally not primary

### `Interpretation`

Preferred backends:

- graph traversal
- document-store queries
- rendered shared page search

Graph use:

- related insight discovery
- support or contradiction exploration
- evidence tracebacks

Markdown search use:

- useful for rendered shared pages
- optional if graph and store queries are sufficient

### `Personal`

Preferred backends:

- personal store queries
- rendered personal page search
- anchor-based graph expansion

Graph use:

- expanding from a personal page into shared interpretations and evidence

Markdown search use:

- especially useful for personal wiki pages
- a strong candidate for `qmd` if personal content is markdown-heavy

## Recommended Initial Retrieval Split

An initial pragmatic split may be:

- `Personal`: markdown search plus anchor lookups
- `Interpretation`: graph-first retrieval plus document lookup
- `Fact`: canonical DB and evidence lookup

This is a recommendation, not a hard rule.

The actual split should be revisited after measuring:

- retrieval latency
- token usage
- page corpus growth
- graph traversal fan-out
- result quality

## Proposal and Promotion Model

When the LLM creates a new interpretation or relation that did not previously exist, the output should first be treated as a proposal.

Recommended stages:

1. `proposed`
2. `validated`
3. `published`
4. `superseded` or `stale` as needed later

This is especially important for:

- newly synthesized interpretation claims
- semantic cross-links
- novel comparison pages
- lint-discovered contradictions

The LLM should be allowed to generate proposals freely within bounded context.
The program should control promotion into authoritative shared state.

## Token and Latency Strategy

The system should optimize for retrieval discipline before model-side tricks.

Recommended strategies:

- prefer curated retrieval by default
- compact context before final generation
- retrieve the smallest useful set of evidence facts
- avoid large raw markdown dumps when structured summaries are available
- cache retrieval results by snapshot tuple where possible
- cache final answers only when scope and snapshot conditions match
- use exploratory mode only when the problem justifies the extra budget

Useful intermediate pattern:

1. retrieve
2. compact
3. generate

instead of:

1. retrieve everything
2. let the LLM sort it out

## Stale and Invalid Awareness

LLM-facing retrieval should honor stale and invalid policy.

Recommended behavior:

- exclude invalid records from normal retrieval
- include stale records only when policy allows fallback
- clearly label stale context when used
- avoid promoting outputs built on invalid upstream state

Exploratory mode may inspect stale artifacts for analysis, but should not silently treat them as current truth.

## Suggested Tool Surface Additions

Examples of bounded retrieval tools that fit this design:

- `search_personal_pages`
- `search_interpretation_pages`
- `explore_related_interpretations`
- `get_evidence_facts`
- `get_personal_anchors`
- `query_markdown_index`
- `propose_interpretation_update`
- `file_personal_answer`

These should expose constrained operations rather than unrestricted datastore access.

## Open Tradeoffs

The following choices are intentionally left open for measurement:

- graph-first versus markdown-search-first retrieval for `Interpretation`
- graph-first versus markdown-search-first retrieval for `Personal`
- whether `qmd` meaningfully improves personal page retrieval over native indexes
- when exploratory mode is triggered automatically versus explicitly
- how much semantic relation writing should be LLM-assisted

These should be decided using practical evaluation on:

- corpus size
- latency targets
- token cost
- retrieval precision
- operator trust and debuggability

## Summary

The LLM should be treated as:

- a bounded explorer
- the main author of `Interpretation`
- the main author of user-facing `Personal` content
- a proposal generator rather than the sole authority on canonical system state

The program should remain responsible for:

- Fact integrity
- scope and access control
- dependency graph authority
- snapshot and cache state
- validation and promotion into durable shared records

Graph and markdown search should coexist as complementary retrieval backends.
The correct balance between them should be measured rather than assumed.
