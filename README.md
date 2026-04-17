# StrataWiki

Multi-user MCP server architecture for shared knowledge, shared interpretation, and user-scoped strategy generation.

## Core Idea

StrataWiki is being rebuilt around three semantic layers:

- `Fact`: canonical observed data
- `Interpretation`: shared derived meaning
- `Personal`: user-scoped plans, notes, and cached outputs

The system is intended for domains such as recruiting and job strategy first, while staying extensible to other domains through domain plugins.

## Architecture Summary

- Fact is stored in a structured canonical store
- Interpretation is stored as canonical derived records plus rendered shared wiki views
- Personal is stored as user-scoped wiki-style output with anchors into upper layers
- Graph is treated as a cross-layer index and dependency system
- Caches and snapshots are explicit, versioned, and inspectable

## Current State

This repository currently contains:

- architecture and design specs in `docs/`
- a lightweight development notebook in `dev-wiki/`
- initial source tree scaffolding under `src/`
- empty data directories under `data/`

Implementation is planned around an MCP-native server rather than the earlier single-user markdown-only workflow.

## Key Documents

- `docs/mcp-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/three-layer-llm-wiki-mcp-idea.md`
- `docs/three-layer-data-model-spec.md`
- `docs/interpretation-schema-and-lifecycle-spec.md`
- `docs/llm-orchestration-and-retrieval-spec.md`
- `docs/graph-index-and-propagation-spec.md`
- `docs/cache-invalidation-consistency-spec.md`
- `docs/mcp-tool-contract-spec.md`
- `docs/deployment-and-operations-spec.md`
- `docs/recruiting-domain-schema-spec.md`
- `docs/docs-cleanup-checklist.md`

## Development Notes

`dev-wiki/` is the repository's working notebook for active implementation notes.

Use it for:

- temporary logs
- experiments
- prompt drafts
- debugging notes

Keep official architecture, lifecycle, roadmap, and contract decisions in `docs/`.
Promote only stable conclusions from `dev-wiki/` into `docs/`.

## Planned Repository Shape

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

## License

MIT License — see [LICENSE](LICENSE) for details.
