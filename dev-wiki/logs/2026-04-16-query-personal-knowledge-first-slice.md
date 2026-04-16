# Query Personal Knowledge First Slice

## Context

The base branch already had:

- rendered page read authority for Personal and shared Interpretation pages
- retrieval candidate read authority via `retrieve_for_query`
- bootstrap/server/tool registry wiring for those read slices

What was still missing was the first real `query_personal_knowledge` path that
turns retrieval output into a user-facing answer without collapsing retrieval
and answer assembly into one service.

## Current Question

What is the thinnest vertical slice that makes `query_personal_knowledge`
actually return an answer while preserving:

- `retrieve_for_query` as the lower-level primitive
- the current page-read and retrieval-read contracts
- the thin bootstrap/tool registry architecture

## Observations

- The retrieval contract was already mature enough to serve as a pre-generation
  input:
  - grouped ids remain the stable identity output
  - grouped page summaries remain the read model surface
  - optional `*_records` summaries provide enough metadata for deterministic
    answer assembly
- Pulling answer generation into `DefaultRetrievalService` would blur the
  retrieval vs orchestration boundary described in
  `docs/internal-architecture-boundaries.md`.
- The first slice does not need LLM synthesis yet; deterministic markdown is
  sufficient to prove the vertical path.

## Options

- Extend `DefaultRetrievalService` so it directly returns `answer_markdown`.
- Add a thin personal-query orchestration service above retrieval that builds an
  answer bundle and deterministic answer payload.

## Decision or Working Direction

Take the second option.

Implemented shape:

- `DefaultRetrievalService`
  - unchanged as the retrieval primitive
- `DefaultPersonalQueryService`
  - consumes retrieval output
  - assembles a thin `input_bundle`
  - emits deterministic `answer_summary`, `answer_markdown`, and citations
- `DefaultPersonalQueryEntrypoint`
  - wraps the service in an application-facing read envelope
- bootstrap/server/tool registry
  - now wire `query_personal_knowledge` as an available tool instead of a
    placeholder

## Contract Decisions

- `query_personal_knowledge` remains retrieval-first:
  it returns both the underlying `retrieval` payload and a higher-level
  `answer` payload.
- The answer-generation input bundle is retrieval-owned, not storage-owned.
  Bundle fields are:
  - `question`
  - `scope_ref`
  - optional `snapshot_ref`
  - optional `profile_context`
  - `personal_context`
  - `interpretation_context`
  - `fact_context`
- Each layer context item is normalized to:
  - `layer`
  - `record_id`
  - `title`
  - `summary`
  - optional `path`
- Retrieval/page contracts were left intact.
  `retrieve_for_query` still stops at candidate resolution and hydration.
- The answer envelope is deterministic for now:
  - `answer_summary`
  - `answer_markdown`
  - `citations`
  - `input_bundle`

## Bootstrap And Tool Wiring

- `ApplicationEntrypoints` now include `personal_queries`
- `build_server(...)` passes the personal-query entrypoint into the default tool
  registry
- `query_personal_knowledge` is now `available` in the thin tool layer with:
  - `domain`
  - `question`
  - `scope_ref`
  - optional `profile_context`

## Testing

- `pytest -q`
  - `53 passed, 15 skipped`
- `DATABASE_URL=postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki pytest -q`
  - `53 passed, 15 skipped`

Added tests:

- `tests/test_personal_query_service.py`
- `tests/test_personal_query_entrypoint.py`
- updated `tests/test_server_bootstrap.py`

## Open Questions

- Whether the answer projection should later get its own projection-family value
  instead of temporarily reusing retrieval-style projection metadata.
- Whether future answer assembly should pull rendered markdown bodies, or remain
  summary-first until a stronger canonical read path exists.
- Whether citation ranking/explanation metadata should become explicit before
  any LLM-backed synthesis is introduced.

## Next Actions

- Decide whether to strengthen the answer envelope with explicit rationale or
  ranking explanation fields.
- Add the first truly domain-shaped personal family that consumes this answer
  path rather than only generic deterministic summaries.
- Revisit projection metadata naming once answer reads and retrieval reads need
  to diverge externally.
