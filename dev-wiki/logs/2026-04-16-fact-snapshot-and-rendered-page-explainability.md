# Fact Snapshot And Rendered Page Explainability

## Context

After canonical lexical search, two retrieval risks still remained:

- canonical-only Fact matches could not contribute authoritative snapshot
  membership because Fact records did not persist `fact_snapshot_id`
- retrieval consumers still had to infer canonical-only matches indirectly by
  comparing `*_ids` with `*_pages`

## Current Question

What is the smallest slice that resolves both issues without widening the outer
personal answer contract or collapsing retrieval into answer assembly?

## Observations

- Fact snapshot membership is created synchronously inside core ingestion, so it
  can be persisted with the canonical Fact write rather than reconstructed later.
- Retrieval explanations are already the contract-owned place for ranking and
  match metadata, so rendered-page presence belongs there rather than in hidden
  answer-layer heuristics.
- The current answer bundle already copies retrieval explanation metadata into
  layer items, so adding one more additive explainability field does not require
  a new answer contract family.

## Options

- Leave Fact snapshot membership implicit and add a join-based lookup later.
- Persist Fact snapshot membership directly on canonical Fact records and reuse
  retrieval explanations for rendered-page presence.

## Decision or Working Direction

Take the second option.

Implemented shape:

- `fact.record_envelopes` now stores nullable `fact_snapshot_id`
- core ingestion now creates `fact_snapshot_id` before the write and passes it
  into `write_facts(...)`
- Postgres Fact repository now writes and reads that field
- retrieval fact summaries now also carry `fact_snapshot_id` when available
- retrieval snapshot merge now uses canonical-only Fact metadata if there is no
  rendered page
- retrieval explanations now expose `has_rendered_page`
- personal query bundle items now copy `has_rendered_page`
- answer-side `match_reason` now explicitly says `without rendered page` for
  canonical-only matches

## Contract Notes

- `retrieve_for_query` remains the retrieval primitive.
- `query_personal_knowledge` remains the answer projection.
- No existing outer answer fields were removed or renamed.
- Additive retrieval changes in this slice are:
  - explanation field: `has_rendered_page`
  - fact summary field: optional `fact_snapshot_id`

## Testing

- added retrieval unit coverage for canonical-only Fact snapshot merge
- added core-ingestion coverage that the generated `fact_snapshot_id` is passed
  into Fact persistence
- extended DB-backed repository coverage for Fact snapshot persistence
- extended personal-query and retrieval entrypoint coverage for explicit
  no-rendered-page explainability
- added an Alembic migration for the new Fact snapshot column
- `pytest -q`
  - `60 passed, 19 skipped`
- `DATABASE_URL=postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki pytest -q`
  - `60 passed, 19 skipped`

## Remaining Risks

- Lexical canonical search is still implemented as pragmatic normalized `LIKE`
  matching rather than formal Postgres FTS or vector retrieval.
- External consumers still get rendered-page presence per explanation item, but
  there is not yet a higher-level summary count or flag at the retrieval root.

## Next Actions

- If retrieval quality remains the priority, consider formal Postgres FTS or a
  stronger indexed search surface.
- If consumer ergonomics become the priority, consider a lightweight
  retrieval-level summary of page-backed versus canonical-only matches.
