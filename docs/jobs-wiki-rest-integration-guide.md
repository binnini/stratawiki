# Jobs-Wiki REST Integration Guide

## Purpose

This document explains how Jobs-Wiki should approach the StrataWiki REST migration.

It is intentionally written from the external integration point of view.

## Current Integration State

### Already Fixed and Implemented

- Jobs-Wiki current cross-repo baseline is HTTP-first for write, Personal, and command flows
- Jobs-Wiki default read path is now HTTP, with SQL read kept only as a deprecated compatibility fallback during migration
- the preferred external write path is `validate_domain_proposal_batch` followed by `ingest_domain_proposal_batch`
- profile provisioning and Personal query already exist through `upsert_profile_context` and `query_personal_knowledge`
- interpretation builds can already run inline or through the worker-backed background path
- Personal document CRUD, asset registration, raw-to-wiki generation, and wiki link flows already exist through dedicated resource-shaped REST endpoints
- a checked-in HTTP deployment baseline now exists through `docker compose` with `server-http`, `worker`, and `http-smoke`
- the wrapper/runtime worktree still exists as a compatibility/dev path, but it is no longer the primary integration baseline

### Recommended but Not Yet Fixed

- a machine-readable REST contract
- the final removal timing for SQL read fallback and any remaining compatibility wrapper usage
- migration of the remaining ask/evidence lookup helpers away from generic tool-calls where a stable resource contract is available

### Currently Unknown and Must Be Decided

- the final HTTP base URL for shared environments
- the final auth env var names for Jobs-Wiki
- the final removal sequence for the remaining compatibility seams

## Current Stable Path

Right now the current baseline is:

```text
Jobs-Wiki
  -> HTTP/REST for write, personal, command, and default read
  -> optional SQL read fallback for rollback/compatibility only
  -> optional wrapper/dev path outside the primary consumer contract
```

The current REST state after `#41` through `#47` is:

- generic HTTP bridge exists
- proposal validation and ingest endpoints exist
- profile sync and Personal query endpoints exist
- interpretation build and operator-status endpoints exist
- bearer token auth baseline exists
- a checked-in Docker Compose deployment path exists for `server-http` plus `worker`

Jobs-Wiki now targets HTTP directly as the primary cross-repo integration boundary.

Important current reality:

- Jobs-Wiki already uses HTTP mode in practice for ask and Personal document flows.
- Personal document CRUD, asset registration, raw-to-wiki generation, and wiki link flows already use dedicated resource-shaped Personal endpoints.
- generic `/api/v1/tool-calls` remains mainly for ask upgrade and evidence lookup helpers such as `get_profile_context`, `get_personal_record`, `get_interpretation_record`, and `get_fact_record`.
- the wrapper path should be understood as compatibility/dev support, not as the current stable consumer contract.

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

### Phase 0: Historical Wrapper-Owned Integration

This is historical context, not the current baseline.

Jobs-Wiki env:

| Env var | Owner | Required now | Purpose |
| --- | --- | --- | --- |
| `STRATAWIKI_CLI_WRAPPER` | Jobs-Wiki | yes | MCP command |
| `JOBS_WIKI_STRATAWIKI_DOMAIN_PACK_PATHS` | Jobs-Wiki | yes for proposal write | write |
| `JOBS_WIKI_STRATAWIKI_ACTIVE_DOMAIN_PACKS` | Jobs-Wiki | recommended | write |

### Phase 1: Dual Mode

Keep only the remaining compatibility seams while HTTP stays primary.

Recommended Jobs-Wiki additions:

| Env var | Owner | Required in dual mode | Purpose |
| --- | --- | --- | --- |
| `STRATAWIKI_BASE_URL` | Jobs-Wiki | yes for current baseline | HTTP read/write |
| `STRATAWIKI_API_TOKEN` | Jobs-Wiki | expected | HTTP auth |

StrataWiki runtime side:

| Env var | Owner | Required in shared HTTP mode | Purpose |
| --- | --- | --- | --- |
| `STRATAWIKI_HTTP_AUTH_TOKEN` | StrataWiki | recommended | HTTP auth gate |

Recommended first dual-mode target:

- point `STRATAWIKI_BASE_URL` at the checked-in Compose HTTP baseline
- keep only the minimum rollback paths needed for read parity and local compatibility

### Phase 2: HTTP-Primary Integration

Treat HTTP as the stable cross-repo contract and remove the remaining compatibility seams in order.

Recommended condition before removing the remaining compatibility seams:

- all required HTTP endpoints are in place
- auth is in place
- the checked-in HTTP deployment baseline has passed `http-smoke`
- idempotency and retry behavior are documented
- Jobs-Wiki smoke tests pass against the networked runtime
- SQL read parity is proven for supported Jobs-Wiki screens before removing the read fallback

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
2. provision or refresh the Profile Context so a concrete `profile_version` exists for that `domain + tenant_id + user_id`
3. if the user selected a PDF or other binary file, upload it through the Jobs-Wiki-owned transport path
4. register the uploaded file in StrataWiki through `POST /api/v1/users/{tenant_id}/{user_id}/personal-assets`
5. create or update a Personal document through `POST/PATCH /api/v1/users/{tenant_id}/{user_id}/personal-documents`
6. if the user requests summarize, rewrite, or structure generation, call the explicit raw-to-wiki endpoint on the raw source document:
   `POST /api/v1/users/{tenant_id}/{user_id}/personal-documents/{document_id}/summarize-wiki`,
   `POST /api/v1/users/{tenant_id}/{user_id}/personal-documents/{document_id}/rewrite-wiki`,
   or `POST /api/v1/users/{tenant_id}/{user_id}/personal-documents/{document_id}/structure-wiki`
7. if the user requests relation or anchor enrichment on a generated wiki artifact, call
   `POST /api/v1/users/{tenant_id}/{user_id}/personal-documents/{document_id}/suggest-links`
   followed by `POST /api/v1/users/{tenant_id}/{user_id}/personal-documents/{document_id}/attach-links`

Current implementation note:

- The sequence below is the current resource-shaped baseline for Personal document/asset/generation/link flows.
- Jobs-Wiki still uses generic `tool-calls` only for a narrower read-helper band in the ask/evidence path while migration is in progress.

Rules:

- shared rendered pages stay read-only
- Personal CRUD targets only user-scoped documents
- Jobs-Wiki should treat `domain + tenant_id + user_id + document_id` as the document key and `profile_version` as scope freshness metadata, not as a separate profile identity
- Jobs-Wiki must send `if_version` on Personal document update and delete
- direct `GET` and `LIST` Personal document reads are the only immediate read-after-write confirmation path
- raw blob upload stays Jobs-Wiki-owned; StrataWiki starts at `register_personal_asset`
- Jobs-Wiki should treat the returned `asset_id` as the StrataWiki reference and should not treat `storage_ref` as the resource id
- asset registration success preserves the original uploaded blob as Personal/raw only and does not imply extracted metadata or shared publication
- generated wiki output stays in Personal and does not promote into shared layers

### Interpretation Build Sequence

1. `POST /api/v1/interpretation-builds`
2. use inline mode for simpler early tests
3. use background mode when the worker path is live
4. poll `GET /api/v1/jobs/{job_id}` for background execution progress

## Do Not Change Yet

Jobs-Wiki should not do these things yet:

- switch production-like traffic to HTTP before auth and idempotency are fixed
- connect to the StrataWiki database directly
- assume browser-style integration needs such as CORS are part of the first migration wave
- assume the generic `/api/v1/tool-calls` bridge is the final long-term consumer contract
- remove SQL read fallback before HTTP read parity is proven for the supported Jobs-Wiki screens

## Handoff Checklist for Jobs-Wiki

- read `docs/http-rest-contract-spec.md`
- treat HTTP as the current source of truth for cross-repo integration
- keep compatibility paths only where the current migration still needs them
- treat `DomainProposalBatch` as the only default external write contract
- prefer the new HTTP proposal endpoints over the generic `/api/v1/tool-calls` bridge for write traffic
- do not describe the wrapper as the normal write/personal/command baseline
- keep generic `/api/v1/tool-calls` usage limited to the remaining ask/evidence lookup helpers
- keep profile sync before Personal query
- use the dedicated HTTP interpretation and status endpoints rather than the generic `/api/v1/tool-calls` bridge for these flows
- use the Personal document and Personal asset endpoints for workspace authoring
- keep binary upload transport separate from StrataWiki resource authority in the first wave
