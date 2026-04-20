# HTTP/REST Contract Spec

## Purpose

This document defines the first human-readable HTTP/REST contract for StrataWiki external clients.

It exists to make the REST migration contract-first rather than implementation-first.

The intended first external consumers are service-to-service clients such as Jobs-Wiki.

## Status

### Already Fixed and Implemented

- the canonical runtime, storage, and tool ownership model
- the preferred external write contract through `validate_domain_proposal_batch` and `ingest_domain_proposal_batch`
- the profile provisioning path through `upsert_profile_context`
- the Personal query path through `query_personal_knowledge`
- the interpretation build path, including `execution_mode: "background"`
- runtime-owned worker execution through `stratawiki worker`
- runtime-owned operator visibility through `get_job_status`, `get_snapshot_status`, `get_cache_status`, and `explain_result`
- the current stable long-lived stdio contract through `stratawiki serve`
- a generic HTTP server baseline through `stratawiki serve-http`
- baseline HTTP probes and generic tool bridge endpoints
- a first service-to-service bearer-token gate for the HTTP runtime through `STRATAWIKI_HTTP_AUTH_TOKEN`
- resource-specific DomainProposalBatch validate and ingest endpoints
- resource-specific profile sync and Personal query endpoints
- resource-specific interpretation build and operator status endpoints

### Recommended but Not Yet Fixed

- a machine-readable HTTP description such as OpenAPI
- an HTTP deployment baseline for Jobs-Wiki and other external WAS clients

### Currently Unknown and Must Be Decided

- the final reverse-proxy and TLS strategy
- whether browser-facing CORS support is needed or whether server-to-server traffic is enough
- whether the long-term external contract remains thin REST over the existing tool layer or grows into a more resource-specific API family

## Design Goals

- preserve StrataWiki ownership of canonical DB access
- preserve StrataWiki ownership of render side effects, snapshot movement, and background jobs
- keep the stdio runtime available during the first migration phase
- give external WAS clients a stable network-facing contract
- keep retry behavior explicit for write endpoints
- keep request tracing and failure diagnosis straightforward for operators

## Non-Goals

- giving external clients direct SQL access
- replacing the existing worker or outbox model
- defining full end-user identity or browser auth in the first HTTP wave
- collapsing the three-layer model into generic CRUD endpoints

## Ownership Rules

The HTTP surface must preserve the same ownership split as the current stdio contract.

StrataWiki owns:

- canonical database access
- Domain Pack resolution and validation
- canonical Fact writes
- snapshot publication
- rendered shared and Personal artifact side effects
- worker coordination and outbox processing
- model-provider credentials
- scope enforcement for user-scoped Personal writes

External clients own:

- request sequencing
- payload construction
- retry behavior within the documented idempotency policy
- their own upstream source collection and normalization

External clients must not:

- connect to the StrataWiki database directly
- write rendered artifacts directly
- bypass Domain Pack validation for canonical writes
- treat shared rendered views as writable resources
- rely on Personal writes to mutate or promote shared upper-layer state

## Proposed Base Path and Versioning

The first HTTP contract should use an explicit versioned prefix:

```text
/api/v1
```

Versioning guidance:

- the human-readable contract in this document is the first draft for `v1`
- the machine-readable contract is expected to land after the HTTP server baseline exists
- breaking HTTP changes should require a new versioned path
- additive endpoint or field changes may remain within `v1`

## Proposed Authentication Baseline

The first HTTP baseline should use service-to-service authentication.

Recommended first approach:

- `Authorization: Bearer <token>`

Status:

- this is now implemented as a static bearer token baseline
- the current runtime env var is `STRATAWIKI_HTTP_AUTH_TOKEN`
- if the env var is unset, the HTTP runtime remains open for local-only development
- if the env var is set, `/api/v1/*` endpoints require a matching bearer token

Recommended access policy:

- `GET /healthz` may remain unauthenticated
- `GET /readyz` may remain unauthenticated inside trusted infrastructure
- `/api/v1/*` endpoints should require authentication in shared environments

## Common Headers

Recommended request headers:

- `Authorization: Bearer <token>` for authenticated endpoints
- `Content-Type: application/json`
- `X-Request-Id: <client-generated-or-proxy-generated-id>` when available
- `Idempotency-Key: <opaque-key>` for retry-sensitive write endpoints

Recommended response headers:

- `X-Request-Id: <resolved-request-id>`
- `Content-Type: application/json`

## Common Response Envelope

The first HTTP contract should keep a stable JSON envelope close to the current stdio runtime.

Success:

```json
{
  "ok": true,
  "request_id": "req-123",
  "result": {}
}
```

Error:

```json
{
  "ok": false,
  "request_id": "req-123",
  "error": {
    "code": "validation_error",
    "message": "Requested profile_version does not match the current stored profile context.",
    "details": {
      "field": "profile_version"
    }
  }
}
```

## Baseline Endpoint Set

The first HTTP baseline intentionally exposes generic runtime endpoints before the resource-specific REST migration is complete.

| Endpoint | Method | Source Tool | Purpose | Status |
| --- | --- | --- | --- | --- |
| `/healthz` | `GET` | n/a | liveness probe | implemented |
| `/readyz` | `GET` | n/a | readiness probe after runtime bootstrap validation | implemented |
| `/api/v1/tools` | `GET` | tool registry | list compact tools or schemas | implemented |
| `/api/v1/tools/{name}` | `GET` | tool registry | inspect one tool schema | implemented |
| `/api/v1/tool-calls` | `POST` | any current tool | execute one tool with its existing argument shape | implemented |
| `/api/v1/domain-proposals/validate` | `POST` | `validate_domain_proposal_batch` | validate one `DomainProposalBatch` | implemented |
| `/api/v1/domain-proposals/ingest` | `POST` | `ingest_domain_proposal_batch` | ingest one validated `DomainProposalBatch` | implemented |
| `/api/v1/profile-contexts/{tenant_id}/{user_id}` | `PUT` | `upsert_profile_context` | upsert one profile context | implemented |
| `/api/v1/personal-queries` | `POST` | `query_personal_knowledge` | run one Personal query | implemented |
| `/api/v1/interpretation-builds` | `POST` | `build_interpretation_snapshot` | request one interpretation build | implemented |
| `/api/v1/jobs/{job_id}` | `GET` | `get_job_status` | inspect one background job | implemented |
| `/api/v1/snapshot-status` | `GET` | `get_snapshot_status` | inspect current snapshot state | implemented |
| `/api/v1/cache-status/{record_id}` | `GET` | `get_cache_status` | inspect one saved Personal output status | implemented |
| `/api/v1/explanations/{layer}/{record_id}` | `GET` | `explain_result` | inspect result explainability | implemented |

## Planned Resource-Specific Endpoint Set

These endpoints remain the target migration surface for external clients such as Jobs-Wiki.

| Endpoint | Method | Source Tool | Purpose | Status |
| --- | --- | --- | --- | --- |
| deployment and migration documentation for the completed HTTP surface | n/a | n/a | final external migration baseline | planned in `#45` |

## Proposed Request Shapes

The HTTP layer should preserve existing tool payloads as much as possible.

### Generic Tool Call Bridge

`POST /api/v1/tool-calls`

```json
{
  "name": "get_snapshot_status",
  "arguments": {
    "domain": "recruiting"
  }
}
```

This baseline exists so the HTTP transport can reuse the current runtime immediately.
The resource-specific endpoints above should gradually replace direct generic tool calls for external integrations.

### Validate Proposal Batch

`POST /api/v1/domain-proposals/validate`

```json
{
  "batch": {
    "batch_id": "jobs-wiki-batch-001",
    "domain": "recruiting",
    "producer": "jobs-wiki",
    "pack_version": "2026-04-18",
    "facts": [],
    "relations": []
  }
}
```

### Ingest Proposal Batch

`POST /api/v1/domain-proposals/ingest`

Body shape should remain the same as validation.

These two proposal endpoints are now the preferred REST write surface for external producer clients.
The generic `/api/v1/tool-calls` bridge should no longer be treated as the default write path for proposal ingestion.

### Upsert Profile Context

`PUT /api/v1/profile-contexts/{tenant_id}/{user_id}`

```json
{
  "domain": "recruiting",
  "profile_version": "profile:v1",
  "goals": [
    "find backend roles"
  ],
  "preferences": {
    "location": "jp"
  },
  "attributes": {
    "level": "mid"
  }
}
```

Path rules:

- `tenant_id` and `user_id` come from the URL path
- the body may omit those two fields
- if the body includes either field, it must match the path value exactly

### Run Personal Query

`POST /api/v1/personal-queries`

```json
{
  "domain": "recruiting",
  "tenant_id": "tenant-1",
  "user_id": "user-1",
  "question": "What backend roles should I target next?",
  "profile_version": "profile:v1",
  "model_profile": "balanced_default",
  "save": false
}
```

Error expectations currently implemented:

- missing stored profile context returns `404 not_found`
- mismatched `profile_version` returns `422 validation_error`

### Request Interpretation Build

`POST /api/v1/interpretation-builds`

```json
{
  "domain": "recruiting",
  "partition": {
    "family": "market_trends",
    "segment": "backend-japan-midlevel"
  },
  "fact_ids": [
    "fact:job:1"
  ],
  "fact_snapshot": "fact_snap:seed",
  "model_profile": "balanced_default",
  "publish": true,
  "execution_mode": "background"
}
```

## Background Execution Semantics

The HTTP contract should preserve the current distinction between inline execution and background execution.

Recommended behavior:

- inline interpretation builds return `200 OK`
- background interpretation builds return `202 Accepted`
- background responses return a stable `job_id`
- clients poll `GET /api/v1/jobs/{job_id}` for progress and terminal status

Recommended background response shape:

```json
{
  "ok": true,
  "request_id": "req-456",
  "result": {
    "status": "queued",
    "job_id": "job-123"
  }
}
```

This `202 Accepted` behavior is now implemented for `POST /api/v1/interpretation-builds` when the payload uses `execution_mode: "background"`.

## Idempotency Policy

The first HTTP contract should make retry behavior explicit.

| Endpoint | Retry-safe without client key | Recommended `Idempotency-Key` | Notes |
| --- | --- | --- | --- |
| `POST /api/v1/domain-proposals/validate` | yes | optional | validation should be side-effect free |
| `POST /api/v1/domain-proposals/ingest` | no | yes | external clients may retry after network failure |
| `PUT /api/v1/profile-contexts/{tenant_id}/{user_id}` | mostly | recommended | natural key is stable, but explicit keys still help request tracing |
| `POST /api/v1/personal-queries` | depends on `save` | recommended when `save=true` | `save=false` is easier to retry safely |
| `POST /api/v1/interpretation-builds` | no | yes | especially important for `execution_mode: "background"` |

The exact storage and conflict semantics for HTTP idempotency are not yet implemented and belong to the HTTP contract issue.

## Error Mapping

Recommended initial mapping:

| HTTP Status | Error Code | Meaning |
| --- | --- | --- |
| `400` | `invalid_request` | malformed JSON or missing required fields |
| `401` | `unauthorized` | missing or invalid auth |
| `403` | `forbidden` | authenticated but not allowed |
| `404` | `not_found` | unknown record or job |
| `409` | `conflict` | duplicate or stale-state conflict |
| `422` | `validation_error` | payload is well-formed but violates domain or lifecycle rules |
| `500` | `internal_error` | unexpected runtime failure |
| `503` | `not_ready` | bootstrap incomplete or backing runtime unavailable |

Tool-specific validation failures should preserve structured details where possible.

## Jobs-Wiki Migration Expectations

Jobs-Wiki should treat this contract as the target network boundary.

Until the HTTP baseline lands:

- keep using the `stratawiki-runtime` wrapper
- keep using the current stdio and CLI contract
- do not switch Jobs-Wiki production-like integration code to HTTP early

After the HTTP baseline lands:

1. authenticate with the runtime-owned service token
2. validate proposal batches before ingest
3. upsert profile context before Personal query
4. prefer `save=false` for early migration until retry behavior is exercised
5. use background interpretation builds only when the worker path is running and job polling is wired

## Open Questions

- Should `readyz` be unauthenticated everywhere or only inside trusted infrastructure?
- Should the first HTTP version keep a uniform response envelope for every endpoint or permit raw resource payloads for some reads?
- Should `get_snapshot_status`, `get_cache_status`, and `explain_result` remain tool-shaped endpoints or evolve into more resource-oriented read models in `v2`?
