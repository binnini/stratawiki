"""Thin tool registry for server bootstrap."""

from wiki_mcp.tools.defaults import build_default_tool_registry
from wiki_mcp.tools.registry import ToolDefinition, ToolRegistry

__all__ = [
    "ToolDefinition",
    "ToolRegistry",
    "build_default_tool_registry",
]
