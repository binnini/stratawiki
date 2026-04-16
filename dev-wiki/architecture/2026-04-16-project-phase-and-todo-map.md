# Project Phase And TODO Map

## Dashboard

| Area | Status | Note |
| --- | --- | --- |
| Overall phase | In progress | Early implementation, no longer design-only |
| Strongest | Good | Storage/contracts, projection, rendered reads, Personal regen, retrieval plus family-aware personal answer slice, indexed Postgres FTS retrieval, direct local CLI invocation |
| Weakest | Early | Broader Personal coverage, domain breadth, full MCP transport/runtime, richer operator flows |
| Next build | Now | Decide whether the next completion slice is worker/runtime operation, scripted end-to-end walkthroughs, or the real MCP transport |

## Operating Metadata

| Item | Value |
| --- | --- |
| Current branch | `feat/query-personal-knowledge-first-slice` |
| Main worktree | `/home/yebin/projects/stratawiki` |
| Last verified tests | `pytest -q` -> `60 passed, 19 skipped` |
| Last verified DB-backed tests | `DATABASE_URL=postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki pytest -q` -> `60 passed, 19 skipped` |
| Current dashboard source | `dev-wiki/architecture/2026-04-16-project-phase-and-todo-map.md` |
| Official roadmap | `docs/implementation-roadmap.md` |

## Done

- [x] Fact ingest writes canonical storage and emits `fact_ingested`
- [x] Interpretation projection exists with at least 2 deterministic families
- [x] Shared Interpretation pages are rendered and readable
- [x] Personal stale marking and regeneration path exists
- [x] Page read authority exists for Personal and shared Interpretation pages
- [x] Retrieval candidate read exists via `retrieve_for_query`
- [x] `query_personal_knowledge` now returns a first deterministic answer payload
- [x] Personal answer reads now use distinct answer projection metadata
- [x] Personal answer bundle now carries retrieval scores and match reasons
- [x] `career_transition_plan` now has a first family-aware answer rendering path
- [x] `profile_gap_analysis` now has a second family-aware answer rendering path
- [x] `weekly_action_plan` now has a third family-aware answer rendering path
- [x] Retrieval explanations now expose rank and token-match metadata
- [x] Personal answers now return structured rationale items
- [x] Current decision: retrieval remains page-summary-first for now
- [x] Current decision: structured answer fields stay at `recommended_actions` plus rationale items
- [x] Retrieval ranking now uses canonical summaries/titles in addition to rendered page metadata
- [x] Stronger retrieval ranking now affects personal answer lead-item selection without changing the answer contract
- [x] Retrieval now supports bounded canonical candidate discovery in addition to rendered page enumeration
- [x] Canonical-only Personal candidates can now influence answer-family selection without synthetic rendered pages
- [x] Canonical candidate discovery now uses query-aware lexical search instead of recent-record listing
- [x] Canonical-only Interpretation matches now preserve `fact_snapshot_id` during retrieval snapshot merge
- [x] Canonical-only Fact matches now preserve `fact_snapshot_id` during retrieval snapshot merge
- [x] Retrieval explanations now explicitly expose whether a match had a rendered page
- [x] Canonical retrieval search now uses indexed Postgres FTS instead of pragmatic normalized `LIKE`
- [x] Bootstrap/server/tool registry wiring exists
- [x] Local CLI now exposes the wired tool surface for direct inspection and invocation
- [x] Local and DB-backed validation are both passing on the current baseline

## Next

- [ ] Decide whether the next system-completion slice should expose projection workers or other runtime operations directly
- [ ] Decide whether to add a scripted end-to-end walkthrough on top of the new local CLI
- [ ] Decide when the real MCP transport/runtime should replace the current local bootstrap path

## Later

- [ ] Add more interpretation families
- [ ] Strengthen lexical/canonical retrieval
- [ ] Define the real MCP runtime/transport
- [ ] Improve multi-domain and operational maturity

## One-Line Read

StrataWiki now has three family-aware personal answer paths plus indexed
canonical FTS retrieval with snapshot carry-through, explicit no-rendered-page
explainability, and a direct local CLI for trying the wired tool surface, but
runtime/transport maturity still remains early.

## Open Questions

- Should the next operator-facing slice expose projection workers and admin flows
  directly, or wait for the real MCP transport?
- How much scripted guidance should sit on top of the local CLI before the
  transport exists?
- When should answer quality move beyond deterministic summary assembly?

## Background

- This is a working dashboard, not the official roadmap.
- Official phase planning stays in `docs/implementation-roadmap.md`.
- Use this file for quick orientation:
  what is done, what is next, and what is still weak.

## Maintenance Rule

- Keep this note updated whenever the project gains a new end-to-end slice or a
  major shift in next-step priority.
- If this note and the official roadmap drift, update `docs/` only for stable
  conclusions and keep working interpretation here first.
