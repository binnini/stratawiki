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

### Recommended but Not Yet Fixed

- the remaining resource-specific HTTP/REST boundary that replaces the wrapper for networked integration
- a machine-readable REST contract
- an HTTP deployment baseline that Jobs-Wiki can target directly

### Currently Unknown and Must Be Decided

- the final HTTP base URL for shared environments
- the final auth env var names for Jobs-Wiki
- whether Jobs-Wiki will keep any local fallback wrapper path after HTTP reaches parity

## Current Stable Path

Right now the stable path remains:

```text
Jobs-Wiki WAS
  -> stratawiki-jobswiki.sh
    -> python -m wiki_mcp.cli
      -> StrataWiki runtime
```

That path is still the right choice until the HTTP milestone reaches at least:

- `#43` profile sync and Personal query over HTTP
- `#46` service-to-service auth baseline
- `#47` versioned HTTP contract and idempotency policy

The current REST state after `#41`, `#42`, and `#46` is:

- generic HTTP bridge exists
- proposal validation and ingest endpoints now exist
- bearer token auth baseline now exists

After `#43`, the REST state is:

- profile sync now exists through `PUT /api/v1/profile-contexts/{tenant_id}/{user_id}`
- Personal query now exists through `POST /api/v1/personal-queries`

After `#44`, the REST state is:

- interpretation build now exists through `POST /api/v1/interpretation-builds`
- background build polling now exists through `GET /api/v1/jobs/{job_id}`
- snapshot, cache, and explanation reads now have dedicated HTTP endpoints

Jobs-Wiki should still treat the wrapper path as the safest default until interpretation build and deployment migration work also land, but the write path and Personal path can now be tested over HTTP.

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

### Phase 2: HTTP-Primary Integration

Move primary calls to HTTP and keep the wrapper only as a temporary rollback path if needed.

Recommended condition before removing the wrapper path:

- all required HTTP endpoints are in place
- auth is in place
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
