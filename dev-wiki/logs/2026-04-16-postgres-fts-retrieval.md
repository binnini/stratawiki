# Postgres FTS Retrieval

## Context

The retrieval stack already supported:

- canonical lexical discovery
- Fact and Interpretation snapshot carry-through for canonical-only matches
- explicit rendered-page presence in retrieval explanations

But the lexical search backend still used pragmatic normalized `LIKE` matching.

That left one clear remaining risk:

- retrieval quality and scalability would plateau without a stronger indexed
  lexical backend

## Current Question

What is the smallest retrieval-only upgrade that improves lexical search quality
and indexing without changing the outer retrieval or personal-answer contracts?

## Observations

- Retrieval orchestration is already separated from the search backend by the
  repository interface, so this upgrade belongs in the Postgres repositories.
- The current search document is already normalized into a lowercased
  alphanumeric string, which can be reused as the source text for `tsvector`
  generation.
- Using Postgres FTS with GIN expression indexes keeps the implementation thin
  and local to the existing storage surface.

## Options

- Keep normalized `LIKE` search and only tune ranking again.
- Replace repository search with Postgres FTS and add GIN indexes over the same
  normalized search documents.

## Decision or Working Direction

Take the second option.

Implemented shape:

- repository search now uses:
  - `websearch_to_tsquery('simple', query_text)`
  - `to_tsvector('simple', normalized_search_document)`
  - `ts_rank_cd(...)` for ordering
- new Alembic migration adds GIN expression indexes for retrieval search on:
  - `fact.record_envelopes`
  - `interp.record`
  - `personal.record`
- retrieval service and answer service remain unchanged at the contract level;
  they still consume repository-provided bounded candidates and produce the same
  outer payloads

## Contract Notes

- `retrieve_for_query` remains the retrieval primitive.
- `query_personal_knowledge` remains the answer projection.
- No outer result fields changed in this slice.
- This is a backend-quality upgrade, not a payload redesign.

## Testing

- focused repository/retrieval tests remained green
- full local suite remained green
- full DB-backed suite remained green after applying the new Alembic head
- `pytest -q`
  - `60 passed, 19 skipped`
- `DATABASE_URL=postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki pytest -q`
  - `60 passed, 19 skipped`

## Remaining Risks

- Search quality is stronger than normalized `LIKE`, but still uses simple
  general-purpose FTS rather than domain-tuned weighting or synonym handling.
- Retrieval still does not have a vector/hybrid path, so semantic recall stays
  intentionally limited.

## Next Actions

- If query quality remains the priority, consider weighted FTS fields or a small
  domain synonym layer before any vector system is introduced.
- If operational visibility becomes the priority, add retrieval-level metrics
  around page-backed versus canonical-only match mix and FTS hit patterns.
