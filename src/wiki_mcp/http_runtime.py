from __future__ import annotations

from copy import deepcopy
import json
import uuid
from dataclasses import dataclass, field
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
from wiki_mcp.services import PersonalAssetRegistrationError


API_VERSION = "v1"


@dataclass(frozen=True)
class HttpRuntimeResponse:
    status_code: int
    payload: dict[str, object]
    headers: dict[str, str]


@dataclass
class _HttpCommandStore:
    commands: dict[str, dict[str, object]] = field(default_factory=dict)
    command_keys: dict[tuple[str, str], str] = field(default_factory=dict)

    def submit(
        self,
        server: StrataWikiServer,
        *,
        request_id: str,
        name: str,
        arguments: dict[str, object],
        idempotency_key: str | None,
    ) -> tuple[dict[str, object], HTTPStatus]:
        argument_fingerprint = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
        if idempotency_key is not None:
            existing_id = self.command_keys.get((idempotency_key, name))
            if existing_id is not None:
                command = self.commands[existing_id]
                if command["argument_fingerprint"] != argument_fingerprint:
                    raise ValueError("Idempotency-Key cannot be reused for a different command payload.")
                public_command = self._public_record(command)
                return public_command, HTTPStatus.ACCEPTED if not bool(command["terminal"]) else HTTPStatus.CREATED

        command_id = f"cmd-{uuid.uuid4().hex}"
        submitted_at = _utc_timestamp()
        base_record: dict[str, object] = {
            "command_id": command_id,
            "name": name,
            "request_id": request_id,
            "submitted_at": submitted_at,
            "started_at": submitted_at,
            "finished_at": None,
            "attempt_count": 1,
            "terminal": False,
            "retryable": False,
            "state": "running",
            "request": {
                "name": name,
                "arguments": deepcopy(arguments),
            },
            "result": None,
            "error": None,
            "job": None,
            "idempotency_key": idempotency_key,
            "argument_fingerprint": argument_fingerprint,
        }

        try:
            result = server.call_tool(name, deepcopy(arguments))
        except Exception as exc:
            error, retryable = _normalize_command_error(exc)
            command = self._finalize_record(
                base_record,
                state="failed",
                terminal=True,
                retryable=retryable,
                result=None,
                error=error,
            )
        else:
            normalized_result = deepcopy(result)
            if isinstance(normalized_result, dict) and str(normalized_result.get("status") or "").strip().lower() == "queued":
                command = self._finalize_record(
                    base_record,
                    state="queued",
                    terminal=False,
                    retryable=False,
                    result=normalized_result,
                    job=_extract_command_job_reference(normalized_result),
                )
            else:
                command = self._finalize_record(
                    base_record,
                    state="succeeded",
                    terminal=True,
                    retryable=False,
                    result=normalized_result,
                )

        self.commands[command_id] = deepcopy(command)
        if idempotency_key is not None:
            self.command_keys[(idempotency_key, name)] = command_id
        return self._public_record(command), HTTPStatus.ACCEPTED if command["state"] == "queued" else HTTPStatus.CREATED

    def get(self, command_id: str) -> dict[str, object]:
        command = self.commands.get(command_id)
        if command is None:
            raise KeyError(f"Unknown command: {command_id}")
        return self._public_record(command)

    def _finalize_record(
        self,
        base_record: dict[str, object],
        *,
        state: str,
        terminal: bool,
        retryable: bool,
        result: object,
        error: dict[str, object] | None = None,
        job: dict[str, object] | None = None,
    ) -> dict[str, object]:
        record = dict(base_record)
        record["state"] = state
        record["terminal"] = terminal
        record["retryable"] = retryable
        record["finished_at"] = _utc_timestamp() if terminal else None
        record["result"] = deepcopy(result)
        record["error"] = deepcopy(error) if error is not None else None
        record["job"] = deepcopy(job) if job is not None else None
        return record

    def _public_record(self, command: dict[str, object]) -> dict[str, object]:
        public_command = deepcopy(command)
        public_command.pop("argument_fingerprint", None)
        return public_command


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

    if normalized_path.startswith("/api/v1/users/") and normalized_path.endswith("/personal-assets"):
        if normalized_method != "POST":
            return _method_not_allowed(request_id, allowed="POST")
        suffix = normalized_path.removeprefix("/api/v1/users/").removesuffix("/personal-assets")
        try:
            tenant_id, user_id = _split_two_path_parts(suffix, label="personal asset path")
            payload = _parse_json_object(body)
            _coerce_path_field(payload, "tenant_id", tenant_id)
            _coerce_path_field(payload, "user_id", user_id)
            return _register_personal_asset(server, request_id=request_id, arguments=payload)
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

    if normalized_path.startswith("/api/v1/users/"):
        try:
            route = _parse_personal_document_action_path(normalized_path)
        except ValueError:
            route = None
        if route is not None:
            if normalized_method != "POST":
                return _method_not_allowed(request_id, allowed="POST")
            try:
                payload = _parse_json_object(body)
                _coerce_path_field(payload, "tenant_id", route["tenant_id"])
                _coerce_path_field(payload, "user_id", route["user_id"])
                return _dispatch_personal_document_generation_post(
                    server,
                    request_id=request_id,
                    action=route["action"],
                    document_id=route["document_id"],
                    payload=payload,
                )
            except Exception as exc:
                return _tool_error_response(request_id, exc)
        try:
            parts = [unquote(part).strip() for part in normalized_path.removeprefix("/api/v1/users/").split("/") if part.strip()]
            if len(parts) < 3:
                raise ValueError("users path must include tenant_id, user_id, and resource path.")
            tenant_id = parts[0]
            user_id = parts[1]
            resource_path = "/".join(parts[2:])
        except Exception as exc:
            return _tool_error_response(request_id, exc)

        if resource_path == "personal-documents":
            return _dispatch_personal_document_request(
                server,
                request_id=request_id,
                method=normalized_method,
                resource_path=resource_path,
                tenant_id=tenant_id,
                user_id=user_id,
                query=query,
                body=body,
            )

        if resource_path.startswith("personal-documents/"):
            return _dispatch_personal_document_request(
                server,
                request_id=request_id,
                method=normalized_method,
                resource_path=resource_path,
                tenant_id=tenant_id,
                user_id=user_id,
                query=query,
                body=body,
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

    if normalized_path == "/api/v1/commands":
        if normalized_method != "POST":
            return _method_not_allowed(request_id, allowed="POST")
        try:
            return _dispatch_command_post(server, request_id=request_id, headers=headers, body=body)
        except Exception as exc:
            return _tool_error_response(request_id, exc)

    if normalized_path.startswith("/api/v1/commands/"):
        if normalized_method != "GET":
            return _method_not_allowed(request_id, allowed="GET")
        try:
            command_id = _single_path_part(normalized_path.removeprefix("/api/v1/commands/"), label="command path")
            return _success_response(request_id, _get_command_status(server, command_id))
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

def _dispatch_personal_document_request(
    server: StrataWikiServer,
    *,
    request_id: str,
    method: str,
    resource_path: str,
    tenant_id: str,
    user_id: str,
    query: Mapping[str, list[str]],
    body: bytes,
) -> HttpRuntimeResponse:
    service = _personal_document_service(server)

    if resource_path == "personal-documents":
        if method == "GET":
            try:
                limit_value = _single_query_value(query, "limit")
                return _success_response(
                    request_id,
                    service.list_documents(
                        domain=_required_query_value(query, "domain"),
                        tenant_id=tenant_id,
                        user_id=user_id,
                        subspace=_single_query_value(query, "subspace"),
                        kind=_single_query_value(query, "kind"),
                        status=_single_query_value(query, "status"),
                        limit=int(limit_value) if limit_value is not None else 20,
                    ),
                )
            except Exception as exc:
                return _tool_error_response(request_id, exc)
        if method == "POST":
            try:
                payload = _parse_json_object(body)
                _coerce_path_field(payload, "tenant_id", tenant_id)
                _coerce_path_field(payload, "user_id", user_id)
                return _success_response(
                    request_id,
                    service.create_document(
                        domain=_required_string(payload, "domain"),
                        tenant_id=_required_string(payload, "tenant_id"),
                        user_id=_required_string(payload, "user_id"),
                        profile_version=_required_string(payload, "profile_version"),
                        subspace=_required_string(payload, "subspace"),
                        kind=_required_string(payload, "kind"),
                        title=_required_string(payload, "title"),
                        body_markdown=_optional_string(payload, "body_markdown"),
                        asset_refs=_optional_string_list(payload, "asset_refs"),
                        anchors=_optional_json_list(payload, "anchors"),
                    ),
                )
            except Exception as exc:
                return _tool_error_response(request_id, exc)
        return _method_not_allowed(request_id, allowed="GET, POST")

    if not resource_path.startswith("personal-documents/"):
        return _error_response(
            request_id,
            status_code=HTTPStatus.BAD_REQUEST,
            code="invalid_request",
            message="document_id must be present in the path.",
        )

    document_id = resource_path.removeprefix("personal-documents/").strip()
    if not document_id:
        return _error_response(
            request_id,
            status_code=HTTPStatus.BAD_REQUEST,
            code="invalid_request",
            message="document_id must be present in the path.",
        )

    if method == "GET":
        try:
            return _success_response(
                request_id,
                service.get_document(
                    domain=_required_query_value(query, "domain"),
                    tenant_id=tenant_id,
                    user_id=user_id,
                    document_id=unquote(document_id),
                ),
            )
        except Exception as exc:
            return _tool_error_response(request_id, exc)
    if method == "PATCH":
        try:
            payload = _parse_json_object(body)
            _coerce_path_field(payload, "tenant_id", tenant_id)
            _coerce_path_field(payload, "user_id", user_id)
            _coerce_path_field(payload, "document_id", unquote(document_id))
            return _success_response(
                request_id,
                service.update_document(
                    domain=_required_string(payload, "domain"),
                    tenant_id=_required_string(payload, "tenant_id"),
                    user_id=_required_string(payload, "user_id"),
                    document_id=_required_string(payload, "document_id"),
                    profile_version=_required_string(payload, "profile_version"),
                    if_version=_required_positive_int(payload, "if_version"),
                    title=_optional_string(payload, "title"),
                    body_markdown=_optional_string(payload, "body_markdown"),
                    anchors=_optional_json_list(payload, "anchors"),
                    asset_refs=_optional_string_list(payload, "asset_refs"),
                    status=_optional_string(payload, "status"),
                ),
            )
        except Exception as exc:
            return _tool_error_response(request_id, exc)
    if method == "DELETE":
        try:
            payload = _parse_json_object(body)
            _coerce_path_field(payload, "tenant_id", tenant_id)
            _coerce_path_field(payload, "user_id", user_id)
            _coerce_path_field(payload, "document_id", unquote(document_id))
            return _success_response(
                request_id,
                service.delete_document(
                    domain=_required_string(payload, "domain"),
                    tenant_id=_required_string(payload, "tenant_id"),
                    user_id=_required_string(payload, "user_id"),
                    document_id=_required_string(payload, "document_id"),
                    if_version=_required_positive_int(payload, "if_version"),
                ),
            )
        except Exception as exc:
            return _tool_error_response(request_id, exc)
    return _method_not_allowed(request_id, allowed="GET, PATCH, DELETE")


def _personal_document_service(server: StrataWikiServer) -> Any:
    bootstrap = getattr(server, "bootstrap", None)
    service = getattr(bootstrap, "personal_document_service", None)
    if service is None:
        raise ValueError("Personal document service is not configured.")
    return service


def _dispatch_personal_document_generation_post(
    server: StrataWikiServer,
    *,
    request_id: str,
    action: str,
    document_id: str,
    payload: dict[str, object],
) -> HttpRuntimeResponse:
    service = _personal_document_generation_service(server)
    domain = _required_string(payload, "domain")
    scope_ref = {
        "scope": "user",
        "tenant_id": _required_string(payload, "tenant_id"),
        "user_id": _required_string(payload, "user_id"),
    }

    if action in {"summarize-wiki", "rewrite-wiki", "structure-wiki"}:
        source_document_ref = _personal_source_document_ref(payload, document_id=document_id)
        if action == "summarize-wiki":
            result = service.summarize_personal_document_to_wiki(
                domain=domain,
                scope_ref=scope_ref,
                source_document_ref=source_document_ref,
                profile_version=_required_string(payload, "profile_version"),
                model_profile=_required_string(payload, "model_profile"),
                save_target=_personal_wiki_save_target(payload),
                summary_style=_optional_string(payload, "summary_style") or "concise",
            )
            return _success_response(request_id, result)
        if action == "rewrite-wiki":
            result = service.rewrite_personal_document_to_wiki(
                domain=domain,
                scope_ref=scope_ref,
                source_document_ref=source_document_ref,
                profile_version=_required_string(payload, "profile_version"),
                model_profile=_required_string(payload, "model_profile"),
                save_target=_personal_wiki_save_target(payload),
                rewrite_goal=_optional_string(payload, "rewrite_goal") or "general",
            )
            return _success_response(request_id, result)
        result = service.structure_personal_document_to_wiki(
            domain=domain,
            scope_ref=scope_ref,
            source_document_ref=source_document_ref,
            profile_version=_required_string(payload, "profile_version"),
            model_profile=_required_string(payload, "model_profile"),
            save_target=_personal_wiki_save_target(payload),
            structure_template=_optional_string(payload, "structure_template") or "default",
        )
        return _success_response(request_id, result)

    _coerce_path_field(payload, "wiki_document_id", document_id)
    wiki_document_id = _required_string(payload, "wiki_document_id")
    wiki_document_version = _required_int(payload, "wiki_document_version")

    if action == "suggest-links":
        result = service.suggest_personal_wiki_links(
            domain=domain,
            scope_ref=scope_ref,
            wiki_document_id=wiki_document_id,
            wiki_document_version=wiki_document_version,
            profile_version=_required_string(payload, "profile_version"),
            model_profile=_required_string(payload, "model_profile"),
            max_suggestions=_optional_limit(payload, default=10, field="max_suggestions"),
        )
        return _success_response(request_id, result)
    if action == "attach-links":
        attachments = payload.get("attachments")
        if not isinstance(attachments, list):
            raise ValueError("attachments must be a list.")
        result = service.attach_personal_wiki_links(
            domain=domain,
            scope_ref=scope_ref,
            wiki_document_id=wiki_document_id,
            wiki_document_version=wiki_document_version,
            attachments=attachments,
        )
        return _success_response(request_id, result)
    raise ValueError(f"Unsupported personal document action: {action}")

def _dispatch_command_post(
    server: StrataWikiServer,
    *,
    request_id: str,
    headers: Mapping[str, str] | None,
    body: bytes,
) -> HttpRuntimeResponse:
    payload = _parse_json_object(body)
    name = _required_string(payload, "name")
    arguments = payload.get("arguments", {})
    if not isinstance(arguments, dict):
        raise ValueError("Command arguments must decode to an object when provided.")
    command_store = _http_command_store(server)
    command, status_code = command_store.submit(
        server,
        request_id=request_id,
        name=name,
        arguments=arguments,
        idempotency_key=_header_value(headers, "Idempotency-Key"),
    )
    command_id = str(command["command_id"])
    response_headers: dict[str, str] = {
        "X-Request-Id": request_id,
        "Location": f"/api/v1/commands/{command_id}",
    }
    if command["state"] == "queued":
        response_headers["Retry-After"] = "1"
    return HttpRuntimeResponse(
        status_code=int(status_code),
        payload={
            "ok": True,
            "request_id": request_id,
            "result": command,
        },
        headers=response_headers,
    )


def _get_command_status(server: StrataWikiServer, command_id: str) -> dict[str, object]:
    command_store = _http_command_store(server)
    command = command_store.get(command_id)
    return {
        "status": "ok",
        "command": command,
    }

def _call_tool(
    server: StrataWikiServer,
    *,
    request_id: str,
    tool_name: str,
    arguments: dict[str, object],
) -> HttpRuntimeResponse:
    result = server.call_tool(tool_name, arguments)
    return _success_response(request_id, result)


def _register_personal_asset(
    server: StrataWikiServer,
    *,
    request_id: str,
    arguments: dict[str, object],
) -> HttpRuntimeResponse:
    service = server.bootstrap.personal_asset_registration_service
    if service is None:
        raise ValueError("Personal asset registration service is not configured.")
    result = service.register_personal_asset(arguments)
    return _success_response(request_id, result)


def _personal_source_document_ref(payload: dict[str, object], *, document_id: str) -> dict[str, object]:
    source_document_ref = payload.get("source_document_ref")
    if source_document_ref is None:
        source_document_ref = {}
        payload["source_document_ref"] = source_document_ref
    if not isinstance(source_document_ref, dict):
        raise ValueError("Field 'source_document_ref' must be an object.")
    _coerce_path_field(source_document_ref, "document_id", document_id)
    _coerce_path_field(source_document_ref, "subspace", "raw")
    return source_document_ref


def _personal_wiki_save_target(payload: dict[str, object]) -> dict[str, object]:
    save_target = payload.get("save_target")
    if save_target is None:
        save_target = {}
        payload["save_target"] = save_target
    if not isinstance(save_target, dict):
        raise ValueError("Field 'save_target' must be an object.")
    _coerce_path_field(save_target, "subspace", "wiki")
    return save_target


def _required_int(payload: Mapping[str, object], field: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Field '{field}' must be an integer.")
    return value


def _optional_limit(payload: Mapping[str, object], *, default: int, field: str) -> int:
    value = payload.get(field)
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Field '{field}' must be an integer.")
    if value < 1:
        raise ValueError(f"Field '{field}' must be greater than zero.")
    return value


def _personal_document_generation_service(server: StrataWikiServer) -> Any:
    bootstrap = getattr(server, "bootstrap", None)
    service = getattr(bootstrap, "personal_document_generation_service", None)
    if service is None:
        raise ValueError("Personal document generation service is not configured.")
    return service


def _tool_error_response(request_id: str, exc: Exception) -> HttpRuntimeResponse:
    if hasattr(exc, "status_code") and hasattr(exc, "code"):
        status_code = getattr(exc, "status_code")
        code = getattr(exc, "code")
        details = getattr(exc, "details", None)
        if isinstance(status_code, int) and isinstance(code, str):
            return _error_response(
                request_id,
                status_code=HTTPStatus(status_code),
                code=code,
                message=str(exc),
                details=details if isinstance(details, dict) else None,
            )
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


def _http_command_store(server: StrataWikiServer) -> _HttpCommandStore:
    store = getattr(server, "_http_command_store", None)
    if store is None:
        store = _HttpCommandStore()
        setattr(server, "_http_command_store", store)
    if not isinstance(store, _HttpCommandStore):
        raise TypeError("HTTP command store has an unexpected type.")
    return store


def _header_value(headers: Mapping[str, str] | None, key: str) -> str | None:
    if headers is None:
        return None
    normalized = {str(header_key).lower(): str(value) for header_key, value in headers.items()}
    raw = normalized.get(key.lower())
    if raw is None:
        return None
    value = raw.strip()
    return value or None


def _required_string(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Field {field!r} must be a non-empty string.")
    return value.strip()


def _normalize_command_error(exc: Exception) -> tuple[dict[str, object], bool]:
    if hasattr(exc, "status_code") and hasattr(exc, "code"):
        status_code = getattr(exc, "status_code")
        code = getattr(exc, "code")
        details = getattr(exc, "details", None)
        retryable = bool(getattr(exc, "retryable", False))
        if isinstance(status_code, int) and isinstance(code, str):
            if not retryable:
                retryable = status_code >= 500
            error: dict[str, object] = {
                "code": code,
                "message": str(exc),
            }
            if isinstance(details, dict) and details:
                error["details"] = deepcopy(details)
            return error, retryable
    if isinstance(exc, ValueError):
        return (
            {
                "code": "validation_error",
                "message": str(exc),
                "details": {"type": exc.__class__.__name__},
            },
            False,
        )
    if isinstance(exc, KeyError):
        return (
            {
                "code": "not_found",
                "message": str(exc),
                "details": {"type": exc.__class__.__name__},
            },
            False,
        )
    return (
        {
            "code": "internal_error",
            "message": str(exc),
            "details": {"type": exc.__class__.__name__},
        },
        True,
    )


def _extract_command_job_reference(result: dict[str, object]) -> dict[str, object] | None:
    if "job_id" not in result:
        return None
    job: dict[str, object] = {"job_id": result["job_id"]}
    for key in ("event_id", "event_type", "execution_mode"):
        if key in result:
            job[key] = result[key]
    return job


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


def _utc_timestamp() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


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


def _required_string(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Field {key!r} must be a non-empty string.")
    return value.strip()


def _required_positive_int(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"Field {key!r} must be a positive integer.")
    return value


def _optional_string(payload: Mapping[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Field {key!r} must be a string when provided.")
    return value.strip()


def _optional_string_list(payload: Mapping[str, object], key: str) -> list[str] | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError(f"Field {key!r} must be a list when provided.")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"Field {key!r} must contain only strings.")
        result.append(item.strip())
    return result


def _optional_json_list(payload: Mapping[str, object], key: str) -> list[object] | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError(f"Field {key!r} must be a list when provided.")
    return list(value)


def _parse_personal_document_action_path(path: str) -> dict[str, str]:
    parts = [unquote(part).strip() for part in path.split("/") if part.strip()]
    if len(parts) != 8:
        raise ValueError("personal document action path must include exactly eight non-empty path parts.")
    if parts[:3] != ["api", "v1", "users"]:
        raise ValueError("personal document action path must start with /api/v1/users.")
    if parts[5] != "personal-documents":
        raise ValueError("personal document action path must include personal-documents.")
    return {
        "tenant_id": parts[3],
        "user_id": parts[4],
        "document_id": parts[6],
        "action": parts[7],
    }


def _personal_document_action_tool_name(action: str) -> str:
    mapping = {
        "summarize-wiki": "summarize_personal_document_to_wiki",
        "rewrite-wiki": "rewrite_personal_document_to_wiki",
        "structure-wiki": "structure_personal_document_to_wiki",
        "suggest-links": "suggest_personal_wiki_links",
        "attach-links": "attach_personal_wiki_links",
    }
    if action not in mapping:
        raise ValueError(f"Unsupported personal document action: {action}")
    return mapping[action]


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
