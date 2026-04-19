from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Mapping
from urllib.parse import parse_qs, unquote, urlsplit

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
) -> int:
    http_server = _StrataWikiHTTPServer(
        (host, port),
        _make_request_handler(),
        stratawiki_server=server,
        ready_payload=dict(ready_payload or {"status": "ok"}),
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
            result = server.call_tool(name.strip(), arguments)
            return _success_response(request_id, result)
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
    ) -> None:
        super().__init__(server_address, handler_class)
        self.stratawiki_server = stratawiki_server
        self.ready_payload = ready_payload


def _make_request_handler() -> type[BaseHTTPRequestHandler]:
    class StrataWikiHTTPRequestHandler(BaseHTTPRequestHandler):
        server: _StrataWikiHTTPServer

        def do_GET(self) -> None:
            self._handle()

        def do_POST(self) -> None:
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
