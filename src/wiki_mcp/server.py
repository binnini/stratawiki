from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wiki_mcp.bootstrap import BootstrapContext, bootstrap_application


@dataclass(slots=True)
class StrataWikiServer:
    """Thin runtime shell for the migration stage.

    Tool wiring and orchestration are intentionally deferred until the new
    service boundaries are rebuilt from the current specs.
    """

    bootstrap: BootstrapContext

    def list_tools(self) -> list[dict[str, object]]:
        return []

    def list_tools_by_group(self) -> dict[str, list[dict[str, object]]]:
        return {}

    def export_tool_schemas(self) -> list[dict[str, object]]:
        return []

    def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> object:
        raise NotImplementedError(
            "Tool execution is not wired in the current migration stage."
        )

    def call_tool_with_envelope(
        self,
        name: str,
        arguments: dict[str, object] | None = None,
    ) -> dict[str, object]:
        try:
            result = self.call_tool(name, arguments)
        except Exception as exc:
            return {
                "ok": False,
                "error": exc.__class__.__name__,
                "message": str(exc),
            }
        return {"ok": True, "result": result}

    def close(self) -> None:
        self.bootstrap.close()


def build_server(
    *,
    connection: Any | None = None,
    database_url: str | None = None,
) -> StrataWikiServer:
    bootstrap = bootstrap_application(
        connection=connection,
        database_url=database_url,
    )
    return StrataWikiServer(bootstrap=bootstrap)


def main() -> None:
    server = build_server()
    try:
        print("StrataWiki migration bootstrap ready.")
        print("No MCP tools are wired yet in this migration stage.")
    finally:
        server.close()
