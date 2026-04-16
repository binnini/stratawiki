# Canonical Retrieval Strengthening

## Context

The branch already had:

- `retrieve_for_query` preserved as the retrieval primitive
- `query_personal_knowledge` preserved as answer projection/orchestration
- three current family-aware personal outputs:
  - `career_transition_plan`
  - `profile_gap_analysis`
  - `weekly_action_plan`

The remaining weakness was that retrieval candidate matching still leaned too
hard on rendered page identifiers and titles:

- `record_id`
- page `title`
- page `path`

That meant canonical summaries could improve output readability, but they could
not materially improve ranking or answer-family selection when page metadata was
weak.

## Current Question

What is the smallest canonical retrieval strengthening slice that:

- changes actual candidate ranking
- can influence `query_personal_knowledge` lead-item selection
- does not leak answer assembly back into retrieval
- does not widen the current personal answer contract

## Observations

- The retrieval boundary should stay candidate-oriented.
- The answer layer already consumes retrieval-owned explanations and should keep
  doing so.
- The repository interfaces only expose `get_by_ids`, not broad canonical
  search/list APIs, so a realistic first strengthening step is:
  - keep rendered page listing for candidate enumeration
  - enrich ranking using canonical record summaries fetched for those candidate
    page ids
- This does not yet solve the full “search all canonical records even when no
  page candidate matches” problem, but it is a real shift away from
  page-title-only ranking.

## Options

- Add answer-aware heuristics inside `DefaultRetrievalService`
- Add page metadata summary scoring only
- Keep retrieval candidate enumeration via rendered pages, but prefetch
  canonical record summaries and use them as ranking fields

## Decision or Working Direction

Take the third option.

Implemented behavior:

- retrieval still enumerates candidates through rendered page listings
- retrieval now prefetches same-layer canonical records for the listed page ids
- ranking now considers:
  - rendered page summary metadata when present
  - canonical personal summary/title/kind
  - canonical interpretation summary/subject_id/kind
  - canonical fact title/summary/key/entity_type
- hydrated retrieval summaries still come from the same repositories, but the
  prefetched records are reused so retrieval does not issue duplicate reads for
  matched items

## Contract Notes

- `retrieve_for_query` remains a retrieval primitive.
- `query_personal_knowledge` remains an answer projection with:
  - `projection.family = "answer"`
  - `projection.kind = "personal_query"`
- Retrieval explanation fields remain stable:
  - `rank`
  - `score`
  - `matched_token_count`
  - `match_type`
  - `matched_fields`
  - `profile_boost_applied`
- `matched_fields` can now include canonical-oriented field names such as:
  - `canonical_title`
  - `canonical_summary`
  - `canonical_key`
  - `subject_id`
  - `kind`

This is additive explainability, not an answer-contract change.

## Testing

- Added retrieval coverage showing canonical personal summary can create a match
  even when rendered page title/path do not match well
- Added personal query coverage showing stronger retrieval ranking can change
  the selected personal family without changing the answer envelope
- `pytest -q`
  - `57 passed, 15 skipped`
- `DATABASE_URL=postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki pytest -q`
  - `57 passed, 15 skipped`

## Open Questions

- Should the next slice widen retrieval discovery beyond rendered page listings
  entirely, so canonical-only records can become first-class candidates?
- Should `matched_fields` later distinguish `page_*` vs `canonical_*` more
  formally if external explainability consumers begin relying on it?
- Is there any family that now needs richer structured output beyond
  `recommended_actions` and rationale items?

## Next Actions

- If retrieval quality remains the priority, move from canonical ranking
  strengthening to canonical candidate discovery.
- If answer richness becomes the priority, keep retrieval unchanged and add
  family-specific structured fields in the answer layer only.
