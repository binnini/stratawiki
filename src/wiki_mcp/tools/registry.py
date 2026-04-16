from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal


ToolHandler = Callable[[Mapping[str, Any]], object]
ToolStatus = Literal["available", "placeholder"]
ToolGroup = Literal[
    "ingestion",
    "page_reads",
    "retrieval",
    "fact",
    "interpretation",
    "personal",
]


@dataclass(frozen=True, slots=True)
class ToolArgument:
    """Thin input contract metadata for one tool argument."""

    name: str
    value_type: str
    description: str
    required: bool = True


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Thin internal tool descriptor used by the bootstrap server slice."""

    name: str
    description: str
    group: ToolGroup
    entrypoint: str | None = None
    arguments: tuple[ToolArgument, ...] = ()
    status: ToolStatus = "available"
    handler: ToolHandler | None = None


class ToolRegistry:
    """Local tool registry for wiring entrypoints before MCP transport exists."""

    def __init__(self, definitions: list[ToolDefinition]) -> None:
        self._definitions: dict[str, ToolDefinition] = {}
        for definition in definitions:
            if definition.name in self._definitions:
                raise ValueError(f"Duplicate tool registration: {definition.name}")
            self._definitions[definition.name] = definition

    def list_tools(self) -> list[ToolDefinition]:
        return sorted(
            self._definitions.values(),
            key=lambda definition: (definition.group, definition.name),
        )

    def list_tools_by_group(self) -> dict[ToolGroup, list[ToolDefinition]]:
        grouped: dict[ToolGroup, list[ToolDefinition]] = {}
        for definition in self.list_tools():
            grouped.setdefault(definition.group, []).append(definition)
        return grouped

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
