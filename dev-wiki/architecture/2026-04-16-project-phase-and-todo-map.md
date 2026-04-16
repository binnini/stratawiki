# Project Phase And TODO Map

## Dashboard

| Area | Status | Note |
| --- | --- | --- |
| Overall phase | In progress | Early implementation, no longer design-only |
| Strongest | Good | Storage/contracts, projection, rendered reads, Personal regen, retrieval plus first personal answer slice |
| Weakest | Early | Answer richness, retrieval explanation, domain breadth, runtime/ops |
| Next build | Now | Improve answer bundle richness and the first real Personal family |

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
- [x] Bootstrap/server/tool registry wiring exists
- [x] Local and DB-backed validation are both passing on the current baseline

## Next

- [ ] Improve the answer-generation input bundle and context richness
- [ ] Add 1-2 truly user-facing Personal families
- [ ] Improve retrieval explanation/ranking

## Later

- [ ] Add more interpretation families
- [ ] Strengthen lexical/canonical retrieval
- [ ] Define the real MCP runtime/transport
- [ ] Improve multi-domain and operational maturity

## One-Line Read

StrataWiki now has a distinct personal answer read contract on top of retrieval,
but answer richness and real Personal families still remain early.

## Open Questions

- Should retrieval remain page-summary centric, or should canonical
  read/search become the next stronger dependency?
- Which Personal family is the best first real consumer of answer generation?
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
