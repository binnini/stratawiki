# Internal Architecture Boundaries

## Purpose

This document defines the internal architectural boundaries inside StrataWiki.

The goal is not to split the system into many physical services immediately.
The goal is to make the internal responsibilities explicit so the codebase does not collapse into one large undifferentiated backend.

StrataWiki should be treated as a knowledge backend with clear internal layers.

## Boundary Strategy

At the current stage, StrataWiki should prioritize:

- strong logical separation
- modular code boundaries
- explicit interfaces
- delayed physical service splitting

This means:

- separate responsibilities in code now
- separate deployment units only when pressure justifies it

## Primary Internal Boundaries

### 1. Core vs Domain Plugins

The core should own:

- three-layer lifecycle
- snapshot logic
- outbox and projection flow
- dependency routing
- retrieval orchestration
- shared contracts

Domain plugins should own:

- ingestion mapping
- domain schema interpretation
- domain-specific validation
- interpretation family rules
- domain-specific rendering conventions where necessary

This boundary prevents the first domain from contaminating the platform core.

### 2. Canonical vs Rendered

Canonical state includes:

- Fact records
- Interpretation canonical records
- Personal metadata
- snapshots
- dependency indexes

Rendered artifacts include:

- markdown pages
- graph artifacts
- user-facing readable outputs

Rendered outputs must not become the only source of truth.

### 3. Retrieval vs Dependency

Retrieval answers:

- what is relevant
- what should be included in the query context

Dependency answers:

- what depends on what
- what must be marked stale or invalid after a change

These should remain distinct even if they share some graph-like structures.

### 4. Synchronous vs Asynchronous Paths

Synchronous paths include:

- user-facing queries
- metadata lookups
- cache inspection
- page retrieval

Asynchronous paths include:

- interpretation rebuilds
- rendered page refresh
- stale marking
- graph rebuilds
- dependency projection

These paths should be separated so query serving is not coupled to background recomputation.

### 5. MCP Interface vs Internal Service Interface

The MCP interface exists for agent-facing and tool-facing integration.

The internal service interface exists for:

- WAS integration
- internal orchestration
- non-agent backend callers

These interfaces may overlap initially, but they should not be treated as conceptually identical.

## Secondary Boundaries to Preserve

### 6. Profile and Context State

User profile and context data are required by StrataWiki, but they should still be treated as their own concern.

This includes:

- goals
- preferences
- tenant membership context
- profile versions

Keep this boundary explicit so a future profile service remains possible.

### 7. Search Backends vs Retrieval Orchestration

Retrieval orchestration should not be tightly coupled to one search implementation.

The orchestration layer should remain distinct from:

- PostgreSQL lexical search
- external markdown search tools
- future vector search

### 8. Rendering Subsystem

Rendering should remain its own subsystem.

This includes:

- shared interpretation page rendering
- personal markdown rendering
- graph artifact rendering

Rendering should consume canonical state rather than redefine it.

## Recommended Code-Level Shape

A practical version-one structure should reflect these boundaries:

- `schemas/`
- `services/interfaces/`
- `services/core/`
- `services/domain/`
- `rendering/`
- `graph/`
- `cache/`
- `auth/`
- `tools/`

The key requirement is not the folder names themselves.
The requirement is that these responsibilities do not silently collapse into one layer.

## What Should Not Be Split Yet

At the current stage, do not force separate physical services for:

- graph
- vector search
- projection workers
- interpretation engine
- personal engine

These can remain part of the StrataWiki backend as long as the internal boundaries remain clear.

## Final Position

StrataWiki should become more internally layered before it becomes more physically distributed.

That is the right trade-off for version one.
