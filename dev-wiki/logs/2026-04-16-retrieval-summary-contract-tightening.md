# Retrieval Summary Contract Tightening

## Context

The previous retrieval hydration slice added optional `*_records` groups to the
read payload, but those groups still exposed full canonical record envelopes.

That solved the immediate data-availability gap, but it left two contract risks:

- retrieval was coupled too directly to storage-layer envelope shapes
- Fact payloads would be hard to evolve once richer canonical reads arrive

## Current Question

How can the retrieval read slice keep canonical hydration benefits while making
the external contract narrower and more durable?

## Observations

- retrieval consumers mainly need stable identity plus a small amount of
  displayable context
- full Personal and Interpretation envelopes carry fields that are not needed
  for candidate selection or pre-generation inspection
- Fact envelopes are especially unstable because attribute payloads are
  intentionally open-ended
- the right seam is inside retrieval service mapping, not inside repository
  contracts

## Options

- keep exposing full canonical envelopes and document them as provisional
- map canonical records into retrieval-owned summary schemas

## Decision or Working Direction

Take the retrieval-owned summary schema path.

The slice now uses:

- `RetrievalPersonalSummary`
- `RetrievalInterpretationSummary`
- `RetrievalFactSummary`

Mapping rules:

- `personal_records` now return only:
  - `id`
  - `domain`
  - `kind`
  - `title`
  - `summary`
  - `snapshot_ref`
- `interpretation_records` now return only:
  - `id`
  - `domain`
  - `kind`
  - `subject_type`
  - `subject_id`
  - `status`
  - `confidence`
  - optional derived `summary`
- `fact_records` now return only:
  - `id`
  - `domain`
  - `entity_type`
  - `canonical_key`
  - `scope`
  - optional derived `title`

This keeps retrieval payloads useful while breaking direct dependence on full
repository envelopes.

## Open Questions

- whether `fact_records` should later expose a generic `display_value` instead
  of optional `title`
- whether retrieval summaries should eventually be renamed away from
  `*_records` to make it clearer that they are not full canonical objects
- whether answer generation should consume these summaries directly or ask for a
  richer internal assembly object

## Next Actions

- keep repository interfaces unchanged for now
- treat retrieval mapping as the stable external boundary
- revisit naming if a WAS consumer starts depending on these fields directly
