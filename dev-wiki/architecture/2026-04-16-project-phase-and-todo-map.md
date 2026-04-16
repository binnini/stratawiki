# Project Phase And TODO Map

## Dashboard

| Area | Status | Note |
| --- | --- | --- |
| Overall phase | In progress | Early implementation, no longer design-only |
| Strongest | Good | Storage/contracts, projection, rendered reads, Personal regen, retrieval plus family-aware personal answer slice |
| Weakest | Early | Canonical candidate discovery breadth, broader Personal coverage, domain breadth, runtime/ops |
| Next build | Now | Decide whether to widen retrieval from canonical ranking strengthening into canonical candidate discovery |

## Operating Metadata

| Item | Value |
| --- | --- |
| Current branch | `feat/query-personal-knowledge-first-slice` |
| Main worktree | `/home/yebin/projects/stratawiki` |
| Last verified tests | `pytest -q` -> `57 passed, 15 skipped` |
| Last verified DB-backed tests | `DATABASE_URL=postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki pytest -q` -> `57 passed, 15 skipped` |
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
- [x] Bootstrap/server/tool registry wiring exists
- [x] Local and DB-backed validation are both passing on the current baseline

## Next

- [ ] Decide whether retrieval should move from canonical ranking strengthening to canonical candidate discovery
- [ ] Decide which additional Personal family matters most after the current trio
- [ ] Decide whether any one family now needs richer structured fields than `recommended_actions`

## Later

- [ ] Add more interpretation families
- [ ] Strengthen lexical/canonical retrieval
- [ ] Define the real MCP runtime/transport
- [ ] Improve multi-domain and operational maturity

## One-Line Read

StrataWiki now has three family-aware personal answer paths plus canonical-aware
retrieval ranking, but broader canonical retrieval discovery and domain maturity
still remain early.

## Open Questions

- Should retrieval now move beyond rendered page enumeration entirely, or is
  canonical-aware ranking sufficient for one more slice?
- When should answer quality move beyond deterministic summary assembly?
- Which follow-up slice matters more now: canonical retrieval quality or another
  Personal family?

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
