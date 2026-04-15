# DB Baseline Core Ingestion Follow-Up

## Context

This follow-up captures the work completed after the initial Postgres storage baseline landed.

Recent commits in this slice:

- `2892d37` `Add Postgres bootstrap baseline and scope-aware recruiting relations`
- `db30ced` `Implement core ingestion service and Postgres repo tests`
- `a2ca032` `Document Postgres storage baseline status`

## Current Question

What was added to move the repository from storage scaffolding toward a real ingestion-owned vertical slice, and what remains unresolved?

## Observations

- Recruiting ingestion now propagates `scope` into `FactRelation`, which aligns domain output with the multiscoped Postgres schema.
- Local DB bootstrap was validated end to end with Docker Compose and Alembic, and the scripts now use `python3 -m alembic` to avoid PATH-interpreter mismatches.
- A first concrete `DefaultCoreIngestionService` now owns batch preparation, core-side validation, fact persistence, fact snapshot publication, and outbox emission.
- Postgres repository integration tests now cover fact write/update behavior, outbox idempotency, snapshot publication history, and scope-aware dependency impact lookup.
- Official docs were updated to reflect that the Postgres baseline is implemented, not merely proposed.

## Options

- Keep expanding the current envelope-first baseline and prove more flow end to end before introducing normalized domain tables.
- Pause implementation and redesign the storage/service split before further code lands.

## Decision or Working Direction

Continue with the current direction.

The right next step is to build on top of the envelope-first baseline rather than redesign it again now. The current code now proves the intended ownership split:

- domain plugin owns extraction semantics
- core service owns write orchestration
- repositories own DB details
- docs describe the implemented baseline rather than a purely conceptual design

## Open Questions

- Whether the outbox should remain batch-level or split into finer-grained downstream events.
- Whether fact snapshot IDs should become deterministic or partition-aware.
- When to introduce recruiting-specific normalized tables beyond the generic envelopes.
- How the first true end-to-end ingestion entrypoint should select plugins and expose errors.

## Next Actions

- Add an application-facing ingest entrypoint that wires adapter, plugin selection, core ingestion service, and repositories together.
- Decide and document the v1 outbox payload contract for downstream workers.
- Add more repository or service tests around scope validation and failure cases.
