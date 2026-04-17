ㅇ ㄷ에
## Purpose

This document proposes cache, invalidation, and consistency rules for a multi-user three-layer LLM Wiki MCP server.

The system has three knowledge layers:

- Fact
- Interpretation
- Personal

Each layer is mutable at different rates and with different scopes. Without explicit rules, the system will quickly accumulate stale views, conflicting answers, duplicated strategy pages, and expensive recomputation.

## Design Goals

- keep shared knowledge reusable
- keep personal outputs responsive
- avoid recomputing everything on every request
- make staleness visible and controllable
- support explainability for why an answer changed

## Consistency Philosophy

The system does not need strict ACID semantics everywhere.

It should instead use mixed consistency models:

- stronger consistency for Fact writes
- versioned eventual consistency for Interpretation
- snapshot-based or cache-aware consistency for Personal

This is a better fit than forcing a single global transaction model across the entire system.

This also implies the system is projection-driven rather than globally transactional across all stores.

## Consistency by Layer

### Fact

Recommended model:

- strong write consistency within canonical storage
- append or snapshot history where feasible
- explicit dedupe and identity constraints

Why:

- upstream truth must be stable enough to support derivation
- duplicate or conflicting Fact writes contaminate every downstream layer

### Interpretation

Recommended model:

- versioned eventual consistency
- recomputation jobs produce new versions or snapshots
- readers see a coherent interpretation snapshot, not half-written updates

Why:

- interpretation is derived and revisable
- it is acceptable for it to lag behind Fact briefly
- it is not acceptable for readers to see partially updated interpretation state

### Personal

Recommended model:

- snapshot-based derivation
- user-scoped cache consistency
- explicit stale markers when upstream versions change

Why:

- personalized outputs are expensive to compute
- some staleness is acceptable if visible and bounded
- user experience depends on fast retrieval and explainable refresh rules

## Cache Layers

The system should not use a single generic cache.

Recommended cache categories:

- retrieval cache
- interpretation render cache
- personal answer cache
- graph cache
- markdown search cache
- profile-aware planning cache
- dependency lookup cache

## Cache Key Model

All cache keys should reflect the upstream state that makes the output valid.

### Minimum Cache Inputs

- domain
- tenant scope
- user scope if applicable
- fact snapshot version
- interpretation snapshot version
- profile version if applicable
- prompt or template version
- model profile
- retrieval mode
- retrieval backend fingerprint

### Example Cache Key

```text
query_answer:
domain=recruiting:
tenant=tenant_a:
user=user_42:
fact=fact_snap_2026_04_15:
interp=interp_snap_2026_04_15:
profile=profile_v7:
prompt=query_v3:
model=balanced_default:
retrieval=curated:
backend=graph_v1:
hash=abc123
```

Without version-rich keys, stale reuse becomes invisible.

## What Should Be Cached

### Good Candidates

- relevant page sets for frequent queries
- rendered interpretation pages
- user-specific strategy answers
- graph summaries
- markdown search result sets
- expensive interpretation build outputs

### Poor Candidates

- low-level Fact mutation results
- records that are already cheap to compute
- outputs with unstable or unknown provenance
- exploratory retrieval traces with weak scope or snapshot guarantees

## Invalidation Triggers

Invalidation should be dependency-aware, not broad by default.

The system should minimize blast radius by tracking:

- direct evidence dependencies
- subject-family dependencies
- render dependencies
- personal anchor dependencies

### Fact-Level Triggers

Invalidate or mark stale when:

- a new Fact record is created
- a Fact record is updated
- a duplicate merge changes canonical identity
- source ingestion changes the source snapshot

Likely affected:

- interpretation records that depend on the changed facts
- rendered shared wiki pages derived from those interpretations
- personal plans based on affected interpretation snapshots

### Interpretation-Level Triggers

Invalidate or mark stale when:

- an interpretation record is refreshed
- its confidence changes materially
- evidence changes
- a contradiction or superseding interpretation appears

Likely affected:

- rendered interpretation pages
- personal plans or cached answers derived from those interpretation records
- graph traversal caches rooted in affected interpretation records
- markdown-search result caches that index rendered interpretation pages

### Profile-Level Triggers

Invalidate or mark stale when:

- a user profile changes
- a goal changes
- preferences change
- permissions or scope access changes

Likely affected:

- personal plans
- personalized retrieval results
- user-specific answer caches
- user-scoped markdown-search caches

## Stale vs Invalid

These should be distinct states.

### Stale

The output still exists and can be shown, but a fresher version is recommended.

Use stale when:

- upstream changed, but the cached result is still usable
- re-rendering is asynchronous
- user experience benefits from immediate fallback

### Invalid

The output should not be used because one or more assumptions no longer hold.

Use invalid when:

- identity merge changed record references
- permission boundary changed
- required source records were deleted
- the output schema version is obsolete

## Snapshot Model

Readers should query against snapshots, not live partial updates.

Recommended snapshot types:

- `fact_snapshot`
- `interpretation_snapshot`
- `profile_version`

Interpretation snapshots should preferably be partitioned by domain, family, segment, or another bounded unit rather than forcing one global snapshot for the entire system.

### Query Rule

Any expensive shared or personal answer should record the exact upstream snapshot tuple it used.

Example:

```json
{
  "fact_snapshot": "fact_snap_2026_04_15_1200",
  "interpretation_snapshot": "interp_snap_2026_04_15_1230",
  "profile_version": "profile_v7"
}
```

This is the minimum needed for reproducibility and explainability.

If retrieval used exploratory mode or a markdown-search backend, the answer should also retain enough metadata to explain:

- retrieval mode
- search backend or graph backend family
- whether stale fallback was used during retrieval

## Write Model

### Fact Writes

Fact writes should be atomic at the canonical record level.

Recommended pattern:

- write or upsert canonical records
- update relation tables
- commit one fact ingestion batch
- publish a new fact snapshot marker

Fact writes should also emit enough change metadata for downstream dependency routing.

### Interpretation Writes

Interpretation writes should use build-and-swap rather than in-place partial mutation for shared views.

Recommended pattern:

1. compute new interpretation records in a job
2. validate them
3. write them as a new snapshot or new versions
4. atomically switch the "current interpretation snapshot" pointer

This avoids half-built shared knowledge.

This pointer may be global, but in many domains it should be family-scoped or segment-scoped to reduce rebuild latency.

### Personal Writes

Personal writes may be incremental, but should be tied to upstream snapshots.

Recommended pattern:

- create or update personal records
- record the fact, interpretation, and profile versions used
- mark prior outputs as superseded rather than mutating them blindly

## Concurrency Risks

### Shared Interpretation Mutation

Risk:

- two jobs refresh the same interpretation family simultaneously

Mitigation:

- job-level locks by interpretation family and domain
- snapshot publish step
- idempotent writes
- family or segment partitioning where possible

### Personal Regeneration Storms

Risk:

- one interpretation refresh causes many user plans to invalidate at once

Mitigation:

- mark personal outputs stale rather than immediate hard invalidation
- refresh on demand plus background warming
- prioritize active users
- batch or rate-limit regeneration jobs

### Graph Rebuild Collisions

Risk:

- graph build runs during interpretation snapshot turnover

Mitigation:

- bind graph build to a specific snapshot tuple
- publish graph artifacts with the snapshot IDs used

### Access Control Drift

Risk:

- records remain technically valid but become inaccessible because tenant or user scope changed

Mitigation:

- treat ACL changes as invalidation inputs
- filter retrieval, graph traversal, rendering, and provenance responses by scope

## Freshness Policies

Freshness should be domain-aware.

Example policy shape:

```json
{
  "recruiting": {
    "fact_ttl_hours": 24,
    "interpretation_ttl_hours": 24,
    "personal_ttl_hours": 12
  },
  "finance": {
    "fact_ttl_hours": 1,
    "interpretation_ttl_hours": 4,
    "personal_ttl_hours": 1
  }
}
```

This is one reason domain plugins should own freshness defaults.

## Cache Warming Strategy

Recommended approach:

- warm shared interpretation pages after snapshot publish
- warm graph summaries after interpretation refresh
- warm markdown indexes after rendered page updates when markdown retrieval is enabled
- warm personal outputs only for active users or high-value queries

Do not precompute every possible user plan. The state space will explode.

## Async Projection Patterns

The system needs asynchronous projection from Fact to Interpretation and from Interpretation to rendered or cached Personal outputs.

This does not require a heavyweight broker on day one.

Acceptable starting options:

- outbox table plus worker
- job queue
- scheduled projection jobs
- polling-based projection refresh

More sophisticated event infrastructure can be introduced later if scale demands it.

## Explainability Requirements

When an answer changes, the system should be able to say why.

Minimum explanation fields:

- prior snapshot tuple
- current snapshot tuple
- changed fact IDs or interpretation IDs
- changed profile version if relevant
- schema or template version changes if relevant

Example:

```json
{
  "reason": "interpretation_refresh",
  "changed_interpretations": ["interp_123", "interp_220"],
  "old_interpretation_snapshot": "interp_snap_2026_04_14",
  "new_interpretation_snapshot": "interp_snap_2026_04_15"
}
```

## Recommended Operational Rules

- Never query against partially refreshed shared interpretation state
- Never return a personal cached answer without attaching its upstream snapshot tuple
- Never silently reuse exploratory retrieval caches across incompatible snapshot tuples
- Prefer stale-but-explained over silent recomputation failures
- Prefer regeneration by snapshot rather than uncontrolled in-place edits
- Treat rendered markdown pages as cacheable views, not sole authorities
- Treat markdown-search backends as retrieval accelerators, not canonical stores
- Treat scope and ACL changes as first-class invalidation events
- Keep dependency indexes small and explicit to avoid unnecessary cascade fan-out

## Domain Examples

### Recruiting

Recommended model:

- daily or twice-daily Fact snapshots
- daily interpretation refresh
- personal plans refreshed on demand or when a user becomes active

Why:

- the domain usually tolerates some latency
- value comes from stable trends and user strategy, not second-by-second updates

### Finance

Recommended model:

- more frequent Fact snapshots
- shorter TTLs
- stronger invalidation for user-facing plans

Why:

- stale data can quickly change the meaning of analysis

### Health and Habit Coaching

Recommended model:

- periodic Fact ingestion
- interpretation refresh tied to meaningful new data
- conservative personal invalidation to avoid overreacting to noise

Why:

- not every new event should trigger a full strategic rewrite

## Open Design Questions

- Should personal records be regenerated fully or compacted incrementally?
- Which interpretation families deserve build-and-swap snapshots versus per-record updates?
- Which caches are in memory, and which should persist across restarts?
- How aggressive should stale marking be for low-value derived pages?
- What schema migration path should exist for old interpretation and personal records?

## Recommended Next Step

The next spec should define MCP tool contracts that expose:

- snapshot lookup
- cache status
- stale detection
- explainability on result provenance

For graph indexing, retrieval expansion, and dependency routing, see the dedicated graph specification document.
