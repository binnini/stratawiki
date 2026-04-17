from __future__ import annotations

from wiki_mcp.adapters.llm import (
    DeterministicLLMGateway,
    LLMGatewayError,
    LLMGatewayRouter,
)


def _text_request(
    *,
    model_profile: str = "balanced_default",
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, object]:
    request: dict[str, object] = {
        "messages": [
            {"role": "system", "content": "Summarize the context."},
            {"role": "user", "content": "What matters most?"},
        ],
        "model_profile": model_profile,
        "prompt_id": "personal.query.answer",
        "prompt_version": "personal.query.answer.v1",
    }
    if provider is not None:
        request["provider"] = provider
    if model is not None:
        request["model"] = model
    return request


def _structured_request(
    *,
    model_profile: str = "deep_synthesis",
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, object]:
    request = _text_request(
        model_profile=model_profile,
        provider=provider,
        model=model,
    )
    request["schema_name"] = "interpretation.market_trend"
    request["schema_version"] = "interpretation.market_trend.v1"
    request["output_schema"] = {
        "type": "object",
        "required": ["summary"],
    }
    return request


def test_deterministic_gateway_structured_generation_surfaces_metadata() -> None:
    gateway = DeterministicLLMGateway(
        provider="mock-provider",
        model="mock-model-v1",
        default_structured_output={"summary": "Structured output"},
    )

    response = gateway.generate_structured(_structured_request())

    assert response["output"] == {"summary": "Structured output"}
    assert response["metadata"] == {
        "provider": "mock-provider",
        "model": "mock-model-v1",
        "model_profile": "deep_synthesis",
        "prompt_id": "personal.query.answer",
        "prompt_version": "personal.query.answer.v1",
        "schema_name": "interpretation.market_trend",
        "schema_version": "interpretation.market_trend.v1",
    }


def test_router_prefers_provider_mapping_before_model_profile_mapping() -> None:
    default_gateway = DeterministicLLMGateway(default_text="default")
    provider_gateway = DeterministicLLMGateway(
        provider="openai",
        model="gpt-test",
        default_text="provider-route",
    )
    profile_gateway = DeterministicLLMGateway(default_text="profile-route")
    router = LLMGatewayRouter(
        default_gateway=default_gateway,
        gateways_by_provider={"openai": provider_gateway},
        gateways_by_model_profile={"deep_synthesis": profile_gateway},
    )

    provider_response = router.generate_text(
        _text_request(provider="openai", model_profile="deep_synthesis")
    )
    profile_response = router.generate_text(_text_request(model_profile="deep_synthesis"))
    default_response = router.generate_text(_text_request(model_profile="balanced_default"))

    assert provider_response["content"] == "provider-route"
    assert provider_response["metadata"]["provider"] == "openai"
    assert profile_response["content"] == "profile-route"
    assert default_response["content"] == "default"


def test_deterministic_gateway_accepts_callable_factories_for_mocking() -> None:
    gateway = DeterministicLLMGateway(
        text_factory=lambda request: str(request["messages"][-1]["content"]).upper(),
        structured_factory=lambda request: {
            "summary": request["messages"][-1]["content"],
            "schema": request["schema_name"],
        },
    )

    text_response = gateway.generate_text(_text_request())
    structured_response = gateway.generate_structured(_structured_request())

    assert text_response["content"] == "WHAT MATTERS MOST?"
    assert structured_response["output"] == {
        "summary": "What matters most?",
        "schema": "interpretation.market_trend",
    }


def test_router_raises_structured_error_when_no_gateway_is_configured() -> None:
    router = LLMGatewayRouter()

    try:
        router.generate_text(_text_request(provider="missing"))
    except LLMGatewayError as exc:
        assert exc.as_dict() == {
            "code": "LLM_GATEWAY_NOT_CONFIGURED",
            "message": "No LLM gateway is configured for the requested provider or model profile.",
            "retryable": False,
            "details": {
                "provider": "missing",
                "model_profile": "balanced_default",
            },
        }
    else:
        raise AssertionError("Expected router to raise LLMGatewayError")
