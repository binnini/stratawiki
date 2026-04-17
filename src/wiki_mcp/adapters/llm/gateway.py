from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, NotRequired, Protocol, TypedDict


class LLMMessage(TypedDict):
    """One message passed into a provider-agnostic LLM gateway call."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str


class LLMInvocationMetadata(TypedDict):
    """Stable generation metadata surfaced alongside gateway outputs."""

    provider: str
    model: str
    model_profile: str
    prompt_id: str
    prompt_version: str
    schema_name: NotRequired[str]
    schema_version: NotRequired[str]


class LLMTextGenerationRequest(TypedDict):
    """Provider-agnostic request envelope for text generation."""

    messages: list[LLMMessage]
    model_profile: str
    prompt_id: str
    prompt_version: str
    provider: NotRequired[str]
    model: NotRequired[str]
    temperature: NotRequired[float]
    max_output_tokens: NotRequired[int]


class LLMStructuredGenerationRequest(LLMTextGenerationRequest):
    """Provider-agnostic request envelope for structured generation."""

    schema_name: str
    schema_version: str
    output_schema: NotRequired[dict[str, Any]]


class LLMTextGenerationResponse(TypedDict):
    """Gateway output for text generation."""

    content: str
    metadata: LLMInvocationMetadata


class LLMStructuredGenerationResponse(TypedDict):
    """Gateway output for structured generation."""

    output: dict[str, Any]
    metadata: LLMInvocationMetadata


class LLMGateway(Protocol):
    """Minimal provider-agnostic contract for LLM-backed generation."""

    def generate_text(
        self,
        request: LLMTextGenerationRequest,
    ) -> LLMTextGenerationResponse: ...

    def generate_structured(
        self,
        request: LLMStructuredGenerationRequest,
    ) -> LLMStructuredGenerationResponse: ...


class LLMGatewayError(RuntimeError):
    """Structured gateway error for provider routing and adapter failures."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = dict(details or {})

    def as_dict(self) -> dict[str, Any]:
        error = {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.details:
            error["details"] = self.details
        return error


class LLMGatewayRouter:
    """Resolve a gateway by provider or model profile before generation."""

    def __init__(
        self,
        *,
        default_gateway: LLMGateway | None = None,
        gateways_by_provider: Mapping[str, LLMGateway] | None = None,
        gateways_by_model_profile: Mapping[str, LLMGateway] | None = None,
    ) -> None:
        self.default_gateway = default_gateway
        self.gateways_by_provider = dict(gateways_by_provider or {})
        self.gateways_by_model_profile = dict(gateways_by_model_profile or {})

    def generate_text(
        self,
        request: LLMTextGenerationRequest,
    ) -> LLMTextGenerationResponse:
        return self._resolve_gateway(request).generate_text(request)

    def generate_structured(
        self,
        request: LLMStructuredGenerationRequest,
    ) -> LLMStructuredGenerationResponse:
        return self._resolve_gateway(request).generate_structured(request)

    def _resolve_gateway(
        self,
        request: LLMTextGenerationRequest | LLMStructuredGenerationRequest,
    ) -> LLMGateway:
        provider = request.get("provider")
        if isinstance(provider, str) and provider in self.gateways_by_provider:
            return self.gateways_by_provider[provider]

        model_profile = request["model_profile"]
        if model_profile in self.gateways_by_model_profile:
            return self.gateways_by_model_profile[model_profile]

        if self.default_gateway is not None:
            return self.default_gateway

        raise LLMGatewayError(
            "LLM_GATEWAY_NOT_CONFIGURED",
            "No LLM gateway is configured for the requested provider or model profile.",
            details={
                "provider": provider,
                "model_profile": model_profile,
            },
        )
