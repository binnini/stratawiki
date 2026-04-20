from __future__ import annotations

import json
from typing import Any, TextIO

from wiki_mcp.server import StrataWikiServer


RUNTIME_PROTOCOL_VERSION = "2026-04-19"


class RuntimeProtocolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def list_tools_payload(
    server: StrataWikiServer,
    *,
    group: str | None,
    full_schemas: bool,
) -> object:
    if full_schemas:
        schemas = server.export_tool_schemas()
        if group is None:
            return schemas
        return [schema for schema in schemas if schema["group"] == group]

    tools = [
        {
            "name": tool.name,
            "group": tool.group,
            "status": tool.status,
            "description": tool.description,
            "entrypoint": tool.entrypoint,
            **({"contract_status": tool.contract_status} if tool.contract_status is not None else {}),
            **(
                {"recommended_for_external_clients": tool.recommended_for_external_clients}
                if tool.recommended_for_external_clients is not None
                else {}
            ),
        }
        for tool in server.list_tools()
    ]
    if group is None:
        return tools
    return [tool for tool in tools if tool["group"] == group]


def show_tool_payload(server: StrataWikiServer, name: str) -> dict[str, object]:
    for schema in server.export_tool_schemas():
        if schema["name"] == name:
            return schema
    raise KeyError(f"Unknown tool: {name}")


def run_stdio_runtime(
    server: StrataWikiServer,
    *,
    stdin: TextIO,
    stdout: TextIO,
) -> int:
    for raw_line in stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            raw_request = json.loads(line)
        except json.JSONDecodeError as exc:
            _write_json_line(
                stdout,
                _error_response(
                    None,
                    code="invalid_json",
                    message=f"Failed to parse runtime request JSON: {exc}",
                ),
            )
            continue

        response, should_exit = _handle_runtime_request(server, raw_request)
        _write_json_line(stdout, response)
        if should_exit:
            return 0
    return 0


def _handle_runtime_request(
    server: StrataWikiServer,
    raw_request: object,
) -> tuple[dict[str, object], bool]:
    request_id = None
    try:
        if not isinstance(raw_request, dict):
            raise RuntimeProtocolError("invalid_request", "Runtime request must decode to an object.")

        request_id = raw_request.get("id")
        method = raw_request.get("method")
        if not isinstance(method, str) or not method.strip():
            raise RuntimeProtocolError("invalid_request", "Runtime request requires a non-empty string method.")

        params = raw_request.get("params", {})
        if not isinstance(params, dict):
            raise RuntimeProtocolError("invalid_request", "Runtime request params must decode to an object.")

        normalized_method = method.strip()
        if normalized_method == "health":
            return _success_response(
                request_id,
                {
                    "status": "ok",
                    "runtime": "stratawiki-stdio",
                    "protocol_version": RUNTIME_PROTOCOL_VERSION,
                    "tool_count": len(server.list_tools()),
                },
            ), False

        if normalized_method == "list_tools":
            group = _optional_string(params, "group")
            full_schemas = _optional_bool(params, "schemas", default=False)
            return _success_response(
                request_id,
                list_tools_payload(server, group=group, full_schemas=full_schemas),
            ), False

        if normalized_method == "show_tool":
            name = _required_string(params, "name")
            return _success_response(request_id, show_tool_payload(server, name)), False

        if normalized_method == "call_tool":
            name = _required_string(params, "name")
            arguments = params.get("arguments", {})
            if not isinstance(arguments, dict):
                raise RuntimeProtocolError(
                    "invalid_request",
                    "call_tool arguments must decode to an object when provided.",
                )
            try:
                result = server.call_tool(name, arguments)
            except Exception as exc:
                return _error_response(
                    request_id,
                    code="tool_error",
                    message=str(exc),
                    details={"type": exc.__class__.__name__},
                ), False
            return _success_response(request_id, result), False

        if normalized_method == "shutdown":
            return _success_response(
                request_id,
                {
                    "status": "ok",
                    "message": "Shutting down StrataWiki stdio runtime.",
                },
            ), True

        raise RuntimeProtocolError(
            "unknown_method",
            f"Unsupported runtime method: {normalized_method}",
        )
    except RuntimeProtocolError as exc:
        return _error_response(request_id, code=exc.code, message=exc.message), False
    except Exception as exc:
        return _error_response(
            request_id,
            code="internal_error",
            message=str(exc),
            details={"type": exc.__class__.__name__},
        ), False


def _success_response(request_id: object, result: object) -> dict[str, object]:
    return {
        "id": request_id,
        "ok": True,
        "protocol_version": RUNTIME_PROTOCOL_VERSION,
        "result": result,
    }


def _error_response(
    request_id: object,
    *,
    code: str,
    message: str,
    details: dict[str, object] | None = None,
) -> dict[str, object]:
    error = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {
        "id": request_id,
        "ok": False,
        "protocol_version": RUNTIME_PROTOCOL_VERSION,
        "error": error,
    }


def _required_string(payload: dict[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeProtocolError(
            "invalid_request",
            f"Runtime request field {field!r} must be a non-empty string.",
        )
    return value.strip()


def _optional_string(payload: dict[str, object], field: str) -> str | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise RuntimeProtocolError(
            "invalid_request",
            f"Runtime request field {field!r} must be a non-empty string when provided.",
        )
    return value.strip()


def _optional_bool(payload: dict[str, object], field: str, *, default: bool) -> bool:
    value = payload.get(field)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise RuntimeProtocolError(
            "invalid_request",
            f"Runtime request field {field!r} must be a boolean when provided.",
        )
    return value


def _write_json_line(stream: TextIO, payload: object) -> None:
    json.dump(payload, stream, sort_keys=True)
    stream.write("\n")
