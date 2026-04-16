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
TOOL_SCHEMA_VERSION = "bootstrap.v1"


class ToolValidationError(ValueError):
    """Raised when tool arguments do not satisfy the thin input contract."""


class ToolResultValidationError(ValueError):
    """Raised when a tool result does not satisfy the declared contract."""


@dataclass(frozen=True, slots=True)
class ToolField:
    """Thin schema field that can be used for inputs, outputs, and nested objects."""

    name: str
    value_type: str
    description: str
    required: bool = True
    fields: tuple["ToolField", ...] = ()


@dataclass(frozen=True, slots=True)
class ToolError:
    """Structured error contract for one tool."""

    code: str
    description: str


class ToolInvocationError(RuntimeError):
    """Structured tool invocation error that can be surfaced by a transport later."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


@dataclass(frozen=True, slots=True)
class ToolArgument(ToolField):
    """Thin input contract metadata for one tool argument."""


@dataclass(frozen=True, slots=True)
class ToolResultField(ToolField):
    """Thin output contract metadata for one tool result field."""


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Thin internal tool descriptor used by the bootstrap server slice."""

    name: str
    description: str
    group: ToolGroup
    entrypoint: str | None = None
    arguments: tuple[ToolArgument, ...] = ()
    result_fields: tuple[ToolResultField, ...] = ()
    errors: tuple[ToolError, ...] = ()
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
        try:
            self._validate_arguments(definition, normalized_arguments)
            result = definition.handler(normalized_arguments)
            self._validate_result(definition, result)
        except ToolInvocationError:
            raise
        except ToolValidationError as exc:
            raise ToolInvocationError(
                code="invalid_arguments",
                message=str(exc),
                details={"tool": definition.name},
            ) from exc
        except ToolResultValidationError as exc:
            raise ToolInvocationError(
                code="invalid_result",
                message=str(exc),
                details={"tool": definition.name},
            ) from exc
        return result

    def call_tool_with_envelope(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> dict[str, object]:
        try:
            result = self.call_tool(name, arguments)
        except ToolInvocationError as exc:
            return {"ok": False, "error": exc.to_dict()}
        return {"ok": True, "result": result}

    def _validate_arguments(
        self,
        definition: ToolDefinition,
        arguments: Mapping[str, Any],
    ) -> None:
        self._validate_fields(
            tool_name=definition.name,
            fields=definition.arguments,
            payload=arguments,
            error_type=ToolValidationError,
            context="argument",
        )

    def _validate_result(self, definition: ToolDefinition, result: object) -> None:
        if not definition.result_fields:
            return
        if not isinstance(result, Mapping):
            raise ToolResultValidationError(
                f"Tool {definition.name!r} must return an object result, "
                f"got {type(result).__name__}."
            )
        self._validate_fields(
            tool_name=definition.name,
            fields=definition.result_fields,
            payload=result,
            error_type=ToolResultValidationError,
            context="result field",
        )

    def _validate_fields(
        self,
        *,
        tool_name: str,
        fields: tuple[ToolField, ...],
        payload: Mapping[str, Any],
        error_type: type[Exception],
        context: str,
    ) -> None:
        for field in fields:
            _validate_field(
                tool_name=tool_name,
                field=field,
                payload=payload,
                error_type=error_type,
                context=context,
            )

    def _export_tool_schema(self, definition: ToolDefinition) -> dict[str, object]:
        return {
            "schema_version": TOOL_SCHEMA_VERSION,
            "name": definition.name,
            "description": definition.description,
            "group": definition.group,
            "entrypoint": definition.entrypoint,
            "status": definition.status,
            "arguments": [_export_field(argument) for argument in definition.arguments],
            "result": [_export_field(field) for field in definition.result_fields],
            "error_contract": {
                "type": "object",
                "fields": [
                    _export_field(
                        ToolField("code", "string", "Stable tool error code."),
                    ),
                    _export_field(
                        ToolField("message", "string", "Human-readable error message."),
                    ),
                    _export_field(
                        ToolField("details", "object", "Additional structured error details.", required=False),
                    ),
                ],
                "codes": [
                    {"code": error.code, "description": error.description}
                    for error in definition.errors
                ],
            },
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


def _validate_field(
    *,
    tool_name: str,
    field: ToolField,
    payload: Mapping[str, Any],
    error_type: type[Exception],
    context: str,
) -> None:
    if field.required and field.name not in payload:
        raise error_type(
            f"Tool {tool_name!r} requires {context} {field.name!r}."
        )

    if field.name not in payload:
        return

    value = payload[field.name]
    if value is None:
        if field.required:
            raise error_type(
                f"Tool {tool_name!r} requires non-null {context} {field.name!r}."
            )
        return

    if not _matches_value_type(value, field.value_type):
        raise error_type(
            f"Tool {tool_name!r} expected {context} {field.name!r} "
            f"to be {field.value_type}, got {type(value).__name__}."
        )

    if field.fields and isinstance(value, Mapping):
        for nested_field in field.fields:
            _validate_field(
                tool_name=tool_name,
                field=nested_field,
                payload=value,
                error_type=error_type,
                context=f"nested field {field.name}",
            )


def _export_field(field: ToolField) -> dict[str, object]:
    exported = {
        "name": field.name,
        "type": field.value_type,
        "description": field.description,
        "required": field.required,
    }
    if field.fields:
        exported["fields"] = [_export_field(nested_field) for nested_field in field.fields]
    return exported
