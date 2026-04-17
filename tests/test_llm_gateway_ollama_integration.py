from __future__ import annotations

import os

import pytest

from wiki_mcp.adapters.llm import (
    LLMGatewayError,
    OllamaChatGateway,
    resolve_ollama_model_for_profile,
)


def test_ollama_gateway_integration_structured_generation_smoke() -> None:
    gateway = OllamaChatGateway(
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/api"),
        api_key=os.environ.get("OLLAMA_API_KEY"),
        model_resolver=lambda profile: resolve_ollama_model_for_profile(profile),
    )

    try:
        response = gateway.generate_structured(
            {
                "messages": [
                    {
                        "role": "system",
                        "content": "Return only JSON matching the schema.",
                    },
                    {
                        "role": "user",
                        "content": "Summarize the signal as a short sentence.",
                    },
                ],
                "model_profile": "balanced_default",
                "prompt_id": "integration.smoke.ollama.structured",
                "prompt_version": "integration.smoke.ollama.structured.v1",
                "provider": "ollama",
                "schema_name": "integration_smoke_summary",
                "schema_version": "integration.smoke.summary.v1",
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                    },
                    "required": ["summary"],
                    "additionalProperties": False,
                },
                "max_output_tokens": 120,
            }
        )
    except LLMGatewayError as exc:
        if exc.code == "LLM_PROVIDER_UNREACHABLE":
            pytest.skip("Ollama server is not reachable. Start Ollama locally to run this smoke test.")
        if exc.code == "LLM_PROVIDER_HTTP_ERROR":
            message = exc.message.lower()
            if "not found" in message:
                pytest.skip(
                    "Configured Ollama model is not available locally. Pull the configured model first."
                )
        raise

    assert isinstance(response["output"]["summary"], str)
    assert response["output"]["summary"].strip()
    assert response["metadata"]["provider"] == "ollama"
