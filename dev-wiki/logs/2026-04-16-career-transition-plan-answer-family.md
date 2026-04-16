# Career Transition Plan Answer Family

## Context

The personal query stack already had:

- retrieval candidate resolution
- answer projection metadata
- explanation-rich answer bundles

What it still lacked was a truly domain-shaped Personal family that consumed
that stack instead of only emitting a generic answer wrapper.

## Current Question

What is the smallest first Personal family that can be made genuinely
user-facing without reopening the storage or retrieval contracts?

## Observations

- `career_transition_plan` is already present in the current recruiting docs.
- The stale-marking and regeneration path already uses
  `career_transition_plan` as a real Personal record kind.
- That makes it the lowest-risk first family to reflect in the answer layer.

## Decision or Working Direction

Implement `career_transition_plan` as the first family-aware personal query
answer.

Current behavior:

- if the top Personal match has `kind = career_transition_plan`
- `query_personal_knowledge` still returns the same high-level answer envelope
- but the answer payload now becomes family-aware:
  - `personal_family = career_transition_plan`
  - `recommended_actions`
  - family-specific markdown sections:
    - `Direction`
    - `Why This Plan`
    - `Active Goals`
    - `Recommended Actions`
    - `Plan Context`
    - `Market Signals`
    - `Supporting Evidence`

## Boundary Notes

- Retrieval remains family-agnostic.
- Family selection happens in the answer assembly layer, not inside retrieval.
- The answer contract remains backward-compatible at the outer envelope level;
  the family-specificity is additive in `answer`.

## Testing

- `pytest -q`
  - `53 passed, 15 skipped`
- `DATABASE_URL=postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki pytest -q`
  - `53 passed, 15 skipped`

## Open Questions

- Whether `career_transition_plan` should later gain structured milestones
  instead of only `recommended_actions`.
- Whether `profile_gap_analysis` should be the next family, or whether
  `weekly_action_plan` is a better consumer of the current retrieval signals.

## Next Actions

- Add the next family-aware answer mode, likely `profile_gap_analysis`.
- Decide whether family-aware answers need structured fields beyond markdown and
  free-text rationale.
