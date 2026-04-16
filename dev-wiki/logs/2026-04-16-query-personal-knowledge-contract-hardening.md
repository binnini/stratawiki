# Query Personal Knowledge Contract Hardening

## Context

The previous slice made `query_personal_knowledge` actually return an answer,
but it still reused retrieval-style projection metadata:

- `projection.family = retrieval`
- no explicit answer type
- no explicit generation strategy identifier

That made the external read semantics muddy even though the implementation
boundary was already separate.

## Current Question

What is the smallest contract refinement that makes personal answer reads
distinct from retrieval candidate reads without widening the implementation
scope again?

## Observations

- `retrieve_for_query` is still an authoritative candidate-resolution read.
- `query_personal_knowledge` is now a distinct answer-producing read on top of
  that retrieval primitive.
- Reusing the same projection family for both shapes weakens the read-authority
  vocabulary described in `docs/jobs-wiki-external-was-contract-draft.md`.
- The current answer generation is still deterministic, so the contract should
  admit that directly instead of implying a generic future synthesis model.

## Options

- Keep the retrieval projection metadata and document the difference informally.
- Give personal answer reads their own projection family and expose the current
  generation strategy explicitly.

## Decision or Working Direction

Take the second option.

New contract shape:

- `projection.family = answer`
- `projection.kind = personal_query`
- `projection.scope = shared | tenant | user`
- `projection.layers = [personal, interpretation, fact]`

Answer payload metadata now also includes:

- `answer_type = personal_query_answer`
- `generation_strategy = deterministic_summary_bundle_v1`

## Why This Boundary

- Retrieval candidate reads and answer reads are both authoritative, but they
  are authoritative for different projection families.
- This keeps the read-authority language aligned with the actual consumer shape
  rather than the internal dependency graph.
- The explicit generation strategy makes current deterministic behavior visible
  without freezing the future answer engine architecture.

## Testing

- `pytest -q`
  - `53 passed, 15 skipped`
- `DATABASE_URL=postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki pytest -q`
  - `53 passed, 15 skipped`

## Open Questions

- Whether answer projections should later expose a version token separate from
  retrieval snapshots once multiple answer strategies exist.
- Whether the answer payload should grow a structured rationale field before
  adding any LLM-backed generation.

## Next Actions

- Improve bundle richness and retrieval explanation metadata so the answer layer
  can explain why context was selected.
- Add the first domain-shaped personal family that uses the hardened answer
  contract instead of only the generic answer slice.
