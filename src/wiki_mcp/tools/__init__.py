"""Thin tool registry for server bootstrap."""

from wiki_mcp.tools.defaults import (
    build_default_tool_definitions,
    build_default_tool_registry,
)
from wiki_mcp.tools.registry import (
    ToolArgument,
    ToolDefinition,
    ToolError,
    ToolField,
    ToolInvocationError,
    ToolRegistry,
    ToolResultField,
    ToolResultValidationError,
    ToolValidationError,
)

__all__ = [
    "ToolArgument",
    "ToolDefinition",
    "ToolError",
    "ToolField",
    "ToolInvocationError",
    "ToolRegistry",
    "ToolResultField",
    "ToolResultValidationError",
    "ToolValidationError",
    "build_default_tool_definitions",
    "build_default_tool_registry",
]
