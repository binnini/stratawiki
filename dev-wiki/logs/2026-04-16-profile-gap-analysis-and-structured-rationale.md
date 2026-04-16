# Profile Gap Analysis And Structured Rationale

## Context

The previous slices had already delivered:

- a first family-aware answer mode for `career_transition_plan`
- explanation-rich retrieval metadata
- deterministic personal answers with plain-text rationale

The remaining `Next` items were:

- add the next Personal family
- improve retrieval explanation/ranking
- decide whether rationale should become structured

## Current Question

Can those remaining items be closed in one coherent slice without changing the
outer personal query envelope again?

## Decision or Working Direction

Yes.

This slice does three things together:

1. Adds `profile_gap_analysis` as the second family-aware personal answer mode.
2. Extends retrieval explanations with explicit ranking metadata.
3. Makes rationale structured as well as plain-text.

## Implemented Shape

### Second Personal Family

If the top Personal match has `kind = profile_gap_analysis`, the answer layer
now emits:

- `personal_family = profile_gap_analysis`
- family-specific markdown
- gap-oriented `recommended_actions`

### Retrieval Explanation / Ranking

Retrieval explanations now include:

- `rank`
- `matched_token_count`

This keeps ranking responsibility retrieval-owned while making the current order
auditable by the answer layer and tests.

### Structured Rationale

Answers now include:

- `answer_rationale`
- `answer_rationale_items`

Current rationale item categories:

- `selection`
- `ranking`
- `context`

This means the system no longer has to rely on one free-text rationale string
for downstream explanation consumers.

## Boundary Notes

- Retrieval still owns matching and ranking.
- Personal answer assembly still owns family selection and output formatting.
- The outer `query_personal_knowledge` response shape remains stable; the new
  fields are additive within `answer` and retrieval explanation payloads.

## Testing

- `pytest -q`
  - `54 passed, 15 skipped`
- `DATABASE_URL=postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki pytest -q`
  - `54 passed, 15 skipped`

## Outcome

The previous dashboard `Next` set is now effectively complete for this branch:

- second Personal family added
- retrieval explanation/ranking strengthened
- rationale structured

## Next Actions

- Add `weekly_action_plan` as the next family-aware output if short-horizon
  execution becomes the product priority.
- Revisit whether retrieval should remain page-summary centric or start using a
  stronger canonical read/search dependency.
