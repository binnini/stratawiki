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


class OllamaChatGateway:
    """Thin Ollama chat API adapter behind the provider-agnostic gateway."""

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434/api",
        api_key: str | None = None,
        model_resolver: ModelResolver | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip() if isinstance(api_key, str) else None
        self.model_resolver = model_resolver or (lambda model_profile: model_profile)
        self.timeout_seconds = timeout_seconds

    def generate_text(
        self,
        request_payload: LLMTextGenerationRequest,
    ) -> LLMTextGenerationResponse:
        response = self._post_chat(self._build_payload(request_payload))
        return {
            "content": self._extract_message_content(response),
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
        payload["format"] = output_schema
        response = self._post_chat(payload)
        content = self._extract_message_content(response)
        try:
            output = self._parse_json_object(content)
        except json.JSONDecodeError as exc:
            raise LLMGatewayError(
                "LLM_INVALID_JSON_RESPONSE",
                "Ollama structured generation returned non-JSON output.",
                retryable=True,
                details={"raw_output": content},
            ) from exc

        if not isinstance(output, dict):
            raise LLMGatewayError(
                "LLM_INVALID_SCHEMA_RESPONSE",
                "Ollama structured generation returned JSON that was not an object.",
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
            "messages": [
                {
                    "role": message["role"],
                    "content": message["content"],
                }
                for message in request_payload["messages"]
            ],
            "stream": False,
            # Thinking-capable models may emit reasoning traces by default.
            # Disable that path here so the gateway can reliably consume the
            # final assistant content for both text and structured outputs.
            "think": False,
        }

        options: dict[str, Any] = {}
        if "temperature" in request_payload:
            options["temperature"] = request_payload["temperature"]
        if "max_output_tokens" in request_payload:
            options["num_predict"] = request_payload["max_output_tokens"]
        if options:
            payload["options"] = options

        return payload

    def _resolve_model(
        self,
        request_payload: LLMTextGenerationRequest | LLMStructuredGenerationRequest,
    ) -> str:
        configured_model = request_payload.get("model")
        if isinstance(configured_model, str) and configured_model.strip():
            return configured_model.strip()
        return self.model_resolver(request_payload["model_profile"])

    def _post_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        encoded_payload = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        http_request = request.Request(
            f"{self.base_url}/chat",
            data=encoded_payload,
            headers=headers,
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
                "Failed to reach the configured Ollama endpoint.",
                retryable=True,
                details={"reason": str(exc.reason)},
            ) from exc

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise LLMGatewayError(
                "LLM_PROVIDER_INVALID_RESPONSE",
                "Ollama returned a non-JSON response.",
                retryable=True,
                details={"raw_body": body},
            ) from exc

        if not isinstance(parsed, dict):
            raise LLMGatewayError(
                "LLM_PROVIDER_INVALID_RESPONSE",
                "Ollama returned an unexpected response payload shape.",
                retryable=True,
                details={"raw_body": body},
            )

        return parsed

    def _extract_message_content(self, response_payload: Mapping[str, Any]) -> str:
        message = response_payload.get("message")
        if not isinstance(message, Mapping):
            raise LLMGatewayError(
                "LLM_PROVIDER_INVALID_RESPONSE",
                "Ollama response did not include a valid message object.",
                retryable=True,
            )

        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()

        raise LLMGatewayError(
            "LLM_PROVIDER_EMPTY_OUTPUT",
            "Ollama returned no message content.",
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
            "provider": str(request_payload.get("provider") or "ollama"),
            "model": str(response_payload.get("model") or self._resolve_model(request_payload)),
            "model_profile": request_payload["model_profile"],
            "prompt_id": request_payload["prompt_id"],
            "prompt_version": request_payload["prompt_version"],
        }
        if "schema_name" in request_payload:
            metadata["schema_name"] = request_payload["schema_name"]
            metadata["schema_version"] = request_payload["schema_version"]
        return metadata

    def _parse_json_object(self, content: str) -> dict[str, Any]:
        normalized = self._extract_json_candidate(content)
        output = json.loads(normalized)
        if not isinstance(output, dict):
            raise LLMGatewayError(
                "LLM_INVALID_SCHEMA_RESPONSE",
                "Ollama structured generation returned JSON that was not an object.",
                retryable=True,
                details={"raw_output": content},
            )
        return output

    def _extract_json_candidate(self, content: str) -> str:
        normalized = content.strip()
        if normalized.startswith("```"):
            lines = normalized.splitlines()
            if lines:
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            normalized = "\n".join(lines).strip()
            if normalized.lower().startswith("json"):
                normalized = normalized[4:].lstrip()

        if normalized.startswith("{") and normalized.endswith("}"):
            return normalized

        extracted = self._find_first_json_object(normalized)
        if extracted is not None:
            return extracted

        return normalized

    def _find_first_json_object(self, content: str) -> str | None:
        start_index = content.find("{")
        while start_index != -1:
            depth = 0
            in_string = False
            escape = False
            for index in range(start_index, len(content)):
                character = content[index]
                if in_string:
                    if escape:
                        escape = False
                    elif character == "\\":
                        escape = True
                    elif character == "\"":
                        in_string = False
                    continue

                if character == "\"":
                    in_string = True
                    continue
                if character == "{":
                    depth += 1
                    continue
                if character == "}":
                    depth -= 1
                    if depth == 0:
                        return content[start_index : index + 1]
            start_index = content.find("{", start_index + 1)
        return None

    def _extract_http_error(self, raw_body: str) -> tuple[str, dict[str, Any]]:
        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError:
            return (
                "Ollama request failed.",
                {"raw_body": raw_body},
            )

        if isinstance(parsed, dict):
            error_message = parsed.get("error")
            if isinstance(error_message, str) and error_message.strip():
                return (error_message.strip(), {"provider_error": parsed})

        return (
            "Ollama request failed.",
            {"provider_error": parsed},
        )
