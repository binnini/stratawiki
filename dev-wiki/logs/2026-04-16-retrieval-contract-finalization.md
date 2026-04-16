# Retrieval Contract Finalization

## Context

This worktree extended the retrieval read-authority slice beyond grouped ids and
rendered page summaries, but stopped intentionally before answer generation and
before implementing the placeholder `query_personal_knowledge` tool.

## Current Question

What final retrieval contract should this branch leave behind so the next slice
can move toward answer assembly without reopening contract-shape debates?

## Observations

- grouped ids remain the stable retrieval identity output
- grouped rendered page summaries remain useful for title/path/snapshot-aware
  consumer hydration
- adding full canonical record envelopes created unnecessary coupling between
  retrieval payloads and storage-layer schemas
- retrieval needed a narrower, retrieval-owned hydration layer instead

## Options

- keep retrieval at ids plus page summaries only
- expose full canonical envelopes
- expose retrieval-owned summaries mapped from canonical records

## Decision or Working Direction

The branch now leaves retrieval in the third state.

Current retrieval payload shape:

- `personal_ids`
- `interpretation_ids`
- `fact_ids`
- `personal_pages`
- `interpretation_pages`
- `fact_pages`
- optional `personal_records`
- optional `interpretation_records`
- optional `fact_records`
- optional merged `snapshot_ref`

Important contract rules:

- `*_records` are retrieval-facing summaries, not full canonical objects
- Personal summaries expose:
  - `id`
  - `domain`
  - `kind`
  - `title`
  - `summary`
  - `snapshot_ref`
- Interpretation summaries expose:
  - `id`
  - `domain`
  - `kind`
  - `subject_type`
  - `subject_id`
  - `status`
  - `confidence`
  - optional derived `summary`
- Fact summaries expose:
  - `id`
  - `domain`
  - `entity_type`
  - `canonical_key`
  - `scope`
  - optional derived `title`
- match order is preserved from retrieval ranking into hydrated summaries
- `query_personal_knowledge` remains intentionally unimplemented

## Open Questions

- whether the next slice should assemble an answer-generation input bundle from
  ids plus pages plus summaries inside retrieval service or in a separate
  orchestration layer
- whether future retrieval explanation metadata should sit alongside
  `*_records` or replace part of the current grouped shape

## Next Actions

- treat the current retrieval payload as the pre-generation contract baseline
- build answer-generation input assembly on top of this contract rather than
  widening storage envelopes again
- only revisit field names if an external consumer demonstrates a concrete need
