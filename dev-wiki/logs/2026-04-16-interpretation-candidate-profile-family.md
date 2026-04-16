# Interpretation Candidate Profile Family

## Context

The repository already had one deterministic shared interpretation family,
`company_hiring_pattern`, wired through:

- canonical interpretation persistence
- shared markdown rendering
- `graph.rendered_page` upsert
- shared read-path compatibility

The next step was to add one more deterministic recruiting interpretation
family without changing the read entrypoint or breaking the existing family.

## Current Question

What is the smallest additional recruiting interpretation family that can be
derived from the current fact batch shape and reuse the same projection,
rendering, and read-path contracts?

## Observations

- The current recruiting ingestion already stores requirement-like fields on
  `recruitment_section` facts: `career_requirement`,
  `education_requirement`, `other_requirement`, and `openings`.
- Those section fields make it possible to derive a stable company-level view
  of what kind of candidate profile the posting is signaling, without adding
  new fact entities or an LLM-backed step.
- The existing shared rendering slice already treats
  `graph.rendered_page(layer="interpretation", record_id=interpretation_id)`
  as the read contract, so a new family can reuse that path unchanged.
- The existing outbox payload for `interpretation_snapshot_published` already
  supports family metadata per emitted event, so multi-family projection can
  reuse one shared snapshot id while emitting family-specific events.

## Options

- Add another family based on job names or section titles only.
- Add a deterministic family derived from section requirement signals.

## Decision or Working Direction

Take the second option.

The new family is `company_candidate_profile_pattern`.

Implementation direction:

- keep `company_hiring_pattern` unchanged
- project multiple interpretation records from one fact batch
- emit one canonical record per family
- render one markdown artifact per interpretation record
- upsert one `graph.rendered_page` row per interpretation record
- emit one `interpretation_snapshot_published` event per family/record
- skip the new family when the affected batch has no requirement-like section
  signals

## Open Questions

- Whether later shared snapshots should become explicitly family-partitioned
  again instead of using one shared multi-family projection snapshot id.
- Whether the shared projection service should keep accumulating family-specific
  rendering logic or move behind a dedicated shared interpretation rendering
  contract.
- Whether additional deterministic recruiting families should be company-level
  like this one, or start introducing role-level subject ids.

## Next Actions

- Run the Postgres-backed interpretation projection integration test on a
  reachable local database to verify dual-family rendered-page writes.
- Consider extracting family builders if a third deterministic family lands.
- Revisit docs promotion once at least one more family passes through review
  and the multi-family projection shape stabilizes.
