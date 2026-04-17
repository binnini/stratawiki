from __future__ import annotations

import json
from urllib import error
from unittest.mock import patch

import pytest

from wiki_mcp.adapters.llm import (
    LLMGatewayError,
    OpenAIResponsesGateway,
    build_llm_gateway_router_from_env,
    resolve_model_for_profile,
)


class _FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def close(self) -> None:
        return None

    def __enter__(self) -> _FakeHTTPResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _structured_request() -> dict[str, object]:
    return {
        "messages": [
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": "Summarize the market signal."},
        ],
        "model_profile": "deep_synthesis",
        "prompt_id": "interp.market_trend",
        "prompt_version": "interp.market_trend.v1",
        "provider": "openai",
        "schema_name": "interpretation_market_trend",
        "schema_version": "interpretation.market_trend.v1",
        "output_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
            },
            "required": ["summary"],
            "additionalProperties": False,
        },
    }


def _text_request() -> dict[str, object]:
    return {
        "messages": [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "What changed?"},
        ],
        "model_profile": "balanced_default",
        "prompt_id": "personal.query.answer",
        "prompt_version": "personal.query.answer.v1",
        "provider": "openai",
    }


def test_openai_gateway_structured_generation_parses_json_schema_response() -> None:
    seen_request: dict[str, object] = {}

    def fake_urlopen(req, timeout):  # type: ignore[no-untyped-def]
        seen_request["url"] = req.full_url
        seen_request["headers"] = dict(req.header_items())
        seen_request["body"] = json.loads(req.data.decode("utf-8"))
        seen_request["timeout"] = timeout
        return _FakeHTTPResponse(
            {
                "model": "gpt-4.1-2025-04-14",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "{\"summary\":\"Demand is rising\"}",
                            }
                        ],
                    }
                ],
            }
        )

    gateway = OpenAIResponsesGateway(
        api_key="test-key",
        model_resolver=lambda profile: {
            "balanced_default": "gpt-4.1-mini",
            "deep_synthesis": "gpt-4.1",
        }[profile],
    )

    with patch("urllib.request.urlopen", fake_urlopen):
        response = gateway.generate_structured(_structured_request())

    assert response["output"] == {"summary": "Demand is rising"}
    assert response["metadata"]["provider"] == "openai"
    assert response["metadata"]["model"] == "gpt-4.1-2025-04-14"
    assert seen_request["url"] == "https://api.openai.com/v1/responses"
    assert seen_request["timeout"] == 30.0
    assert seen_request["body"]["model"] == "gpt-4.1"
    assert seen_request["body"]["text"]["format"]["type"] == "json_schema"
    assert seen_request["body"]["text"]["format"]["name"] == "interpretation_market_trend"
    assert seen_request["body"]["text"]["format"]["strict"] is True


def test_openai_gateway_text_generation_extracts_output_text() -> None:
    gateway = OpenAIResponsesGateway(
        api_key="test-key",
        model_resolver=lambda profile: "gpt-4.1-mini",
    )

    with patch(
        "urllib.request.urlopen",
        lambda req, timeout: _FakeHTTPResponse(
            {
                "model": "gpt-4.1-mini-2025-04-14",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": "A concise answer."}
                        ],
                    }
                ],
            }
        ),
    ):
        response = gateway.generate_text(_text_request())

    assert response["content"] == "A concise answer."
    assert response["metadata"]["model"] == "gpt-4.1-mini-2025-04-14"


def test_openai_gateway_raises_structured_error_for_http_failure() -> None:
    gateway = OpenAIResponsesGateway(
        api_key="test-key",
        model_resolver=lambda profile: "gpt-4.1-mini",
    )

    def fake_urlopen(req, timeout):  # type: ignore[no-untyped-def]
        raise error.HTTPError(
            url=req.full_url,
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=_FakeHTTPResponse(
                {
                    "error": {
                        "message": "Incorrect API key provided.",
                        "type": "invalid_request_error",
                    }
                }
            ),
        )

    with patch("urllib.request.urlopen", fake_urlopen):
        with pytest.raises(LLMGatewayError) as exc_info:
            gateway.generate_text(_text_request())

    assert exc_info.value.as_dict()["code"] == "LLM_PROVIDER_HTTP_ERROR"
    assert exc_info.value.as_dict()["details"]["status_code"] == 401


def test_resolve_model_for_profile_prefers_env_override() -> None:
    model = resolve_model_for_profile(
        "balanced_default",
        environ={"WIKI_MCP_OPENAI_MODEL_BALANCED_DEFAULT": "gpt-4.1-nano"},
    )

    assert model == "gpt-4.1-nano"


def test_build_router_from_env_registers_openai_when_api_key_exists() -> None:
    router = build_llm_gateway_router_from_env(
        environ={
            "OPENAI_API_KEY": "test-key",
            "WIKI_MCP_OPENAI_MODEL_BALANCED_DEFAULT": "gpt-4.1-mini",
            "WIKI_MCP_OPENAI_MODEL_DEEP_SYNTHESIS": "gpt-4.1",
        }
    )

    provider_gateway = router.gateways_by_provider["openai"]
    assert isinstance(provider_gateway, OpenAIResponsesGateway)
    assert router.gateways_by_model_profile["balanced_default"] is provider_gateway
    assert router.gateways_by_model_profile["deep_synthesis"] is provider_gateway
