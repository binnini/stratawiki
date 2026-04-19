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

- a resource-specific HTTP/REST boundary that replaces the wrapper for networked integration
- service-to-service auth for that HTTP boundary
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

- `#41` HTTP server baseline
- `#42` DomainProposalBatch over HTTP
- `#43` profile sync and Personal query over HTTP
- `#46` service-to-service auth baseline
- `#47` versioned HTTP contract and idempotency policy

The `#41` baseline does introduce a generic HTTP bridge, but Jobs-Wiki should still treat that as migration infrastructure rather than the final consumer contract.

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

### Phase 2: HTTP-Primary Integration

Move primary calls to HTTP and keep the wrapper only as a temporary rollback path if needed.

Recommended condition before removing the wrapper path:

- all required HTTP endpoints are in place
- auth is in place
- idempotency and retry behavior are documented
- Jobs-Wiki smoke tests pass against the networked runtime

## Recommended Call Sequences

### Fact Write Sequence

1. submit one proposal batch for validation
2. if validation succeeds, submit the same batch for ingest
3. record the returned affected Fact identifiers or snapshot metadata for downstream calls

### Personal Query Sequence

1. upsert the current profile context
2. call Personal query with the same `profile_version`
3. prefer `save=false` in the first migration stage unless persistence is explicitly required

### Interpretation Build Sequence

1. submit one interpretation build request
2. use inline mode for simpler early tests
3. use background mode only when the worker path and job polling are live

## Do Not Change Yet

Jobs-Wiki should not do these things yet:

- remove the `stratawiki-runtime` wrapper path
- switch production-like traffic to HTTP before auth and idempotency are fixed
- connect to the StrataWiki database directly
- assume browser-style integration needs such as CORS are part of the first migration wave

## Handoff Checklist for Jobs-Wiki

- read `docs/http-rest-contract-spec.md`
- keep the current wrapper path as the source of truth until HTTP reaches parity
- prepare dual-mode config keys for wrapper and HTTP
- treat `DomainProposalBatch` as the only default external write contract
- keep profile sync before Personal query
- do not make background interpretation builds the default until job polling is wired
