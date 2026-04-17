# Issue #3 Fact Storage Audit

## Purpose

This note records the audit and focused correction pass for closed issue `#3 Build canonical Fact storage and snapshot publish flow`.

`docs/` remains the source of truth.
This file is only a development log for what was checked, what was fixed, and what still needs follow-up.

## Audit Scope

Reviewed against:

- `AGENTS.md`
- `docs/implementation-roadmap.md`
- `docs/three-layer-data-model-spec.md`
- `docs/cache-invalidation-consistency-spec.md`
- `docs/mcp-architecture.md`
- `docs/deployment-and-operations-spec.md`

Primary code inspected:

- `src/wiki_mcp/services/core_ingestion.py`
- `src/wiki_mcp/services/interfaces/core_ingestion.py`
- `src/wiki_mcp/services/interfaces/domain_ingestion.py`
- `src/wiki_mcp/services/interfaces/repositories.py`
- `src/wiki_mcp/storage/postgres/base.py`
- `src/wiki_mcp/storage/postgres/repositories.py`
- `src/wiki_mcp/domains/recruiting/ingestion.py`
- `src/wiki_mcp/adapters/sources/worknet.py`
- `tests/test_core_ingestion_service.py`
- `tests/test_recruiting_ingestion.py`

## Issue #3 Acceptance Criteria Restated

In repository terms, issue `#3` means:

- ingest a normalized `SourceRecord` through a domain ingestion plugin
- persist canonical `FactRecord` values in the Fact repository
- persist explicit `FactRelation` values alongside the records
- publish a fact snapshot for the ingest batch
- support retrieval of stored facts

## What Was Already Working

- `DefaultCoreIngestionService` already orchestrated source normalization, fact extraction, validation, persistence, snapshot publication, and outbox emission
- the recruiting adapter and plugin already supported a sample source-to-fact ingestion path
- Postgres repositories already supported Fact persistence, relation persistence, ID lookup, and retrieval search
- snapshot publication already wrote to `ops.snapshot_pointer` and `ops.snapshot_publication`

## Focused Fixes Made

### 1. Canonical identity validation at batch time

Added validation to reject duplicate canonical Fact identity inside one ingest batch.

Why:

- the docs treat canonical identity as the authoritative Fact boundary
- the previous code validated relation targets and scope shapes, but it did not reject two different fact IDs for the same canonical key and scope tuple

Files:

- `src/wiki_mcp/services/core_ingestion.py`
- `tests/test_core_ingestion_service.py`

### 2. Explicit canonical-key lookup contract

Added `get_by_canonical_keys(...)` to the Fact repository contract and the Postgres implementation.

Why:

- issue `#3` calls for canonical lookup and query
- the existing implementation had `get_by_ids(...)` and retrieval search, but not explicit canonical-key lookup

Files:

- `src/wiki_mcp/services/interfaces/repositories.py`
- `src/wiki_mcp/storage/postgres/repositories.py`
- `tests/test_postgres_fact_repository.py`

## Validation Run

Executed in the isolated worktree with:

```bash
PYTHONPATH=src pytest tests/test_core_ingestion_service.py tests/test_recruiting_ingestion.py tests/test_postgres_fact_repository.py
```

Result:

- `8 passed`

## Remaining Gaps

These gaps did not justify reopening `#3`, but they do justify follow-up issue work:

- Fact schema contracts still do not model the fuller docs-facing envelope fields such as `version`, `status`, `created_at`, and `updated_at`
- canonical identity appears to be protected primarily by service behavior; durable DB-level uniqueness constraints were not verified in this pass
- snapshot publication exists, but the current Fact slice remains intentionally minimal rather than fully aligned with richer docs-defined metadata and versioning expectations

## Outcome

Recommendation after this audit:

- keep issue `#3` closed
- track the remaining schema and storage-hardening work in a follow-up issue rather than widening the scope of this audit
