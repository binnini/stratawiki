---
status: draft
---

# Personal Document Tool and REST Spec

## Purpose

This document defines the first resource-shaped tool and REST draft for user-scoped Personal document authoring.

It exists to support workspace-first external clients such as Jobs-Wiki without weakening the existing three-layer ownership model.

The main goal is to add personal document CRUD and raw-to-wiki generation while preserving these boundaries:

- `Fact` stays canonical and code-owned
- `Interpretation` stays shared, published, and read-only to external clients
- `Personal` stays user-scoped and writable
- Personal writes never auto-promote into upper shared layers

## Boundary Check

The current upper-layer REST and tool surfaces are already reasonably bounded for the existing responsibilities.

Already in good shape:

- canonical Fact writes through `validate_domain_proposal_batch` and `ingest_domain_proposal_batch`
- profile provisioning through `upsert_profile_context`
- user-scoped Personal query through `query_personal_knowledge`
- shared Interpretation build requests through `build_interpretation_snapshot`

Main gap for workspace-first authoring:

- there is no first-class resource for user-authored Personal documents
- there is no resource-shaped Personal CRUD surface
- there is no explicit raw-to-wiki generation contract
- shared rendered pages are conceptually present, but their read model is not yet expressed as a dedicated resource family

This means the upper shared-layer contract does not need redesign.
It needs one additional family: Personal document resources plus a clearer shared rendered-page read resource.

## Design Goals

- preserve the existing upper-layer ownership model
- give external WAS clients a stable Personal authoring contract
- keep shared rendered pages explicitly read-only
- support both markdown notes and PDF-backed personal documents
- separate raw user material from LLM-reworked wiki artifacts
- keep provenance, snapshot binding, and anchor metadata explicit

## Non-Goals

- direct binary upload into the canonical Fact layer
- treating shared rendered pages as writable documents
- generic cross-layer CRUD over Fact, Interpretation, and Personal
- automatic promotion from Personal into shared Interpretation

## Resource Model

## 1. Shared Rendered Page

This is the user-facing document-form view of `Interpretation`.

Properties:

- scope: `shared`
- layer: `interpretation`
- writable: `false`
- source of truth: canonical interpretation record plus render pipeline

External clients may:

- fetch
- search
- use as LLM context

External clients may not:

- patch
- delete
- overwrite rendered content

## 2. Personal Document

This is the first-class writable user-scoped document resource.

Minimum shape:

```json
{
  "document_id": "pdoc_123",
  "domain": "recruiting",
  "tenant_id": "tenant_a",
  "user_id": "user_42",
  "subspace": "raw",
  "kind": "note",
  "title": "Toss backend prep",
  "body_markdown": "## Notes\n...",
  "asset_refs": [],
  "anchors": [
    "interp_123",
    "fact_job_posting_999"
  ],
  "based_on": {
    "fact_snapshot": "fact_snap_2026_04_15",
    "interpretation_snapshot": "interp_snap_2026_04_15",
    "profile_version": "profile_v7"
  },
  "provenance": {},
  "status": "active",
  "created_at": "2026-04-20T10:00:00Z",
  "updated_at": "2026-04-20T10:00:00Z"
}
```

Required rules:

- `subspace` must be one of `raw` or `wiki`
- Personal documents are always writable by the owning user scope
- Personal documents may reference upper-layer records through anchors
- Personal documents must not directly mutate shared `Interpretation` or canonical `Fact`

Authoritative identity and concurrency fields:

- `document_id` is the StrataWiki-assigned stable resource id
- `domain + tenant_id + user_id + document_id` is the full resource identity
- there is no separate `profile_id` in this contract
- `profile_version` is required on create and update as Personal provenance and scope freshness metadata, but it is not part of the resource key
- `version` is the server-managed optimistic write token and must increase on every successful update or delete transition

## 3. Personal Asset

This is an uploaded or externally stored binary asset associated with a Personal document, such as a PDF.

Minimum shape:

```json
{
  "asset_id": "passet_123",
  "domain": "recruiting",
  "tenant_id": "tenant_a",
  "user_id": "user_42",
  "media_type": "application/pdf",
  "filename": "resume.pdf",
  "storage_ref": "s3://bucket/path/resume.pdf",
  "status": "active",
  "created_at": "2026-04-20T10:00:00Z"
}
```

First-wave recommendation:

- StrataWiki should accept asset metadata and a storage reference
- external WAS clients may own the raw multipart upload flow in the first wave
- StrataWiki should remain the owner of Personal asset registration and Personal document references

This keeps the resource contract stable without forcing the first HTTP wave to solve binary transport and storage in the same change.

## Authority Rules

- shared rendered pages are read-only
- Personal documents in `raw` and `wiki` are user-scoped and writable
- `raw -> wiki` generation always creates or updates a Personal document in `subspace: "wiki"`
- link generation may attach anchors or related refs to a Personal document
- no Personal write may publish or mutate shared Interpretation state
- any future promotion from Personal to shared state must be a separate explicit proposal flow

## Proposed Tool Surface

These tools are proposed additions to the Personal family.

For `#51`, the authoritative Personal document CRUD write tools are:

- `create_personal_document`
- `update_personal_document`
- `delete_personal_document`

The read companions for downstream consumers are:

- `list_personal_documents`
- `get_personal_document`

### `get_shared_page`

Return one rendered shared page.

Input:

```json
{
  "domain": "recruiting",
  "page_id": "shared/market/backend-japan-midlevel"
}
```

### `list_personal_documents`

List Personal documents for one user scope.

Input:

```json
{
  "domain": "recruiting",
  "tenant_id": "tenant_a",
  "user_id": "user_42",
  "subspace": "raw",
  "kind": "note",
  "status": "active"
}
```

### `get_personal_document`

Return one Personal document.

Input:

```json
{
  "domain": "recruiting",
  "tenant_id": "tenant_a",
  "user_id": "user_42",
  "document_id": "pdoc_123"
}
```

### `create_personal_document`

Create one Personal document in `raw` or `wiki`.

Input:

```json
{
  "domain": "recruiting",
  "tenant_id": "tenant_a",
  "user_id": "user_42",
  "profile_version": "profile_v7",
  "subspace": "raw",
  "kind": "note",
  "title": "Toss backend prep",
  "body_markdown": "## Notes\n...",
  "asset_refs": [],
  "anchors": []
}
```

### `update_personal_document`

Patch one Personal document.

Input:

```json
{
  "domain": "recruiting",
  "tenant_id": "tenant_a",
  "user_id": "user_42",
  "document_id": "pdoc_123",
  "profile_version": "profile_v7",
  "if_version": 3,
  "title": "Updated title",
  "body_markdown": "## Updated\n..."
}
```

### `delete_personal_document`

Soft-delete one Personal document.

Input:

```json
{
  "domain": "recruiting",
  "tenant_id": "tenant_a",
  "user_id": "user_42",
  "document_id": "pdoc_123",
  "if_version": 4
}
```

## Personal Document CRUD Contract

This section is the concrete `#51` contract for downstream writers such as Jobs-Wiki.

### Scope Rules

- Personal document writes are valid only for `scope_ref.scope: "user"`.
- `tenant_id` and `user_id` define the writable owner scope. Shared and tenant-scoped document writes are out of scope.
- `domain`, `tenant_id`, and `user_id` must resolve to one explicit Personal namespace.
- There is no contract-level `profile_id`. The profile dimension is expressed through the existing `profile_version`.
- `profile_version` is required on create and update and records which stored profile context the write was based on.
- create and update require an already provisioned stored profile context for the same `domain + tenant_id + user_id`
- the supplied `profile_version` must match that stored profile context exactly
- `DELETE` does not change profile scope and therefore uses only the existing record plus `if_version`.

### Required Create Fields

- `domain`
- `tenant_id`
- `user_id`
- `profile_version`
- `subspace`
- `kind`
- `title`
- exactly one of `body_markdown` or an asset-backed document shape such as non-empty `asset_refs`

Server-populated fields:

- `document_id`
- `scope_ref`
- `snapshot_ref`
- `status`
- `version`
- `created_at`
- `updated_at`

### Required Update Fields

- `domain`
- `tenant_id`
- `user_id`
- `document_id`
- `profile_version`
- `if_version`
- at least one mutable field such as `title`, `body_markdown`, `anchors`, `asset_refs`, or `status`

### Required Delete Fields

- `domain`
- `tenant_id`
- `user_id`
- `document_id`
- `if_version`

Delete behavior:

- delete is a Personal-layer soft delete
- the server marks `status: "deleted"` and increments `version`
- delete does not remove shared records, published interpretations, or registered assets

### Optimistic Write Contract

- `create_personal_document` allocates `version: 1` for a new document
- `update_personal_document` requires `if_version` equal to the current stored `version`
- `delete_personal_document` requires `if_version` equal to the current stored `version`
- stale `if_version` values fail with `409 conflict`
- successful writes return the committed document payload including the new `version`

Conflict response example:

```json
{
  "ok": false,
  "request_id": "req-409",
  "error": {
    "code": "conflict",
    "message": "Personal document version mismatch.",
    "details": {
      "resource": "personal_document",
      "document_id": "pdoc_123",
      "expected_version": 3,
      "current_version": 4
    }
  }
}
```

### Normalized Error Contract

Personal document CRUD must normalize failures into the shared response envelope with these issue-level codes:

| Code | HTTP Status | Meaning | Required `details` |
| --- | --- | --- | --- |
| `validation_error` | `422` | payload shape or domain rule violation | invalid field names and reasons |
| `conflict` | `409` | stale `if_version` or duplicate idempotent create collision | current resource version when known |
| `not_found` | `404` | unknown `document_id` in the requested user scope | requested `document_id` |
| `temporarily_unavailable` | `503` | Personal store, render root, or dependent runtime unavailable | retryability hint |

Additional rules:

- scope mismatches must not degrade into cross-user lookups; they should return `404 not_found`
- missing stored profile context for create or update is `422 validation_error`
- `profile_version` mismatch against the current stored profile context is `422 validation_error`
- unexpected failures may still use the wider runtime `internal_error`, but downstream consumers should not rely on it for normal branching

### Write-To-Read Visibility

The contract makes only the direct Personal read surfaces authoritative for immediate post-write reads:

- after a successful `create_personal_document`, `update_personal_document`, or `delete_personal_document`, the same runtime must return the committed result immediately through `get_personal_document`
- `list_personal_documents` for the same `domain + tenant_id + user_id` scope must reflect the committed state in the same request path without waiting for background indexing
- downstream consumers such as Jobs-Wiki must treat search indexes, rendered wiki projections, and any later derived views as eventually consistent unless a later contract says otherwise
- successful Personal writes do not imply any visibility change in shared `Interpretation` reads

### `register_personal_asset`

Register one user-scoped binary asset such as a PDF and return an `asset_id`.

Input:

```json
{
  "domain": "recruiting",
  "tenant_id": "tenant_a",
  "user_id": "user_42",
  "media_type": "application/pdf",
  "filename": "resume.pdf",
  "storage_ref": "s3://bucket/path/resume.pdf"
}
```

### `generate_personal_wiki_document`

Generate or refresh a Personal wiki artifact from a source document plus bounded upper-layer context.

Input:

```json
{
  "domain": "recruiting",
  "tenant_id": "tenant_a",
  "user_id": "user_42",
  "source_document_id": "pdoc_raw_123",
  "mode": "rewrite",
  "profile_version": "profile_v7",
  "model_profile": "balanced_default",
  "save_target": "wiki"
}
```

Allowed `mode` values:

- `summarize`
- `rewrite`
- `wiki`

Rules:

- output target is always `subspace: "wiki"`
- shared rendered pages may be used as context only
- generated output remains Personal

### `link_personal_document`

Attach or refresh anchors and related refs for one Personal document.

Input:

```json
{
  "domain": "recruiting",
  "tenant_id": "tenant_a",
  "user_id": "user_42",
  "document_id": "pdoc_wiki_123",
  "mode": "suggest",
  "model_profile": "balanced_default"
}
```

Allowed `mode` values:

- `suggest`
- `apply`

## Proposed REST Surface

The first resource-shaped REST surface should keep the user scope explicit in the path.

### Shared Read Endpoints

- `GET /api/v1/shared-pages/{page_id}`

This endpoint is read-only.

### Personal Document Endpoints

- `GET /api/v1/users/{tenant_id}/{user_id}/personal-documents`
- `POST /api/v1/users/{tenant_id}/{user_id}/personal-documents`
- `GET /api/v1/users/{tenant_id}/{user_id}/personal-documents/{document_id}`
- `PATCH /api/v1/users/{tenant_id}/{user_id}/personal-documents/{document_id}`
- `DELETE /api/v1/users/{tenant_id}/{user_id}/personal-documents/{document_id}`
- `POST /api/v1/users/{tenant_id}/{user_id}/personal-documents/{document_id}/generate-wiki`
- `POST /api/v1/users/{tenant_id}/{user_id}/personal-documents/{document_id}/link`

Authoritative write endpoints for `#51`:

- `POST /api/v1/users/{tenant_id}/{user_id}/personal-documents`
- `PATCH /api/v1/users/{tenant_id}/{user_id}/personal-documents/{document_id}`
- `DELETE /api/v1/users/{tenant_id}/{user_id}/personal-documents/{document_id}`

### Personal Asset Endpoints

- `POST /api/v1/users/{tenant_id}/{user_id}/personal-assets`

## Request Notes

### Create Personal Document

```json
{
  "domain": "recruiting",
  "profile_version": "profile_v7",
  "subspace": "raw",
  "kind": "note",
  "title": "Preparation notes",
  "body_markdown": "## Notes\n...",
  "asset_refs": []
}
```

### Update Personal Document

```json
{
  "domain": "recruiting",
  "profile_version": "profile_v7",
  "if_version": 3,
  "title": "Preparation notes revised",
  "body_markdown": "## Revised notes\n- tighten backend examples\n- map shared trend note to my portfolio"
}
```

### Register Personal Asset

```json
{
  "domain": "recruiting",
  "media_type": "application/pdf",
  "filename": "backend-resume.pdf",
  "storage_ref": "s3://jobs-wiki-user-assets/user-42/backend-resume.pdf"
}
```

### Generate Wiki

```json
{
  "domain": "recruiting",
  "mode": "rewrite",
  "profile_version": "profile_v7",
  "model_profile": "balanced_default"
}
```

### Link Personal Document

```json
{
  "domain": "recruiting",
  "mode": "suggest",
  "model_profile": "balanced_default"
}
```

## Response Notes

Recommended document response envelope:

```json
{
  "ok": true,
  "request_id": "req-123",
  "result": {
    "document": {
      "document_id": "pdoc_123",
      "domain": "recruiting",
      "tenant_id": "tenant_a",
      "user_id": "user_42",
      "profile_version": "profile_v7",
      "version": 1,
      "subspace": "wiki",
      "title": "Preparation notes rewritten",
      "writable": true
    }
  }
}
```

Recommended list response envelope:

```json
{
  "ok": true,
  "request_id": "req-456",
  "result": {
    "items": [
      {
        "document_id": "pdoc_raw_123",
        "subspace": "raw",
        "kind": "note",
        "title": "Preparation notes",
        "version": 3,
        "writable": true,
        "updated_at": "2026-04-20T10:00:00Z"
      },
      {
        "document_id": "pdoc_wiki_456",
        "subspace": "wiki",
        "kind": "wiki_summary",
        "title": "Preparation notes rewritten",
        "version": 1,
        "writable": true,
        "updated_at": "2026-04-20T10:05:00Z"
      }
    ]
  }
}
```

Recommended shared page response envelope:

```json
{
  "ok": true,
  "request_id": "req-123",
  "result": {
    "page": {
      "page_id": "shared/market/backend-japan-midlevel",
      "scope": "shared",
      "layer": "interpretation",
      "writable": false
    }
  }
}
```

Recommended asset registration response envelope:

```json
{
  "ok": true,
  "request_id": "req-789",
  "result": {
    "asset": {
      "asset_id": "passet_123",
      "filename": "backend-resume.pdf",
      "media_type": "application/pdf"
    }
  }
}
```

Recommended generate-wiki response envelope:

```json
{
  "ok": true,
  "request_id": "req-790",
  "result": {
    "document": {
      "document_id": "pdoc_wiki_456",
      "subspace": "wiki",
      "title": "Preparation notes rewritten",
      "writable": true,
      "anchors": [
        "interp_123",
        "fact_job_posting_999"
      ],
      "based_on": {
        "fact_snapshot": "fact_snap_2026_04_15",
        "interpretation_snapshot": "interp_snap_2026_04_15",
        "profile_version": "profile_v7"
      }
    }
  }
}
```

Recommended delete response envelope:

```json
{
  "ok": true,
  "request_id": "req-791",
  "result": {
    "document_id": "pdoc_raw_123",
    "status": "deleted",
    "version": 5,
    "deleted_at": "2026-04-20T10:06:00Z"
  }
}
```

## End-to-End Examples

### Example 1. Create a raw markdown note

1. `POST /api/v1/users/tenant_a/user_42/personal-documents`
2. body:

```json
{
  "domain": "recruiting",
  "subspace": "raw",
  "kind": "note",
  "title": "Toss backend prep",
  "body_markdown": "## Notes\n- review JD\n- compare with shared trend page"
}
```

Expected outcome:

- one writable Personal document in `subspace: "raw"`
- no mutation to shared rendered pages
- no mutation to canonical `Fact` or published `Interpretation`

### Example 2. Register a PDF and attach it to a raw document

1. `POST /api/v1/users/tenant_a/user_42/personal-assets`
2. receive `asset_id`
3. `POST /api/v1/users/tenant_a/user_42/personal-documents`
4. body:

```json
{
  "domain": "recruiting",
  "subspace": "raw",
  "kind": "raw_document",
  "title": "Backend resume package",
  "asset_refs": ["passet_123"]
}
```

### Example 3. Rewrite a raw note into a personal wiki page

1. `POST /api/v1/users/tenant_a/user_42/personal-documents/pdoc_raw_123/generate-wiki`
2. body:

```json
{
  "domain": "recruiting",
  "mode": "rewrite",
  "profile_version": "profile_v7",
  "model_profile": "balanced_default"
}
```

Expected outcome:

- one new or refreshed Personal document in `subspace: "wiki"`
- shared rendered pages may have been used as context only
- saved output remains user-scoped

### Example 4. Link a personal wiki page to shared context

1. `POST /api/v1/users/tenant_a/user_42/personal-documents/pdoc_wiki_456/link`
2. body:

```json
{
  "domain": "recruiting",
  "mode": "apply",
  "model_profile": "balanced_default"
}
```

Expected outcome:

- anchors or related refs are attached to the Personal document
- no promotion into shared `Interpretation`

## Idempotency Guidance

| Endpoint | Retry-safe without key | Recommended `Idempotency-Key` |
| --- | --- | --- |
| `GET` Personal or shared reads | yes | optional |
| `POST` create personal document | no | yes |
| `PATCH` personal document | mostly | recommended |
| `DELETE` personal document | mostly | recommended |
| `POST` register personal asset | no | yes |
| `POST` generate wiki | no | yes |
| `POST` link | depends on mode | recommended |

## Relationship to Existing Contracts

This document does not replace:

- `query_personal_knowledge`
- `create_personal_plan`
- `build_interpretation_snapshot`
- DomainProposalBatch ingest

Instead, it adds the missing authoring resource family needed by workspace-first clients.

Recommended reading order:

1. `docs/three-layer-data-model-spec.md`
2. `docs/llm-orchestration-and-retrieval-spec.md`
3. this document
4. `docs/http-rest-contract-spec.md`
5. `docs/mcp-tool-contract-spec.md`
