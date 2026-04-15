# MCP Architecture Draft for 3-Layer LLM Wiki Server

## Purpose

This document proposes an MCP-native architecture for a multi-user three-layer LLM Wiki system.

The architecture is intended to support:

- shared knowledge with personal overlays
- domain-specific plugins
- provider-agnostic LLM orchestration
- rendered markdown wiki views
- snapshot-aware retrieval and invalidation

It is no longer just a migration sketch for a local `AGENTS.md` workflow. It is the current top-level system view for the production-oriented MCP direction.

## Architectural Position

This architecture should be understood as:

- CQRS-inspired rather than strict textbook CQRS
- tiered storage rather than one universal storage system
- snapshot-aware rather than globally ACID across all derived layers
- graph-assisted rather than graph-native for canonical truth
- a separate knowledge backend service rather than a database-bound application module

## Design Goals

- expose stable MCP tools for shared and personal workflows
- separate canonical records from rendered markdown views
- support multiple source connectors and multiple LLM providers
- support multi-user and multi-tenant scope boundaries
- preserve provenance, snapshot traceability, and explainability
- keep domain-specific logic modular
- support graph-based retrieval expansion and dependency routing

## Non-Goals

- making markdown the only system of record
- forcing one LLM provider or one agent client
- requiring Kafka or heavyweight event infrastructure on day one
- hiding derivation and invalidation logic from operators

## Layer Model

The system uses three semantic layers:

- `Fact`: canonical observed data
- `Interpretation`: shared derived meaning
- `Personal`: user-scoped strategy, notes, and cached outputs

This split exists to prevent shared truth, shared meaning, and user-specific strategy from being mixed together.

## Target Architecture

```text
Agent Clients
  Codex / Claude / Gemini / custom UI / schedulers

        |
        v

MCP Server
  - source tools
  - fact tools
  - interpretation tools
  - personal tools
  - graph tools
  - cache/snapshot tools
  - admin tools

        |
        +--> Source Adapters
        |     - filesystem
        |     - notion
        |     - slack
        |     - web / rss / news api
        |     - github / docs / internal systems
        |
        +--> LLM Router
        |     - openai adapter
        |     - anthropic adapter
        |     - gemini adapter
        |     - optional litellm adapter
        |
        +--> Canonical Stores
        |     - Fact store
        |     - Interpretation canonical store
        |     - Profile store
        |
        +--> Rendered Stores
        |     - shared wiki pages
        |     - user wiki pages
        |     - graph artifacts
        |
        +--> Snapshot and Cache Layer
              - snapshot pointers
              - dependency indexes
              - rendered page caches
              - personal answer caches
```

## Major Layers

### 1. MCP Tool Layer

This is the public interface exposed to clients.

Responsibilities:

- accept structured requests
- validate inputs
- dispatch to services
- return structured outputs
- avoid embedding provider-specific behavior in tool definitions

Examples:

- `ingest_fact_batch`
- `build_interpretation_snapshot`
- `query_personal_knowledge`
- `create_personal_plan`
- `get_dependency_impact`
- `get_cache_status`
- `fetch_source`
- `list_sources`

### 2. Service Layer

This is the core application logic.

Responsibilities:

- normalize sources
- write canonical fact records
- build interpretation projections
- render shared and personal wiki pages
- execute user-scoped retrieval
- detect stale or invalid downstream records
- build graph outputs and dependency indexes

This layer should be testable without any specific MCP client.

### 3. Source Adapter Layer

This layer knows how to talk to external systems.

Responsibilities:

- connect to data sources
- fetch raw records
- map source-native payloads into a common `SourceRecord`
- track provenance and incremental sync state

Initial adapters:

- filesystem
- web fetch or RSS
- Notion
- Slack
- GitHub

### 4. LLM Router Layer

This layer hides provider-specific differences behind common operations.

Responsibilities:

- select provider and model profile
- execute text generation or structured extraction
- normalize provider-specific responses
- handle retries and fallbacks
- enforce schema validation for structured outputs

This is the key to OpenAI, Anthropic, and Gemini compatibility.

### 5. Canonical Storage Layer

This layer persists the system-of-record data.

Responsibilities:

- store canonical facts
- store shared interpretation records
- store user profiles and profile versions
- preserve provenance and schema versions
- support dedupe, normalization, and replayability

Recommended direction:

- Fact in PostgreSQL
- Interpretation canonical in PostgreSQL JSONB for version one
- Profile and Personal metadata in PostgreSQL
- Personal rendered markdown on the filesystem

PostgreSQL should be treated as a separate infrastructure dependency owned by StrataWiki, not as an in-process storage detail.

### 6. Rendered View Layer

This layer produces human-readable markdown and graph artifacts.

Responsibilities:

- render shared interpretation pages
- render user-scoped personal pages
- render graph artifacts
- preserve snapshot references used for rendering

Markdown is a view layer here, not the sole authority.

### 7. Graph and Dependency Layer

Graph is not just for visualization.

Responsibilities:

- semantic navigation
- retrieval expansion
- dependency routing
- provenance traversal
- impact analysis

Graph should be treated as a cross-layer index and dependency system, not as the canonical truth store.

### 8. Snapshot and Cache Layer

Responsibilities:

- publish fact snapshots
- publish interpretation snapshots or family snapshots
- key caches by snapshot tuple and profile version
- track stale versus invalid states
- support selective regeneration

This layer is what makes multi-user performance and explainability practical.

## Canonical Data Model

The architectural pivot is to ingest everything through a provider-neutral source schema and then separate:

- canonical observed data
- canonical derived meaning
- rendered personal or shared views

### SourceRecord

```json
{
  "source_id": "notion:page:abc123",
  "source_type": "notion",
  "title": "Q2 Planning Notes",
  "author": "Jane Doe",
  "created_at": "2026-04-15T10:00:00Z",
  "updated_at": "2026-04-15T11:20:00Z",
  "body_markdown": "Normalized markdown content",
  "tags": ["meeting"],
  "metadata": {
    "workspace": "product",
    "url": "https://example.com/page"
  },
  "provenance": {
    "connector": "notion",
    "external_id": "abc123",
    "fetched_at": "2026-04-15T12:00:00Z"
  }
}
```

Every adapter should produce this shape before the Fact ingest pipeline runs.

## Core Data Flows

### Fact Ingest Flow

1. fetch source
2. normalize to `SourceRecord`
3. dedupe and canonicalize
4. write Fact records
5. publish fact snapshot or delta metadata
6. route dependency impact to downstream layers

### Interpretation Projection Flow

1. select affected fact partitions
2. compute interpretation records
3. validate and version them
4. publish interpretation snapshot or family snapshot
5. render shared interpretation pages if needed

### Personal Retrieval and Generation Flow

1. resolve user profile and current profile version
2. retrieve from Personal first
3. expand through Interpretation
4. drill down into Fact for evidence if needed
5. generate or refresh personal output
6. store anchors and snapshot tuple

## Retrieval Principle

The default retrieval order for user-facing strategy or synthesis should usually be:

- Personal
- Interpretation
- Fact

This keeps user context first while preserving shared meaning and factual grounding.

## Multi-Provider LLM Compatibility

An MCP architecture can be LLM-agnostic if the server owns the provider abstraction.

Recommended internal interface:

- `generate_text(task, prompt, options)`
- `generate_json(task, prompt, schema, options)`
- `embed_texts(texts, options)`

Provider implementations:

- OpenAI adapter
- Anthropic adapter
- Gemini adapter
- optional LiteLLM adapter

Important distinction:

- interface compatibility is realistic
- identical behavior across providers is not realistic

The design should optimize for consistent contracts, not identical model output.

## Internal Layering Requirement

StrataWiki should become more internally layered before it becomes more physically distributed.

Important internal boundaries include:

- core vs domain plugins
- canonical vs rendered
- retrieval vs dependency routing
- synchronous request paths vs asynchronous projection paths
- MCP interface vs internal service interface

## Multi-User and ACL Requirements

Access control must apply consistently to:

- retrieval candidate selection
- graph traversal
- rendered page access
- provenance lookups
- cache inspection

Shared, tenant-scoped, and user-scoped records should be explicitly distinguishable.

## Operational Considerations

- use asynchronous projection rather than cross-store synchronous mutation
- use outbox plus worker as the version-one projection model
- partition interpretation snapshots by family or segment where possible
- keep reverse dependency indexes in PostgreSQL to limit invalidation blast radius
- attach schema versions and prompt/template versions to derived records
- keep markdown as a rendered view, not the only operational storage layer
- enforce shared, tenant, and user scope in the application layer
- start retrieval with structured filtering plus lexical search

## Recommended Repository Shape

```text
src/
  server/
  tools/
  services/
  adapters/
  schemas/
  graph/
  rendering/
  cache/
  auth/
data/
  raw/
  wiki/
  graph/
  state/
config/
  models.yaml
  domains/
docs/
```

The exact file layout can vary, but the conceptual separation should remain.

## Recommended Next Step

Use this architecture document as the high-level system view, then rely on the dedicated specs for:

- data model
- cache, invalidation, and consistency
- graph, indexing, and propagation
- MCP tool contracts
- domain-specific schemas
