# Retrieval Canonical Hydration Slice

## Context

The current retrieval read authority already returned:

- layered candidate ids
- grouped rendered page summaries
- one merged snapshot tuple

That was enough for candidate routing, but still left a contract gap before the
future `query_personal_knowledge` tool:

- consumers could identify candidates
- consumers could show titles and paths
- consumers still could not read canonical metadata without a second internal
  lookup path

## Current Question

What is the thinnest retrieval extension that strengthens the pre-generation
contract without jumping to answer synthesis or broad page-read orchestration?

## Observations

- retrieval already has stable per-layer ids, so hydration can key off those ids
  without changing match semantics
- repository interfaces for all three layers already exist:
  - `FactRepository.get_by_ids`
  - `InterpretationRepository.get_by_ids`
  - `PersonalRepository.get_by_ids`
- adding canonical hydration stays inside retrieval boundaries more cleanly than
  widening the slice into page-body reads
- bootstrap changes can stay minimal if retrieval simply receives the existing
  Postgres repositories

## Options

- extend retrieval with richer rendered page reads
- extend retrieval with canonical record hydration grouped by layer

## Decision or Working Direction

Take canonical record hydration first.

The implemented slice now adds:

- `personal_records`
- `interpretation_records`
- `fact_records`

Rules for this slice:

- existing `*_ids` remain the stable identity contract
- existing `*_pages` remain the rendered summary contract
- new `*_records` are optional hydration groups, not replacements
- hydration preserves match order from retrieval rather than raw repository
  return order
- Personal hydration uses the caller scope
- Interpretation and Fact hydration use shared scope
- `query_personal_knowledge` remains a placeholder because answer generation is
  still intentionally out of scope

Follow-up tightening:

- retrieval no longer exposes full canonical envelopes in these groups
- `*_records` are now retrieval-facing summaries produced by service-level
  mappers
- Fact hydration now crosses an explicit retrieval mapper boundary so future
  canonical Fact read changes do not leak straight into the retrieval contract

## Open Questions

- whether future retrieval contracts should expose slimmer canonical summaries
  rather than full record envelopes
- whether Fact retrieval should later hydrate from a richer canonical read model
  than the current fact envelope table
- whether answer generation should consume `*_records`, `*_pages`, or both as
  its immediate input contract

## Next Actions

- keep retrieval answerless for now
- decide whether the next thin slice is per-match explanation metadata or
  answer-generation input assembly
- revisit docs once a consumer depends on `*_records` as a stable external
  contract
