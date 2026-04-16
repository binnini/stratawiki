# Personal Read Entrypoint Slice

## Context

The previous slice added:

- scope-aware rendered page reads from `graph.rendered_page`
- filesystem markdown body loading
- `DefaultPageReadService` as the internal read-side service

What still did not exist was an application-facing read authority entrypoint that a WAS or other internal caller could use directly.

## Current Question

What is the smallest read API slice that turns the new page-read service into a real external boundary without prematurely implementing full retrieval/query/search semantics?

## Observations

- Current docs intentionally separate read path from command path, and they explicitly avoid making broad query execution the next fixed contract.
- The repository already has enough information to serve Personal page reads authoritatively for the current projection family.
- Personal rendered pages are the only rendered artifacts with a real write path today, so they are the right first read authority slice.
- The existing ingestion entrypoint already establishes the preferred pattern: application-facing wrapper plus structured result envelopes.

## Options

- Expose a broad generic retrieval API next.
- Expose a narrower rendered-page entrypoint first and keep retrieval/query orchestration for later.

## Decision or Working Direction

Take the narrower entrypoint first.

The implemented slice adds:

- `DefaultPageReadEntrypoint`
- generic `get_page(...)` and `list_pages(...)`
- thin personal wrappers:
  - `get_personal_page(...)`
  - `list_personal_pages(...)`
- structured read result envelopes with `read_model_state`
- a default builder that wires Postgres rendered-page metadata to filesystem markdown loading

This makes the current Personal rendered-page projection reachable through a real application-facing boundary while preserving the documented read-vs-command separation.

## Open Questions

- Whether the first WAS-facing contract should expose only Personal reads or also shared Interpretation page reads once shared rendering exists.
- Whether future read authority responses should include stronger projection-family metadata in addition to `read_model_state`.
- Whether `page_not_found` should remain a terminal response or later distinguish `pending` from truly absent once shared render workers exist.
- Whether path-based addressing should become an external option or remain internal while record-id addressing stays primary.

## Next Actions

- Add shared Interpretation rendering and expose it through the same entrypoint.
- Decide whether the next read slice should be page-detail enrichment or retrieval/list orchestration.
- Re-run the Postgres integration suite with a reachable `DATABASE_URL`.
- Keep `server.py` and MCP bootstrap deferred until the internal read and mutation entrypoints are slightly more complete.
