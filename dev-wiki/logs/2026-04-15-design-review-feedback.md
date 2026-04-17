# StrataWiki Design Review Feedback

## Context

Reviewed the current official docs, working notes, and early code scaffolding to assess architectural coherence and implementation risk.

## Current Question

Is the current StrataWiki design internally consistent, and what needs clarification before deeper implementation?

## Observations

- The three-layer split is consistent across `README`, architecture docs, working notes, and early schema/interfaces.
- The repo already reflects the intended seams: domain ingestion plugin, repository protocols, rendering boundary, and PostgreSQL-backed storage stubs.
- The design is strongest around conceptual separation of canonical state, rendered state, and dependency/caching concerns.
- The implementation is still mostly contract-first; the code does not yet prove the harder parts such as snapshot publication, invalidation routing, or ACL-safe retrieval.

## Options

- Keep the current architecture and begin vertical-slice implementation with tighter contract hardening around snapshots and scope.
- Simplify the model further by collapsing some layers early, at the cost of future explainability and multi-user clarity.
- Expand implementation breadth now, which risks locking in ambiguous contracts before the difficult invariants are settled.

## Decision or Working Direction

Prefer the first option.

The architecture is directionally strong and should not be collapsed. The next implementation work should narrow ambiguity in a few high-risk seams:

- unify snapshot terminology and tuple shape across docs and code
- make scope/ACL invariants explicit enough to enforce consistently
- define whether interpretation records are append-only versioned records or mutable current-state envelopes
- separate dependency graph requirements from semantic graph requirements at the storage-contract level, not only in prose
- define stronger idempotency and canonical-key rules for ingestion plugins

## Open Questions

- What is the exact publish unit for interpretation snapshots: global, family, segment, or subject partition?
- Which identifiers are immutable versus versioned in canonical stores?
- How will user/tenant scope be guaranteed in retrieval and graph traversal before introducing DB-level enforcement?
- What operational signal marks a personal artifact as safe-to-serve stale versus invalid?

## Next Actions

- Add one concrete snapshot contract doc or schema shared by Fact, Interpretation, Personal, cache, and tool responses.
- Write a short ACL invariants note covering repository filters, graph traversal, and cache key composition.
- Implement one end-to-end vertical slice from source adapter -> fact write -> snapshot publish -> outbox event.
- Delay broader retrieval/search sophistication until the snapshot and scope contracts are harder.
