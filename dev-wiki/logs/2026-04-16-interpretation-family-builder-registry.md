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

- Whether future recruiting families should stay in the same local registry
  module or move behind domain-specific packages once recruiting adds more
  family count and subject types.
- Whether rendered markdown concerns should later split again so builders own
  canonical record construction while a separate renderer registry owns page
  formatting.
- Whether family enablement should eventually become configuration-driven per
  domain rather than code-registered.

## Next Actions

- Keep new shared interpretation families out of
  `DefaultInterpretationProjectionService`; add them through the registry
  instead.
- If a third or fourth family lands, consider a recruiting-specific builder
  package so the registry module does not become the next accumulation point.
- Re-run the Postgres-backed suite when a reachable DB is available to confirm
  the refactor preserved rendered-page writes and snapshot publication.
