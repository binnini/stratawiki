# Query-Personal Migration Checklist

## Purpose

This note defines how to salvage implementation work from
`feat/query-personal-knowledge-first-slice` without letting legacy design
choices override the current architecture in `docs/`.

The migration target is the branch:

- `feat/query-personal-migration`

The frozen reference branch is:

- `feat/query-personal-knowledge-first-slice`

## Non-Negotiable Rule

If legacy code disagrees with the current specs in `docs/`, the specs win.

Legacy code may be:

- reused as-is when it matches the current docs
- refactored when the concepts are useful but the boundaries are wrong
- dropped when it pulls the codebase back toward the older page-centric design

## Primary Reference Specs

- `docs/implementation-roadmap.md`
- `docs/three-layer-data-model-spec.md`
- `docs/interpretation-schema-and-lifecycle-spec.md`
- `docs/llm-orchestration-and-retrieval-spec.md`
- `docs/deployment-and-operations-spec.md`

## Migration Guardrails

Preserve these architectural constraints during migration:

1. `Fact` remains canonical and code-owned.
2. `Interpretation` follows proposal -> validated -> published lifecycle.
3. retrieval and orchestration remain separate from storage backends.
4. graph, page search, orchestration, and LLM gateway should not collapse back into one service.
5. rendered markdown stays a view layer, not the system of record.
6. snapshot, provenance, stale, and cache semantics must not regress.

## Do Not Migrate Directly

These areas should not be copied forward as-is:

- old `docs/` content from the frozen branch
- old `dev-wiki/` notes and dashboards
- `README.md` and `AGENTS.md` from the frozen branch
- page-read-centric architectural assumptions
- legacy interpretation projection flow that bypasses lifecycle validation

## Reuse As Foundation

These areas are strong candidates for direct reuse or near-direct reuse.

### Runtime and bootstrap

- `src/wiki_mcp/bootstrap.py`
- `src/wiki_mcp/server.py`
- `src/wiki_mcp/cli.py`

### Storage and repository boundaries

- `src/wiki_mcp/services/interfaces/repositories.py`
- `src/wiki_mcp/storage/postgres/base.py`
- `src/wiki_mcp/storage/postgres/repositories.py`

### Source adapters and domain ingestion

- `src/wiki_mcp/adapters/sources/worknet.py`
- `src/wiki_mcp/domains/recruiting/ingestion.py`

### Common schema concepts

- `src/wiki_mcp/schemas/scope_ref.py`
- `src/wiki_mcp/schemas/snapshot_ref.py`
- `src/wiki_mcp/schemas/source_record.py`
- `src/wiki_mcp/schemas/profile_context.py`
- `src/wiki_mcp/schemas/dependency_edge.py`
- `src/wiki_mcp/schemas/dependency_impact.py`

## Reuse With Careful Refactoring

These areas contain useful logic, but should only be migrated after being
reshaped to match the current architecture.

### Retrieval and user-facing generation

- `src/wiki_mcp/services/retrieval.py`
- `src/wiki_mcp/services/personal_query.py`

Required refactor direction:

- split retrieval policy from backend execution
- preserve `Personal -> Interpretation -> Fact` curated retrieval
- avoid page-read-first coupling
- make room for graph and optional markdown-search backends

### Interpretation family logic

- `src/wiki_mcp/services/interpretation_families/*`

Required refactor direction:

- keep the family registry idea
- rework family outputs to fit the canonical interpretation envelope
- integrate proposal, validation, and publish semantics

### Tool registration

- `src/wiki_mcp/tools/registry.py`
- `src/wiki_mcp/tools/defaults.py`

Required refactor direction:

- keep registry mechanics
- rebuild tool surface around the current tool contract docs

### Rendering persistence

- `src/wiki_mcp/storage/filesystem/rendering.py`

Required refactor direction:

- keep rendered artifacts as views
- avoid making rendered pages the primary read authority

## Likely Replace or Deprecate

These areas should be treated as legacy and replaced by new services aligned to
the current specs.

- `src/wiki_mcp/services/interpretation_projection.py`
- `src/wiki_mcp/services/page_reads.py`
- `src/wiki_mcp/services/page_read_entrypoint.py`
- `src/wiki_mcp/services/interfaces/page_reads.py`
- old retrieval read entrypoint patterns that assume page summaries are the main authority

Replacement targets:

- `interpretation_service`
- `retrieval_service`
- `graph_service`
- `page_search_service`
- `orchestration_service`
- `llm_gateway`

## Keep As Reference Assets

Do not delete these immediately, even if they are not migrated directly:

- `tests/` from the frozen branch
- worker and outbox related tests
- legacy retrieval and personal query tests

These tests are useful for:

- understanding previous behavior
- building regression expectations
- comparing old and new service boundaries

## Migration Batches

### Batch 1: Foundation

Move first:

- runtime bootstrap files
- repository interfaces
- Postgres storage base and repositories
- source adapter and recruiting ingestion
- common schema primitives

Success condition:

- the new branch has durable storage and canonical ingest foundations without importing legacy read-path assumptions

### Batch 2: Schema and retrieval salvage

Move next:

- fact, interpretation, personal schema candidates
- retrieval and personal query service code for reference-driven refactor
- interpretation family registry

Success condition:

- useful logic is preserved while service boundaries are rewritten to match docs

### Batch 3: Operator, worker, and test assets

Move last:

- worker-compatible flows
- selected tests
- runtime helpers

Success condition:

- the migrated implementation remains operable and testable without restoring obsolete architecture

## Decision Rule During Migration

For each candidate file, ask:

1. Does it preserve the current docs-defined ownership boundary?
2. Does it help the MVP roadmap without dragging in obsolete assumptions?
3. Can it be adapted faster than rewriting it cleanly?

If any answer is clearly "no", prefer replacement over salvage.
