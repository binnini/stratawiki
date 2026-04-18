# Closed Issues #1-#10 Audit and Manual Test Guide

## Purpose

This note checks whether closed issues `#1` through `#10` are implemented to the stated Week 1 MVP bar and records a manual validation path that can be run locally.

This is a working audit note.
`docs/` remains the source of truth for contracts and architecture.

## Overall Result

All closed issues `#1` through `#10` appear implemented to their stated MVP "done when" criteria.

The strongest evidence is:

- matching code paths exist for every issue
- matching automated tests exist for every issue area
- the current local demo flow exercises the full `Fact -> Interpretation -> Personal` happy path

Current known limits are follow-up scope, not blockers for closing `#1` through `#10`.

- `#8` follow-up: persisted personal anchors are saved, but retrieval reuse is not yet indexed as a first-class read model. Follow-up issue: `#29`
- `#9` MVP limit: `build_interpretation_snapshot` still requires explicit `fact_ids` on the happy path
- `#10` follow-up: non-demo Postgres bootstrap still needs local provisioning guidance. Follow-up issue: `#30`

## Issue Audit

### #1 Define core schemas and shared metadata

Status: implemented

Evidence:

- shared schema exports and lifecycle constants are centralized in `src/wiki_mcp/schemas/__init__.py`
- lifecycle constants include the documented interpretation statuses
- smoke tests exist for schema construction and lifecycle ordering

Relevant files:

- `src/wiki_mcp/schemas/__init__.py`
- `tests/test_schema_smoke.py`

Conclusion:

The minimum shared schema layer is in place and importable.

### #2 Implement provider-agnostic LLM gateway interface

Status: implemented

Evidence:

- provider-agnostic request and response envelopes are defined in `src/wiki_mcp/adapters/llm/gateway.py`
- `LLMGatewayRouter` resolves by provider or model profile and raises structured errors if nothing is configured
- deterministic, OpenAI, and Ollama tests all exist

Relevant files:

- `src/wiki_mcp/adapters/llm/gateway.py`
- `tests/test_llm_gateway.py`
- `tests/test_llm_gateway_openai.py`
- `tests/test_llm_gateway_ollama.py`

Conclusion:

The abstraction is real, mockable, and already used by interpretation and personal-query flows.

### #3 Build canonical Fact storage and snapshot publish flow

Status: implemented

Evidence:

- `DefaultCoreIngestionService` normalizes, validates, writes facts, publishes a fact snapshot, and appends an outbox event
- repository tests cover fact retrieval and validation

Relevant files:

- `src/wiki_mcp/services/core_ingestion.py`
- `tests/test_core_ingestion_service.py`
- `tests/test_postgres_fact_repository.py`

Conclusion:

The canonical Fact write path exists and publishes inspectable snapshot ids.

### #4 Add recruiting fact normalization for initial entities

Status: implemented

Evidence:

- recruiting plugin extracts `job_posting`, `company`, `role`, `location`, and `skill`
- relation generation persists `posted_by`, `has_role`, `requires_skill`, and `located_in`
- tests verify decomposition, dedupe, and relation scope inheritance

Relevant files:

- `src/wiki_mcp/domains/recruiting/ingestion.py`
- `tests/test_recruiting_ingestion.py`

Conclusion:

The initial recruiting normalization slice is stronger than the bare minimum asked by the issue.

### #5 Implement interpretation proposal and validation flow

Status: implemented

Evidence:

- proposals are created through the interpretation family registry and persisted as `proposed`
- validation checks state transition, required fields, provenance, confidence, and evidence fact existence
- invalid evidence paths return structured validation errors

Relevant files:

- `src/wiki_mcp/services/interpretation_proposals.py`
- `tests/test_interpretation_proposal_service.py`

Conclusion:

The proposal and validation lifecycle exists and rejects unsupported proposals in a structured way.

### #6 Publish one interpretation family end-to-end

Status: implemented

Evidence:

- publication promotes validated proposals to `published`
- prior `published` and `stale` records are superseded
- interpretation snapshots are published and queryable
- tests cover `market_trend` end-to-end publication behavior

Relevant files:

- `src/wiki_mcp/services/interpretation_publication.py`
- `src/wiki_mcp/services/interpretation_queries.py`
- `tests/test_interpretation_publication_service.py`
- `tests/test_market_trend_interpretation_builder.py`

Conclusion:

One interpretation family is fully wired through proposal, validation, publish, and retrieval.

### #7 Implement curated retrieval path

Status: implemented

Evidence:

- retrieval order is explicitly `Personal -> Interpretation -> Fact`
- personal anchors expand interpretation and fact context before search fallback
- retrieval metadata and merged snapshot refs are returned

Relevant files:

- `src/wiki_mcp/services/retrieval.py`
- `tests/test_curated_retrieval_service.py`

Conclusion:

The default curated retrieval path exists and matches the docs-defined layering.

### #8 Implement personal query orchestration

Status: implemented

Evidence:

- `PersonalKnowledgeQueryService` builds the retrieval bundle, assembles the prompt, invokes the LLM gateway, binds provenance, and optionally persists the answer
- persisted personal answers include snapshot-bound provenance and explicit anchors
- tests cover both `save=false` and `save=true`

Relevant files:

- `src/wiki_mcp/services/personal_query.py`
- `tests/test_personal_query_service.py`

Conclusion:

The first end-to-end personal answer path is implemented to MVP scope.

Residual MVP limit:

- anchor persistence is present, but downstream indexed anchor reuse is still follow-up work in `#29`

### #9 Expose MVP MCP tools

Status: implemented

Evidence:

- server exports six MVP tools and dispatches them through one runtime surface
- bootstrap wires the concrete repositories and services behind those tools
- tests cover tool listing and happy-path tool calls

Relevant files:

- `src/wiki_mcp/server.py`
- `src/wiki_mcp/bootstrap.py`
- `tests/test_server_tools.py`

Conclusion:

The MVP tool surface is implemented and usable through the local CLI wrapper.

Residual MVP limit:

- `build_interpretation_snapshot` still depends on explicit `fact_ids`

### #10 Wire local server for MVP demo

Status: implemented

Evidence:

- CLI supports `--demo`, `--seed-path`, `list-tools`, `call`, and `demo-mvp`
- in-memory demo runtime exists with deterministic LLM behavior
- sample seed exists
- tests cover list-tools and full demo execution

Relevant files:

- `src/wiki_mcp/cli.py`
- `src/wiki_mcp/demo.py`
- `examples/demo/mvp-seed.json`
- `tests/test_demo_cli.py`

Conclusion:

The local Week 1 MVP happy path is runnable without Postgres or external LLM credentials.

Residual MVP limit:

- production-like non-demo local bootstrap still depends on follow-up provisioning work in `#30`

## Recommended Manual Validation

### 1. Install the package into the shared venv

```bash
/Users/yebin/venv/bin/python -m pip install -e .
```

### 2. Run the current automated baseline

```bash
/Users/yebin/venv/bin/python -m pytest -q
```

Expected result at the time of this audit:

- `48 passed, 2 skipped`

If that number changes later, treat the command as the source of truth and compare the failures against the issue area you are checking.

### 3. Verify the exported MVP tool surface

```bash
/Users/yebin/venv/bin/python -m wiki_mcp.cli --demo list-tools
```

Expected tool names:

- `ingest_fact_batch`
- `get_fact_record`
- `build_interpretation_snapshot`
- `get_interpretation_record`
- `query_personal_knowledge`
- `get_snapshot_status`

This is the fastest manual check for `#9` and `#10`.

### 4. Run the full Week 1 MVP flow

```bash
/Users/yebin/venv/bin/python -m wiki_mcp.cli \
  --demo \
  --seed-path examples/demo/mvp-seed.json \
  --render-root /tmp/stratawiki-manual-check \
  demo-mvp
```

Expected behavior:

- `ingest_fact_batch.status == "ok"`
- `build_interpretation_snapshot.status == "ok"`
- `query_personal_knowledge.status == "ok"`
- `get_snapshot_status.status == "ok"`

This one command gives a practical manual pass across `#3`, `#4`, `#5`, `#6`, `#7`, `#8`, `#9`, and `#10`.

### 5. Inspect the persisted Personal output

After the demo command, check the generated answer file:

```bash
ls /tmp/stratawiki-manual-check/wiki/users/user-1/answers
```

Open the generated markdown and verify:

- the file exists
- it contains the answer markdown
- it contains `stratawiki:personal_query_answer`
- it includes snapshot-bound provenance
- it includes explicit anchors to interpretation and fact records

This is the most direct manual check for `#8`.

### 6. Optional targeted tool calls

If you want to test the tools one by one instead of using `demo-mvp`, use the CLI `call` command.

List one tool schema:

```bash
/Users/yebin/venv/bin/python -m wiki_mcp.cli --demo show-tool query_personal_knowledge
```

Call the full happy path manually:

1. `ingest_fact_batch`
2. `build_interpretation_snapshot`
3. `query_personal_knowledge`
4. `get_snapshot_status`

Use `examples/demo/mvp-seed.json` as the argument source when building your JSON payloads.

### 7. What to treat as failure

Treat the implementation as suspect if any of the following happens:

- schema smoke tests fail
- gateway tests fail or provider metadata disappears
- fact ingestion no longer emits a fact snapshot id
- interpretation publication does not produce an interpretation snapshot id
- curated retrieval no longer returns `retrieval_metadata` or merged snapshot refs
- personal query output no longer includes provenance or used-record ids
- demo mode requires Postgres or live LLM credentials
- the saved personal answer file is not written

## Audit Verdict

`#1` through `#10` are in acceptable shape for the stated Week 1 MVP scope.

The implementation is not feature-complete beyond MVP, but the currently closed issues do not look incorrectly closed.
