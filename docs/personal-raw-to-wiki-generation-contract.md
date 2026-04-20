---
status: draft
---

# Personal Raw-to-Wiki Generation Contract

## Purpose

This document defines the StrataWiki upstream contract for generating Personal wiki artifacts from Personal raw source material.

It exists to unblock workspace-first downstream clients such as Jobs-Wiki without weakening the current three-layer authority model.

The contract in this document applies only to:

- `personal/raw -> personal/wiki summarize`
- `personal/raw -> personal/wiki rewrite`
- `personal/raw -> personal/wiki structure`
- link suggestion and link attachment for `personal/wiki`

It does not define:

- Personal document CRUD beyond the fields this flow depends on
- Personal asset upload transport
- shared Interpretation mutation or publication

## Boundary Rules

These rules are mandatory for every operation in this contract.

- the source document must be a Personal document in `subspace: "raw"`
- the persistence target must be a Personal document in `subspace: "wiki"`
- generation success must never imply a write to `fact`, `interpretation`, or shared rendered pages
- shared Interpretation and Fact records may be used as bounded context only
- source raw references, provenance, and shared anchors must remain attached to the generated Personal wiki artifact
- link attachment may only mutate the target Personal wiki artifact metadata in the caller's Personal scope

## Dependency on Adjacent Personal Contracts

This contract depends on the Personal write boundary defined by:

- issue `#51` for Personal document identity, CRUD, and optimistic version rules
- issue `#50` for Personal asset registration and asset reference identity

This contract should be implemented after, or together with, those contracts.
It should not redefine document CRUD or asset authority independently.

## Contract Surface

### MCP / Runtime Tool Names

The raw-to-wiki contract should use explicit tool names rather than a generic generation tool with an overloaded `mode`.

- `summarize_personal_document_to_wiki`
- `rewrite_personal_document_to_wiki`
- `structure_personal_document_to_wiki`
- `suggest_personal_wiki_links`
- `attach_personal_wiki_links`

The summarize, rewrite, and structure tools are write operations.
They always persist only into `personal/wiki`.

The link tools split non-mutating suggestion from mutating attachment:

- `suggest_personal_wiki_links` returns candidate links and anchors only
- `attach_personal_wiki_links` persists selected candidates to an existing `personal/wiki` document only

### HTTP Endpoint Names

The corresponding HTTP resources should remain user-scoped and action-explicit:

- `POST /api/v1/users/{tenant_id}/{user_id}/personal-documents/{document_id}/summarize-wiki`
- `POST /api/v1/users/{tenant_id}/{user_id}/personal-documents/{document_id}/rewrite-wiki`
- `POST /api/v1/users/{tenant_id}/{user_id}/personal-documents/{document_id}/structure-wiki`
- `POST /api/v1/users/{tenant_id}/{user_id}/personal-documents/{document_id}/suggest-links`
- `POST /api/v1/users/{tenant_id}/{user_id}/personal-documents/{document_id}/attach-links`

The `{document_id}` path parameter in the first three endpoints is always the raw source document id.
The `{document_id}` path parameter in the link endpoints is always the target wiki document id.

## Required Source Reference Model

Every summarize, rewrite, and structure request must carry a source reference model that makes the raw source explicit and reproducible.

Minimum shape:

```json
{
  "source_document_ref": {
    "document_id": "pdoc_raw_123",
    "subspace": "raw",
    "version": 4,
    "kind": "raw_document",
    "asset_refs": ["passet_123"]
  }
}
```

Required rules:

- `document_id` must identify a Personal document owned by the caller scope
- `subspace` must equal `raw`
- `version` is required and acts as the optimistic source version guard
- `kind` must describe the current raw document type as read by the client
- `asset_refs` should be included when the raw document depends on registered Personal assets

Validation guidance:

- if the stored document is missing, return `not_found`
- if the stored document exists but is not `subspace: "raw"`, return `validation_error`
- if the stored source version differs from the supplied version, return `conflict`

## Request Shapes

### Shared Request Fields for Summarize / Rewrite / Structure

```json
{
  "domain": "recruiting",
  "source_document_ref": {
    "document_id": "pdoc_raw_123",
    "subspace": "raw",
    "version": 4,
    "kind": "raw_document",
    "asset_refs": ["passet_123"]
  },
  "profile_version": "profile_v7",
  "model_profile": "balanced_default",
  "save_target": {
    "subspace": "wiki",
    "document_id": "pdoc_wiki_456",
    "version": 2
  }
}
```

Required rules:

- `save_target.subspace` must equal `wiki`
- omitting `save_target.document_id` means create a new Personal wiki document
- supplying `save_target.document_id` means update that existing Personal wiki document
- when `save_target.document_id` is supplied, `save_target.version` is required as the optimistic target version guard
- if `save_target.document_id` resolves to a non-wiki Personal document, return `validation_error`
- no request field may target shared Interpretation, shared pages, or Fact persistence

### Summarize

Tool: `summarize_personal_document_to_wiki`

Purpose:

- produce a concise wiki-style summary from one Personal raw source document

Additional request fields:

```json
{
  "summary_style": "concise"
}
```

### Rewrite

Tool: `rewrite_personal_document_to_wiki`

Purpose:

- rewrite one Personal raw source into clearer wiki prose while preserving source traceability

Additional request fields:

```json
{
  "rewrite_goal": "job-prep"
}
```

### Structure

Tool: `structure_personal_document_to_wiki`

Purpose:

- transform one Personal raw source into a more structured wiki artifact with stable sections

Additional request fields:

```json
{
  "structure_template": "job-brief"
}
```

### Suggest Links

Tool: `suggest_personal_wiki_links`

Minimum shape:

```json
{
  "domain": "recruiting",
  "wiki_document_id": "pdoc_wiki_456",
  "wiki_document_version": 3,
  "profile_version": "profile_v7",
  "model_profile": "balanced_default",
  "max_suggestions": 10
}
```

Required rules:

- `wiki_document_id` must resolve to `subspace: "wiki"`
- this operation does not persist anything
- results may include candidate Fact and Interpretation anchors, plus optional related raw asset refs already owned by the same Personal scope

### Attach Links

Tool: `attach_personal_wiki_links`

Minimum shape:

```json
{
  "domain": "recruiting",
  "wiki_document_id": "pdoc_wiki_456",
  "wiki_document_version": 3,
  "attachments": [
    {
      "layer": "interpretation",
      "id": "interp_123"
    },
    {
      "layer": "fact",
      "id": "fact_job_posting_999"
    }
  ]
}
```

Required rules:

- `wiki_document_id` must resolve to `subspace: "wiki"`
- `wiki_document_version` is required and acts as the optimistic target version guard
- every attachment target must already exist in the referenced layer
- attachment writes must update only the Personal wiki document metadata
- attachment writes must not create or mutate shared records

## Persistence Target Rules

The save boundary is fixed.

- summarize, rewrite, and structure must save only to `personal/wiki`
- link attachment must save only to `personal/wiki`
- summarize, rewrite, and structure must never overwrite the raw source document
- suggest-links must not save anything
- generation may read shared context, but success must not advance shared snapshot pointers or publish interpretation state

Recommended target kinds:

- summarize -> `wiki_summary`
- rewrite -> `wiki_note`
- structure -> `wiki_note`

The exact markdown body format may vary by domain or template, but the persisted record family remains a Personal wiki document.

## Persisted Artifact Shape

Every persisted summarize, rewrite, or structure result should return and store a Personal wiki document with generation metadata.

Minimum response shape:

```json
{
  "status": "ok",
  "document": {
    "document_id": "pdoc_wiki_456",
    "subspace": "wiki",
    "kind": "wiki_summary",
    "version": 3,
    "title": "Backend resume summary",
    "source_document_ref": {
      "document_id": "pdoc_raw_123",
      "subspace": "raw",
      "version": 4,
      "kind": "raw_document",
      "asset_refs": ["passet_123"]
    },
    "snapshot_ref": {
      "fact_snapshot_id": "fact_snap_2026_04_20",
      "interpretation_snapshot_id": "interp_snap_2026_04_20",
      "profile_version": "profile_v7"
    },
    "anchors": [
      {
        "layer": "interpretation",
        "id": "interp_123"
      },
      {
        "layer": "fact",
        "id": "fact_job_posting_999"
      }
    ],
    "generation": {
      "generation_id": "pgen_2026_04_20_001",
      "operation": "summarize"
    }
  }
}
```

## Provenance and Source-Link Rules

Every persisted wiki artifact produced by summarize, rewrite, or structure must preserve:

- `source_document_ref` as a first-class field on the generated Personal wiki document
- `snapshot_ref` showing the shared state used during generation
- `provenance.source_ids` including the raw Personal document id and any raw Personal asset ids used as source material
- `provenance.generated_by` with generator kind, provider, model, and prompt version when applicable
- `provenance.generated_at`
- `anchors` for shared Fact and Interpretation records attached to the wiki artifact

Recommended provenance shape:

```json
{
  "source_ids": [
    "personal_document:pdoc_raw_123",
    "personal_asset:passet_123"
  ],
  "upstream_versions": {
    "fact_snapshot": "fact_snap_2026_04_20",
    "interpretation_snapshot": "interp_snap_2026_04_20",
    "profile_version": "profile_v7",
    "source_document_version": "4"
  },
  "generated_by": {
    "kind": "llm",
    "provider": "openai",
    "model": "gpt-5.4",
    "prompt_version": "personal.raw_to_wiki.summarize.v1"
  },
  "generated_at": "2026-04-20T09:30:00Z"
}
```

The generated markdown body may cite or summarize shared Interpretation material, but source linkage must remain explicit in structured metadata rather than relying only on free text.

## Identity and Versioning

The generated artifact identity model is:

- `document_id` is the stable Personal wiki document identity
- `version` is the persisted document revision and increments on each successful update
- `generation.generation_id` is the immutable per-run identifier for one summarize, rewrite, or structure execution
- `source_document_ref.version` is the exact raw source version used for the saved result

Rules:

- create-on-generate returns a new `document_id` with `version: 1`
- update-on-generate preserves `document_id` and increments `version`
- version conflicts must fail rather than silently overwrite
- a re-run against the same target wiki document is allowed only when the caller supplies the current target version
- a re-run may point to a newer raw source version; that newer source version must appear in the saved `source_document_ref` and provenance

## Link Suggestion and Attachment Result Shapes

### Suggest Links Result

```json
{
  "status": "ok",
  "wiki_document_id": "pdoc_wiki_456",
  "wiki_document_version": 3,
  "suggestions": [
    {
      "layer": "interpretation",
      "id": "interp_123",
      "reason": "matches backend-ai trend language",
      "confidence": 0.88
    },
    {
      "layer": "fact",
      "id": "fact_job_posting_999",
      "reason": "raw source references the same job posting",
      "confidence": 0.84
    }
  ]
}
```

### Attach Links Result

```json
{
  "status": "ok",
  "wiki_document_id": "pdoc_wiki_456",
  "wiki_document_version": 4,
  "attached": [
    {
      "layer": "interpretation",
      "id": "interp_123"
    },
    {
      "layer": "fact",
      "id": "fact_job_posting_999"
    }
  ]
}
```

## Normalized Failure Shape

The generation family should use one normalized failure envelope across tools and HTTP resources.

```json
{
  "ok": false,
  "request_id": "req-123",
  "error": {
    "code": "conflict",
    "message": "wiki_document_version does not match the current stored version.",
    "retryable": false,
    "details": {
      "field": "wiki_document_version",
      "document_id": "pdoc_wiki_456",
      "current_version": 4
    }
  }
}
```

Required logical error codes:

- `invalid_request`
- `not_found`
- `validation_error`
- `conflict`
- `temporarily_unavailable`
- `internal_error`

Recommended meanings:

- `not_found`: missing source document, target wiki document, or shared anchor target
- `validation_error`: source is not `personal/raw`, target is not `personal/wiki`, `save_target.subspace` is not `wiki`, or attachment targets violate scope rules
- `conflict`: source or target version mismatch
- `temporarily_unavailable`: model provider unavailable, rate-limited, or dependent runtime unavailable

## Retry and Re-Run Guidance

Retry guidance:

- summarize, rewrite, structure, and attach-links are not retry-safe without `Idempotency-Key`
- suggest-links is retry-safe when the same wiki document version is requested
- clients should reuse the same `Idempotency-Key` when retrying after a network failure on a write operation
- clients should not blindly retry `validation_error` or `conflict`
- clients may retry `temporarily_unavailable` with backoff

Re-run guidance:

- re-running summarize, rewrite, or structure is allowed and should create a new generation event
- re-running against an existing target wiki document requires the latest target version
- re-running after the raw source changes requires the new `source_document_ref.version`
- link suggestions should be refreshed after a successful rewrite or structure re-run because anchors may have changed

## Downstream Guidance for Jobs-Wiki

Jobs-Wiki issue `#42` should treat this contract as the required upstream authority for raw-to-wiki generation.

Jobs-Wiki should not:

- generate Personal wiki artifacts by guessing implicit StrataWiki save rules
- infer shared-layer mutation from generation success
- write directly into shared Interpretation or shared rendered pages

Jobs-Wiki may safely assume:

- a raw Personal source document is the only supported generation input
- the save target is always `personal/wiki`
- source references and provenance are preserved in the generated artifact
- link suggestions are separate from persisted link attachment
