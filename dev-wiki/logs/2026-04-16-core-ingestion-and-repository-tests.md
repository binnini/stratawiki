# Core Ingestion And Repository Tests

## Context

The previous DB slice established schema, repositories, and bootstrap scripts, but the code still lacked two things:

- repository-level integration tests against real Postgres
- a concrete `CoreIngestionService` that owns fact write orchestration

## Current Question

What is the smallest implementation that proves the intended v1 ingestion split without leaking persistence concerns into the domain plugin?

## Observations

- The repository layer already exposes enough seams to test fact writes, snapshot publication, outbox append, and dependency impact directly.
- The service interface for core ingestion existed, but no implementation connected domain extraction to persistence.
- The docs consistently assign snapshot publication and outbox emission to core, not to domain plugins.

## Options

- Keep repository changes untested and implement more features first.
- Lock repository semantics first, then add the smallest viable orchestration service over them.

## Decision or Working Direction

Add Postgres integration tests for the repository baseline and implement a first `DefaultCoreIngestionService` that:

- prepares a validated batch from a domain plugin
- adds core-side validation for scope shape and relation targets
- persists facts and relations
- publishes a fact snapshot
- emits one fact-ingested outbox event for downstream workers

## Open Questions

- Whether the outbox should stay at one batch-level event or evolve into finer-grained fact-level events.
- Whether snapshot IDs should later become deterministic or partition-aware instead of timestamp-plus-random.
- Whether repository integration tests should eventually own container startup rather than assuming a reachable `DATABASE_URL`.

## Next Actions

- Run `pytest` for unit and Postgres integration coverage.
- If the tests hold, consider promoting the resulting ingestion flow into official docs after one more implementation pass.
