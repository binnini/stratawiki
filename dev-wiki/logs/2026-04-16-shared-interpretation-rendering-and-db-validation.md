# Shared Interpretation Rendering And DB Validation

## Context

The repository already had:

- deterministic Fact -> Interpretation projection
- Personal regeneration writing markdown plus `graph.rendered_page`
- internal and application-facing read paths for Personal pages

The next missing vertical slice was the shared side of readable output: Interpretation pages existed canonically, but there was still no shared markdown artifact or page-level read path proving the same mechanism worked outside Personal.

## Current Question

What is the smallest shared rendering slice that closes the gap between Interpretation projection and rendered-page reads, and can that slice be verified against real Postgres rather than only skipped integration tests?

## Observations

- `graph.rendered_page` already uses `(layer, record_id, scope)` and existing dependency impact lookup can resolve a rendered path when the page row shares the same layer and record id.
- That means an Interpretation rendered page does not need a separate graph shape right now; writing `layer = interpretation` with `record_id = interpretation_id` is enough.
- The current deterministic `company_hiring_pattern` record already contains enough body fields to produce a stable readable shared page without introducing another rendering subsystem abstraction first.
- Database integration had accumulated enough skipped tests that another read/render slice should not land without actually running the suite against a reachable Postgres.

## Options

- Delay shared rendering until a larger rendering subsystem refactor.
- Render one deterministic Interpretation family now, reuse the existing rendering repository, and validate the whole repository/service path against real Postgres immediately.

## Decision or Working Direction

Take the second option.

The implemented slice now does the following:

- `DefaultInterpretationProjectionService` writes a shared markdown artifact for `company_hiring_pattern`
- the artifact upserts `graph.rendered_page` with `layer = interpretation`
- `DefaultPageReadEntrypoint` now includes thin shared wrappers:
  - `get_interpretation_page(...)`
  - `list_interpretation_pages(...)`
- integration coverage now includes the shared interpretation render write path

Database validation was also run against a real local Postgres instance:

- `docker compose up -d postgres`
- `DATABASE_URL=postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki python3 -m alembic upgrade head`
- `DATABASE_URL=postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki pytest -q`
- final result: `40 passed in 8.26s`

## Open Questions

- Whether shared rendering should stay inside the projection service for one more slice or move behind a dedicated shared rendering subsystem contract.
- Whether Interpretation page metadata should include more explicit provenance beyond title and snapshot tuple once richer families exist.
- Whether the read authority should eventually expose projection-family metadata or visibility state beyond `applied` / `not_applicable`.
- Whether shared rendered page paths should remain family-based markdown paths or later become partition-aware by subject segment and freshness window.

## Next Actions

- Add the next shared interpretation family or generalize shared rendering conventions across families.
- Decide whether retrieval/list orchestration should build directly on page reads or on canonical Interpretation search first.
- Wire one WAS-facing shared read endpoint shape on top of the existing page read entrypoint.
- Keep real Postgres validation in the loop for subsequent storage, rendering, and read-path slices rather than allowing integration coverage to drift back to skipped-only.
