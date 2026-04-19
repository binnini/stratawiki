# Deployment and Operations Spec

## Purpose

This document defines deployment-facing and operations-facing constraints for the StrataWiki system.

It focuses on:

- runtime topology
- process separation
- state durability classes
- asynchronous execution boundaries
- operational visibility requirements
- deployment assumptions that should influence implementation

This document is not a platform-specific deployment guide.
It is an architecture and runtime constraints document.

## Design Goals

- keep the architecture deployable from the beginning
- support local development without hiding production-critical boundaries
- separate durable state from disposable state
- support background work for interpretation, graph, and cache workflows
- make operator visibility a first-class requirement
- avoid premature commitment to one infrastructure platform

## Non-Goals

- prescribing Kubernetes, ECS, Nomad, or any specific platform
- defining CI/CD pipelines
- defining secrets management details
- defining multi-region architecture on day one

## Runtime Topology

The system should be deployable with at least the following logical runtime roles:

- MCP server
- worker
- scheduler

Optional roles:

- markdown-search indexer
- graph build worker
- operator UI or operator API

These roles may run in one process during local development, but the architecture should not assume that they always do.

## Runtime Roles

### MCP Server

Responsibilities:

- expose MCP tools
- authenticate and authorize requests
- run request-time orchestration
- execute low-latency retrieval paths
- return snapshot-aware and scope-aware responses

The MCP server should avoid long-running rebuilds on the synchronous request path where possible.

### Worker

Responsibilities:

- interpretation generation jobs
- interpretation validation and publish jobs
- rendered page regeneration
- graph artifact builds
- cache warming
- stale refresh jobs

Workers should operate against explicit snapshot or partition inputs whenever possible.

### Scheduler

Responsibilities:

- periodic source sync triggers
- interpretation refresh scheduling
- cache warming schedules
- health or consistency checks
- stale sweep and maintenance jobs

The scheduler may be a dedicated process or a thin wrapper over a simpler job system in early stages.

Current early baseline:

- interpretation build requests can already be queued from the request path
- the worker can claim and execute those queued requests
- broader scheduler coordination remains follow-up work

### Optional Markdown Indexer

Responsibilities:

- maintain markdown page indexes
- refresh optional `qmd` or equivalent search backends
- rebuild page-search indexes after render updates

This role is optional because markdown retrieval is an accelerator, not a canonical requirement.

## Deployment Modes

### Local Development

Recommended shape:

- single machine
- one MCP server process
- worker and scheduler may run inline or as simple local processes
- local durable storage is acceptable
- repository-provided database bootstrap artifacts should be enough to initialize the local canonical store

Goal:

- maximize iteration speed while preserving core architectural boundaries

Current local baseline:

- the repository now supports a long-lived stdio runtime entrypoint through `stratawiki serve`
- this gives external clients a stable process boundary without giving them direct database access
- it is acceptable as the first long-lived runtime contract before a later networked deployment surface is chosen
- the repository now also supports a minimal worker entrypoint through `stratawiki worker --limit N`
- the repository now ships `.env.example` plus `stratawiki doctor` so another developer can validate the non-demo runtime before starting server and worker roles

### Single-Node Shared Environment

Recommended shape:

- one MCP server process
- separate worker process
- scheduler process or scheduled job runner
- durable shared storage for canonical state

Goal:

- validate async flows, snapshot publishing, and operator workflows before more distributed deployment

The single-node shared environment may still use the stdio runtime boundary when one upstream producer launches and owns the StrataWiki process.
Later networked or queue-backed deployment surfaces can be added without changing ownership of canonical state.

Current first deployment target:

- `Dockerfile`
- `docker-compose.yml`
- one Postgres container
- one interactive stdio server container
- one networked HTTP server container
- one looping worker container
- one repository-provided HTTP smoke container
- shared render volume for filesystem artifacts

Current HTTP deployment baseline:

- `server-http` runs `stratawiki serve-http`
- `worker` shares the same Postgres-backed canonical store and render volume
- `http-smoke` performs a small end-to-end HTTP validation against the same durable store
- `STRATAWIKI_HTTP_AUTH_TOKEN` is the first service-to-service auth control for shared environments

### Multi-Process Production-Like Environment

Recommended shape:

- one or more MCP server instances
- one or more workers
- dedicated scheduler or queue-driven scheduler
- shared durable storage
- shared cache and index backends where required

Goal:

- support scale, isolation, and operational recovery without changing core service boundaries

## State Classes

The system should distinguish state by durability and rebuild cost.

### 1. Canonical Durable State

Examples:

- Fact records
- Interpretation canonical records
- profiles
- personal canonical records
- snapshot metadata

Requirements:

- durable
- restart-safe
- authoritative

### 2. Durable Derived Artifacts

Examples:

- rendered shared pages
- rendered personal pages
- persisted graph artifacts if stored durably

Requirements:

- may be regenerated
- useful to persist across restarts
- should always reference the snapshots used

### 3. Operational State

Examples:

- job metadata
- proposal review state
- publication locks
- cache status records

Requirements:

- durable enough for operator visibility and recovery

### 4. Ephemeral Cache State

Examples:

- retrieval cache
- graph traversal cache
- markdown search result cache
- temporary compaction outputs

Requirements:

- disposable
- restart loss should be acceptable
- must not become the only source of important state

### 5. Temporary Work Artifacts

Examples:

- in-progress graph builds
- partial interpretation generation outputs
- staging render outputs

Requirements:

- scoped to a job or task
- safe to discard on failure

## Filesystem Assumptions

The implementation should not assume that local process filesystem state is globally shared across all runtime roles.

This matters especially for:

- rendered markdown pages
- graph artifact outputs
- markdown search indexes
- temporary job outputs

If local files are used in development, the architecture should still allow migration to shared durable storage or shared artifact stores later.

## Request Path Versus Background Path

The system should draw a clear boundary between synchronous request work and asynchronous background work.

### Request Path

Appropriate tasks:

- tool request validation
- curated retrieval
- bounded exploratory retrieval
- prompt assembly
- LLM generation for user-facing answers
- lightweight persistence

The current long-lived stdio runtime belongs to the request path.
It is a transport boundary for tool requests, not a substitute for worker or scheduler roles.

Inappropriate tasks:

- large interpretation family rebuilds
- full graph rebuilds
- broad cache invalidation sweeps
- large markdown index rebuilds

### Background Path

Appropriate tasks:

- interpretation snapshot rebuild
- render regeneration
- graph artifact publish
- markdown index refresh
- cache warming
- stale refresh

## Job Model

The deployment should support jobs with:

- explicit job IDs
- status tracking
- retryability
- failure visibility
- partition or snapshot binding

Recommended early options:

- outbox table plus worker
- simple job queue
- scheduled jobs plus durable job metadata

Current implementation baseline:

- queued interpretation build requests use the outbox repository as the first job carrier
- `stratawiki worker` claims queued interpretation build requests and executes them out of band
- `stratawiki doctor` can validate that the Postgres bootstrap relations exist before the worker starts

Heavyweight event infrastructure is not required on day one.

## Publish Boundaries

The deployment model should preserve coherent publish boundaries.

Important examples:

- Fact ingestion batch commit
- interpretation partition publish
- graph artifact publish against a snapshot tuple
- markdown index publish after page render update

Partially published state should not become the default read target.

Current interpretation baseline:

- interpretation record updates, snapshot pointer movement, and outbox append are now committed as one publish bundle
- shared page replacement is handled through a rollback-capable filesystem swap
- if the publish bundle raises before completion, the prior rendered page is restored and the canonical default read target does not advance

## LLM Runtime Considerations

The implementation should support LLM integration from early phases.

Deployment implications:

- model provider credentials must be available to server and worker roles as needed
- request-time and background-time LLM usage should be observable separately
- prompt and model version metadata should be durable
- LLM failures should surface as operator-visible events, not silent partial state

The architecture should support both:

- direct request-time LLM usage
- background job LLM usage for interpretation generation and maintenance flows

## Retrieval Runtime Considerations

Deployment should not assume one retrieval backend only.

The runtime should allow:

- graph-backed retrieval
- markdown-search-backed retrieval
- canonical-store retrieval
- retrieval caching

This implies backend health and freshness visibility should be observable.

## Operator Visibility Requirements

Operators should be able to inspect at least:

- current fact and interpretation snapshots
- job status and failures
- cache state and invalidation reason
- proposal validation and publish state
- graph build status
- markdown index freshness when markdown retrieval is enabled
- explanation metadata for changed outputs

Without this visibility, the system will be difficult to trust and recover in practice.

Current implementation baseline:

- `get_snapshot_status` exposes the current published snapshot registry
- `get_cache_status` exposes saved Personal cache freshness and invalidation reasons
- `get_job_status` exposes runtime-owned outbox job state for the current background path
- interpretation proposal lifecycle is operator-visible through list, validate, publish, and status tools
- `explain_result` exposes snapshot tuple, anchors, lifecycle context, and change reason for Personal and Interpretation results
- `get_graph_neighbors` and `get_dependency_impact` expose the first graph/dependency operator views
- graph build status and markdown index freshness are still follow-up work

## Failure and Recovery Expectations

The deployment model should assume:

- jobs can fail mid-run
- workers can restart
- caches can be lost
- indexes can lag behind canonical records
- external LLM providers can fail or timeout

Therefore the system should support:

- idempotent publish paths where possible
- replayable jobs where possible
- explicit stale markers
- explainable partial degradation

## Security and Access Boundaries

Deployment must preserve scope boundaries across runtime roles.

This includes:

- MCP server request handling
- worker-driven regeneration
- graph traversal jobs
- markdown indexing
- cache storage

Cross-user or cross-tenant leakage through caches, indexes, or artifact stores should be treated as a critical failure mode.

## Recommended Initial Deployment Posture

For early implementation, a reasonable target is:

- one MCP server process
- one worker process
- one scheduler process or lightweight scheduled runner
- durable canonical storage
- durable snapshot metadata
- disposable cache
- optional local markdown artifact and index storage for development

This is enough to validate the architecture without overcommitting to heavyweight infrastructure.

Current repository baseline:

- copy `.env.example` to `.env`
- run `stratawiki init-db`
- run `stratawiki doctor`
- start one stdio server and one worker against the same durable store
- use `docker compose` as the first checked-in deployment target for that baseline

## Open Deployment Questions

- which state should persist across restarts in the first milestone
- whether markdown indexes are rebuilt eagerly or lazily
- whether graph artifacts are stored durably or rebuilt on demand
- whether operator tooling remains MCP-only or later grows a dedicated operator API/UI
- when a shared cache backend becomes necessary

## Summary

Deployment should be treated as a design constraint, not a late-stage packaging concern.

The architecture should assume:

- at least server, worker, and scheduler roles
- clear durable versus ephemeral state boundaries
- asynchronous rebuild and publish paths
- operator visibility into snapshots, jobs, caches, and proposals

This is enough to guide implementation without prematurely locking the project to one platform.
