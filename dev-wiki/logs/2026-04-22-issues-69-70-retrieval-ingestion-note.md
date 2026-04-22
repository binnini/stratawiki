# Retrieval and Ingestion Compatibility Note

## Preferred Paths

- Default retrieval remains `Personal -> Interpretation -> Fact`.
- Personal retrieval is metadata-first with bounded markdown-body support so the runtime does not assume DB metadata is the canonical Personal body.
- Graph- or anchor-style expansion remains a support surface only.
- External write clients should treat `DomainProposalBatch` as the primary contract.

## Compatibility Paths

- `ingest_fact_batch` remains available only as a compatibility wrapper around the legacy `SourceRecord -> DomainIngestionPlugin` flow.
- `DefaultCoreIngestionService.prepare_batch()` and `ingest_source()` now act as compatibility aliases for explicit legacy-source helpers.
- Personal anchor reverse lookup remains available only as an opt-in compatibility path in retrieval; it is no longer the default discovery strategy.

## Cleanup Guidance

- Keep `RecruitingSourceIngestionPlugin` only for internal transition, demo seeding, and rollback-safe source-driven flows until all external producers emit `DomainProposalBatch`.
- Prefer adding richer `DomainProposalBatch` producer-side mapping over extending legacy plugin decomposition behavior.
- If a future dedicated markdown search backend is introduced, it should replace the bounded body scan support path before any broader reverse-lookup expansion is reconsidered.
