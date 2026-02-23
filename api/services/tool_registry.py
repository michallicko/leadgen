"""Tool registry for the AI agent.

Manages tool definitions that are passed to the Claude API as the `tools`
parameter. Each tool has a handler function that executes the action and
returns a JSON-serializable result.

AGENT owns the framework only. Tool definitions (strategy tools, search tools,
etc.) are registered by their respective feature modules at app startup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class ToolContext:
    """Execution context passed to every tool handler."""

    tenant_id: str
    user_id: Optional[str] = None
    document_id: Optional[str] = None


@dataclass
class ToolDefinition:
    """A registered tool available to the AI.

    Attributes:
        name: Unique tool name (e.g., "get_strategy").
        description: Human-readable description for Claude.
        input_schema: JSON Schema for the tool's parameters.
        handler: Function that executes the tool.
            Signature: (args: dict, context: ToolContext) -> dict
        requires_confirmation: If True, frontend should show a confirmation
            dialog before executing. NOT implemented in Sprint 2.
    """

    name: str
    description: str
    input_schema: dict
    handler: Callable[[dict, ToolContext], dict]
    requires_confirmation: bool = False


# Global registry -- populated at import time by feature modules
TOOL_REGISTRY: dict[str, ToolDefinition] = {}


def register_tool(tool: ToolDefinition) -> None:
    """Register a tool definition in the global registry.

    Raises:
        ValueError: If a tool with the same name is already registered.
    """
    if tool.name in TOOL_REGISTRY:
        raise ValueError(
            "Tool '{}' is already registered".format(tool.name)
        )
    TOOL_REGISTRY[tool.name] = tool


def unregister_tool(name: str) -> None:
    """Remove a tool from the registry. Mainly used in tests."""
    TOOL_REGISTRY.pop(name, None)


def get_tool(name: str) -> Optional[ToolDefinition]:
    """Look up a tool by name. Returns None if not found."""
    return TOOL_REGISTRY.get(name)


def get_tools_for_api() -> list[dict]:
    """Return tool definitions in Claude API format.

    Returns a list of dicts matching the Claude Messages API `tools` schema:
    [{"name": ..., "description": ..., "input_schema": ...}, ...]
    """
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.input_schema,
        }
        for t in TOOL_REGISTRY.values()
    ]


def clear_registry() -> None:
    """Clear all registered tools. Used in tests."""
    TOOL_REGISTRY.clear()
