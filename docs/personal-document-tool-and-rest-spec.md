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
  "document_id": "pdoc_123"
}
```

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

### Personal Asset Endpoints

- `POST /api/v1/users/{tenant_id}/{user_id}/personal-assets`

## Request Notes

### Create Personal Document

```json
{
  "domain": "recruiting",
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
        "writable": true,
        "updated_at": "2026-04-20T10:00:00Z"
      },
      {
        "document_id": "pdoc_wiki_456",
        "subspace": "wiki",
        "kind": "wiki_summary",
        "title": "Preparation notes rewritten",
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
