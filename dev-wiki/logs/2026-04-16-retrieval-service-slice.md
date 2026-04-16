# Retrieval Service Slice

## Context

The repository already had:

- rendered-page metadata reads through `DefaultPageReadService`
- application-facing page reads through `DefaultPageReadEntrypoint`
- a retrieval interface contract with no concrete implementation

The goal for this task was to add the first retrieval vertical slice without expanding into broad search, ranking, or MCP-facing query contracts.

## Current Question

What is the smallest retrieval implementation that proves the documented `Personal -> Interpretation -> Fact` order while staying aligned with the existing rendered-page read path?

## Observations

- `RetrievalResult` only carried per-layer ids plus one snapshot tuple, so the first implementation needed to stay id-oriented rather than returning full page payloads.
- Existing rendered-page metadata already contains enough structured fields for a narrow lookup slice: `record_id`, `title`, `path`, `scope_ref`, and `snapshot_ref`.
- Shared Interpretation pages already read through the same service boundary as Personal pages, which makes `PageReadService.list_pages(...)` the lowest-friction retrieval seam.
- A no-match response is valid for retrieval, so `RetrievalResult` needed a minimal schema relaxation to allow omission of `snapshot_ref`.

## Options

- Wait for a future lexical/vector index and implement retrieval later.
- Add a small structured lookup service now on top of rendered-page listings.

## Decision or Working Direction

Take the second option.

The implemented slice adds:

- `DefaultRetrievalService`
- layer-aware scope routing:
  - Personal uses the caller scope
  - Interpretation and Fact use shared scope
- structured matching against `record_id`, `title`, and `path`
- deterministic layer order: `Personal -> Interpretation -> Fact`
- snapshot merging that prefers higher-priority layer matches
- unit coverage for exact id lookup, layered title lookup, empty results, and blank-query behavior

This keeps retrieval narrowly defined as candidate id resolution over the read model, not a broad search engine.

## Open Questions

- Whether the next retrieval slice should stay rendered-page centric or switch to canonical repositories once Fact read paths mature.
- Whether future query contracts need per-layer match metadata instead of ids only.
- Whether shared Interpretation and Fact retrieval should later use lexical indexes before rendered-page listings for larger datasets.
- Whether profile context should become a real ranking input or remain only a tie-breaker.

## Next Actions

- Decide when to expose retrieval through an application-facing entrypoint.
- Revisit result shape if a future caller needs page summaries or per-layer explanations.
- Add lexical or graph expansion only after the current structured lookup slice has a stable consumer.
