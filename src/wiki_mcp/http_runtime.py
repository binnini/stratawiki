from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Mapping
from urllib.parse import parse_qs, unquote, urlsplit

from wiki_mcp.auth import resolve_bearer_token, resolve_http_auth_token
from wiki_mcp.runtime_protocol import (
    RUNTIME_PROTOCOL_VERSION,
    list_tools_payload,
    show_tool_payload,
)
from wiki_mcp.server import StrataWikiServer


API_VERSION = "v1"


@dataclass(frozen=True)
class HttpRuntimeResponse:
    status_code: int
    payload: dict[str, object]
    headers: dict[str, str]


def run_http_runtime(
    server: StrataWikiServer,
    *,
    host: str,
    port: int,
    ready_payload: Mapping[str, Any] | None = None,
    auth_token: str | None = None,
) -> int:
    http_server = _StrataWikiHTTPServer(
        (host, port),
        _make_request_handler(),
        stratawiki_server=server,
        ready_payload=dict(ready_payload or {"status": "ok"}),
        auth_token=resolve_http_auth_token(auth_token),
    )
    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        http_server.server_close()
    return 0


def dispatch_http_request(
    server: StrataWikiServer,
    *,
    method: str,
    path: str,
    headers: Mapping[str, str] | None,
    body: bytes,
    ready_payload: Mapping[str, Any] | None = None,
    auth_token: str | None = None,
) -> HttpRuntimeResponse:
    request_id = _resolve_request_id(headers)
    parsed = urlsplit(path)
    normalized_path = parsed.path.rstrip("/") or "/"
    query = parse_qs(parsed.query, keep_blank_values=False)
    normalized_method = method.strip().upper()

    if normalized_path == "/healthz":
        if normalized_method != "GET":
            return _method_not_allowed(request_id, allowed="GET")
        return _success_response(
            request_id,
            {
                "status": "ok",
                "runtime": "stratawiki-http",
                "protocol_version": RUNTIME_PROTOCOL_VERSION,
                "api_version": API_VERSION,
                "tool_count": len(server.list_tools()),
            },
        )

    if normalized_path == "/readyz":
        if normalized_method != "GET":
            return _method_not_allowed(request_id, allowed="GET")
        payload = {
            "status": "ready",
            "runtime": "stratawiki-http",
            "protocol_version": RUNTIME_PROTOCOL_VERSION,
            "api_version": API_VERSION,
            "checks": dict(ready_payload or {"status": "ok"}),
        }
        return _success_response(request_id, payload)

    resolved_auth_token = resolve_http_auth_token(auth_token)
    if normalized_path.startswith("/api/") and resolved_auth_token is not None:
        bearer_token = resolve_bearer_token(headers)
        if bearer_token != resolved_auth_token:
            return _unauthorized_response(request_id)

    if normalized_path == "/api/v1/tools":
        if normalized_method != "GET":
            return _method_not_allowed(request_id, allowed="GET")
        group = _single_query_value(query, "group")
        full_schemas = _query_bool(query, "schemas", default=False)
        return _success_response(
            request_id,
            list_tools_payload(server, group=group, full_schemas=full_schemas),
        )

    if normalized_path.startswith("/api/v1/tools/"):
        if normalized_method != "GET":
            return _method_not_allowed(request_id, allowed="GET")
        tool_name = unquote(normalized_path.removeprefix("/api/v1/tools/")).strip()
        if not tool_name:
            return _error_response(
                request_id,
                status_code=HTTPStatus.BAD_REQUEST,
                code="invalid_request",
                message="Tool name must be present in the path.",
            )
        try:
            return _success_response(request_id, show_tool_payload(server, tool_name))
        except KeyError as exc:
            return _tool_error_response(request_id, exc)

    if normalized_path == "/api/v1/domain-proposals/validate":
        if normalized_method != "POST":
            return _method_not_allowed(request_id, allowed="POST")
        return _dispatch_tool_post(
            server,
            request_id=request_id,
            body=body,
            tool_name="validate_domain_proposal_batch",
        )

    if normalized_path == "/api/v1/domain-proposals/ingest":
        if normalized_method != "POST":
            return _method_not_allowed(request_id, allowed="POST")
        return _dispatch_tool_post(
            server,
            request_id=request_id,
            body=body,
            tool_name="ingest_domain_proposal_batch",
        )

    if normalized_path.startswith("/api/v1/profile-contexts/"):
        if normalized_method != "PUT":
            return _method_not_allowed(request_id, allowed="PUT")
        suffix = normalized_path.removeprefix("/api/v1/profile-contexts/")
        tenant_id, user_id = _split_two_path_parts(suffix, label="profile context path")
        try:
            payload = _parse_json_object(body)
            _coerce_path_field(payload, "tenant_id", tenant_id)
            _coerce_path_field(payload, "user_id", user_id)
            return _call_tool(
                server,
                request_id=request_id,
                tool_name="upsert_profile_context",
                arguments=payload,
            )
        except Exception as exc:
            return _tool_error_response(request_id, exc)

    if normalized_path == "/api/v1/personal-queries":
        if normalized_method != "POST":
            return _method_not_allowed(request_id, allowed="POST")
        return _dispatch_tool_post(
            server,
            request_id=request_id,
            body=body,
            tool_name="query_personal_knowledge",
        )

    if normalized_path == "/api/v1/interpretation-builds":
        if normalized_method != "POST":
            return _method_not_allowed(request_id, allowed="POST")
        try:
            payload = _parse_json_object(body)
            response = _call_tool(
                server,
                request_id=request_id,
                tool_name="build_interpretation_snapshot",
                arguments=payload,
            )
            result = response.payload.get("result")
            if isinstance(result, dict) and result.get("status") == "queued":
                return HttpRuntimeResponse(
                    status_code=int(HTTPStatus.ACCEPTED),
                    payload=response.payload,
                    headers=response.headers,
                )
            return response
        except Exception as exc:
            return _tool_error_response(request_id, exc)

    if normalized_path.startswith("/api/v1/jobs/"):
        if normalized_method != "GET":
            return _method_not_allowed(request_id, allowed="GET")
        try:
            job_id = _single_path_part(normalized_path.removeprefix("/api/v1/jobs/"), label="job path")
            return _call_tool(
                server,
                request_id=request_id,
                tool_name="get_job_status",
                arguments={"job_id": job_id},
            )
        except Exception as exc:
            return _tool_error_response(request_id, exc)

    if normalized_path == "/api/v1/snapshot-status":
        if normalized_method != "GET":
            return _method_not_allowed(request_id, allowed="GET")
        try:
            domain = _required_query_value(query, "domain")
            arguments: dict[str, object] = {"domain": domain}
            family = _single_query_value(query, "family")
            segment = _single_query_value(query, "segment")
            if family is not None or segment is not None:
                if family is None or segment is None:
                    raise ValueError("snapshot-status partition queries require both 'family' and 'segment'.")
                arguments["partition"] = {"family": family, "segment": segment}
            return _call_tool(
                server,
                request_id=request_id,
                tool_name="get_snapshot_status",
                arguments=arguments,
            )
        except Exception as exc:
            return _tool_error_response(request_id, exc)

    if normalized_path.startswith("/api/v1/cache-status/"):
        if normalized_method != "GET":
            return _method_not_allowed(request_id, allowed="GET")
        try:
            record_id = _single_path_part(normalized_path.removeprefix("/api/v1/cache-status/"), label="cache-status path")
            return _call_tool(
                server,
                request_id=request_id,
                tool_name="get_cache_status",
                arguments={
                    "domain": _required_query_value(query, "domain"),
                    "tenant_id": _required_query_value(query, "tenant_id"),
                    "user_id": _required_query_value(query, "user_id"),
                    "record_id": record_id,
                },
            )
        except Exception as exc:
            return _tool_error_response(request_id, exc)

    if normalized_path.startswith("/api/v1/explanations/"):
        if normalized_method != "GET":
            return _method_not_allowed(request_id, allowed="GET")
        try:
            layer, record_id = _split_two_path_parts(
                normalized_path.removeprefix("/api/v1/explanations/"),
                label="explanations path",
            )
            arguments: dict[str, object] = {
                "domain": _required_query_value(query, "domain"),
                "layer": layer,
                "result_id": record_id,
            }
            tenant_id = _single_query_value(query, "tenant_id")
            user_id = _single_query_value(query, "user_id")
            if tenant_id is not None:
                arguments["tenant_id"] = tenant_id
            if user_id is not None:
                arguments["user_id"] = user_id
            return _call_tool(
                server,
                request_id=request_id,
                tool_name="explain_result",
                arguments=arguments,
            )
        except Exception as exc:
            return _tool_error_response(request_id, exc)

    if normalized_path == "/api/v1/tool-calls":
        if normalized_method != "POST":
            return _method_not_allowed(request_id, allowed="POST")
        try:
            payload = _parse_json_object(body)
            name = payload.get("name")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Field 'name' must be a non-empty string.")
            arguments = payload.get("arguments", {})
            if not isinstance(arguments, dict):
                raise ValueError("Field 'arguments' must decode to an object when provided.")
            return _call_tool(server, request_id=request_id, tool_name=name.strip(), arguments=arguments)
        except Exception as exc:
            return _tool_error_response(request_id, exc)

    return _error_response(
        request_id,
        status_code=HTTPStatus.NOT_FOUND,
        code="not_found",
        message=f"Unknown HTTP path: {normalized_path}",
    )


class _StrataWikiHTTPServer(HTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        stratawiki_server: StrataWikiServer,
        ready_payload: dict[str, Any],
        auth_token: str | None,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.stratawiki_server = stratawiki_server
        self.ready_payload = ready_payload
        self.auth_token = auth_token


def _make_request_handler() -> type[BaseHTTPRequestHandler]:
    class StrataWikiHTTPRequestHandler(BaseHTTPRequestHandler):
        server: _StrataWikiHTTPServer

        def do_GET(self) -> None:
            self._handle()

        def do_POST(self) -> None:
            self._handle()

        def do_PUT(self) -> None:
            self._handle()

        def log_message(self, format: str, *args: object) -> None:
            return

        def _handle(self) -> None:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(content_length) if content_length > 0 else b""
            response = dispatch_http_request(
                self.server.stratawiki_server,
                method=self.command,
                path=self.path,
                headers={key: value for key, value in self.headers.items()},
                body=raw_body,
                ready_payload=self.server.ready_payload,
                auth_token=self.server.auth_token,
            )
            encoded = json.dumps(response.payload, sort_keys=True).encode("utf-8")
            self.send_response(response.status_code)
            for key, value in response.headers.items():
                self.send_header(key, value)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return StrataWikiHTTPRequestHandler


def _parse_json_object(raw_body: bytes) -> dict[str, object]:
    if not raw_body:
        raise ValueError("Request body must contain one JSON object.")
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Failed to parse JSON request body: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("HTTP request body must decode to one JSON object.")
    return payload


def _dispatch_tool_post(
    server: StrataWikiServer,
    *,
    request_id: str,
    body: bytes,
    tool_name: str,
) -> HttpRuntimeResponse:
    try:
        payload = _parse_json_object(body)
        return _call_tool(server, request_id=request_id, tool_name=tool_name, arguments=payload)
    except Exception as exc:
        return _tool_error_response(request_id, exc)


def _call_tool(
    server: StrataWikiServer,
    *,
    request_id: str,
    tool_name: str,
    arguments: dict[str, object],
) -> HttpRuntimeResponse:
    result = server.call_tool(tool_name, arguments)
    return _success_response(request_id, result)


def _tool_error_response(request_id: str, exc: Exception) -> HttpRuntimeResponse:
    if isinstance(exc, KeyError):
        return _error_response(
            request_id,
            status_code=HTTPStatus.NOT_FOUND,
            code="not_found",
            message=str(exc),
            details={"type": exc.__class__.__name__},
        )
    if isinstance(exc, ValueError):
        return _error_response(
            request_id,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            code="validation_error",
            message=str(exc),
            details={"type": exc.__class__.__name__},
        )
    return _error_response(
        request_id,
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        code="internal_error",
        message=str(exc),
        details={"type": exc.__class__.__name__},
    )


def _success_response(request_id: str, result: object) -> HttpRuntimeResponse:
    return HttpRuntimeResponse(
        status_code=HTTPStatus.OK,
        payload={
            "ok": True,
            "request_id": request_id,
            "result": result,
        },
        headers={"X-Request-Id": request_id},
    )


def _error_response(
    request_id: str,
    *,
    status_code: HTTPStatus,
    code: str,
    message: str,
    details: dict[str, object] | None = None,
) -> HttpRuntimeResponse:
    error: dict[str, object] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return HttpRuntimeResponse(
        status_code=int(status_code),
        payload={
            "ok": False,
            "request_id": request_id,
            "error": error,
        },
        headers={"X-Request-Id": request_id},
    )


def _method_not_allowed(request_id: str, *, allowed: str) -> HttpRuntimeResponse:
    return HttpRuntimeResponse(
        status_code=int(HTTPStatus.METHOD_NOT_ALLOWED),
        payload={
            "ok": False,
            "request_id": request_id,
            "error": {
                "code": "method_not_allowed",
                "message": f"Use {allowed} for this endpoint.",
            },
        },
        headers={
            "X-Request-Id": request_id,
            "Allow": allowed,
        },
    )


def _unauthorized_response(request_id: str) -> HttpRuntimeResponse:
    return HttpRuntimeResponse(
        status_code=int(HTTPStatus.UNAUTHORIZED),
        payload={
            "ok": False,
            "request_id": request_id,
            "error": {
                "code": "unauthorized",
                "message": "Missing or invalid bearer token.",
            },
        },
        headers={
            "X-Request-Id": request_id,
            "WWW-Authenticate": "Bearer",
        },
    )


def _resolve_request_id(headers: Mapping[str, str] | None) -> str:
    if headers is not None:
        normalized = {str(key).lower(): value for key, value in headers.items()}
        raw = str(normalized.get("x-request-id") or "").strip()
        if raw:
            return raw
    return f"req-{uuid.uuid4().hex}"


def _single_query_value(query: Mapping[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if not values:
        return None
    value = str(values[0]).strip()
    return value or None


def _query_bool(query: Mapping[str, list[str]], key: str, *, default: bool) -> bool:
    raw = _single_query_value(query, key)
    if raw is None:
        return default
    normalized = raw.lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise ValueError(f"Query parameter {key!r} must be a boolean string.")


def _required_query_value(query: Mapping[str, list[str]], key: str) -> str:
    value = _single_query_value(query, key)
    if value is None:
        raise ValueError(f"Query parameter {key!r} is required.")
    return value


def _split_two_path_parts(raw: str, *, label: str) -> tuple[str, str]:
    parts = [unquote(part).strip() for part in raw.split("/") if part.strip()]
    if len(parts) != 2:
        raise ValueError(f"{label} must include exactly two non-empty path parts.")
    return parts[0], parts[1]


def _single_path_part(raw: str, *, label: str) -> str:
    parts = [unquote(part).strip() for part in raw.split("/") if part.strip()]
    if len(parts) != 1:
        raise ValueError(f"{label} must include exactly one non-empty path part.")
    return parts[0]


def _coerce_path_field(payload: dict[str, object], field: str, value: str) -> None:
    existing = payload.get(field)
    if existing is None:
        payload[field] = value
        return
    if not isinstance(existing, str) or existing.strip() != value:
        raise ValueError(f"Field '{field}' must match the path value.")
