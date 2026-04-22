# Interpretation Schema and Lifecycle Spec

## Purpose

This document defines the canonical shared `Interpretation` layer in more detail.

It focuses on:

- interpretation document structure
- required metadata and contracts
- proposal, validation, and publish lifecycle
- separation between canonical interpretation records and rendered pages
- how to preserve integrity while allowing LLM-driven synthesis

This document complements:

- `docs/three-layer-data-model-spec.md`
- `docs/llm-orchestration-and-retrieval-spec.md`
- `docs/cache-invalidation-consistency-spec.md`
- `docs/graph-index-and-propagation-spec.md`

## Design Position

`Interpretation` is:

- LLM-generated
- shared and reusable
- evidence-backed
- revisable
- versioned
- lighter and more flexible than `Fact`

`Interpretation` is not:

- canonical source truth
- arbitrary free-form text with no contract
- equivalent to rendered markdown pages

The correct mental model is:

- `Fact` is code-owned canonical truth
- `Interpretation` is program-validated LLM-authored shared insight
- rendered wiki pages are views built from interpretation records
- `Interpretation` should stay lighter than a full shared wiki brain

This document refines the generic `Interpretation` model in `docs/three-layer-data-model-spec.md`.

## Design Goals

- keep the interpretation layer flexible enough for new insight families
- keep enough structure for provenance, stale handling, and graph linkage
- support proposal before promotion into published shared knowledge
- separate canonical interpretation records from rendered page artifacts
- support both structured retrieval and readable wiki rendering
- keep subject-centered multi-interpretation storage possible without forcing dense interpretation-to-interpretation graphs

## Non-Goals

- forcing one rigid schema for every interpretation family
- allowing arbitrary LLM output directly into published shared state
- making markdown pages the only durable representation of interpretation
- making interpretation-to-interpretation relations part of the mandatory base contract

## Interpretation Storage Shape

The interpretation layer should be document-oriented or JSON-friendly.

This does not mean unconstrained schemaless storage.
It means:

- flexible body shape by interpretation family
- strong required metadata
- explicit evidence and provenance contracts
- stable lifecycle state
- subject-centered records that can be supported by multiple facts

Recommended storage choices:

- document store
- PostgreSQL plus JSONB
- another semi-structured store with strong indexing support

## Canonical Interpretation Record

Minimum canonical record shape:

```json
{
  "id": "interp_123",
  "layer": "interpretation",
  "domain": "recruiting",
  "scope": "shared",
  "tenant_id": null,
  "subject": {
    "type": "role",
    "id": "role:backend_engineer",
    "label": "Backend Engineer"
  },
  "family": "trend",
  "kind": "skill_demand_shift",
  "title": "Production LLM experience preference is increasing",
  "claim": "Production LLM experience is increasingly preferred in this segment.",
  "summary": "Shared interpretation summary",
  "body": {
    "signals": [],
    "observations": [],
    "counterpoints": []
  },
  "evidence": [
    {
      "fact_id": "job_posting_123",
      "weight": 0.4,
      "role": "primary"
    }
  ],
  "confidence": 0.81,
  "confidence_detail": {
    "evidence_strength": 0.84,
    "coverage": 0.73,
    "consistency": 0.81,
    "freshness": 0.69,
    "generation_reliability": 0.92
  },
  "freshness": {
    "computed_at": "2026-04-15T12:00:00Z",
    "expires_at": "2026-04-16T12:00:00Z"
  },
  "render_hints": {
    "page_family": "trend",
    "page_key": "role-backend-engineer",
    "priority": "high"
  },
  "provenance": {
    "source_ids": [
      "greenhouse:job:abc123"
    ],
    "upstream_versions": {
      "fact_snapshot": "fact_snap_2026_04_15_1200"
    },
    "generated_by": {
      "kind": "llm",
      "provider": "openai",
      "model": "gpt-5.4",
      "prompt_version": "interp.market_trend.v1"
    },
    "generated_at": "2026-04-15T12:00:00Z"
  },
  "version": 1,
  "schema_version": "interpretation.v2",
  "status": "published",
  "created_at": "2026-04-15T12:00:00Z",
  "updated_at": "2026-04-15T12:00:00Z"
}
```

## Required Fields

Every interpretation record should require:

- `id`
- `layer`
- `domain`
- `scope`
- `subject`
- `family`
- `kind`
- `claim`
- `summary`
- `evidence`
- `provenance`
- `version`
- `schema_version`
- `status`
- `created_at`
- `updated_at`

Recommended but optional family-dependent fields:

- `title`
- `body`
- `confidence_detail`
- `freshness`
- `render_hints`
- limited interpretation links

## Schema Philosophy

Interpretation should be schema-flexible, not schema-free.

Recommended structure split:

- stable envelope fields for identity, provenance, evidence, lifecycle, and scope
- family-specific body fields for domain-dependent synthesis

This lets the system:

- preserve integrity and explainability
- support new interpretation families without redesigning the entire storage layer
- render wiki pages from consistent metadata while still allowing rich family-specific content

## Body Versus Envelope

The record should be understood as two layers.

### Envelope

The envelope is stable and operationally important.

It includes:

- identity
- subject
- family and kind
- evidence
- provenance
- confidence
- freshness
- lifecycle status
- render hints

### Body

The body is family-specific and flexible.

Examples:

- market trend signals
- regional opportunities
- contradiction narratives
- comparison tables
- strategy inputs

The body may vary substantially by family as long as the envelope remains valid.

## Subject-Centered Model

The preferred base model is:

- `Subject 1 -> Interpretation N`
- `Interpretation N -> Fact M`

This is intentionally different from a one-fact-one-summary model.

Interpretation should usually be generated from a fact bundle around a subject rather than from an isolated single fact.

## Interpretation Families

Each family should define:

- allowed `kind` values
- required body sections
- rendering expectations
- confidence policy overrides if needed
- freshness defaults if needed

Examples:

- `trend`
- `opportunity`
- `risk`
- `comparison`
- `strategy_input`

## Interpretation Links

Interpretation-to-Interpretation links may be useful later for:

- `derived_from`
- `contrasts_with`
- `bundles`
- `supersedes`

But they are optional and should not be treated as required base structure.

The critical path remains subject, evidence, and lifecycle.

## Evidence Contract

Interpretation must remain evidence-backed.

Minimum evidence requirements:

- every published interpretation should reference one or more fact IDs
- evidence items should support weighting or role metadata
- evidence must point to canonical Fact records, not only rendered text

Recommended evidence item shape:

```json
{
  "fact_id": "job_posting_123",
  "weight": 0.4,
  "role": "primary",
  "notes": "Mentions Python and production LLM experience"
}
```

An interpretation without valid evidence should not become `published`.

## Canonical Record Versus Rendered Page

These should remain separate.

Canonical interpretation record:

- durable shared meaning
- structured retrieval target
- graph node and relation source
- stale and invalid tracking unit

Rendered page:

- human-readable markdown artifact
- may aggregate one or more interpretation records
- may be regenerated from canonical records

Rendered pages should reference:

- interpretation IDs used
- interpretation snapshot used
- render template version

## Lifecycle States

Interpretation needs a richer lifecycle than the generic record model.

In the generic three-layer data model, many records use `active` as a cross-layer status.
For interpretation specifically, `published` should be treated as the shared-layer equivalent of active state for normal retrieval.

Recommended states:

- `proposed`
- `validated`
- `published`
- `stale`
- `superseded`
- `rejected`
- `deleted`

### `proposed`

Meaning:

- LLM or another process generated a candidate interpretation
- not yet trusted as shared canonical meaning

Allowed characteristics:

- may be incomplete
- may have partial evidence
- may require dedupe or family review

### `validated`

Meaning:

- basic structural and evidence checks passed
- eligible for publication
- still not yet the active shared interpretation if publish has not occurred

### `published`

Meaning:

- accepted as active shared interpretation state
- visible to normal shared retrieval
- eligible for rendering and downstream Personal use

### `stale`

Meaning:

- still useful as prior interpretation
- upstream facts or freshness policy indicate refresh is recommended

### `superseded`

Meaning:

- replaced by a newer published interpretation version or partition snapshot

### `rejected`

Meaning:

- proposal failed validation or quality review
- should not be used for shared retrieval

### `deleted`

Meaning:

- hidden from normal retrieval
- retained only if policy requires historical traceability

## Lifecycle Transitions

Recommended primary path:

1. `proposed`
2. `validated`
3. `published`
4. `stale`
5. `superseded`

Possible side paths:

- `proposed -> rejected`
- `validated -> rejected`
- `published -> deleted`
- `stale -> superseded`

Not every interpretation family requires manual review.
Some families may move automatically from `proposed` to `validated` to `published` if checks are deterministic enough.

## Validation Rules

Before promotion to `published`, the program should validate:

- required envelope fields exist
- schema version is supported
- subject fields are valid
- evidence fact IDs exist and are in scope
- provenance is attached
- confidence and freshness can be computed
- duplicate or near-duplicate published interpretations are handled according to policy

Optional validation checks:

- contradiction with stronger current interpretation
- low evidence coverage warning
- low confidence warning
- rendering contract completeness

## Publish Model

Interpretation publication should prefer build-and-swap or partition-scoped publish over uncontrolled in-place mutation.

Recommended pattern:

1. generate candidate records
2. validate them
3. store them as `validated` or staged records
4. publish a new partition snapshot
5. mark prior active records as `superseded` or `stale`

This keeps shared retrieval coherent.

## Partitioning Model

Interpretation should not assume one giant global snapshot.

Recommended partition axes:

- domain
- family
- segment
- tenant if tenant-scoped interpretation exists

Example:

```json
{
  "family": "market_trend",
  "segment": "backend_japan_midlevel"
}
```

This allows:

- smaller rebuild units
- lower publish latency
- less invalidation blast radius

## Semantic Relation Policy

Interpretation relations belong in the semantic graph world, not the dependency authority world.

Recommended policy:

- LLM may propose semantic relations
- program validates relation type, target existence, and scope
- published relations should carry status and confidence

Suggested relation status values:

- `proposed`
- `active`
- `rejected`
- `superseded`

This helps avoid noisy graph growth from unconstrained model output.

## Duplicate and Overlap Policy

Interpretation overlap is expected.

The system should define policy for:

- near-duplicate claims in the same family and subject
- overlapping claims with different evidence windows
- contradiction versus refinement
- family-level supersession

Recommended starting rule:

- only one primary `published` interpretation per `family + subject + kind + partition`
- alternatives remain `proposed`, `validated`, or `superseded` until explicitly promoted

## Retrieval Visibility by Status

Default retrieval policy:

- `published`: visible to normal shared retrieval
- `stale`: visible with warning or fallback policy
- `validated`: hidden from normal user retrieval
- `proposed`: hidden from normal user retrieval
- `rejected`: hidden
- `superseded`: hidden from default retrieval, available for explainability

Exploratory or operator workflows may inspect non-published states with explicit tooling.

## Freshness and Confidence

Confidence and freshness should be part of the canonical interpretation contract.

Why:

- they affect user trust
- they influence rendering priority
- they help decide whether a stale record is still usable
- they support explainability and operator review

Confidence should be computed by the program from structured factors, not taken as a raw self-rating from the model.

## Suggested Implementation Steps

1. define the stable envelope schema
2. define one family-specific body schema
3. implement proposal persistence
4. implement validation checks
5. implement partition-scoped publish
6. render pages from published records only
7. add retrieval filtering by lifecycle status

## Summary

`Interpretation` should be:

- flexible in body
- strict in metadata
- evidence-backed
- proposal-driven before publication
- separate from rendered markdown

For implementation sequencing, pair this document with:

- `docs/implementation-roadmap.md`
- `docs/mcp-tool-contract-spec.md`
- `docs/llm-orchestration-and-retrieval-spec.md`

This allows the project to use LLM creativity where it is most valuable without giving up reproducibility, stale handling, or shared-knowledge integrity.
