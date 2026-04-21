from __future__ import annotations

import os
import pytest

from wiki_mcp.bootstrap import bootstrap_application


class _FakeConnection:
    closed = False

    def close(self) -> None:
        self.closed = True


def test_non_demo_bootstrap_requires_configured_llm_provider(tmp_path) -> None:
    previous_env = {
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
        "WIKI_MCP_ENABLE_OLLAMA": os.environ.get("WIKI_MCP_ENABLE_OLLAMA"),
        "OLLAMA_BASE_URL": os.environ.get("OLLAMA_BASE_URL"),
        "WIKI_MCP_DEFAULT_PROVIDER": os.environ.get("WIKI_MCP_DEFAULT_PROVIDER"),
    }
    try:
        for key in previous_env:
            os.environ.pop(key, None)
        with pytest.raises(RuntimeError, match="No non-demo LLM provider is configured"):
            bootstrap_application(
                connection=_FakeConnection(),
                render_root=tmp_path,
            )
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
