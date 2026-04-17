# DB Review And Relation Scope Fix

## Context

Reviewed externally added PostgreSQL bootstrap and repository changes alongside the recruiting ingestion plugin.

## Current Question

Does the new DB envelope contract line up with current domain ingestion output, and is the bootstrap path usable as committed?

## Observations

- The Postgres migration and repository layer now require explicit `scope` metadata on `fact.relation_envelopes`.
- `RecruitingSourceIngestionPlugin.extract_fact_relations()` was still emitting relations without `scope`.
- Fact records already carry `scope`, and the relation scope should stay aligned with the originating posting scope.
- Bootstrap scripts and Alembic wiring are present, but shell `alembic` resolution can hit a different Python environment than the active project interpreter.

## Options

- Keep relations implicitly shared and let repositories infer scope later.
- Make relations explicit at ingestion time and propagate scope metadata from the fact records.

## Decision or Working Direction

Propagate `scope` and optional `tenant_id` / `user_id` from the posting fact record into each emitted `FactRelation`.
Use `python3 -m alembic` in DB scripts and docs so bootstrap follows the active interpreter instead of whichever global `alembic` binary happens to be first on `PATH`.

## Open Questions

- Whether later recruiting sources will provide non-shared source envelopes directly, or whether scope will be injected only by core ingestion orchestration.
- Whether repository-level tests should be added next for outbox idempotency and snapshot publication semantics.

## Next Actions

- Run `pytest`.
- Validate the DB bootstrap path with `docker compose` and `alembic upgrade head`.
- Commit the reviewed DB changes plus the ingestion scope fix once verification passes.
