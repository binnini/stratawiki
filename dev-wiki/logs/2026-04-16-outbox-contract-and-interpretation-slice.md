# Outbox Contract And Interpretation Slice

## Context

The previous vertical slice ended at:

- external adapter -> `SourceRecord`
- recruiting plugin -> fact envelopes
- core ingestion -> Fact persistence
- fact snapshot publication
- batch-level outbox append

What remained unresolved was whether the outbox payload was concrete enough to support real downstream work, and what the first Interpretation vertical slice should look like.

## Current Question

What is the smallest stable v1 contract that lets a worker consume fact ingestion results and produce shared Interpretation state without pulling source-specific logic back into core or into the worker?

## Observations

- The repository already had `interp.record`, snapshot publication storage, dependency edge storage, and outbox status fields.
- The existing `fact_ingested` event payload only exposed snapshot id and write counters, which was too thin for a deterministic projection worker.
- The current recruiting fact batch naturally includes one `job_posting` plus company/job/section facts, which is enough context for a first shared interpretation without introducing LLM generation yet.
- Outbox table columns already support claim/process/fail state transitions, so a first synchronous worker path can be added without another migration.

## Options

- Keep the outbox as an opaque notification channel and postpone worker semantics again.
- Define a typed v1 payload now, add claim/process repository methods, and implement one deterministic interpretation family.

## Decision or Working Direction

Take the second option.

The implemented v1 contract is:

- ingestion emits `fact_ingested`
- payload includes `domain`, `source_id`, `connector`, `fact_snapshot_id`, `affected_fact_ids`, `affected_entity_types`, scope fields, and write counters
- worker claims pending `fact_ingested` events
- interpretation projection builds one shared recruiting `company_hiring_pattern` record
- projection saves the interpretation, rewrites fact -> interpretation dependency edges, publishes an interpretation snapshot, and emits `interpretation_snapshot_published`
- worker marks the source outbox event `processed` or `failed`

This keeps provider-specific semantics in the adapter/plugin layer and keeps downstream projection fully snapshot-aware.

## Open Questions

- Whether failed outbox events should stay terminal as `failed` or move to retryable `pending` with backoff and max-attempt policy.
- Whether the next interpretation family should remain deterministic or introduce an LLM-backed build step behind a stable service boundary.
- Whether interpretation snapshot ids should become family-partition-aware in a stronger way than the current timestamp-based identifier.
- Whether the worker should append a separate stale-marking event for Personal instead of requiring Personal to infer staleness only from dependency impact.

## Next Actions

- Add more interpretation families on top of the same outbox contract.
- Decide retry semantics for failed outbox events.
- Add Postgres-backed verification for the new claim/process and interpretation repository paths when a test database is available.
- Connect the next downstream path: Personal stale marking or Personal worker projection.

## Follow-Up

The next downstream path is now connected.

- `interpretation_snapshot_published` includes scope metadata as well as interpretation ids
- a Personal stale worker now claims that event type
- dependency lookup runs from each interpretation id to downstream Personal ids
- affected Personal records are re-saved with `status = stale`
- the original personal snapshot tuple is preserved
- the fresher upstream fact/interpretation snapshot ids are written into `provenance.stale_marker`
- the worker emits `personal_records_marked_stale`

This keeps stale propagation explicit without forcing immediate Personal regeneration.

### New Open Questions

- Whether `personal_records_marked_stale` should remain an audit/integration event only or later trigger render refresh and active-user warming.
- Whether Personal stale marking should be able to distinguish `stale` from `invalid` based on the dependency reason.
- Whether the Personal repository needs a dedicated bulk status update path once the worker starts handling larger volumes.
