# External Ingestion Delegation Review

## Context

Reviewed whether StrataWiki should delegate ingestion to an external system, based on the current docs and WorkNet adapter shape.

## Current Question

Is the current decision to delegate ingestion externally appropriate for this project?

## Observations

- The current design does not fully delegate ingestion. It delegates external fetching and domain-normalized payload production, then reclaims control at `SourceRecord` and domain plugin boundaries.
- Official docs consistently keep canonical identity, validation, persistence, snapshot publication, outbox publication, and propagation inside StrataWiki.
- The WorkNet adapter currently stops at `SourceRecord`, which is the safer default integration level.
- This design protects StrataWiki from upstream schema leakage and release coupling.

## Options

- Keep the current source-level or controlled-intermediate adapter boundary.
- Move more extraction responsibility into the external system and ingest near-final batches.
- Pull all ingestion logic back into StrataWiki and reduce the external system to a raw fetch client.

## Decision or Working Direction

Prefer the current boundary for v1.

It is appropriate because:

- StrataWiki keeps authority over canonicalization and downstream consistency.
- the external system can evolve as a source integration package without redefining StrataWiki core contracts.
- recruiting remains the first domain without contaminating the platform core.

## Open Questions

- How much canonical-key authority should external payloads be allowed to suggest?
- What happens when upstream payload schema versions drift from StrataWiki domain expectations?
- Should StrataWiki persist the external normalized payload itself for replay and audit?
- When would a batch-level adapter become worth the additional coupling?

## Next Actions

- Keep external integrations at `SourceRecord` by default.
- Define strict adapter validation and version-mismatch handling.
- Add replayability policy for normalized external payloads.
- Consider `IngestionBatch`-level adapters only for stable, trusted upstream extraction services.
