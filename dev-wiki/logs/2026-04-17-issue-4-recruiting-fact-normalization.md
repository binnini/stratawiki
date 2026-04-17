# Issue #4 Recruiting Fact Normalization

## Purpose

This note records the focused implementation pass for issue `#4 Add recruiting fact normalization for initial entities`.

`docs/` remains the source of truth.
This file is only a development log for the implementation choices, the validated scope, and the follow-up work intentionally left out of the first slice.

## Specs Reviewed

- `AGENTS.md`
- `docs/implementation-roadmap.md`
- `docs/three-layer-data-model-spec.md`
- `docs/recruiting-domain-schema-spec.md`
- `docs/mcp-architecture.md`

## Acceptance Criteria Restated

In repository terms, issue `#4` means:

- normalize recruiting source data into docs-aligned initial Fact entities
- ensure the first slice explicitly includes `job_posting`, `company`, and `skill`
- persist at least one relation path from the posting to normalized entities
- keep the work inside the canonical Fact ingestion pipeline without widening into interpretation or MCP tool scope

## What Was Already Implemented

Before this pass, the recruiting ingestion slice already supported:

- `WorknetRecruitingExternalAdapter` producing a normalized `SourceRecord`
- `RecruitingSourceIngestionPlugin` extracting a thin initial set of Fact records
- relation creation from `job_posting` to source-shaped child entities
- end-to-end persistence through `DefaultCoreIngestionService`

However, the extracted entity set was still source-shaped:

- `job_posting`
- `company`
- `job`
- `recruitment_section`

That did not yet match the recommended initial recruiting Fact slice in `docs/recruiting-domain-schema-spec.md`.

## Focused Changes Made

### 1. Shifted extraction to docs-aligned initial entities

The recruiting ingestion plugin now emits:

- `job_posting`
- `company`
- `role`
- `skill`
- `location`

This replaces the earlier emphasis on `job` and `recruitment_section` as canonical entities in the initial Fact slice.

### 2. Added explicit `skill` Facts

The first slice now creates explicit `skill` Fact records from recruiting requirement text.

This implementation is intentionally narrow and deterministic:

- it extracts explicit skill-like Latin-script tokens from posting and section text
- it avoids broad heuristic parsing that would be hard to trust in the canonical Fact layer

### 3. Updated minimal relation generation

Relations now align with the recruiting schema guidance:

- `job_posting -> company` via `posted_by`
- `job_posting -> role` via `has_role`
- `job_posting -> skill` via `requires_skill`
- `job_posting -> location` via `located_in`

### 4. Added dedupe behavior for normalized entities

Repeated skill mentions and repeated section locations now collapse to one canonical Fact and one relation edge within the batch.

### 5. Hardened canonical keys for non-ASCII labels

Fallback canonical key generation now uses a stable hash when ASCII slugging would otherwise collapse a value such as `서울` to `unknown`.

This keeps location and name-derived canonical keys stable without pretending the project already has a full multilingual taxonomy.

## Validation

Executed in the isolated issue worktree with:

```bash
PYTHONPATH=src pytest tests/test_recruiting_ingestion.py tests/test_core_ingestion_service.py
```

Result:

- `8 passed`

## Remaining Gaps

These are intentionally left for follow-up rather than widening issue `#4`:

- multilingual skill extraction is still limited
- alias merging and taxonomy-backed skill canonicalization are not yet implemented
- Korean skill names and mixed-language variants are not normalized into a richer skill dictionary

This follow-up work was split into GitHub issue `#22 Improve recruiting skill normalization with multilingual extraction`.

## Outcome

Recommendation after implementation:

- treat issue `#4` as complete for the initial Fact normalization slice
- continue multilingual and taxonomy-backed skill normalization under `#22`
