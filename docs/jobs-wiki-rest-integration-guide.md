# Jobs-Wiki REST Integration Guide

## Purpose

This document explains how Jobs-Wiki should approach the StrataWiki REST migration.

It is intentionally written from the external integration point of view.

## Current Integration State

### Already Fixed and Implemented

- Jobs-Wiki can call StrataWiki through the dedicated runtime worktree at `/Users/yebin/workSpace/stratawiki-runtime`
- Jobs-Wiki can call the wrapper at `/Users/yebin/workSpace/stratawiki-runtime/bin/stratawiki-jobswiki.sh`
- the preferred external write path is `validate_domain_proposal_batch` followed by `ingest_domain_proposal_batch`
- profile provisioning and Personal query already exist through `upsert_profile_context` and `query_personal_knowledge`
- interpretation builds can already run inline or through the worker-backed background path
- a checked-in HTTP deployment baseline now exists through `docker compose` with `server-http`, `worker`, and `http-smoke`

### Recommended but Not Yet Fixed

- a machine-readable REST contract
- the final decision to remove or keep the wrapper as a long-term rollback path

### Currently Unknown and Must Be Decided

- the final HTTP base URL for shared environments
- the final auth env var names for Jobs-Wiki
- whether Jobs-Wiki will keep any local fallback wrapper path after HTTP reaches parity

## Current Stable Path

Right now the lowest-risk compatibility path remains:

```text
Jobs-Wiki WAS
  -> stratawiki-jobswiki.sh
    -> python -m wiki_mcp.cli
      -> StrataWiki runtime
```

The current REST state after `#41` through `#47` is:

- generic HTTP bridge exists
- proposal validation and ingest endpoints exist
- profile sync and Personal query endpoints exist
- interpretation build and operator-status endpoints exist
- bearer token auth baseline exists
- a checked-in Docker Compose deployment path exists for `server-http` plus `worker`

Jobs-Wiki can now target HTTP directly for shared-environment testing, while still keeping the wrapper path as a rollback option during the migration.

## Future Target Path

The target path is:

```text
Jobs-Wiki WAS
  -> HTTP/REST
    -> StrataWiki server
      -> Postgres
      -> worker
      -> render root
```

Jobs-Wiki should still treat StrataWiki as the owner of:

- canonical DB access
- Domain Pack validation
- snapshot and publication behavior
- worker coordination

The first checked-in networked deployment path is:

```text
docker compose up -d postgres
docker compose run --rm init-db
docker compose run --rm doctor
docker compose run --rm seed-mvp
docker compose up -d worker server-http
docker compose run --rm http-smoke
```

That baseline keeps Postgres, worker, and HTTP server on one machine while removing the need for Jobs-Wiki to own a stdio subprocess.

## Migration Phases

### Phase 0: Wrapper-Owned Integration

Use the wrapper only.

Jobs-Wiki env:

| Env var | Owner | Required now | Purpose |
| --- | --- | --- | --- |
| `STRATAWIKI_CLI_WRAPPER` | Jobs-Wiki | yes | MCP command |
| `JOBS_WIKI_STRATAWIKI_DOMAIN_PACK_PATHS` | Jobs-Wiki | yes for proposal write | write |
| `JOBS_WIKI_STRATAWIKI_ACTIVE_DOMAIN_PACKS` | Jobs-Wiki | recommended | write |

### Phase 1: Dual Mode

Keep the wrapper path available while adding HTTP code paths behind feature flags.

Recommended Jobs-Wiki additions:

| Env var | Owner | Required in dual mode | Purpose |
| --- | --- | --- | --- |
| `STRATAWIKI_BASE_URL` | Jobs-Wiki | yes for HTTP mode | HTTP read/write |
| `STRATAWIKI_API_TOKEN` | Jobs-Wiki | expected | HTTP auth |

StrataWiki runtime side:

| Env var | Owner | Required in shared HTTP mode | Purpose |
| --- | --- | --- | --- |
| `STRATAWIKI_HTTP_AUTH_TOKEN` | StrataWiki | recommended | HTTP auth gate |

Recommended first dual-mode target:

- point `STRATAWIKI_BASE_URL` at the checked-in Compose HTTP baseline
- keep wrapper calls available for rollback while HTTP requests are being exercised in staging or local shared environments

### Phase 2: HTTP-Primary Integration

Move primary calls to HTTP and keep the wrapper only as a temporary rollback path if needed.

Recommended condition before removing the wrapper path:

- all required HTTP endpoints are in place
- auth is in place
- the checked-in HTTP deployment baseline has passed `http-smoke`
- idempotency and retry behavior are documented
- Jobs-Wiki smoke tests pass against the networked runtime

## Recommended Call Sequences

### Fact Write Sequence

1. submit one proposal batch to `/api/v1/domain-proposals/validate`
2. if validation succeeds, submit the same batch to `/api/v1/domain-proposals/ingest`
3. record the returned affected Fact identifiers or snapshot metadata for downstream calls

### Personal Query Sequence

1. `PUT /api/v1/profile-contexts/{tenant_id}/{user_id}`
2. `POST /api/v1/personal-queries` with the same `profile_version`
3. prefer `save=false` in the first migration stage unless persistence is explicitly required

### Personal Document Authoring Sequence

For workspace-first document authoring:

1. create or identify the user scope
2. if the user selected a PDF or other binary file, upload it through the Jobs-Wiki-owned transport path
3. register the uploaded file in StrataWiki through `POST /api/v1/users/{tenant_id}/{user_id}/personal-assets`
4. create or update a Personal document through `POST/PATCH /api/v1/users/{tenant_id}/{user_id}/personal-documents`
5. if the user requests LLM rewriting, call `POST /api/v1/users/{tenant_id}/{user_id}/personal-documents/{document_id}/generate-wiki`
6. if the user requests relation or anchor enrichment, call `POST /api/v1/users/{tenant_id}/{user_id}/personal-documents/{document_id}/link`

Rules:

- shared rendered pages stay read-only
- Personal CRUD targets only user-scoped documents
- generated wiki output stays in Personal and does not promote into shared layers

### Interpretation Build Sequence

1. `POST /api/v1/interpretation-builds`
2. use inline mode for simpler early tests
3. use background mode when the worker path is live
4. poll `GET /api/v1/jobs/{job_id}` for background execution progress

## Do Not Change Yet

Jobs-Wiki should not do these things yet:

- remove the `stratawiki-runtime` wrapper path
- switch production-like traffic to HTTP before auth and idempotency are fixed
- connect to the StrataWiki database directly
- assume browser-style integration needs such as CORS are part of the first migration wave
- assume the generic `/api/v1/tool-calls` bridge is the final long-term consumer contract

## Handoff Checklist for Jobs-Wiki

- read `docs/http-rest-contract-spec.md`
- keep the current wrapper path as the source of truth until HTTP reaches parity
- prepare dual-mode config keys for wrapper and HTTP
- treat `DomainProposalBatch` as the only default external write contract
- prefer the new HTTP proposal endpoints over the generic `/api/v1/tool-calls` bridge for write traffic
- use the new HTTP profile and Personal endpoints rather than the generic `/api/v1/tool-calls` bridge for these flows
- keep profile sync before Personal query
- use the dedicated HTTP interpretation and status endpoints rather than the generic `/api/v1/tool-calls` bridge for these flows
- use the Personal document and Personal asset endpoints for workspace authoring once implemented
- keep binary upload transport separate from StrataWiki resource authority in the first wave
