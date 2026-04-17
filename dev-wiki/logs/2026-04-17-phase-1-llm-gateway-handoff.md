# Next Session Handoff

## Current Branch

- `feat/llm-gateway`

This branch was created from:

- `feat/query-personal-migration`

## Current Position

Legacy migration is intentionally considered complete enough.

Do not resume broad legacy salvage work by default.

From this point onward, work should follow the GitHub backlog in issue order
unless there is a strong reason to deviate.

## What Is Already In Place

### Foundation

- thin runtime shell in `bootstrap.py`, `server.py`, `cli.py`
- Postgres repository base and repository protocols
- WorkNet source adapter
- recruiting domain ingestion plugin
- shared schema primitives for scope, snapshot, source, dependency, and core envelopes

### Retrieval and personal-query skeleton

- repo-backed curated retrieval skeleton
- personal query bundle orchestration skeleton
- interpretation family proposal registry skeleton

### Core ingestion slice

- `DefaultCoreIngestionService`
- domain ingestion protocol
- ingestion result and batch schemas
- ingestion-focused tests

## Verified Status

The following currently pass locally:

- `python -m compileall src tests`
- `PYTHONPATH=src python -m pytest -q`

Current result at handoff time:

- `6 passed`

## Backlog Status Summary

### Substantially progressed

- `#1 Define core schemas and shared metadata`
- `#3 Build canonical Fact storage and snapshot publish flow`
- `#4 Add recruiting fact normalization for initial entities`
- `#7 Implement curated retrieval path`
- `#10 Wire local server for MVP demo`
- `#18 Stabilize MVP with smoke tests`

### `#3` status

`#3` was treated as complete enough and has already been closed.

### Partially started

- `#8 Implement personal query orchestration`

### Not yet properly started

- `#2 Implement provider-agnostic LLM gateway interface`
- `#5 Implement interpretation proposal and validation flow`
- `#6 Publish one interpretation family end-to-end`
- `#9 Expose MVP MCP tools`

## Immediate Next Target

Start with:

- `#2 Implement provider-agnostic LLM gateway interface`

Why this is next:

1. backlog order says so
2. retrieval and personal-query skeletons already exist
3. interpretation lifecycle work depends on a clean LLM boundary

## Recommended Scope For The Next Session

Implement the minimum provider-agnostic LLM gateway contract only.

Good targets:

- add a small interface under `src/wiki_mcp/adapters/llm/`
- define text and structured generation entrypoints
- keep provider selection abstract
- return model/prompt metadata with responses
- make the gateway easy to mock in tests

Avoid in the next step:

- building the full interpretation lifecycle at the same time
- wiring MCP tools before the LLM contract exists
- reintroducing page-read-centric behavior from legacy code

## Guardrails

- `docs/` remains the source of truth
- do not widen the migration scope again unless blocked
- preserve the separation between retrieval, orchestration, and LLM gateway
- preserve `Fact` integrity and current snapshot semantics

## Suggested Prompt For The Next Session

```text
We are on branch `feat/llm-gateway` in `/Users/yebin/workspace/projects/stratawiki`.

Legacy migration is complete enough; do not resume broad salvage work unless blocked.

Please work backlog-first, starting with GitHub issue `#2 Implement provider-agnostic LLM gateway interface`.

Relevant source-of-truth docs:
- `docs/implementation-roadmap.md`
- `docs/llm-orchestration-and-retrieval-spec.md`
- `docs/interpretation-schema-and-lifecycle-spec.md`
- `docs/mcp-tool-contract-spec.md`

Current code status:
- foundation, curated retrieval skeleton, and core ingestion slice are already migrated
- `PYTHONPATH=src python -m pytest -q` currently passes (`6 passed`)

Your task:
1. inspect the current `src/wiki_mcp/adapters/llm/` area
2. implement the minimum provider-agnostic LLM gateway contract
3. keep it mock-friendly and aligned with the current docs
4. run relevant tests or add minimal tests if needed
5. summarize what remains for issue `#2`
```
