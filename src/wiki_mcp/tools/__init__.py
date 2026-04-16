"""Thin tool registry for server bootstrap."""

from wiki_mcp.tools.defaults import (
    build_default_tool_definitions,
    build_default_tool_registry,
)
from wiki_mcp.tools.registry import (
    ToolArgument,
    ToolDefinition,
    ToolRegistry,
    ToolResultField,
    ToolValidationError,
)

__all__ = [
    "ToolArgument",
    "ToolDefinition",
    "ToolRegistry",
    "ToolResultField",
    "ToolValidationError",
    "build_default_tool_definitions",
    "build_default_tool_registry",
]
