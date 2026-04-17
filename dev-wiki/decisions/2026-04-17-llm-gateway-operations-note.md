# LLM Gateway Operations Note

## Purpose

This note captures the current operational baseline for the provider-agnostic
LLM gateway introduced for GitHub issue `#2`.

`docs/` remains the architecture source of truth.
This file is only a practical working note for local operation and verification.

## Current Status

The gateway now supports:

- deterministic mock mode
- OpenAI via the Responses API
- Ollama via the local `/api/chat` endpoint

The current local verification baseline is:

- `python -m compileall src tests`
- `PYTHONPATH=src python -m pytest -q`

Current result when this note was written:

- `21 passed, 2 skipped`

## Provider Routing

Runtime routing is built from:

- `src/wiki_mcp/adapters/llm/config.py`

Key environment variables:

- `WIKI_MCP_DEFAULT_PROVIDER`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OLLAMA_BASE_URL`
- `WIKI_MCP_ENABLE_OLLAMA`
- `WIKI_MCP_OPENAI_MODEL_BALANCED_DEFAULT`
- `WIKI_MCP_OPENAI_MODEL_DEEP_SYNTHESIS`
- `WIKI_MCP_OLLAMA_MODEL_BALANCED_DEFAULT`
- `WIKI_MCP_OLLAMA_MODEL_DEEP_SYNTHESIS`

## Recommended Local Default

For local provider-contract verification, prefer Ollama first.

Suggested local values:

- `WIKI_MCP_DEFAULT_PROVIDER=ollama`
- `WIKI_MCP_ENABLE_OLLAMA=1`
- `WIKI_MCP_OLLAMA_MODEL_BALANCED_DEFAULT=gemma4:e2b`

`gemma4:e2b` has already been exercised successfully against the integration
smoke path in this branch.

## Ollama Notes

Current adapter behavior:

- uses `http://localhost:11434/api` by default
- sends `stream=false`
- sends `think=false` to avoid reasoning-trace-first responses
- normalizes fenced JSON before structured parsing

This matters because some thinking-capable local models may otherwise emit:

- reasoning in `message.thinking`
- empty or truncated `message.content`
- JSON wrapped in markdown fences

## Smoke Commands

### Full local test suite

```bash
python -m compileall src tests
PYTHONPATH=src python -m pytest -q
```

### Ollama integration smoke

```bash
OLLAMA_BASE_URL=http://127.0.0.1:11434/api \
WIKI_MCP_ENABLE_OLLAMA=1 \
WIKI_MCP_DEFAULT_PROVIDER=ollama \
WIKI_MCP_OLLAMA_MODEL_BALANCED_DEFAULT=gemma4:e2b \
PYTHONPATH=src python -m pytest -q tests/test_llm_gateway_ollama_integration.py
```

### OpenAI integration smoke

```bash
OPENAI_API_KEY=... \
OPENAI_BASE_URL=https://api.openai.com/v1 \
PYTHONPATH=src python -m pytest -q tests/test_llm_gateway_openai_integration.py
```

## Practical Rule

When testing gateway behavior:

1. verify unit tests first
2. verify Ollama local smoke next if available
3. use OpenAI smoke only when API-backed verification is needed

## Next Work

After `#2`, the recommended next backlog item is:

- `#5 Implement interpretation proposal and validation flow`
