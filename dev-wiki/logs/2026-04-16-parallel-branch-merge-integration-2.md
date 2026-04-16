# Parallel Branch Merge Integration 2

## Context

The current base branch `feat/read-authority-contract` already contained:

- rendered page read authority for Personal and shared Interpretation pages
- retrieval read authority with grouped ids and page summaries
- thin bootstrap and tool registry wiring
- deterministic shared interpretation families and DB-backed validation history

This session merged three follow-up parallel branches on top of that base:

- `feat/interpretation-family-`
- `feat/bootstrap-tool-layer`
- `feat/retrieval-canonical-hydration`

## Current Question

Can these three branches be integrated on the current base without semantic
drift across:

- retrieval read contract
- page read contract
- interpretation projection/family builder structure
- bootstrap/server/tool registry wiring
- official docs and dev-wiki status notes

## Observations

- The branch overlap was limited but real:
  - interpretation branch owned projection-family refactoring and one official
    architecture note
  - bootstrap branch owned tool-layer contracts plus roadmap/runtime notes
  - retrieval branch overlapped bootstrap on `bootstrap.py`,
    `tests/test_server_bootstrap.py`, and roadmap/doc contract text
- No textual conflicts occurred in any of the three merges.
- The semantic integration risk was concentrated in two areas:
  - whether retrieval canonical hydration was actually wired through the thin
    bootstrap/server path
  - whether roadmap/WAS contract docs still described the merged state
- Post-merge inspection confirmed the retrieval bootstrap wiring is aligned:
  server bootstrap now injects Postgres Fact/Interpretation/Personal
  repositories into `DefaultRetrievalService`, so `retrieve_for_query` returns
  optional `*_records` hydration through the real server/tool path as intended.

## Options

- Rewrite the three slices manually after inspecting each branch diff.
- Preserve branch history with sequential merge commits, then validate and only
  patch the merged baseline where semantic drift remains.

## Decision or Working Direction

Take the second option.

Merge order used:

- `feat/interpretation-family-`
- `feat/bootstrap-tool-layer`
- `feat/retrieval-canonical-hydration`

Final integration decisions:

- keep the interpretation family registry split:
  projection service stays orchestration-only, family modules own per-family
  record/render logic
- keep retrieval candidate reads answerless:
  `retrieve_for_query` remains a retrieval authority slice, while
  `query_personal_knowledge` stays placeholder
- keep retrieval hydration grouped and retrieval-owned:
  ids are still the stable identity contract, page summaries remain the read
  model contract, and optional `*_records` stay summary-level rather than full
  canonical envelopes
- keep the thin bootstrap/tool registry path authoritative for current server
  wiring and public tool schemas
- update only stable official docs:
  roadmap status and WAS retrieval contract wording now match the merged code

## Open Questions

- Whether the interpretation family registry should later become
  configuration-driven per domain rather than code-registered.
- Whether retrieval explanation metadata should appear before answer generation,
  or whether the next slice should go straight to answer-input assembly.
- Whether the current `50 passed, 14 skipped` baseline should be reduced in
  skip count by making more DB-backed tests unconditional once local bootstrap
  is fully routine.

## Next Actions

- Use this merged branch as the baseline for the next read/retrieval/tool-layer
  slice.
- If answer generation lands next, build it on top of the current retrieval
  ids/pages/records contract instead of widening storage envelopes again.
- Keep DB-backed verification in the merge workflow for future service and
  bootstrap changes.

## Verification

- merge order:
  - `feat/interpretation-family-`
  - `feat/bootstrap-tool-layer`
  - `feat/retrieval-canonical-hydration`
- textual conflicts:
  - none
- semantic conflicts:
  - one checked closely: retrieval canonical hydration had to remain wired
    through bootstrap/server/tool registry; merged result is consistent
- test commands:
  - `pytest -q`
  - `bash scripts/bootstrap_db.sh`
  - `DATABASE_URL=postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki pytest -q`
- results:
  - `50 passed, 14 skipped in 0.42s`
  - Postgres bootstrap succeeded and Alembic upgraded successfully
  - `50 passed, 14 skipped in 0.42s`
