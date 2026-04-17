"""Provider-agnostic LLM gateway primitives for the current migration slice."""

from wiki_mcp.adapters.llm.gateway import (
    LLMGateway,
    LLMGatewayError,
    LLMGatewayRouter,
    LLMInvocationMetadata,
    LLMMessage,
    LLMStructuredGenerationRequest,
    LLMStructuredGenerationResponse,
    LLMTextGenerationRequest,
    LLMTextGenerationResponse,
)
from wiki_mcp.adapters.llm.config import (
    build_llm_gateway_router_from_env,
    resolve_model_for_profile,
    resolve_ollama_model_for_profile,
)
from wiki_mcp.adapters.llm.mock import DeterministicLLMGateway
from wiki_mcp.adapters.llm.openai import OpenAIResponsesGateway
from wiki_mcp.adapters.llm.ollama import OllamaChatGateway

__all__ = [
    "DeterministicLLMGateway",
    "LLMGateway",
    "LLMGatewayError",
    "LLMGatewayRouter",
    "LLMInvocationMetadata",
    "LLMMessage",
    "OpenAIResponsesGateway",
    "OllamaChatGateway",
    "LLMStructuredGenerationRequest",
    "LLMStructuredGenerationResponse",
    "LLMTextGenerationRequest",
    "LLMTextGenerationResponse",
    "build_llm_gateway_router_from_env",
    "resolve_model_for_profile",
    "resolve_ollama_model_for_profile",
]
