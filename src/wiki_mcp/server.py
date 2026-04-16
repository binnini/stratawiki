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

    def list_tools_by_group(self) -> dict[str, list[ToolDefinition]]:
        return self.tools.list_tools_by_group()

    def export_tool_schemas(self) -> list[dict[str, object]]:
        return self.tools.export_tool_schemas()

    def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> object:
        return self.tools.call_tool(name, arguments)

    def call_tool_with_envelope(
        self,
        name: str,
        arguments: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return self.tools.call_tool_with_envelope(name, arguments)

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
            retrieval_read_entrypoint=bootstrap.entrypoints.retrieval_reads,
            personal_query_entrypoint=bootstrap.entrypoints.personal_queries,
        ),
    )


def main() -> None:
    """Build the thin server runtime and report what is wired today."""
    server = build_server()
    try:
        print("StrataWiki server bootstrap ready.")
        for group, definitions in server.list_tools_by_group().items():
            tool_summary = ", ".join(
                f"{tool.name}[{tool.status}]"
                for tool in definitions
            )
            print(f"{group}: {tool_summary}")
        print(f"Public tool schemas: {len(server.export_tool_schemas())}")
        print("MCP transport/runtime remains unimplemented in this slice.")
    finally:
        server.close()
