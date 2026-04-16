# Canonical Lexical Search

## Context

The previous slice added bounded canonical candidate discovery, but that
repository surface still used recent-record listing.

That left a meaningful quality risk:

- newer but irrelevant canonical records could crowd out older relevant ones
- retrieval quality still depended partly on recency even when the query intent
  was clearly lexical

There was also a smaller snapshot risk:

- canonical-only Interpretation matches could lose `fact_snapshot_id` when the
  retrieval-level merged snapshot was assembled without a rendered page

## Current Question

What is the smallest next slice that resolves those risks while preserving:

- retrieval as the candidate-oriented primitive
- answer assembly above retrieval
- the current personal answer families and outer answer contract

## Observations

- The retrieval service already normalizes queries into:
  - `normalized_question`
  - `query_tokens`
- That means the missing piece is not query analysis, but a repository surface
  that can use those normalized inputs to return bounded lexical matches.
- The repo boundary in `docs/internal-architecture-boundaries.md` explicitly
  allows retrieval orchestration to stay distinct from a particular search
  backend implementation.
- Interpretation canonical rows already store `fact_snapshot_id`, but the
  in-memory `InterpretationRecord` schema and retrieval snapshot merge were not
  carrying it through for canonical-only matches.

## Options

- Keep recent-record listing and only tune scoring again.
- Move all lexical logic into retrieval service and inspect canonical records in
  Python only.
- Add query-aware repository search methods, keep retrieval orchestration above
  them, and carry Interpretation snapshot metadata through the retrieval merge.

## Decision or Working Direction

Take the third option.

Implemented shape:

- repository interfaces now expose `search_for_retrieval(...)` instead of recent
  `list_for_retrieval(...)`
- Postgres repositories now build a normalized lexical search document per layer
  and apply bounded query-aware matching in SQL
- lexical score ordering is repository-local and intentionally narrow:
  - full normalized phrase hit gets the strongest weight
  - token hits add smaller weight
- retrieval still merges:
  - rendered page candidates
  - page-prefetched canonical records
  - canonical search results
- retrieval still owns final matching/ranking explanations
- canonical-only Interpretation records now carry `fact_snapshot_id` into the
  retrieval snapshot merge path

## Contract Notes

- `retrieve_for_query` remains the retrieval primitive.
- `query_personal_knowledge` remains the answer projection.
- No outer answer contract fields changed.
- Retrieval result shape still stays honest:
  - canonical-only matches can appear in `*_ids`, `*_records`,
    `*_explanations`
  - they do not fabricate `*_pages`

## Testing

- added repository coverage for:
  - Personal lexical search preferring relevant older record over newer
    irrelevant record
  - Interpretation lexical search matching canonical summary and preserving
    `fact_snapshot_id`
- added DB-backed retrieval entrypoint coverage showing canonical lexical search
  beats recent-only behavior for Personal canonical-only candidates
- existing unit coverage continues to verify:
  - canonical-only Personal discovery
  - family-aware answer selection with no synthetic rendered page
- `pytest -q`
  - `59 passed, 19 skipped`
- `DATABASE_URL=postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki pytest -q`
  - `59 passed, 19 skipped`

## Remaining Risks

- Fact canonical-only matches still do not carry their own snapshot id because
  Fact envelopes do not currently persist snapshot membership directly.
- Current lexical search is still a pragmatic SQL search document, not a full
  FTS/vector hybrid design.
- External consumers still cannot tell explicitly whether a selected record had
  no rendered page unless they compare `*_ids` and `*_pages`.

## Next Actions

- Decide whether Fact retrieval now needs explicit snapshot membership or a
  snapshot lookup join.
- Decide whether retrieval should expose an explicit `has_rendered_page` style
  flag for explainability consumers.
- If retrieval quality remains the priority, consider formal Postgres FTS or a
  more explicit lexical index rather than only normalized `LIKE` matching.
