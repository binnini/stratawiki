from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from wiki_mcp.adapters.llm.gateway import (
    LLMInvocationMetadata,
    LLMStructuredGenerationRequest,
    LLMStructuredGenerationResponse,
    LLMTextGenerationRequest,
    LLMTextGenerationResponse,
)

TextResponseFactory = Callable[[LLMTextGenerationRequest], str]
StructuredResponseFactory = Callable[[LLMStructuredGenerationRequest], Mapping[str, Any]]


@dataclass(slots=True)
class DeterministicLLMGateway:
    """Deterministic mock-friendly gateway used for tests and early wiring."""

    provider: str = "mock"
    model: str = "deterministic-mock-v1"
    default_text: str = ""
    default_structured_output: Mapping[str, Any] | None = None
    text_factory: TextResponseFactory | None = None
    structured_factory: StructuredResponseFactory | None = None

    def generate_text(
        self,
        request: LLMTextGenerationRequest,
    ) -> LLMTextGenerationResponse:
        content = self.default_text
        if self.text_factory is not None:
            content = self.text_factory(request)

        return {
            "content": content,
            "metadata": self._build_metadata(request),
        }

    def generate_structured(
        self,
        request: LLMStructuredGenerationRequest,
    ) -> LLMStructuredGenerationResponse:
        output: dict[str, Any]
        if self.structured_factory is not None:
            output = dict(self.structured_factory(request))
        else:
            output = dict(self.default_structured_output or {})

        return {
            "output": output,
            "metadata": self._build_metadata(request),
        }

    def _build_metadata(
        self,
        request: LLMTextGenerationRequest | LLMStructuredGenerationRequest,
    ) -> LLMInvocationMetadata:
        metadata: LLMInvocationMetadata = {
            "provider": str(request.get("provider") or self.provider),
            "model": str(request.get("model") or self.model),
            "model_profile": request["model_profile"],
            "prompt_id": request["prompt_id"],
            "prompt_version": request["prompt_version"],
        }

        if "schema_name" in request:
            metadata["schema_name"] = request["schema_name"]
            metadata["schema_version"] = request["schema_version"]

        return metadata
