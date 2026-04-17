# Issue #5 Interpretation Proposal Validation

## Purpose

This note records the focused implementation pass for issue `#5 Implement interpretation proposal and validation flow`.

`docs/` remains the source of truth.
This file is only a development log describing the scoped implementation choices made in this branch.

## Audit Scope

Reviewed against:

- `AGENTS.md`
- `docs/implementation-roadmap.md`
- `docs/interpretation-schema-and-lifecycle-spec.md`
- `docs/three-layer-data-model-spec.md`
- `docs/llm-orchestration-and-retrieval-spec.md`
- `docs/mcp-architecture.md`

Primary code inspected:

- `src/wiki_mcp/schemas/interpretation_record.py`
- `src/wiki_mcp/services/interpretation_families/`
- `src/wiki_mcp/services/interfaces/repositories.py`
- `src/wiki_mcp/storage/postgres/repositories.py`
- `src/wiki_mcp/services/retrieval.py`
- `src/wiki_mcp/services/personal_query.py`

## Issue #5 Acceptance Criteria Restated

In repository terms, issue `#5` means:

- persist proposal-shaped shared `InterpretationRecord` values from a fact snapshot
- keep those records in a non-published lifecycle state until program validation passes
- validate required envelope metadata before publish
- verify that referenced evidence fact IDs exist inside the current scope
- reject invalid proposals with structured errors rather than silently accepting them
- keep non-published interpretations hidden from normal retrieval

## What Already Existed

- interpretation lifecycle statuses already included `proposed`, `validated`, `published`, and `rejected`
- the interpretation repository contract and Postgres implementation already existed
- the interpretation family registry already had a proposal-builder shape
- retrieval already included an interpretation layer, but it did not yet enforce published-only visibility

## Focused Fixes Made

### 1. Minimal proposal service

Added `InterpretationProposalService` to:

- normalize builder output into proposal-shaped interpretation records
- persist proposals against a fact snapshot
- validate proposals by ID
- move valid proposals to `validated`
- move invalid proposals to `rejected`

Files:

- `src/wiki_mcp/services/interpretation_proposals.py`
- `src/wiki_mcp/services/__init__.py`

### 2. Structured validation result and error shape

Added a dedicated schema for structured proposal validation results and errors.

Why:

- issue `#5` requires invalid proposals to fail with structured errors
- the existing generic validation result shape was too coarse for interpretation lifecycle review

Files:

- `src/wiki_mcp/schemas/interpretation_validation_result.py`
- `src/wiki_mcp/schemas/__init__.py`

### 3. Fuller interpretation envelope persistence

Extended the Postgres interpretation repository to persist and reload:

- `family`
- `title`
- `claim`
- `summary`
- `evidence`
- `relations`

Why:

- the docs treat these as part of the stable interpretation envelope
- the prior repository implementation dropped important proposal metadata during persistence

Files:

- `src/wiki_mcp/storage/postgres/repositories.py`

### 4. Retrieval visibility aligned to lifecycle docs

Restricted default interpretation retrieval to `published` and `stale`.

Why:

- docs specify that `proposed`, `validated`, and `rejected` should be hidden from normal user retrieval

Files:

- `src/wiki_mcp/storage/postgres/repositories.py`
- `src/wiki_mcp/services/retrieval.py`
- `src/wiki_mcp/schemas/retrieval_interpretation_summary.py`

### 5. Family registry targeting

Adjusted the family registry to prefer the explicitly requested family when one is supplied in the proposal context.

Why:

- proposal generation should stay scoped to the requested family instead of fan-out across every registered builder

Files:

- `src/wiki_mcp/services/interpretation_families/registry.py`

## Validation Run

Executed in the isolated worktree with:

```bash
PYTHONPATH=src pytest tests/test_interpretation_proposal_service.py tests/test_interpretation_repository_visibility.py tests/test_repository_metadata_validation.py tests/test_schema_smoke.py tests/test_postgres_fact_repository.py tests/test_core_ingestion_service.py
```

Result:

- `15 passed`

## Remaining Gaps

These are intentionally left for follow-up issue work, especially issue `#6`:

- no end-to-end concrete interpretation family publish path yet
- no `validated -> published` orchestration yet
- no interpretation snapshot publication or family partition publish flow yet
- no dedicated operator or MCP tooling for inspecting and promoting interpretation proposals yet
- duplicate or overlap policy is not enforced beyond the minimal lifecycle validation introduced here

## Outcome

Recommendation after this pass:

- issue `#5` is implementation-complete for the MVP proposal/validation slice
- close it after merge into `mvp/week-1`
- continue issue `#6` for first family publish and snapshot flow
