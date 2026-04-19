from __future__ import annotations

from typing import Any

from wiki_mcp.http_runtime import dispatch_http_request
from wiki_mcp.tools import ToolDefinition


class FakeHttpServer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self._tools = [
            ToolDefinition(
                name="validate_domain_proposal_batch",
                group="fact",
                status="mvp",
                description="Validate one proposal batch.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": ["batch"],
                    "properties": {"batch": {"type": "object"}},
                },
            ),
            ToolDefinition(
                name="ingest_domain_proposal_batch",
                group="fact",
                status="mvp",
                description="Ingest one proposal batch.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": ["batch"],
                    "properties": {"batch": {"type": "object"}},
                },
            ),
            ToolDefinition(
                name="get_snapshot_status",
                group="snapshot",
                status="mvp",
                description="Return snapshot pointers.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": ["domain"],
                    "properties": {"domain": {"type": "string"}},
                },
            ),
            ToolDefinition(
                name="explode",
                group="admin",
                status="mvp",
                description="Raise an internal error.",
                entrypoint="server.call_tool",
                input_schema={"type": "object", "properties": {}},
            ),
        ]

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools)

    def export_tool_schemas(self) -> list[dict[str, object]]:
        return [tool.export_schema() for tool in self._tools]

    def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> dict[str, Any]:
        payload = dict(arguments or {})
        self.calls.append((name, payload))
        if name == "validate_domain_proposal_batch":
            batch = payload.get("batch")
            if not isinstance(batch, dict):
                raise ValueError("batch is required")
            return {
                "ok": True,
                "committed": False,
                "audit": {
                    "evaluated_pack_version": batch.get("pack_version") or "2026-04-18",
                },
            }
        if name == "ingest_domain_proposal_batch":
            batch = payload.get("batch")
            if not isinstance(batch, dict):
                raise ValueError("batch is required")
            return {
                "ok": True,
                "committed": True,
                "affected_fact_ids": ["fact:job_posting:EMP-1"],
                "audit": {
                    "evaluated_pack_version": batch.get("pack_version") or "2026-04-18",
                },
            }
        if name == "get_snapshot_status":
            domain = payload.get("domain")
            if not isinstance(domain, str) or not domain.strip():
                raise ValueError("domain is required")
            return {"status": "ok", "domain": domain}
        if name == "explode":
            raise RuntimeError("boom")
        raise KeyError(f"Unknown tool: {name}")


def test_http_runtime_health_and_readiness_return_success_envelopes() -> None:
    fake_server = FakeHttpServer()

    health = dispatch_http_request(
        fake_server,
        method="GET",
        path="/healthz",
        headers={"X-Request-Id": "req-health"},
        body=b"",
    )
    ready = dispatch_http_request(
        fake_server,
        method="GET",
        path="/readyz",
        headers={"X-Request-Id": "req-ready"},
        body=b"",
        ready_payload={"status": "ok", "bootstrap_tables_checked": True},
    )

    assert health.status_code == 200
    assert health.payload["ok"] is True
    assert health.payload["request_id"] == "req-health"
    assert health.payload["result"]["runtime"] == "stratawiki-http"
    assert health.headers["X-Request-Id"] == "req-health"

    assert ready.status_code == 200
    assert ready.payload["ok"] is True
    assert ready.payload["request_id"] == "req-ready"
    assert ready.payload["result"]["status"] == "ready"
    assert ready.payload["result"]["checks"]["bootstrap_tables_checked"] is True


def test_http_runtime_lists_tools_and_shows_one_tool() -> None:
    fake_server = FakeHttpServer()

    list_response = dispatch_http_request(
        fake_server,
        method="GET",
        path="/api/v1/tools",
        headers={},
        body=b"",
    )
    show_response = dispatch_http_request(
        fake_server,
        method="GET",
        path="/api/v1/tools/get_snapshot_status",
        headers={},
        body=b"",
    )

    assert list_response.status_code == 200
    assert list_response.payload["ok"] is True
    tool_names = [tool["name"] for tool in list_response.payload["result"]]
    assert "get_snapshot_status" in tool_names

    assert show_response.status_code == 200
    assert show_response.payload["ok"] is True
    assert show_response.payload["result"]["name"] == "get_snapshot_status"


def test_http_runtime_executes_tool_call_and_propagates_request_id() -> None:
    fake_server = FakeHttpServer()

    response = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/tool-calls",
        headers={"X-Request-Id": "req-123"},
        body=b'{"name":"get_snapshot_status","arguments":{"domain":"recruiting"}}',
    )

    assert response.status_code == 200
    assert response.payload["ok"] is True
    assert response.payload["request_id"] == "req-123"
    assert response.payload["result"] == {"status": "ok", "domain": "recruiting"}
    assert response.headers["X-Request-Id"] == "req-123"
    assert fake_server.calls == [("get_snapshot_status", {"domain": "recruiting"})]


def test_http_runtime_exposes_domain_proposal_validate_and_ingest_endpoints() -> None:
    fake_server = FakeHttpServer()
    payload = b'{"batch":{"batch_id":"jobs-wiki-batch-001","domain":"recruiting","producer":"jobs-wiki","pack_version":"2026-04-18","facts":[],"relations":[]}}'

    validate_response = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/domain-proposals/validate",
        headers={"X-Request-Id": "req-validate"},
        body=payload,
    )
    ingest_response = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/domain-proposals/ingest",
        headers={"X-Request-Id": "req-ingest"},
        body=payload,
    )

    assert validate_response.status_code == 200
    assert validate_response.payload["ok"] is True
    assert validate_response.payload["request_id"] == "req-validate"
    assert validate_response.payload["result"]["committed"] is False
    assert validate_response.payload["result"]["audit"]["evaluated_pack_version"] == "2026-04-18"

    assert ingest_response.status_code == 200
    assert ingest_response.payload["ok"] is True
    assert ingest_response.payload["request_id"] == "req-ingest"
    assert ingest_response.payload["result"]["committed"] is True
    assert "fact:job_posting:EMP-1" in ingest_response.payload["result"]["affected_fact_ids"]

    assert fake_server.calls == [
        (
            "validate_domain_proposal_batch",
            {
                "batch": {
                    "batch_id": "jobs-wiki-batch-001",
                    "domain": "recruiting",
                    "producer": "jobs-wiki",
                    "pack_version": "2026-04-18",
                    "facts": [],
                    "relations": [],
                }
            },
        ),
        (
            "ingest_domain_proposal_batch",
            {
                "batch": {
                    "batch_id": "jobs-wiki-batch-001",
                    "domain": "recruiting",
                    "producer": "jobs-wiki",
                    "pack_version": "2026-04-18",
                    "facts": [],
                    "relations": [],
                }
            },
        ),
    ]


def test_http_runtime_requires_bearer_token_when_configured() -> None:
    fake_server = FakeHttpServer()

    unauthorized = dispatch_http_request(
        fake_server,
        method="GET",
        path="/api/v1/tools",
        headers={},
        body=b"",
        auth_token="secret-token",
    )
    authorized = dispatch_http_request(
        fake_server,
        method="GET",
        path="/api/v1/tools",
        headers={"Authorization": "Bearer secret-token"},
        body=b"",
        auth_token="secret-token",
    )
    health = dispatch_http_request(
        fake_server,
        method="GET",
        path="/healthz",
        headers={},
        body=b"",
        auth_token="secret-token",
    )

    assert unauthorized.status_code == 401
    assert unauthorized.payload["ok"] is False
    assert unauthorized.payload["error"]["code"] == "unauthorized"
    assert unauthorized.headers["WWW-Authenticate"] == "Bearer"

    assert authorized.status_code == 200
    assert authorized.payload["ok"] is True

    assert health.status_code == 200
    assert health.payload["ok"] is True


def test_http_runtime_maps_validation_and_lookup_errors() -> None:
    fake_server = FakeHttpServer()

    invalid = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/tool-calls",
        headers={},
        body=b'{"name":"get_snapshot_status","arguments":{}}',
    )
    missing = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/tool-calls",
        headers={},
        body=b'{"name":"unknown_tool","arguments":{}}',
    )

    assert invalid.status_code == 422
    assert invalid.payload["ok"] is False
    assert invalid.payload["error"]["code"] == "validation_error"

    assert missing.status_code == 404
    assert missing.payload["ok"] is False
    assert missing.payload["error"]["code"] == "not_found"


def test_http_runtime_maps_internal_errors_and_method_mismatch() -> None:
    fake_server = FakeHttpServer()

    internal = dispatch_http_request(
        fake_server,
        method="POST",
        path="/api/v1/tool-calls",
        headers={},
        body=b'{"name":"explode","arguments":{}}',
    )
    wrong_method = dispatch_http_request(
        fake_server,
        method="POST",
        path="/healthz",
        headers={},
        body=b"",
    )

    assert internal.status_code == 500
    assert internal.payload["ok"] is False
    assert internal.payload["error"]["code"] == "internal_error"

    assert wrong_method.status_code == 405
    assert wrong_method.payload["ok"] is False
    assert wrong_method.payload["error"]["code"] == "method_not_allowed"
    assert wrong_method.headers["Allow"] == "GET"
