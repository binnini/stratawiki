# Graph, Index, and Propagation Spec

## Purpose

This document defines how graph, indexing, retrieval, and downstream propagation work in a three-layer LLM Wiki MCP server.

It complements the higher-level architecture, data model, and consistency documents by focusing on:

- graph responsibilities
- layer-specific indexing
- personal query retrieval flow
- fact-to-personal propagation

## Graph Position

Graph should not be treated as a visualization artifact only.

In this system, graph is a cross-layer operational structure that supports:

- semantic navigation
- retrieval expansion
- dependency tracking
- provenance traversal
- invalidation routing

Graph is not the canonical store of Facts, Interpretations, or Personal records. Each layer retains its own storage of record.

## Logical Graph Types

One physical implementation may store these together, but the system should distinguish them conceptually.

### Semantic Graph

Used for knowledge exploration and retrieval expansion.

Examples:

- interpretation supports interpretation
- interpretation relevant to fact entity
- personal note refers to interpretation trend

### Dependency Graph

Used for invalidation, refresh routing, and impact analysis.

Examples:

- interpretation derived from fact
- rendered page built from interpretation
- personal strategy anchored to interpretation

### Retrieval Graph

Used during query-time expansion from an initial match to related records.

Examples:

- from a personal strategy to related interpretations
- from an interpretation to its evidence facts
- from a fact subject to neighboring interpretations

## LLM Traversal Policy

LLM access to graph-backed retrieval should be allowed, but bounded.

Recommended position:

- ordinary user requests should default to curated retrieval
- graph exploration should be enabled when the request is open-ended, cross-cutting, or poorly aligned to a predefined query shape
- LLMs should use bounded tools rather than arbitrary raw graph queries

Recommended guardrails:

- read-only graph access for LLM-facing exploration
- scope and ACL filtering on every traversal step
- hop limits
- result-count limits
- stale and invalid awareness
- tool-budget limits for exploratory sessions

This keeps graph useful for discovery without making it a free-form escape hatch around canonical and scope controls.

## Node Types

Recommended node families:

- `source`
- `fact`
- `interpretation`
- `personal`
- `profile`
- `rendered_page`

Minimum node metadata:

```json
{
  "id": "interp_123",
  "node_type": "interpretation",
  "layer": "interpretation",
  "domain": "recruiting",
  "scope": "shared",
  "tenant_id": null,
  "user_id": null,
  "snapshot_ref": "interp_snap_2026_04_15"
}
```

## Edge Types

Recommended semantic edge types:

- `supports`
- `contradicts`
- `refines`
- `relevant_to`
- `mentions`

Recommended dependency edge types:

- `derived_from`
- `evidence_for`
- `rendered_as`
- `anchored_to`
- `personalizes_for`
- `supersedes`

Minimum edge metadata:

```json
{
  "from": "interp_123",
  "to": "fact_job_posting_999",
  "type": "evidence_for",
  "scope": "shared",
  "confidence": 0.82,
  "snapshot_ref": "interp_snap_2026_04_15"
}
```

## Dependency Index vs Semantic Graph

These should not be conflated.

### Semantic Graph

Answers:

- what is related
- what is similar
- what supports or contradicts what

### Dependency Reverse Index

Answers:

- what must be marked stale if this record changes
- what rendered pages depend on this interpretation
- which personal outputs were built from this snapshot or anchor set

The dependency reverse index is often more important operationally than the semantic graph.

## Layer-Specific Index Strategy

### Fact

Primary index goals:

- exact lookup
- canonical identity
- relation traversal
- filtered evidence retrieval

Recommended indexes:

- primary key and canonical key
- source and external ID
- type index
- updated-at or snapshot index
- relation indexes
- lexical search
- optional embeddings

### Interpretation

Primary index goals:

- subject lookup
- shared insight retrieval
- evidence reverse lookup
- freshness and status filtering

Recommended indexes:

- subject type plus subject ID
- interpretation kind
- evidence.fact_id reverse index
- relation.target_id reverse index
- freshness or expiry
- lexical search
- embedding search
- page family index

### Personal

Primary index goals:

- user-scoped retrieval
- stale detection
- regeneration targeting

Recommended indexes:

- user ID and tenant ID
- profile version
- kind
- based-on snapshot tuple
- anchor reverse index
- stale and status
- lexical search
- embedding search

## Retrieval Principle

For most user-facing requests, retrieval should flow from the most specific layer to the most general layer.

Recommended default order:

- Personal
- Interpretation
- Fact

This keeps retrieval grounded in personalization while still allowing shared interpretation and factual evidence to enter the final answer.

This default order is compatible with both:

- graph-first retrieval for cross-layer expansion
- markdown-search-first retrieval for rendered personal or shared pages

The correct backend split should be treated as an implementation tradeoff, not a fixed architectural law.

## Personal Query Retrieval Flow

### Step 1: Personal Candidate Lookup

Search user-scoped records first:

- recent strategy pages
- saved syntheses
- prior answers
- user notes
- cached plans

This identifies the user's immediate context and may already answer part of the query.

### Step 2: Anchor Expansion into Interpretation

Use personal anchors and based-on snapshot metadata to retrieve related interpretation nodes.

Examples:

- the market trend pages previously used for the user's plan
- the skill gap interpretations relevant to the target role
- the contradiction summaries associated with the user's region or company targets

### Step 3: Interpretation Search and Graph Expansion

Search interpretation using:

- subject match
- kind match
- lexical and embedding similarity
- neighboring nodes in the semantic graph

Depending on implementation choices, this step may also consult markdown-search indexes over rendered interpretation pages before or after graph expansion.

This finds the shared knowledge most relevant to the current user request.

### Step 4: Fact Drill-Down

Only after interpretation retrieval should the system fetch supporting facts.

Examples:

- recent job postings
- latest compensation evidence
- company-specific requirement facts

Fact is usually used to:

- verify freshness
- provide concrete evidence
- enrich the final response

### Step 5: Prompt Assembly

The final LLM context should combine:

- personal context
- top interpretation summaries
- selected fact evidence
- current profile snapshot

This is the main reason Interpretation exists as a middle layer.

## Personal Document Creation Rules

When a personal document or answer is created, it should retain structured references to upper layers.

Minimum linkage:

```json
{
  "based_on": {
    "fact_snapshot": "fact_snap_2026_04_15",
    "interpretation_snapshot": "interp_snap_2026_04_15",
    "profile_version": "profile_v7"
  },
  "anchors": [
    "interp_skill_gap_22",
    "interp_tokyo_market_10",
    "fact_job_posting_999"
  ]
}
```

Without this, the system cannot reliably:

- explain the output
- mark it stale
- regenerate it selectively

## Fact Change Propagation Flow

The system should not immediately regenerate every downstream artifact after every Fact change.

The correct flow is:

1. write canonical Fact changes
2. publish Fact change metadata
3. identify affected Interpretation dependencies
4. mark downstream artifacts stale or invalid
5. recompute according to policy
6. publish new snapshots

## Step-by-Step Propagation

### Step 1: Fact Write

Examples:

- new source ingested
- canonical company record merged
- job posting expired
- compensation data corrected

The Fact layer records:

- affected fact IDs
- change type
- new fact snapshot or delta reference

### Step 2: Dependency Lookup

Use reverse dependency indexes to find:

- interpretation records using the changed facts as evidence
- interpretation families depending on the affected subject type or segment
- rendered shared pages built from those interpretations
- personal records anchored to those interpretations or their snapshots

### Step 3: Stale or Invalid Routing

Not all changes are equal.

Examples:

- new job posting: interpretation likely becomes `stale`
- company merge with new canonical ID: some records become `invalid`
- ACL change: user-scoped records may become `invalid`
- fact deletion or supersession: dependent interpretation may be `stale` or `invalid`

### Step 4: Recompute Policy

Apply the appropriate policy:

- eager recompute for critical shared artifacts
- scheduled recompute for batch domains
- lazy recompute on user access
- active-user warming for hot personal caches

### Step 5: Snapshot Publish

After recomputation:

- publish new interpretation snapshot or family snapshot
- refresh rendered shared pages
- refresh graph summaries if needed
- keep personal outputs tied to their exact upstream tuple

## Removal and Merge Behavior

Hard deletes should be rare.

Prefer:

- `status = deleted`
- `status = superseded`
- alias tables
- `superseded_by` references

This preserves:

- reproducibility
- explanation quality
- stable downstream references

## ACL and Scope Filtering

Graph traversal must respect scope at every stage.

This includes:

- candidate retrieval
- neighbor expansion
- dependency lookup
- rendered page selection
- provenance display

The graph cannot be treated as globally visible if the underlying records are not globally visible.

This applies equally to:

- curated retrieval assembled by the program
- exploratory retrieval initiated by the LLM
- any markdown-search result that is later expanded through graph traversal

## Partitioning Strategy

Graph and propagation should not assume one giant global snapshot.

Recommended partition dimensions:

- domain
- interpretation family
- segment
- tenant

This reduces:

- rebuild time
- invalidation blast radius
- lock contention

## Recommended Operational Rule

Keep semantic relevance and dependency routing separate:

- semantic graph helps find useful context
- dependency index tells the system what must be refreshed

Treating these as the same structure usually creates noisy invalidation or weak retrieval.

## Recommended Next Step

The next implementation-facing document should define:

- concrete graph storage options
- edge construction jobs
- retrieval ranking policy
- MCP tools for dependency inspection and explainability

For orchestration and retrieval-mode policy, see `docs/llm-orchestration-and-retrieval-spec.md`.
