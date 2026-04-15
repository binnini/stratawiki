# StrataWiki

StrataWiki is a multi-user MCP-native knowledge system built around a three-layer model:

- `Fact`: canonical observed data
- `Interpretation`: shared derived meaning
- `Personal`: user-scoped strategy, notes, and cached outputs

It starts with recruiting and job strategy as the first reference domain, but the architecture is intended to remain domain-extensible.

StrataWiki should be positioned as a separate knowledge backend service, not just a database and not just a markdown wiki.

## Philosophy

StrataWiki is inspired by the LLM Wiki pattern: knowledge should compound over time instead of being rediscovered from raw documents on every query.

The main adaptation is structural.

In the original markdown-only LLM Wiki pattern, the wiki itself is the main knowledge substrate.
In StrataWiki, the readable wiki is only one layer of a larger system.

StrataWiki keeps the compounding-knowledge idea, but implements it through:

- canonical Fact storage
- canonical Interpretation storage
- user-scoped Personal overlays
- rendered markdown views
- graph-based dependency and retrieval support
- snapshots, caches, and invalidation

One-sentence summary:

StrataWiki adopts the LLM Wiki pattern as a compounding knowledge philosophy, but reimplements it as a multi-layer MCP system where markdown is a readable view, not the only source of truth.

## Core Model

### Fact

Fact stores normalized observed data with provenance and canonical identity.

This layer is the strongest source of truth in the system.

### Interpretation

Interpretation stores shared derived meaning from Facts.

This is where trends, comparisons, contradictions, opportunity summaries, and relation-rich derived knowledge live.

### Personal

Personal stores user-scoped strategy, notes, plans, and cached outputs.

Personal records are anchored to upstream snapshots and records rather than treated as isolated documents.

## Retrieval and Propagation Model

StrataWiki treats graph as more than visualization.

Graph supports:

- semantic navigation
- retrieval expansion
- dependency routing
- provenance traversal
- impact analysis

Default user-facing retrieval order:

- Personal
- Interpretation
- Fact

Default downstream propagation order after Fact changes:

- Fact
- Interpretation
- Personal

## Service Position

StrataWiki is intended to sit behind a separate WAS or product backend.

- the WAS owns user-facing product APIs, session/auth entrypoints, and UI-specific orchestration
- StrataWiki owns knowledge ingestion, canonicalization, interpretation refresh, personalization, snapshots, dependency routing, and retrieval orchestration
- PostgreSQL is a separate infrastructure dependency owned by StrataWiki at the schema and migration level

## Version-One Technical Baseline

The current version-one stack is:

- runtime: Python 3.11+
- Fact store: PostgreSQL
- Interpretation canonical store: PostgreSQL JSONB
- Personal metadata store: PostgreSQL
- Personal rendered body: filesystem markdown
- projection model: outbox + worker
- graph and dependency storage: PostgreSQL reverse dependency indexes + derived graph artifacts
- retrieval indexing: structured filtering + lexical search
- ACL enforcement: application-level scope enforcement
- ingestion model: core pipeline + domain ingestion interface

## Current State

This repository currently contains:

- architecture and design specs in `docs/`
- local working knowledge support through `dev-wiki/`
- initial package scaffolding under `src/`
- empty data directories under `data/`

Implementation is still in the design-to-build transition.

## Documentation Guide

### Official project docs

The official architecture and implementation documents live in `docs/`.

Key documents:

- `docs/mcp-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/three-layer-llm-wiki-mcp-idea.md`
- `docs/three-layer-data-model-spec.md`
- `docs/cache-invalidation-consistency-spec.md`
- `docs/graph-index-and-propagation-spec.md`
- `docs/mcp-tool-contract-spec.md`
- `docs/recruiting-domain-schema-spec.md`
- `docs/technology-decision-memo.md`
- `docs/postgres-vs-mongodb-for-interpretation.md`
- `docs/postgresql-schema-structure.md`
- `docs/llm-wiki-pattern-adapted-for-stratawiki.md`
- `docs/domain-ingestion-interface-spec.md`
- `docs/external-ingestion-adapter-spec.md`
- `docs/internal-architecture-boundaries.md`
- `docs/service-boundary-and-database-positioning.md`

### Working notes

`dev-wiki/` is the repository's local working knowledge layer.

Use it for:

- architecture scratch notes
- experiments
- temporary decision logs
- prompt drafts
- development logs

Promote stable content from `dev-wiki/` into `docs/` once it becomes reusable and official.

## Repository Shape

```text
src/
  wiki_mcp/
    adapters/
    auth/
    cache/
    graph/
    rendering/
    schemas/
    services/
    tools/
data/
  raw/
  wiki/
  graph/
  state/
config/
  domains/
docs/
dev-wiki/
tests/
```

## Domain Position

Recruiting is the first reference domain, not the definition of the platform.

The core architecture should remain domain-neutral.
Domain-specific logic should live behind domain interfaces and domain-specific schema or rendering modules.

## License

MIT License — see [LICENSE](LICENSE) for details.
