from __future__ import annotations

import json
from urllib import error
from unittest.mock import patch

import pytest

from wiki_mcp.adapters.llm import (
    LLMGatewayError,
    OllamaChatGateway,
    build_llm_gateway_router_from_env,
    resolve_ollama_model_for_profile,
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
        "provider": "ollama",
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
        "provider": "ollama",
    }


def test_ollama_gateway_structured_generation_parses_schema_response() -> None:
    seen_request: dict[str, object] = {}

    def fake_urlopen(req, timeout):  # type: ignore[no-untyped-def]
        seen_request["url"] = req.full_url
        seen_request["headers"] = dict(req.header_items())
        seen_request["body"] = json.loads(req.data.decode("utf-8"))
        seen_request["timeout"] = timeout
        return _FakeHTTPResponse(
            {
                "model": "gemma3:1b",
                "message": {
                    "role": "assistant",
                    "content": "{\"summary\":\"Demand is rising\"}",
                },
            }
        )

    gateway = OllamaChatGateway(
        model_resolver=lambda profile: {
            "balanced_default": "gemma3:270m",
            "deep_synthesis": "gemma3:1b",
        }[profile]
    )

    with patch("urllib.request.urlopen", fake_urlopen):
        response = gateway.generate_structured(_structured_request())

    assert response["output"] == {"summary": "Demand is rising"}
    assert response["metadata"]["provider"] == "ollama"
    assert response["metadata"]["model"] == "gemma3:1b"
    assert seen_request["url"] == "http://localhost:11434/api/chat"
    assert seen_request["timeout"] == 60.0
    assert seen_request["body"]["model"] == "gemma3:1b"
    assert seen_request["body"]["format"]["type"] == "object"
    assert seen_request["body"]["stream"] is False
    assert seen_request["body"]["think"] is False


def test_ollama_gateway_text_generation_extracts_message_content() -> None:
    gateway = OllamaChatGateway(model_resolver=lambda profile: "gemma3:270m")

    with patch(
        "urllib.request.urlopen",
        lambda req, timeout: _FakeHTTPResponse(
            {
                "model": "gemma3:270m",
                "message": {
                    "role": "assistant",
                    "content": "A concise answer.",
                },
            }
        ),
    ):
        response = gateway.generate_text(_text_request())

    assert response["content"] == "A concise answer."
    assert response["metadata"]["model"] == "gemma3:270m"


def test_ollama_gateway_structured_generation_accepts_fenced_json() -> None:
    gateway = OllamaChatGateway(model_resolver=lambda profile: "gemma3:1b")

    with patch(
        "urllib.request.urlopen",
        lambda req, timeout: _FakeHTTPResponse(
            {
                "model": "gemma3:1b",
                "message": {
                    "role": "assistant",
                    "content": "```json\n{\"summary\":\"Demand is rising\"}\n```",
                },
            }
        ),
    ):
        response = gateway.generate_structured(_structured_request())

    assert response["output"] == {"summary": "Demand is rising"}


def test_ollama_gateway_raises_structured_error_for_http_failure() -> None:
    gateway = OllamaChatGateway(model_resolver=lambda profile: "gemma3:270m")

    def fake_urlopen(req, timeout):  # type: ignore[no-untyped-def]
        raise error.HTTPError(
            url=req.full_url,
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=_FakeHTTPResponse({"error": "model 'gemma3:270m' not found"}),
        )

    with patch("urllib.request.urlopen", fake_urlopen):
        with pytest.raises(LLMGatewayError) as exc_info:
            gateway.generate_text(_text_request())

    assert exc_info.value.as_dict()["code"] == "LLM_PROVIDER_HTTP_ERROR"
    assert exc_info.value.as_dict()["details"]["status_code"] == 404


def test_resolve_ollama_model_for_profile_prefers_env_override() -> None:
    model = resolve_ollama_model_for_profile(
        "balanced_default",
        environ={"WIKI_MCP_OLLAMA_MODEL_BALANCED_DEFAULT": "llama3.2:1b"},
    )

    assert model == "llama3.2:1b"


def test_build_router_from_env_registers_ollama_when_enabled() -> None:
    router = build_llm_gateway_router_from_env(
        environ={
            "WIKI_MCP_ENABLE_OLLAMA": "1",
            "OLLAMA_BASE_URL": "http://localhost:11434/api",
            "WIKI_MCP_OLLAMA_MODEL_BALANCED_DEFAULT": "gemma3:270m",
            "WIKI_MCP_OLLAMA_MODEL_DEEP_SYNTHESIS": "gemma3:1b",
            "WIKI_MCP_DEFAULT_PROVIDER": "ollama",
        }
    )

    provider_gateway = router.gateways_by_provider["ollama"]
    assert isinstance(provider_gateway, OllamaChatGateway)
    assert router.gateways_by_model_profile["balanced_default"] is provider_gateway
    assert router.gateways_by_model_profile["deep_synthesis"] is provider_gateway
