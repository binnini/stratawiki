# Canonical Candidate Discovery

## Context

The previous slice strengthened retrieval ranking with canonical summaries and
titles, but candidate enumeration still depended on rendered page listings.

That meant canonical records with weak or missing rendered-page coverage could
not become first-class retrieval candidates even when their canonical summaries
were clearly relevant.

## Current Question

What is the smallest retrieval-only slice that reduces rendered-page dependence
without:

- changing the current personal answer contract
- leaking answer assembly into the retrieval service
- fabricating rendered-page outputs for records that do not actually have pages

## Observations

- `query_personal_knowledge` already builds answers from retrieval-owned record
  summaries and explanations, so it does not require rendered pages for every
  selected candidate.
- The retrieval contract allows `*_records` and `*_explanations` to exist
  alongside `*_pages`; the contract does not require the page arrays to be a
  one-to-one mirror of ids.
- Repository interfaces previously exposed only `get_by_ids`, which was enough
  for page-backed hydration but not for canonical discovery.
- Personal records already carry `snapshot_ref`, so canonical-only Personal
  matches can still contribute authoritative snapshot metadata even without a
  rendered page.

## Options

- Keep page enumeration only and strengthen scoring again.
- Add broad canonical search APIs and move discovery entirely off rendered-page
  listings.
- Add bounded canonical candidate listing per layer, merge it with rendered-page
  candidates inside retrieval, and keep page outputs limited to real pages.

## Decision or Working Direction

Take the third option.

Implemented shape:

- repository interfaces now expose bounded `list_for_retrieval(...)` methods for
  Fact, Interpretation, and Personal
- Postgres repositories implement those methods with simple domain/scope-bounded
  recent-record listing
- `DefaultRetrievalService` now merges:
  - rendered-page candidates
  - page-prefetched canonical records
  - canonical-only records returned by `list_for_retrieval(...)`
- matching and ranking still happen inside retrieval and still produce the same
  explanation fields:
  - `rank`
  - `score`
  - `matched_token_count`
  - `match_type`
  - `matched_fields`
  - `profile_boost_applied`

## Contract Notes

- `retrieve_for_query` remains the retrieval primitive.
- `query_personal_knowledge` remains an answer projection on top of retrieval.
- Canonical-only candidates can now appear in:
  - `*_ids`
  - `*_records`
  - `*_explanations`
- But they do not force synthetic entries into `*_pages`.
- This keeps rendered-page metadata honest while still allowing answer
  selection to benefit from canonical discovery.

## Testing

- Added retrieval unit coverage for canonical-only Personal discovery without a
  rendered page
- Added personal-query coverage showing family selection still works when the
  lead Personal candidate is canonical-only
- Added DB-backed retrieval entrypoint coverage for canonical-only Personal
  discovery through Postgres repositories
- `pytest -q`
  - `59 passed, 16 skipped`
- `DATABASE_URL=postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki pytest -q`
  - `59 passed, 16 skipped`

## Open Questions

- Whether Interpretation and Fact layers now need explicit snapshot publication
  metadata on canonical records if canonical-only discovery becomes common.
- Whether `list_for_retrieval(...)` should remain recency-based or gain a more
  explicit lexical prefilter before the repository surface widens again.
- Whether external consumers will eventually want an explicit signal that a
  matched record had no rendered page.

## Next Actions

- Revisit whether bounded canonical discovery is enough, or whether retrieval
  now needs a true lexical canonical search surface.
- Decide if `matched_fields` should eventually distinguish page-backed versus
  canonical-only signals more formally.
- Keep answer contracts stable until a concrete consumer requires richer
  family-specific structured output.
