# StrataWiki

Multi-user MCP server architecture for shared knowledge, shared interpretation, and user-scoped strategy generation.

## Core Idea

StrataWiki is being rebuilt around three semantic layers:

- `Fact`: canonical observed data
- `Interpretation`: shared derived meaning
- `Personal`: user-scoped plans, notes, and cached outputs

The system is intended for domains such as recruiting and job strategy first, while staying extensible to other domains through a domain-neutral core plus registered `Domain Pack` artifacts for canonical schema semantics.

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
- an implemented Week 1 MVP runtime under `src/`
- a working local `Fact -> Interpretation -> Personal` demo path
- canonical Fact ingestion, interpretation proposal and publish flow, and personal query orchestration
- a schema-governance layer with Domain Pack registry, validator, compatibility checks, approval gating, proposal ingestion, artifact loading, and review-audit persistence
- empty data directories under `data/`

## Current Gaps

The main remaining gaps are no longer whether an MVP path exists at all.
They are follow-up hardening and read-model work:

- Fact identity and metadata alignment with the current docs
- interpretation read and shared-rendering follow-ups
- persisted Personal anchor reuse for retrieval
- worker, scheduler, and broader operator-runtime paths beyond the single-process demo

## Local MVP Demo

The fastest local path does not require Postgres or external LLM credentials.
It uses the built-in deterministic demo runtime and the sample seed at `examples/demo/mvp-seed.json`.

Install the package into your venv:

```bash
/Users/yebin/venv/bin/python -m pip install -e .
```

List the MVP tools in demo mode:

```bash
/Users/yebin/venv/bin/python -m wiki_mcp.cli --demo list-tools
```

Run the full Week 1 MVP flow in one process:

```bash
/Users/yebin/venv/bin/python -m wiki_mcp.cli --demo demo-mvp
```

That demo flow will:

- load the sample seed file
- ingest the sample recruiting source into `Fact`
- build and publish one `Interpretation` snapshot
- run `query_personal_knowledge`
- write the saved personal answer markdown under `data/wiki/users/user-1/answers/`

You can also override the seed and render paths:

```bash
/Users/yebin/venv/bin/python -m wiki_mcp.cli \
  --demo \
  --seed-path examples/demo/mvp-seed.json \
  --render-root data \
  demo-mvp
```

## Postgres Runtime

The non-demo runtime still expects a PostgreSQL database reachable through `DATABASE_URL` or the default local URL in `src/wiki_mcp/bootstrap.py`.

The runtime can also load Domain Pack artifacts from configured file paths during bootstrap.

Use demo mode for the Week 1 MVP walkthrough unless you have already provisioned the database schema locally.

## Key Documents

- `docs/mcp-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/domain-pack-and-schema-governance-spec.md`
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
