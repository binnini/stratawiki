from __future__ import annotations

import os

import pytest

from wiki_mcp.adapters.llm import OpenAIResponsesGateway, resolve_model_for_profile


pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY is not configured for integration smoke tests.",
)


def test_openai_gateway_integration_structured_generation_smoke() -> None:
    gateway = OpenAIResponsesGateway(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        model_resolver=lambda profile: resolve_model_for_profile(profile),
    )

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
            "prompt_id": "integration.smoke.structured",
            "prompt_version": "integration.smoke.structured.v1",
            "provider": "openai",
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

    assert isinstance(response["output"]["summary"], str)
    assert response["output"]["summary"].strip()
    assert response["metadata"]["provider"] == "openai"
