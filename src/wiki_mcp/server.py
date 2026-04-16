from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from psycopg import Connection

from wiki_mcp.bootstrap import BootstrapContext, bootstrap_application
from wiki_mcp.tools import ToolDefinition, ToolRegistry, build_default_tool_registry


@dataclass(slots=True)
class StrataWikiServer:
    """Minimal server bootstrap that wires entrypoints and tool handlers."""

    bootstrap: BootstrapContext
    tools: ToolRegistry

    def list_tools(self) -> list[ToolDefinition]:
        return self.tools.list_tools()

    def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> object:
        return self.tools.call_tool(name, arguments)

    def close(self) -> None:
        self.bootstrap.close()


def build_server(
    *,
    connection: Connection[dict] | None = None,
    database_url: str | None = None,
    render_root: str | Path = Path("data"),
) -> StrataWikiServer:
    bootstrap = bootstrap_application(
        connection=connection,
        database_url=database_url,
        render_root=render_root,
    )
    return StrataWikiServer(
        bootstrap=bootstrap,
        tools=build_default_tool_registry(
            ingestion_entrypoint=bootstrap.entrypoints.ingestion,
            page_read_entrypoint=bootstrap.entrypoints.page_reads,
        ),
    )


def main() -> None:
    """Build the thin server runtime and report what is wired today."""
    server = build_server()
    try:
        available = [tool.name for tool in server.list_tools() if tool.status == "available"]
        placeholders = [
            tool.name for tool in server.list_tools() if tool.status == "placeholder"
        ]
        print("StrataWiki server bootstrap ready.")
        print(f"Wired tools: {', '.join(available)}")
        print(f"Placeholder tool contracts: {', '.join(placeholders)}")
        print("MCP transport/runtime remains unimplemented in this slice.")
    finally:
        server.close()
