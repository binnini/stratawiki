# 3-Layer Data Model Spec

## Purpose

This document defines a concrete data model for a three-layer LLM Wiki MCP server:

- Fact
- Interpretation
- Personal

The model is intended to support:

- shared knowledge
- domain-specific plugins
- user-scoped personalization
- markdown rendering
- cache-aware recomputation

This is not a vendor-specific schema. It is a conceptual spec that can be implemented with a mix of RDBMS, NoSQL, and file-based rendering.

## Design Principles

- Every layer must have a clear system of record
- Every derived record must retain provenance
- Shared and user-scoped records must be separable
- Markdown pages are rendered artifacts, not the only source of truth
- Domain plugins should specialize the schema without breaking the core contracts
- Every record family should carry an explicit `schema_version`

## Core Concepts

### Record Identity

Every persistent record should have:

- `id`
- `layer`
- `domain`
- `tenant_id` if multi-tenant
- `user_id` if user-scoped
- `created_at`
- `updated_at`
- `version`
- `schema_version`
- `status`

Recommended status values:

- `active`
- `superseded`
- `stale`
- `deleted`
- `draft`

For the `Interpretation` layer, this generic status model is refined further by the dedicated lifecycle in `docs/interpretation-schema-and-lifecycle-spec.md`.
In particular, `published` there corresponds to the active shared interpretation state used for normal retrieval.

### Provenance

Every derived record should retain provenance metadata.

Minimum provenance shape:

```json
{
  "source_ids": ["source_1", "source_2"],
  "upstream_versions": {
    "fact_snapshot": "fact_snap_2026_04_15",
    "profile_version": "profile_v7"
  },
  "generated_by": {
    "kind": "llm",
    "provider": "anthropic",
    "model": "claude-sonnet",
    "prompt_version": "interp-v3"
  },
  "generated_at": "2026-04-15T12:00:00Z"
}
```

### Snapshot Awareness

Any response that depends on upstream state should be attributable to:

- a fact snapshot
- an interpretation snapshot
- a profile snapshot

This is necessary for reproducibility and invalidation.

### Access Scope

Every record that can be queried or rendered across users should carry an explicit scope model.

Minimum scope fields:

- `scope`: `shared`, `tenant`, or `user`
- `tenant_id` when not globally shared
- `user_id` when user-scoped

This is required for ACL-safe retrieval and graph traversal.

## Layer 1: Fact

### Definition

Fact records represent observed, normalized, canonical data.

### Fact Record Interface

```json
{
  "id": "job_posting_123",
  "layer": "fact",
  "domain": "recruiting",
  "entity_type": "job_posting",
  "canonical_key": "indeed:posting:abc123",
  "attributes": {},
  "relations": [],
  "provenance": {},
  "created_at": "2026-04-15T00:00:00Z",
  "updated_at": "2026-04-15T00:00:00Z",
  "version": 3,
  "schema_version": "fact.v1",
  "status": "active"
}
```

### Fact Subtypes

Common subtype categories:

- `source_document`
- `entity`
- `event`
- `measurement`
- `observation`
- `classification`

Domain plugins define the concrete types.

### Example: Recruiting Fact Types

- `job_posting`
- `company`
- `role`
- `skill`
- `location`
- `compensation_range`
- `language_requirement`
- `visa_requirement`
- `source_snapshot`

### Fact Relations

Fact relations should be explicit rather than inferred from free text.

Example:

```json
{
  "type": "requires_skill",
  "from_id": "job_posting_123",
  "to_id": "skill_python",
  "confidence": 1.0
}
```

### Recommended Storage

- primary: RDBMS
- optional read model: columnar or analytics replica

The point is not just transactions. It is canonical normalization.

### Fact Indexing

Fact should support:

- canonical key indexes
- entity type indexes
- relation indexes
- snapshot or updated-at indexes
- lexical and optional embedding indexes for controlled retrieval

## Layer 2: Interpretation

### Definition

Interpretation records represent shared derived meaning from Facts.

Interpretation is not raw source truth. It is derived, revisable, and versioned.

### Interpretation Record Interface

```json
{
  "id": "interp_123",
  "layer": "interpretation",
  "domain": "recruiting",
  "subject_type": "market_segment",
  "subject_id": "backend_japan_midlevel",
  "kind": "trend",
  "claim": "Production LLM experience is increasingly preferred in this segment.",
  "summary": "Shared interpretation summary",
  "confidence": 0.81,
  "freshness": {
    "computed_at": "2026-04-15T12:00:00Z",
    "expires_at": "2026-04-16T12:00:00Z"
  },
  "evidence": [
    {
      "fact_id": "job_posting_123",
      "weight": 0.4
    }
  ],
  "relations": [
    {
      "type": "supports",
      "target_id": "interp_122",
      "confidence": 0.72
    }
  ],
  "render_hints": {
    "page_family": "market_trend",
    "priority": "high"
  },
  "provenance": {},
  "created_at": "2026-04-15T12:00:00Z",
  "updated_at": "2026-04-15T12:00:00Z",
  "version": 1,
  "schema_version": "interpretation.v1",
  "status": "active"
}
```

### Interpretation Categories

Recommended categories:

- `trend`
- `comparison`
- `tension`
- `opportunity`
- `risk`
- `contradiction`
- `correlation`
- `hypothesis`
- `strategy_input`

### Interpretation Relations

Recommended relation types:

- `supports`
- `contradicts`
- `refines`
- `depends_on`
- `supersedes`
- `relevant_to`

### Interpretation Rendering

For the detailed interpretation envelope, lifecycle, validation, and publish model, see `docs/interpretation-schema-and-lifecycle-spec.md`.

Interpretation records may be rendered into shared markdown pages.

Rendered page families might include:

- trend pages
- segment summaries
- company insight pages
- concept pages
- contradiction reports

These are views, not the only storage format.

### Recommended Storage

- primary: NoSQL or document store
- secondary: rendered markdown pages

### Interpretation Indexing

Interpretation should support:

- subject indexes
- evidence reverse indexes by `fact_id`
- relation reverse indexes by `target_id`
- freshness and status indexes
- lexical and embedding indexes
- page family or render target indexes

## Layer 3: Personal

### Definition

Personal records represent user-scoped strategy, notes, plans, and cached derived views.

Personal records are allowed to be opinionated and user-specific.

### Personal Record Interface

```json
{
  "id": "personal_plan_123",
  "layer": "personal",
  "domain": "recruiting",
  "tenant_id": "tenant_a",
  "user_id": "user_42",
  "profile_version": "profile_v7",
  "kind": "job_search_strategy",
  "title": "Q2 transition plan",
  "summary": "Three-month strategy focused on backend roles in Tokyo startups.",
  "body_markdown": "## Strategy\n...",
  "based_on": {
    "fact_snapshot": "fact_snap_2026_04_15",
    "interpretation_snapshot": "interp_snap_2026_04_15",
    "profile_version": "profile_v7"
  },
  "relations": [
    {
      "type": "derived_from_interpretation",
      "target_id": "interp_123"
    }
  ],
  "provenance": {},
  "created_at": "2026-04-15T13:00:00Z",
  "updated_at": "2026-04-15T13:00:00Z",
  "version": 1,
  "schema_version": "personal.v1",
  "status": "active"
}
```

### Personal Categories

- `strategy`
- `plan`
- `note`
- `answer_cache`
- `reading_list`
- `priority_tree`
- `weekly_actions`
- `profile_gap_analysis`

### Recommended Storage

- primary: user-scoped markdown or wiki pages plus metadata store
- optional secondary: object store or document DB for large cached bodies

### Personal Anchoring

Personal records should keep explicit anchors to upper-layer records rather than copying all upstream content into the markdown body.

Minimum anchor model:

```json
{
  "anchors": [
    "interp_123",
    "interp_220",
    "fact_job_posting_999"
  ]
}
```

These anchors support:

- retrieval expansion
- stale detection
- explainability
- selective regeneration

### Personal Indexing

Personal should support:

- user and tenant indexes
- kind indexes
- snapshot tuple indexes
- anchor reverse indexes
- stale and status indexes
- lexical and embedding indexes

## Profile Model

Personalization requires an explicit profile model.

### UserProfile

```json
{
  "user_id": "user_42",
  "tenant_id": "tenant_a",
  "version": "profile_v7",
  "domain": "recruiting",
  "goals": ["transition_to_backend"],
  "preferences": {
    "location": ["tokyo", "remote"],
    "seniority": "mid",
    "salary_floor": 9000000
  },
  "attributes": {
    "skills": ["python", "sql", "analytics"],
    "experience_years": 4,
    "language": ["en", "ja"]
  },
  "updated_at": "2026-04-15T12:55:00Z"
}
```

The profile is not itself a wiki page. It is application state that informs Personal derivation.

Profile changes should be versioned because they participate directly in cache keys and invalidation.

## Source Model

The system should normalize raw inputs before entering Fact.

### SourceRecord

```json
{
  "source_id": "notion:page:abc123",
  "connector": "notion",
  "domain": "recruiting",
  "title": "Hiring memo",
  "body_markdown": "Normalized content",
  "metadata": {},
  "fetched_at": "2026-04-15T10:00:00Z",
  "content_hash": "sha256:...",
  "status": "active"
}
```

## Rendered Wiki Model

Markdown pages remain useful as readable artifacts.

### RenderedPage

```json
{
  "page_id": "shared/market/backend-japan-midlevel",
  "scope": "shared",
  "layer": "interpretation",
  "path": "wiki/shared/market/backend-japan-midlevel.md",
  "title": "Backend Japan Mid-Level Market",
  "body_markdown": "---\n...",
  "render_source_ids": ["interp_123", "interp_124"],
  "rendered_at": "2026-04-15T12:05:00Z"
}
```

Scope values:

- `shared`
- `tenant`
- `user`

Rendered pages should also retain the snapshot tuple used to produce them.

## Graph Model

The graph should be multi-layer aware.

### Graph Node

```json
{
  "id": "interp_123",
  "layer": "interpretation",
  "domain": "recruiting",
  "label": "LLM experience demand trend",
  "scope": "shared"
}
```

### Graph Edge

```json
{
  "from": "interp_123",
  "to": "skill_llmops",
  "type": "relevant_to",
  "confidence": 0.82,
  "scope": "shared"
}
```

Shared and user-scoped graphs should be separable.

The graph should be treated as a cross-layer index and dependency system, not as the sole canonical store.

## Domain Plugin Contract

Each domain plugin should define:

- fact entity types
- fact relation types
- interpretation categories
- interpretation builders
- rendering templates
- freshness policies
- validation rules
- schema evolution and migration rules where needed

### Minimal Domain Plugin Shape

```json
{
  "domain": "recruiting",
  "fact_types": ["job_posting", "company", "skill"],
  "interpretation_kinds": ["trend", "comparison", "risk"],
  "personal_kinds": ["strategy", "weekly_actions"],
  "freshness": {
    "fact_hours": 24,
    "interpretation_hours": 24
  }
}
```

## Example: Recruiting Data Model Slice

### Fact

- `job_posting`
- `company`
- `skill`
- `role`
- `location`

### Interpretation

- `market_trend`
- `role_transition_risk`
- `skill_gap_pattern`
- `regional_opportunity_summary`

### Personal

- `career_transition_plan`
- `application_priority_list`
- `interview_preparation_tree`

## Example: Finance Data Model Slice

### Fact

- `transaction`
- `holding`
- `account`
- `price_event`

### Interpretation

- `spending_pattern`
- `concentration_risk`
- `cashflow_tension`

### Personal

- `budget_plan`
- `watchlist_strategy`
- `rebalance_note`

## Example: Health Data Model Slice

### Fact

- `sleep_event`
- `symptom_entry`
- `medication_event`
- `biometric_reading`

### Interpretation

- `correlation_pattern`
- `adherence_summary`
- `trigger_cluster`

### Personal

- `routine_plan`
- `experiment_note`
- `daily_support_plan`

## Recommended Implementation Rule

When in doubt:

- store canonical observed data in Fact
- store shared derived claims in Interpretation
- store user-scoped plans and notes in Personal

Do not allow Personal to become the only place where important shared knowledge exists.

For detailed graph, retrieval, and propagation behavior, see the dedicated graph specification document.
