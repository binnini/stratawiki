# Personal Query Bundle Richness

## Context

The personal answer contract was already separated from retrieval candidate
reads, but the actual answer bundle was still too thin:

- no retrieval score surfaced into the answer bundle
- no explicit match reason
- no answer rationale beyond the top summary sentence

That made the answer readable, but not yet very explainable.

## Current Question

What is the smallest improvement that makes `query_personal_knowledge`
explain why a candidate was selected without turning retrieval into a full
ranking subsystem redesign?

## Observations

- `DefaultRetrievalService` already has internal match scoring.
- The missing piece was exposing retrieval-owned explanation metadata in a
  stable, narrow shape.
- The answer layer should consume explanation metadata rather than recompute its
  own hidden ranking logic.

## Decision or Working Direction

Expose retrieval-owned explanation metadata per layer and carry it through to
the personal answer bundle.

New retrieval fields:

- `personal_explanations`
- `interpretation_explanations`
- `fact_explanations`

Each explanation item currently includes:

- `layer`
- `record_id`
- `score`
- `match_type`
- `matched_fields`
- `profile_boost_applied`

The personal query bundle now copies the relevant parts into each context item:

- `retrieval_score`
- `match_reason`
- `matched_fields`

The answer payload now also includes:

- `answer_rationale`

## Boundary Notes

- Retrieval remains the primitive and owns scoring/explanation metadata.
- Personal answer assembly remains the consumer and formatter of that metadata.
- No canonical storage envelope was widened for this slice.

## Testing

- `pytest -q`
  - `53 passed, 15 skipped`
- `DATABASE_URL=postgresql+psycopg://stratawiki:stratawiki@localhost:5432/stratawiki pytest -q`
  - `53 passed, 15 skipped`

## Open Questions

- Whether the retrieval explanation shape should later expose normalized score
  bands or ranking position explicitly.
- Whether answer rationale should stay plain text or become structured with
  bullet-like evidence blocks.

## Next Actions

- Add a first real Personal family that uses the richer bundle and rationale
  fields.
- Consider exposing retrieval explanation metadata through the external WAS
  contract as optional debug/explainability fields.
