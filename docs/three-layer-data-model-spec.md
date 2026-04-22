---
status: draft
---

# 3-Layer Data Model Spec

## Purpose

This document defines the current target data model for StrataWiki after the architecture reframe.

The key design shift is:

- the system center is `Personal`, not `Fact` or `Interpretation`
- `Fact` and `Interpretation` exist to support a markdown-native Personal wiki
- the overall shape is a lightweight RAG-like substrate, not a heavy shared knowledge graph

This document replaces earlier assumptions that treated the three layers as roughly symmetric.

## Design Position

StrataWiki should be understood as:

- a domain-neutral shared runtime
- a canonical store for minimal shared truth in `Fact`
- a store for lightweight reusable shared insight in `Interpretation`
- a retrieval substrate that helps a Personal wiki stay grounded with lower cost than full RAG

StrataWiki should not be understood as:

- the complete owner of all user knowledge
- a heavy graph-first ontology system
- a system where markdown is the source of truth for every layer
- a system where every shared insight must be modeled before Personal can work

## Core Principles

- `Personal` is the product center of gravity
- `Fact` is source-grounded and canonical
- `Interpretation` is shared, lightweight, revisable, and evidence-backed
- `Fact` and `Interpretation` are DB-first layers
- `Personal` is a markdown-first layer
- PostgreSQL owns metadata, lifecycle, and cross-record relations
- JSONB stores the flexible payload bodies for system-owned layers
- markdown is canonical only for user-authored Personal content
- relation density should stay intentionally low in shared layers

## Layer Summary

### `Fact`

`Fact` stores observed, normalized, canonical records.

Its role is not to express every possible domain nuance.
Its role is to provide a stable substrate for shared retrieval and interpretation generation.

### `Interpretation`

`Interpretation` stores reusable shared insight derived from Facts.

It is:

- subject-centered
- evidence-backed
- revisable
- lighter than a full shared wiki brain

It is not:

- the canonical source of truth
- a rendered markdown page
- a mandatory dense relation graph between insights

### `Personal`

`Personal` is the real working wiki for the user.

It is:

- markdown-native
- user-authored or user-curated
- free-form
- personalized with shared context from `Fact` and `Interpretation`

It is not:

- a structured document store that must round-trip through JSON
- an upper-layer mutation path

## Storage Model

### Shared Layers

`Fact` and `Interpretation` are stored in PostgreSQL.

Recommended storage split:

- relational columns for identity, scope, lifecycle, snapshot, and routing fields
- JSONB for flexible payload bodies
- explicit relation tables or support-link tables where needed

### Personal Layer

`Personal` content is stored as markdown files.

PostgreSQL stores only minimal Personal metadata such as:

- document id
- user id
- path
- parent path or parent id
- title
- document type
- status
- timestamps
- content hash or sync token

The Personal markdown body should not be treated as canonical JSONB payload.

## Layer 1: Fact

## Definition

Fact records represent source-grounded canonical data.

They should remain intentionally conservative.
If identity is weak, data should remain an attribute or source detail rather than be promoted into a canonical Fact.

## Fact Record Shape

Minimum conceptual shape:

```json
{
  "id": "fact:job_posting:159750",
  "layer": "fact",
  "domain": "recruiting",
  "scope": "shared",
  "entity_type": "job_posting",
  "canonical_key": "job_posting:159750",
  "status": "active",
  "attributes": {
    "title": "Backend Developer",
    "requirements_text": "Python, API development experience"
  },
  "provenance": {
    "connector": "worknet",
    "source_ids": ["159750"]
  },
  "current_snapshot_id": "fact_snap_2026_04_22",
  "created_at": "2026-04-22T00:00:00Z",
  "updated_at": "2026-04-22T00:00:00Z"
}
```

## Fact Relations

Fact relations should be explicit, sparse, and worth keeping.

They should exist only when:

- the source clearly supports the relation
- identity on both ends is stable enough
- the relation is reusable across multiple retrieval or interpretation flows

Example:

```json
{
  "id": "rel:posted_by:job_posting_159750:company_8821",
  "layer": "fact_relation",
  "domain": "recruiting",
  "relation_type": "posted_by",
  "from_canonical_key": "job_posting:159750",
  "to_canonical_key": "company:8821",
  "status": "active",
  "attributes": {},
  "provenance": {
    "connector": "worknet",
    "source_ids": ["159750"]
  }
}
```

Non-goal:

- making Fact a dense semantic graph just because relations are possible

## Recommended Fact Storage

- `fact.record_envelopes`
- `fact.relation_envelopes`

Recommended physical model:

- stable metadata in relational columns
- `attributes_json` in JSONB
- `provenance_json` in JSONB

## Layer 2: Interpretation

## Definition

Interpretation records represent shared reusable insight derived from a subject-centered bundle of facts.

The correct mental model is not:

- `Fact 1 -> Interpretation 1`

The preferred mental model is:

- `Subject 1 -> Interpretation N`
- `Interpretation N -> Fact M`

This makes room for multiple insight families without forcing every fact into its own one-to-one summary.

## Interpretation Design Rules

- interpretation is about a `subject`
- each interpretation belongs to a `family` and `kind`
- each interpretation is supported by zero or more fact or relation links
- interpretation-to-interpretation relations are optional and not first-class in v1 of this reframe
- rendered markdown pages are projections, not the canonical record

## Interpretation Metadata Shape

Minimum canonical metadata shape:

```json
{
  "id": "interp:role_backend:trend_skill_demand_shift",
  "layer": "interpretation",
  "domain": "recruiting",
  "scope": "shared",
  "subject_type": "role",
  "subject_id": "role:backend_engineer",
  "family": "trend",
  "kind": "skill_demand_shift",
  "status": "published",
  "fact_snapshot_id": "fact_snap_2026_04_22",
  "pack_version": "recruiting.v2",
  "confidence": 0.81,
  "freshness_score": 0.73,
  "stale": false,
  "created_at": "2026-04-22T00:00:00Z",
  "updated_at": "2026-04-22T00:00:00Z"
}
```

## Interpretation Payload Shape

The payload should stay flexible and family-specific.

Example:

```json
{
  "title": "AI/API demand is rising for backend roles",
  "summary": "Recent job postings and market signals indicate higher demand for backend roles with AI integration capability.",
  "claims": [
    {
      "type": "signal",
      "text": "Multiple postings repeat Python and API integration requirements."
    }
  ],
  "signals": [
    "job posting demand increase",
    "training supply expansion"
  ],
  "counter_signals": [
    "experience expectations remain high"
  ],
  "watchpoints": [
    "production experience",
    "portfolio evidence"
  ]
}
```

## Interpretation Support Links

Support links connect one interpretation to the facts and relations that justify it.

Example conceptual shape:

```json
{
  "interpretation_id": "interp:role_backend:trend_skill_demand_shift",
  "fact_id": "fact:job_posting:159750",
  "relation_id": null,
  "support_role": "evidence",
  "weight": 0.4
}
```

Recommended storage:

- `interpretation.records`
- `interpretation.support_links`
- `interpretation.payloads`

## Interpretation Uniqueness

The recommended primary shared uniqueness boundary is:

- `domain`
- `subject_type`
- `subject_id`
- `family`
- `kind`
- `scope`
- `status = published`

This allows multiple interpretations for the same subject while keeping one published primary record per family and kind.

## Interpretation Relations

Interpretation-to-Interpretation relations may become useful later for:

- `derived_from`
- `contrasts_with`
- `bundles`
- `supersedes`

But they are not required for the base architecture.

The initial reframe intentionally keeps them out of the critical path.

## Layer 3: Personal

## Definition

Personal is the user's working wiki and PKM surface.

It is the layer where:

- user-authored notes live
- LLM-reworked personal notes live
- question results can be filed back into the workspace
- upper-layer shared context is adapted to user goals

## Personal Storage Position

Personal is markdown-first.

Markdown is the canonical content.
The filesystem is the authoritative content store for the body.

PostgreSQL stores only minimal Personal metadata and sync state.

This means:

- markdown is not rendered from canonical JSONB
- markdown is not expected to round-trip into a strict JSON schema
- user freedom is preferred over full structural normalization

## Recommended Personal Filesystem Layout

```text
wiki/
  users/
    <user>/
      profile/
      inbox/
      notes/
      projects/
      plans/
      journal/
      queries/
```

`shared/` rendered pages may also exist under the filesystem, but they are not part of Personal ownership.

## Recommended Personal Metadata

Recommended DB metadata:

- `document_id`
- `user_id`
- `path`
- `parent_path` or `parent_id`
- `title`
- `doc_type`
- `status`
- `created_at`
- `updated_at`
- `content_hash`

Non-goal:

- parsing every personal markdown document into canonical structured JSON

## Retrieval Model

The default retrieval order remains:

1. `Personal`
2. `Interpretation`
3. `Fact`

But the architecture should now be read as:

- `Personal` is the main workspace
- `Interpretation` is reusable shared context
- `Fact` is canonical grounding fallback

This is why the overall system is best described as a lightweight RAG-like architecture rather than a full graph-first knowledge system.

## Responsibility Summary

### StrataWiki

StrataWiki owns:

- canonical Fact storage
- shared Interpretation storage
- metadata, lifecycle, snapshots, and provenance
- domain pack governance and runtime enforcement
- retrieval substrate

### Domain Services such as Jobs-Wiki

External domain services own:

- source ingestion
- domain semantics
- domain packs
- source-to-proposal mapping
- user-facing product and Personal workspace experience

## Summary

The three-layer model is no longer meant to imply three equally heavy layers.

The intended shape is:

- `Fact`: minimal canonical shared truth
- `Interpretation`: lightweight shared reusable insight
- `Personal`: markdown-native user knowledge workspace

That is the current target architecture for StrataWiki.
