# Project Phase And TODO Map

## Dashboard

| Area | Status | Note |
| --- | --- | --- |
| Overall phase | In progress | Early implementation, no longer design-only |
| Strongest | Good | Storage/contracts, projection, rendered reads, Personal regen, retrieval plus first personal answer slice |
| Weakest | Early | Broader Personal family coverage, retrieval quality, domain breadth, runtime/ops |
| Next build | Now | Add the next Personal family after `career_transition_plan` |

## Operating Metadata

| Item | Value |
| --- | --- |
| Current branch | `feat/query-personal-knowledge-first-slice` |
| Main worktree | `/home/yebin/projects/stratawiki` |
| Last verified tests | `pytest -q` -> `53 passed, 15 skipped` |
| Last verified DB-backed tests | `DATABASE_URL=postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki pytest -q` -> `53 passed, 15 skipped` |
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
- [x] Bootstrap/server/tool registry wiring exists
- [x] Local and DB-backed validation are both passing on the current baseline

## Next

- [ ] Add `profile_gap_analysis` or `weekly_action_plan` as the next Personal family
- [ ] Improve retrieval explanation/ranking
- [ ] Decide whether answer rationale should become structured instead of plain text

## Later

- [ ] Add more interpretation families
- [ ] Strengthen lexical/canonical retrieval
- [ ] Define the real MCP runtime/transport
- [ ] Improve multi-domain and operational maturity

## One-Line Read

StrataWiki now has a first family-aware personal answer path for
`career_transition_plan`, but broader Personal family coverage and stronger
ranking still remain early.

## Open Questions

- Should retrieval remain page-summary centric, or should canonical
  read/search become the next stronger dependency?
- Should `profile_gap_analysis` or `weekly_action_plan` be the second
  family-aware answer mode?
- When should answer quality move beyond deterministic summary assembly?
- Should answer rationale stay plain text or become structured evidence blocks?

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
