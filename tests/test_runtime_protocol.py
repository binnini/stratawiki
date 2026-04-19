from __future__ import annotations

import json
from io import StringIO
from typing import Any

from wiki_mcp.cli import run_cli
from wiki_mcp.tools import ToolDefinition


class FakeServeServer:
    def __init__(self) -> None:
        self.closed = False
        self.calls: list[tuple[str, dict[str, object] | None]] = []
        self._tools = [
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
                name="query_personal_knowledge",
                group="personal",
                status="mvp",
                description="Run the Personal query flow.",
                entrypoint="server.call_tool",
                input_schema={
                    "type": "object",
                    "required": ["domain", "tenant_id", "user_id", "question"],
                    "properties": {},
                },
            ),
        ]

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools)

    def export_tool_schemas(self) -> list[dict[str, object]]:
        return [tool.export_schema() for tool in self._tools]

    def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> dict[str, Any]:
        self.calls.append((name, arguments))
        if name == "get_snapshot_status":
            return {
                "status": "ok",
                "domain": arguments["domain"] if arguments is not None else None,
            }
        raise KeyError(f"Unknown tool: {name}")

    def close(self) -> None:
        self.closed = True


def test_serve_cli_processes_long_lived_runtime_requests() -> None:
    fake_server = FakeServeServer()
    stdin = StringIO(
        "\n".join(
            [
                json.dumps({"id": "req-1", "method": "health"}),
                json.dumps({"id": "req-2", "method": "list_tools"}),
                json.dumps(
                    {
                        "id": "req-3",
                        "method": "show_tool",
                        "params": {"name": "get_snapshot_status"},
                    }
                ),
                json.dumps(
                    {
                        "id": "req-4",
                        "method": "call_tool",
                        "params": {
                            "name": "get_snapshot_status",
                            "arguments": {"domain": "recruiting"},
                        },
                    }
                ),
                json.dumps({"id": "req-5", "method": "shutdown"}),
                "",
            ]
        )
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli(
        ["serve"],
        server_factory=lambda **kwargs: fake_server,
        runtime_validator=lambda **kwargs: {"status": "ok"},
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
    )

    responses = [json.loads(line) for line in stdout.getvalue().splitlines()]

    assert exit_code == 0
    assert [response["id"] for response in responses] == [
        "req-1",
        "req-2",
        "req-3",
        "req-4",
        "req-5",
    ]
    assert responses[0]["ok"] is True
    assert responses[0]["result"]["runtime"] == "stratawiki-stdio"
    assert responses[1]["result"][0]["name"] == "get_snapshot_status"
    assert responses[2]["result"]["name"] == "get_snapshot_status"
    assert responses[3]["result"] == {"domain": "recruiting", "status": "ok"}
    assert responses[4]["result"]["message"] == "Shutting down StrataWiki stdio runtime."
    assert fake_server.calls == [("get_snapshot_status", {"domain": "recruiting"})]
    assert fake_server.closed is True
    assert stderr.getvalue() == ""


def test_serve_cli_emits_structured_request_errors_and_keeps_running() -> None:
    fake_server = FakeServeServer()
    stdin = StringIO(
        "\n".join(
            [
                "not-json",
                json.dumps(
                    {
                        "id": "req-1",
                        "method": "call_tool",
                        "params": {"name": 17},
                    }
                ),
                json.dumps({"id": "req-2", "method": "shutdown"}),
                "",
            ]
        )
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli(
        ["serve"],
        server_factory=lambda **kwargs: fake_server,
        runtime_validator=lambda **kwargs: {"status": "ok"},
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
    )

    responses = [json.loads(line) for line in stdout.getvalue().splitlines()]

    assert exit_code == 0
    assert responses[0]["ok"] is False
    assert responses[0]["error"]["code"] == "invalid_json"
    assert responses[1]["ok"] is False
    assert responses[1]["error"]["code"] == "invalid_request"
    assert responses[2]["ok"] is True
    assert responses[2]["result"]["status"] == "ok"
    assert fake_server.closed is True
    assert stderr.getvalue() == ""
