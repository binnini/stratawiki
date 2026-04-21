from __future__ import annotations

import os

from wiki_mcp.adapters.llm.gateway import LLMGatewayRouter
from wiki_mcp.adapters.llm.mock import DeterministicLLMGateway
from wiki_mcp.adapters.llm.openai import OpenAIResponsesGateway
from wiki_mcp.adapters.llm.ollama import OllamaChatGateway

DEFAULT_OPENAI_MODEL_BY_PROFILE = {
    "balanced_default": "gpt-4.1-mini",
    "deep_synthesis": "gpt-4.1",
}

DEFAULT_OLLAMA_MODEL_BY_PROFILE = {
    "balanced_default": "gemma3:270m",
    "deep_synthesis": "gemma3:1b",
}


def resolve_model_for_profile(
    model_profile: str,
    *,
    environ: dict[str, str] | None = None,
) -> str:
    """Resolve a concrete model for a logical model profile."""

    env = os.environ if environ is None else environ
    env_key = f"WIKI_MCP_OPENAI_MODEL_{model_profile.upper()}"
    if env_key in env and env[env_key].strip():
        return env[env_key].strip()
    return DEFAULT_OPENAI_MODEL_BY_PROFILE.get(model_profile, "gpt-4.1-mini")


def resolve_ollama_model_for_profile(
    model_profile: str,
    *,
    environ: dict[str, str] | None = None,
) -> str:
    """Resolve a concrete Ollama model for a logical model profile."""

    env = os.environ if environ is None else environ
    env_key = f"WIKI_MCP_OLLAMA_MODEL_{model_profile.upper()}"
    if env_key in env and env[env_key].strip():
        return env[env_key].strip()
    return DEFAULT_OLLAMA_MODEL_BY_PROFILE.get(model_profile, "gemma3:270m")


def build_llm_gateway_router_from_env(
    *,
    environ: dict[str, str] | None = None,
    default_gateway: DeterministicLLMGateway | None = None,
) -> LLMGatewayRouter:
    """Build the minimal runtime gateway router for the current MVP slice."""

    env = os.environ if environ is None else environ
    gateways_by_provider = {}
    gateways_by_model_profile = {}
    preferred_provider = env.get("WIKI_MCP_DEFAULT_PROVIDER", "").strip().lower()

    api_key = env.get("OPENAI_API_KEY", "").strip()
    openai_gateway = None
    if api_key:
        openai_gateway = OpenAIResponsesGateway(
            api_key=api_key,
            base_url=env.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            model_resolver=lambda model_profile: resolve_model_for_profile(
                model_profile,
                environ=env,
            ),
        )
        gateways_by_provider["openai"] = openai_gateway

    enable_ollama = env.get("WIKI_MCP_ENABLE_OLLAMA", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    ollama_gateway = None
    if enable_ollama or env.get("OLLAMA_BASE_URL", "").strip():
        ollama_gateway = OllamaChatGateway(
            base_url=env.get("OLLAMA_BASE_URL", "http://localhost:11434/api"),
            api_key=env.get("OLLAMA_API_KEY"),
            model_resolver=lambda model_profile: resolve_ollama_model_for_profile(
                model_profile,
                environ=env,
            ),
        )
        gateways_by_provider["ollama"] = ollama_gateway

    if preferred_provider == "ollama" and ollama_gateway is not None:
        for model_profile in DEFAULT_OLLAMA_MODEL_BY_PROFILE:
            gateways_by_model_profile[model_profile] = ollama_gateway
    elif openai_gateway is not None:
        for model_profile in DEFAULT_OPENAI_MODEL_BY_PROFILE:
            gateways_by_model_profile[model_profile] = openai_gateway
    elif ollama_gateway is not None:
        for model_profile in DEFAULT_OLLAMA_MODEL_BY_PROFILE:
            gateways_by_model_profile[model_profile] = ollama_gateway

    return LLMGatewayRouter(
        default_gateway=default_gateway,
        gateways_by_provider=gateways_by_provider,
        gateways_by_model_profile=gateways_by_model_profile,
    )
