# Next Session Handoff

## Current Branch

- `feat/llm-gateway`

## Current Position

Issue `#2 Implement provider-agnostic LLM gateway interface` is now effectively complete.

Legacy migration remains "complete enough" for current work.
Do not reopen broad salvage work unless a very specific old reference is required.

## What Was Added For `#2`

### Provider-agnostic gateway contract

- `LLMGateway` protocol
- `LLMGatewayRouter`
- shared request/response envelopes for:
  - text generation
  - structured generation
- surfaced generation metadata:
  - `provider`
  - `model`
  - `model_profile`
  - `prompt_id`
  - `prompt_version`
  - schema metadata for structured generation

### Mock and real provider paths

- deterministic mock gateway for unit tests
- OpenAI Responses API adapter
- Ollama local adapter

### Minimal runtime config

- env-based provider routing
- env-based `model_profile -> provider/model` resolution
- support for default-provider selection

## Important Provider Notes

### OpenAI

- OpenAI support is wired through the Responses API adapter
- integration smoke remains opt-in via `OPENAI_API_KEY`

### Ollama

- Ollama support is wired through `/api/chat`
- structured generation is supported
- the adapter disables `think` by default for more reliable machine-readable output
- fenced JSON responses are normalized before parsing

Verified locally with:

- model: `gemma4:e2b`
- path: `tests/test_llm_gateway_ollama_integration.py`

## Relevant Commits

- `bc2bf73` Implement provider-agnostic LLM gateway for issue #2
- `1021b5a` Add Ollama gateway support for issue #2

## Verified Status

The following currently pass locally:

- `python -m compileall src tests`
- `PYTHONPATH=src python -m pytest -q`

Current result at handoff time:

- `21 passed, 2 skipped`

The two skipped tests are opt-in integration smokes that require provider availability:

- OpenAI smoke requires `OPENAI_API_KEY`
- Ollama smoke skips if the local server or model is unavailable

## Current Working Tree Note

This handoff file is being updated as part of the current wrap-up.

There was also an older `dev-wiki/logs/2026-04-17-phase-1-llm-gateway-handoff.md` entry that had already disappeared from the working tree before this update. Treat it as superseded by this file.

## Recommended Next Backlog Target

- `#5 Implement interpretation proposal and validation flow`

Why this is the best next target:

1. `#2` created the clean LLM boundary needed downstream
2. retrieval and personal-query skeletons already exist
3. interpretation lifecycle is now the main missing contract before end-to-end shared generation work

## Recommended Scope For The Next Session

Keep the next step tightly scoped to proposal and validation flow only.

Good targets:

- proposal-shaped interpretation persistence
- envelope validation
- evidence existence checks
- lifecycle status transitions such as `proposed -> validated`
- structured errors for invalid proposals

Avoid in the next step:

- publishing a full family and lifecycle tool surface at the same time
- wiring MCP tools before proposal validation exists
- widening the scope back into migration cleanup

## Guardrails

- `docs/` remains the source of truth
- preserve separation between retrieval, orchestration, and LLM gateway
- preserve `Fact` integrity and current snapshot semantics
- avoid reintroducing page-read-centric legacy behavior
