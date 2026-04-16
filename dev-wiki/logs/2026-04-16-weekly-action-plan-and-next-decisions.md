# Weekly Action Plan And Next Decisions

## Context

After the previous slices, the dashboard `Next` items were:

- add `weekly_action_plan`
- decide whether retrieval should remain page-summary-first
- decide whether family-aware answers need richer structured fields

## Decision or Working Direction

This slice closes those items in the smallest coherent way.

### `weekly_action_plan`

`query_personal_knowledge` now supports a third family-aware answer mode:

- `personal_family = weekly_action_plan`
- family-specific markdown with:
  - `Weekly Focus`
  - `Why These Actions`
  - `This Week`
  - supporting context sections

### Retrieval Strategy Decision

Decision for the current branch:

- keep retrieval page-summary-first for now

Reason:

- the current answer stack already depends on retrieval-owned summaries and
  explanations
- moving to stronger canonical retrieval should be treated as a separate slice,
  not mixed into family rollout work

### Structured Answer Decision

Decision for the current branch:

- keep structured answer fields at:
  - `recommended_actions`
  - `answer_rationale_items`

Reason:

- this is enough to support explainability and family-specific rendering
- richer structured payloads should be introduced per family only when a real
  consumer demonstrates the need

## Testing

- `pytest -q`
  - `55 passed, 15 skipped`
- `DATABASE_URL=postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki pytest -q`
  - not rerun in this micro-slice; previous DB-backed baseline remained green

## Next Actions

- If the goal is breadth, add more Personal families.
- If the goal is retrieval quality, open a distinct canonical retrieval slice.
