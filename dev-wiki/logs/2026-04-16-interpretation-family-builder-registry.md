# Interpretation Family Builder Registry

## Context

The shared interpretation projection path already supports at least two
deterministic families:

- `company_hiring_pattern`
- `company_candidate_profile_pattern`

Rendered page write/read behavior is already proven, but
`DefaultInterpretationProjectionService` had started to accumulate
family-specific record building, summary composition, markdown rendering, and
family dispatch in one file.

## Current Question

What is the smallest refactor that makes shared interpretation projection more
extendable for additional families without changing the existing outbox,
snapshot, dependency, or rendered-page contracts?

## Observations

- The projection service still has one clear core responsibility:
  load the fact batch, coordinate persistence, publish the snapshot, replace
  dependency edges, write rendered artifacts, and emit outbox events.
- The family-specific variation points are separate from that orchestration:
  subject extraction, optional skip logic, canonical body construction, and
  rendered markdown layout.
- The second family already introduced optional build behavior
  (`company_candidate_profile_pattern` returns no record when no requirement
  signals exist), which is a good indicator that family registration should be
  explicit rather than hard-coded in a sequential helper list.

## Options

- Keep adding `_build_*` and `_build_*_rendered_artifact` methods to the
  projection service.
- Extract one family builder abstraction and keep the service as a coordinator.

## Decision or Working Direction

Take the second option.

The structure introduced in this worktree is:

- `InterpretationBuildContext`
  shared inputs passed to a family builder
- `InterpretationFamilyBuilder`
  owns `build_record(...)` and `build_rendered_artifact(...)`
- `InterpretationFamilyRegistry`
  owns enabled builder ordering and `kind -> builder` dispatch
- `DefaultInterpretationProjectionService`
  remains responsible for orchestration only

Separation rule:

- service owns batch-level orchestration and persistence
- builder owns family-specific canonical shape and markdown rendering
- registry owns which families are enabled and how rendered dispatch resolves

## Open Questions

- The immediate registry growth risk is now reduced by moving to
  `services/interpretation_families/` with one file per family plus separate
  `base.py`, `common.py`, and `registry.py`.
- Rendered markdown remains colocated with each builder for now because the
  current families still have a simple 1:1 relationship between canonical
  record shape and markdown shape.
- A separate renderer registry should be reconsidered only when multiple
  families start sharing one canonical subject shape with different page
  layouts, or when one family needs multiple render targets.
- Whether family enablement should eventually become configuration-driven per
  domain rather than code-registered.

## Next Actions

- Keep new shared interpretation families out of
  `DefaultInterpretationProjectionService`; add them through the registry
  instead.
- Keep each new family in its own module under
  `services/interpretation_families/` so extension remains additive instead of
  requiring edits to one large shared file.
- Revisit renderer splitting only if page-format variance starts growing faster
  than canonical interpretation-family count.
- Re-run the Postgres-backed suite when a reachable DB is available to confirm
  the refactor preserved rendered-page writes and snapshot publication.

## Verification

- `pytest -q`
  - `41 passed, 14 skipped, 1 warning`
- `DATABASE_URL=postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki pytest -q`
  - `41 passed, 14 skipped, 1 warning`

## Final State

- `DefaultInterpretationProjectionService` now remains a batch coordinator only.
- Shared interpretation family logic now lives under
  `src/wiki_mcp/services/interpretation_families/`.
- Current package split:
  - `base.py`
  - `common.py`
  - `registry.py`
  - `company_hiring_pattern.py`
  - `company_candidate_profile_pattern.py`
- Renderer splitting was intentionally deferred because current families still
  have a 1:1 relationship between canonical record shape and markdown layout.

## Commits

- `793efb4` `Refactor interpretation family builders`
- `0f62451` `Split interpretation family modules`
