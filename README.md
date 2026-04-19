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
- a profile context write path for external Personal query clients
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

The non-demo runtime expects a PostgreSQL database reachable through `DATABASE_URL` or the default local URL in `src/wiki_mcp/bootstrap.py`.

The runtime can also load Domain Pack artifacts from configured file paths during bootstrap.

The repository now includes a checked-in bootstrap SQL artifact at `config/postgres/bootstrap.sql`.

The repository now also includes a checked-in `.env.example` for non-demo local runs and the Docker/Compose baseline.

Copy it first when you want a shared server/worker environment:

```bash
cp .env.example .env
```

For bare-metal local development, update `DATABASE_URL` from the container host `postgres` to your local host, for example `localhost`.

Create a local database first, then initialize the schema from the repository:

```bash
createdb stratawiki_dev

/Users/yebin/venv/bin/python -m wiki_mcp.cli \
  --database-url postgresql://stratawiki:stratawiki@localhost:5432/stratawiki_dev \
  init-db
```

Validate the non-demo runtime before starting the server or worker:

```bash
/Users/yebin/venv/bin/python -m wiki_mcp.cli \
  --database-url postgresql://stratawiki:stratawiki@localhost:5432/stratawiki_dev \
  --render-root data-dev \
  doctor
```

Load the sample MVP seed into the real storage path:

```bash
/Users/yebin/venv/bin/python -m wiki_mcp.cli \
  --database-url postgresql://stratawiki:stratawiki@localhost:5432/stratawiki_dev \
  --render-root data-dev \
  seed-mvp
```

That non-demo seed flow uses the same sample seed file as the demo walkthrough, but persists through the Postgres-backed repositories and filesystem render root instead of the in-memory runtime.

Verify the runtime can start against the initialized database:

```bash
/Users/yebin/venv/bin/python -m wiki_mcp.cli \
  --database-url postgresql://stratawiki:stratawiki@localhost:5432/stratawiki_dev \
  --render-root data-dev \
  list-tools
```

To reset the local database, recreate the database and rerun `init-db`:

```bash
dropdb stratawiki_dev
createdb stratawiki_dev
```

If your existing venv was created before the Postgres runtime dependency was added, rerun:

```bash
/Users/yebin/venv/bin/python -m pip install -e .
```

Current baseline:

- `stratawiki doctor` validates the bootstrap SQL path, render root, configured Domain Pack paths, and Postgres bootstrap tables
- `stratawiki serve` and `stratawiki worker` now run that validation automatically before startup
- `STRATAWIKI_DOMAIN_PACK_PATHS` and `STRATAWIKI_ACTIVE_DOMAIN_PACKS` can now come from the environment without repeating CLI flags

## Docker Compose Baseline

The first repository-provided deployment target is `Dockerfile + docker-compose.yml`.

Bring up Postgres first:

```bash
docker compose up -d postgres
```

Initialize the schema and validate the runtime:

```bash
docker compose run --rm init-db
docker compose run --rm doctor
```

Seed the sample MVP data:

```bash
docker compose run --rm seed-mvp
```

Start the worker loop in one terminal:

```bash
docker compose up worker
```

Start the stdio server in another terminal:

```bash
docker compose run --rm server
```

Important notes:

- the server container stays interactive because the current long-lived runtime contract is stdio, not HTTP
- the Compose baseline is meant to validate server and worker separation on one machine before later networked deployment choices are made
- rendered pages are written to the shared `stratawiki-render` volume

## External Write Contract

For external integration clients, the preferred write contract is now `DomainProposalBatch`.

Use:

- `validate_domain_proposal_batch`
- `ingest_domain_proposal_batch`

Treat `ingest_fact_batch` as a legacy transition path for internal or source-driven flows.
It remains available, but it is not the recommended external integration contract.

The repository includes a sample recruiting Domain Pack artifact and a matching proposal batch:

- `examples/domain-packs/recruiting.v2026-04-18.json`
- `examples/integration/recruiting-domain-proposal-batch.json`

Example validation call:

```bash
/Users/yebin/venv/bin/python -m wiki_mcp.cli \
  --demo \
  --domain-pack-path examples/domain-packs/recruiting.v2026-04-18.json \
  call validate_domain_proposal_batch \
  --args-file examples/integration/recruiting-domain-proposal-batch.json
```

Example ingest call:

```bash
/Users/yebin/venv/bin/python -m wiki_mcp.cli \
  --demo \
  --domain-pack-path examples/domain-packs/recruiting.v2026-04-18.json \
  call ingest_domain_proposal_batch \
  --args-file examples/integration/recruiting-domain-proposal-batch.json
```

Ownership split:

- external producers own source collection, normalization, and proposal batch construction
- StrataWiki owns canonical validation, canonical key resolution, Fact writes, snapshots, and downstream publication

## Long-Lived Runtime Contract

For external clients that should not depend on one-shot subprocess calls, the repository now exposes a long-lived stdio runtime entrypoint:

```bash
/Users/yebin/venv/bin/python -m wiki_mcp.cli \
  --database-url postgresql://stratawiki:stratawiki@localhost:5432/stratawiki_dev \
  --render-root data-dev \
  serve
```

That process keeps the StrataWiki runtime open and accepts one JSON request per line on stdin.
Responses are emitted as one JSON object per line on stdout.

Supported runtime methods today:

- `health`
- `list_tools`
- `show_tool`
- `call_tool`
- `shutdown`

Example:

```bash
printf '%s\n%s\n' \
  '{"id":"req-1","method":"health"}' \
  '{"id":"req-2","method":"list_tools"}' \
  | /Users/yebin/venv/bin/python -m wiki_mcp.cli \
      --database-url postgresql://stratawiki:stratawiki@localhost:5432/stratawiki_dev \
      --render-root data-dev \
      serve
```

Ownership remains on the StrataWiki side:

- StrataWiki owns `DATABASE_URL`, canonical DB access, render output, snapshot pointers, and LLM credentials
- external clients own request construction and tool invocation sequencing
- external clients should not directly access StrataWiki tables or filesystem render artifacts as part of the runtime contract

## Worker Entry Point

The repository now includes a minimal worker-compatible background path for interpretation builds.

Queue an interpretation build request instead of running it inline:

```bash
/Users/yebin/venv/bin/python -m wiki_mcp.cli \
  --database-url postgresql://stratawiki:stratawiki@localhost:5432/stratawiki_dev \
  --render-root data-dev \
  call build_interpretation_snapshot \
  --args '{"domain":"recruiting","partition":{"family":"market_trends","segment":"backend-japan-midlevel"},"fact_ids":["fact:job:1"],"fact_snapshot":"fact_snap:seed","model_profile":"balanced_default","publish":true,"execution_mode":"background"}'
```

Then process queued jobs through the worker entrypoint:

```bash
/Users/yebin/venv/bin/python -m wiki_mcp.cli \
  --database-url postgresql://stratawiki:stratawiki@localhost:5432/stratawiki_dev \
  --render-root data-dev \
  worker --limit 10
```

Current baseline:

- `build_interpretation_snapshot` defaults to inline execution
- `execution_mode: "background"` queues one outbox-backed job
- `stratawiki worker` currently claims and processes queued interpretation build requests
- scheduler orchestration and broader job families remain follow-up work

## Interpretation Lifecycle Tooling

The runtime now exposes operator-facing lifecycle tools around shared interpretation proposals.

Current baseline:

- `list_interpretation_proposals` lists non-public candidates for one shared partition
- `validate_interpretation_proposal` promotes a candidate from `proposed` to `validated` when structural and evidence checks pass
- `publish_interpretation_partition` publishes the matching shared partition candidates from one lifecycle state, usually `validated`
- `get_interpretation_proposal_status` returns lifecycle plus review state for one candidate

These tools sit on top of the existing interpretation publication service, so the first implementation publishes partition candidates one proposal at a time instead of as one fully atomic multi-record operator transaction.

## Personal Query Provisioning

External clients should provision profile context through the StrataWiki runtime before calling `query_personal_knowledge`.

Write one profile context:

```bash
/Users/yebin/venv/bin/python -m wiki_mcp.cli \
  --database-url postgresql://stratawiki:stratawiki@localhost:5432/stratawiki_dev \
  call upsert_profile_context \
  --args '{"domain":"recruiting","tenant_id":"tenant-1","user_id":"user-1","profile_version":"profile:v1","goals":["find backend roles"],"preferences":{"location":"jp"},"attributes":{"level":"mid"}}'
```

Then call `query_personal_knowledge` with the same `profile_version`.

Current baseline:

- `upsert_profile_context` is the runtime-owned write path for Personal query prerequisites
- `query_personal_knowledge` still requires an exact `profile_version` match
- external clients should not insert profile context out of band

## Interpretation Publish Boundary

The interpretation publish path now treats canonical publish as one coordinated boundary instead of independent best-effort steps.

Current baseline:

- shared page replacement is prepared through a rollback-capable filesystem swap
- interpretation record updates, snapshot pointer movement, and outbox append are committed as one DB publish bundle
- if publish raises before the bundle completes, the prior rendered shared page is restored and the default canonical read target does not advance

## Snapshot and Cache Visibility

The runtime now exposes two operator-facing visibility paths:

- `get_snapshot_status` returns the current published snapshot registry for a domain, or the interpretation-layer pointer when called with a partition family
- `get_cache_status` compares one saved Personal output against the current fact/interpretation snapshot tuple and current profile version

Current baseline:

- `get_cache_status` is currently for saved Personal outputs, not broader retrieval or graph caches
- `cache_state` can currently be `fresh`, `stale`, `invalid`, or `missing`
- `profile_version` drift is treated as `invalid`

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
