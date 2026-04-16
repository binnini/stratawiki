from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal


ToolHandler = Callable[[Mapping[str, Any]], object]
ToolStatus = Literal["available", "placeholder"]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Thin internal tool descriptor used by the bootstrap server slice."""

    name: str
    description: str
    status: ToolStatus = "available"
    handler: ToolHandler | None = None


class ToolRegistry:
    """Local tool registry for wiring entrypoints before MCP transport exists."""

    def __init__(self, definitions: list[ToolDefinition]) -> None:
        self._definitions = {definition.name: definition for definition in definitions}

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._definitions.values())

    def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> object:
        definition = self._definitions.get(name)
        if definition is None:
            raise KeyError(f"Unknown tool: {name}")
        if definition.handler is None:
            raise NotImplementedError(
                f"Tool {name!r} is registered as a placeholder and is not wired yet."
            )
        return definition.handler(arguments or {})
