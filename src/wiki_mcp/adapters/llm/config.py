from __future__ import annotations

import os

from wiki_mcp.adapters.llm.gateway import LLMGatewayRouter
from wiki_mcp.adapters.llm.mock import DeterministicLLMGateway
from wiki_mcp.adapters.llm.openai import OpenAIResponsesGateway

DEFAULT_OPENAI_MODEL_BY_PROFILE = {
    "balanced_default": "gpt-4.1-mini",
    "deep_synthesis": "gpt-4.1",
}


def resolve_model_for_profile(
    model_profile: str,
    *,
    environ: dict[str, str] | None = None,
) -> str:
    """Resolve a concrete model for a logical model profile."""

    env = environ or os.environ
    env_key = f"WIKI_MCP_OPENAI_MODEL_{model_profile.upper()}"
    if env_key in env and env[env_key].strip():
        return env[env_key].strip()
    return DEFAULT_OPENAI_MODEL_BY_PROFILE.get(model_profile, "gpt-4.1-mini")


def build_llm_gateway_router_from_env(
    *,
    environ: dict[str, str] | None = None,
    default_gateway: DeterministicLLMGateway | None = None,
) -> LLMGatewayRouter:
    """Build the minimal runtime gateway router for the current MVP slice."""

    env = environ or os.environ
    fallback_gateway = default_gateway or DeterministicLLMGateway()
    gateways_by_provider = {}
    gateways_by_model_profile = {}

    api_key = env.get("OPENAI_API_KEY", "").strip()
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
        for model_profile in DEFAULT_OPENAI_MODEL_BY_PROFILE:
            gateways_by_model_profile[model_profile] = openai_gateway

    return LLMGatewayRouter(
        default_gateway=fallback_gateway,
        gateways_by_provider=gateways_by_provider,
        gateways_by_model_profile=gateways_by_model_profile,
    )
