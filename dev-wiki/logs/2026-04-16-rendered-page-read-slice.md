# Rendered Page Read Slice

## Context

The repository already had:

- Personal markdown regeneration into the filesystem
- `graph.rendered_page` upserts during Personal regeneration
- dependency impact lookup that could point at rendered paths

What was still missing was an actual read-side path that consumed those rendered-page rows instead of treating them as write-only metadata.

## Current Question

What is the smallest read vertical slice that proves rendered-page metadata is useful now, without prematurely implementing full retrieval ranking or MCP server bootstrap?

## Observations

- The repository already separates read path and command path in docs, and `knowledge.query.run` is intentionally not the next stable external contract.
- `RetrievalService` still has no implementation, so a full query path would either be fake or would pull too much future ranking/indexing work into one step.
- `graph.rendered_page` already stores enough metadata to resolve a page by `(domain, layer, record_id, scope)` and to list visible pages for a scope.
- Personal regeneration already writes deterministic markdown files, so a read service can combine Postgres metadata with filesystem body loading immediately.

## Options

- Jump directly to a broad retrieval/query service.
- Add a smaller rendered-page read service first, then layer retrieval/list/search behavior on top of it later.

## Decision or Working Direction

Take the second option.

The implemented slice adds:

- rendered page metadata schemas for list and get results
- `RenderingRepository.get_page(...)`
- `RenderingRepository.list_pages(...)`
- filesystem-backed body loading for rendered pages
- `DefaultPageReadService` as the internal read-side service
- unit coverage for the service and Postgres integration coverage for the repository path when `DATABASE_URL` is reachable

This keeps the slice aligned with the documented read-vs-command separation while making `graph.rendered_page` operational instead of speculative.

## Open Questions

- Whether shared Interpretation rendering should use the same repository contract unchanged or split into a distinct shared-page read service once those pages exist.
- Whether future WAS-facing read APIs should expose `record_id` addressing, `path` addressing, or both.
- Whether list ordering should stay `updated_at DESC` or later become family-specific once shared pages and search indexes arrive.
- Whether lexical retrieval should query rendered markdown directly, page metadata first, or canonical records first and use rendered pages only for final readout.

## Next Actions

- Connect this service to the first WAS-facing or MCP-adjacent read endpoint.
- Add shared Interpretation rendering so `layer = interpretation` pages can use the same read path.
- Decide whether retrieval/list APIs should build on top of `DefaultPageReadService` or keep a separate orchestration layer.
- Re-run the Postgres integration suite in an environment with a reachable `DATABASE_URL`.
