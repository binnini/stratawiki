# Retrieval Read Authority Slice

## Context

The merged branch already had:

- `DefaultRetrievalService` as an internal layered retrieval service
- `DefaultPageReadEntrypoint` as the first application-facing read authority for
  rendered document pages
- thin bootstrap and tool registry wiring for ingestion and page reads

What was still missing was a consumer-facing retrieval read contract. The
retrieval logic existed only as an internal service result, which left read
authority and retrieval talking in different envelope shapes.

## Current Question

What is the smallest retrieval-oriented read slice that makes the current
`Personal -> Interpretation -> Fact` retrieval order consumable through the same
authoritative read language as page reads, without pretending answer generation
or full MCP query semantics already exist?

## Observations

- The current retrieval implementation is still rendered-page-summary centric,
  so the first consumer contract should expose candidate record ids rather than
  synthesized answers.
- The page read contract already established the right boundary vocabulary:
  `projection` metadata plus `read_model_state = applied`.
- Reusing the full future MCP tool name `query_personal_knowledge` would be
  misleading because the current slice does not generate `answer_markdown`.
- Bootstrap wiring already had a natural place to add one more application
  entrypoint and one more available tool without introducing transport-level MCP
  concerns.

## Options

- Keep retrieval internal until answer generation exists.
- Add a small retrieval read authority slice now and expose it explicitly as a
  candidate-resolution operation.

## Decision or Working Direction

Take the second option.

The implemented slice adds:

- `DefaultRetrievalReadEntrypoint`
- `RetrievalReadResult` and `RetrievalProjectionRef`
- authoritative retrieval envelopes with:
  - `projection.family = retrieval`
  - `projection.scope`
  - `projection.layers = [personal, interpretation, fact]`
  - `read_model_state = applied`
- hydrated page-summary groups alongside ids:
  - `personal_pages`
  - `interpretation_pages`
  - `fact_pages`
- `retrieve_personal_context(...)` as the first user-scoped wrapper
- bootstrap wiring for `entrypoints.retrieval_reads`
- a non-placeholder server tool:
  - `retrieve_for_query`

Importantly, the official placeholder `query_personal_knowledge` tool remains a
placeholder. The current slice is candidate retrieval only, not answer
generation.

## Open Questions

- Whether future retrieval result envelopes need per-match explanation metadata
  instead of only grouped record ids.
- Whether the retrieval read slice should remain rendered-page based once Fact
  canonical read paths mature.
- Whether the eventual MCP tool contract should wrap this candidate retrieval
  slice directly or hide it behind answer generation.
- Whether a tenant-scoped retrieval mode will need a distinct wrapper once
  tenant-level non-personal overlays exist.

## Next Actions

- Decide when to add page-summary hydration or canonical record hydration on top
  of the current candidate ids.
- Revisit naming once the MCP tool contract for personal querying is actually
  implemented.

## Verification

- `pytest -q`
  - `38 passed, 14 skipped`
- `bash scripts/bootstrap_db.sh`
  - local Postgres became reachable and Alembic upgraded successfully
- `DATABASE_URL=postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki pytest -q`
  - `52 passed in 8.40s`
