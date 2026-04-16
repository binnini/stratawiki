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


class ToolValidationError(ValueError):
    """Raised when tool arguments do not satisfy the thin input contract."""


@dataclass(frozen=True, slots=True)
class ToolArgument:
    """Thin input contract metadata for one tool argument."""

    name: str
    value_type: str
    description: str
    required: bool = True


@dataclass(frozen=True, slots=True)
class ToolResultField:
    """Thin output contract metadata for one tool result field."""

    name: str
    value_type: str
    description: str


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Thin internal tool descriptor used by the bootstrap server slice."""

    name: str
    description: str
    group: ToolGroup
    entrypoint: str | None = None
    arguments: tuple[ToolArgument, ...] = ()
    result_fields: tuple[ToolResultField, ...] = ()
    error_codes: tuple[str, ...] = ()
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

    def export_tool_schemas(self) -> list[dict[str, object]]:
        return [self._export_tool_schema(definition) for definition in self.list_tools()]

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
        normalized_arguments = arguments or {}
        self._validate_arguments(definition, normalized_arguments)
        return definition.handler(normalized_arguments)

    def _validate_arguments(
        self,
        definition: ToolDefinition,
        arguments: Mapping[str, Any],
    ) -> None:
        for argument in definition.arguments:
            if argument.required and argument.name not in arguments:
                raise ToolValidationError(
                    f"Tool {definition.name!r} requires argument {argument.name!r}."
                )

            if argument.name not in arguments:
                continue

            value = arguments[argument.name]
            if value is None:
                if argument.required:
                    raise ToolValidationError(
                        f"Tool {definition.name!r} requires non-null argument {argument.name!r}."
                    )
                continue

            if not _matches_value_type(value, argument.value_type):
                raise ToolValidationError(
                    "Tool "
                    f"{definition.name!r} expected argument {argument.name!r} "
                    f"to be {argument.value_type}, got {type(value).__name__}."
                )

    def _export_tool_schema(self, definition: ToolDefinition) -> dict[str, object]:
        return {
            "name": definition.name,
            "description": definition.description,
            "group": definition.group,
            "entrypoint": definition.entrypoint,
            "status": definition.status,
            "arguments": [
                {
                    "name": argument.name,
                    "type": argument.value_type,
                    "description": argument.description,
                    "required": argument.required,
                }
                for argument in definition.arguments
            ],
            "result": [
                {
                    "name": field.name,
                    "type": field.value_type,
                    "description": field.description,
                }
                for field in definition.result_fields
            ],
            "error_codes": list(definition.error_codes),
        }


def _matches_value_type(value: object, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "object":
        return isinstance(value, Mapping)
    if expected_type == "array":
        return isinstance(value, list)
    return True
