from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any
from urllib import error, request

from wiki_mcp.adapters.llm.gateway import (
    LLMGatewayError,
    LLMInvocationMetadata,
    LLMStructuredGenerationRequest,
    LLMStructuredGenerationResponse,
    LLMTextGenerationRequest,
    LLMTextGenerationResponse,
)

ModelResolver = Callable[[str], str]


class OpenAIResponsesGateway:
    """Thin OpenAI Responses API adapter behind the provider-agnostic gateway."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model_resolver: ModelResolver | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_resolver = model_resolver or (lambda model_profile: model_profile)
        self.timeout_seconds = timeout_seconds

    def generate_text(
        self,
        request_payload: LLMTextGenerationRequest,
    ) -> LLMTextGenerationResponse:
        payload = self._build_payload(request_payload)
        payload["text"] = {"format": {"type": "text"}}
        response = self._post_responses(payload)
        return {
            "content": self._extract_output_text(response),
            "metadata": self._build_metadata(
                request_payload=request_payload,
                response_payload=response,
            ),
        }

    def generate_structured(
        self,
        request_payload: LLMStructuredGenerationRequest,
    ) -> LLMStructuredGenerationResponse:
        output_schema = request_payload.get("output_schema")
        if not isinstance(output_schema, dict) or not output_schema:
            raise LLMGatewayError(
                "LLM_SCHEMA_REQUIRED",
                "Structured generation requires a non-empty output_schema.",
                details={
                    "schema_name": request_payload["schema_name"],
                    "schema_version": request_payload["schema_version"],
                },
            )

        payload = self._build_payload(request_payload)
        payload["text"] = {
            "format": {
                "type": "json_schema",
                "name": request_payload["schema_name"],
                "schema": output_schema,
                "strict": True,
            }
        }
        response = self._post_responses(payload)
        content = self._extract_output_text(response)
        try:
            output = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMGatewayError(
                "LLM_INVALID_JSON_RESPONSE",
                "OpenAI structured generation returned non-JSON output.",
                retryable=True,
                details={"raw_output": content},
            ) from exc

        if not isinstance(output, dict):
            raise LLMGatewayError(
                "LLM_INVALID_SCHEMA_RESPONSE",
                "OpenAI structured generation returned JSON that was not an object.",
                retryable=True,
                details={"raw_output": content},
            )

        return {
            "output": output,
            "metadata": self._build_metadata(
                request_payload=request_payload,
                response_payload=response,
            ),
        }

    def _build_payload(
        self,
        request_payload: LLMTextGenerationRequest | LLMStructuredGenerationRequest,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._resolve_model(request_payload),
            "input": [
                {
                    "role": message["role"],
                    "content": message["content"],
                }
                for message in request_payload["messages"]
            ],
            "store": False,
        }

        if "temperature" in request_payload:
            payload["temperature"] = request_payload["temperature"]
        if "max_output_tokens" in request_payload:
            payload["max_output_tokens"] = request_payload["max_output_tokens"]

        return payload

    def _resolve_model(
        self,
        request_payload: LLMTextGenerationRequest | LLMStructuredGenerationRequest,
    ) -> str:
        configured_model = request_payload.get("model")
        if isinstance(configured_model, str) and configured_model.strip():
            return configured_model.strip()
        return self.model_resolver(request_payload["model_profile"])

    def _post_responses(self, payload: dict[str, Any]) -> dict[str, Any]:
        encoded_payload = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            f"{self.base_url}/responses",
            data=encoded_payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            raw_body = exc.read().decode("utf-8", errors="replace")
            message, details = self._extract_http_error(raw_body)
            raise LLMGatewayError(
                "LLM_PROVIDER_HTTP_ERROR",
                message,
                retryable=500 <= exc.code < 600,
                details={
                    "status_code": exc.code,
                    **details,
                },
            ) from exc
        except error.URLError as exc:
            raise LLMGatewayError(
                "LLM_PROVIDER_UNREACHABLE",
                "Failed to reach the configured OpenAI endpoint.",
                retryable=True,
                details={"reason": str(exc.reason)},
            ) from exc

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise LLMGatewayError(
                "LLM_PROVIDER_INVALID_RESPONSE",
                "OpenAI returned a non-JSON response.",
                retryable=True,
                details={"raw_body": body},
            ) from exc

        if not isinstance(parsed, dict):
            raise LLMGatewayError(
                "LLM_PROVIDER_INVALID_RESPONSE",
                "OpenAI returned an unexpected response payload shape.",
                retryable=True,
                details={"raw_body": body},
            )

        return parsed

    def _extract_output_text(self, response_payload: Mapping[str, Any]) -> str:
        output_items = response_payload.get("output", [])
        if not isinstance(output_items, list):
            raise LLMGatewayError(
                "LLM_PROVIDER_INVALID_RESPONSE",
                "OpenAI response did not include a valid output list.",
                retryable=True,
            )

        chunks: list[str] = []
        refusals: list[str] = []

        for output_item in output_items:
            if not isinstance(output_item, Mapping):
                continue
            contents = output_item.get("content", [])
            if not isinstance(contents, list):
                continue
            for content_item in contents:
                if not isinstance(content_item, Mapping):
                    continue
                item_type = content_item.get("type")
                if item_type == "output_text":
                    text = content_item.get("text")
                    if isinstance(text, str):
                        chunks.append(text)
                elif item_type == "refusal":
                    refusal = content_item.get("refusal")
                    if isinstance(refusal, str):
                        refusals.append(refusal)

        if refusals:
            raise LLMGatewayError(
                "LLM_PROVIDER_REFUSAL",
                "OpenAI refused the request.",
                details={"refusal": "\n".join(refusals)},
            )

        text_output = "\n".join(chunk for chunk in chunks if chunk).strip()
        if text_output:
            return text_output

        raise LLMGatewayError(
            "LLM_PROVIDER_EMPTY_OUTPUT",
            "OpenAI returned no output_text content.",
            retryable=True,
            details={"response": dict(response_payload)},
        )

    def _build_metadata(
        self,
        *,
        request_payload: LLMTextGenerationRequest | LLMStructuredGenerationRequest,
        response_payload: Mapping[str, Any],
    ) -> LLMInvocationMetadata:
        metadata: LLMInvocationMetadata = {
            "provider": str(request_payload.get("provider") or "openai"),
            "model": str(response_payload.get("model") or self._resolve_model(request_payload)),
            "model_profile": request_payload["model_profile"],
            "prompt_id": request_payload["prompt_id"],
            "prompt_version": request_payload["prompt_version"],
        }
        if "schema_name" in request_payload:
            metadata["schema_name"] = request_payload["schema_name"]
            metadata["schema_version"] = request_payload["schema_version"]
        return metadata

    def _extract_http_error(self, raw_body: str) -> tuple[str, dict[str, Any]]:
        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError:
            return (
                "OpenAI request failed.",
                {"raw_body": raw_body},
            )

        if isinstance(parsed, dict):
            error_payload = parsed.get("error")
            if isinstance(error_payload, dict):
                message = error_payload.get("message")
                if isinstance(message, str) and message.strip():
                    return (message.strip(), {"provider_error": error_payload})

        return (
            "OpenAI request failed.",
            {"provider_error": parsed},
        )
