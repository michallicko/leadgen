"""Tool adapter: converts ToolRegistry definitions to LangGraph-compatible format.

The existing tool registry (api/services/tool_registry.py) stores tools as
ToolDefinition dataclasses with handler functions. This module provides adapters
to use them within LangGraph while preserving the existing registration pattern.

Phase-filtered tool routing is handled by prompts.filter_tools_for_phase().
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ..services.tool_registry import ToolContext, get_tool, get_tools_for_api

logger = logging.getLogger(__name__)

# Per-turn rate limits by tool name. Tools not listed here get the default.
TOOL_RATE_LIMITS: dict[str, int] = {
    "web_search": 5,
}
DEFAULT_TOOL_RATE_LIMIT = 15  # max calls per tool per turn


def execute_tool_call(
    tool_name: str,
    tool_input: dict[str, Any],
    tool_context_dict: dict[str, Any],
    app: Any = None,
) -> dict[str, Any]:
    """Execute a single tool call using the existing ToolRegistry.

    Args:
        tool_name: Name of the tool to execute.
        tool_input: Input arguments for the tool.
        tool_context_dict: Dict with tenant_id, user_id, document_id, turn_id.
        app: Flask app for DB access.

    Returns:
        Dict with keys: output, is_error, error_message, duration_ms.
    """
    start = time.monotonic()

    tool_def = get_tool(tool_name)
    if tool_def is None:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "output": None,
            "is_error": True,
            "error_message": "Unknown tool: {}".format(tool_name),
            "duration_ms": elapsed_ms,
        }

    # Build ToolContext from dict
    ctx = ToolContext(
        tenant_id=tool_context_dict.get("tenant_id", ""),
        user_id=tool_context_dict.get("user_id"),
        document_id=tool_context_dict.get("document_id"),
        turn_id=tool_context_dict.get("turn_id"),
    )

    try:
        if app is not None:
            with app.app_context():
                result = tool_def.handler(tool_input, ctx)
        else:
            result = tool_def.handler(tool_input, ctx)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "output": result,
            "is_error": False,
            "error_message": None,
            "duration_ms": elapsed_ms,
        }
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.exception("Tool '%s' failed: %s", tool_name, exc)
        return {
            "output": None,
            "is_error": True,
            "error_message": str(exc),
            "duration_ms": elapsed_ms,
        }


def get_phase_filtered_tools(phase: str) -> list[dict[str, Any]]:
    """Get tool definitions filtered for the current phase.

    Combines get_tools_for_api() with phase filtering.

    Args:
        phase: Current playbook phase.

    Returns:
        List of tool definitions in Claude API format.
    """
    from .prompts import filter_tools_for_phase

    all_tools = get_tools_for_api()
    return filter_tools_for_phase(all_tools, phase)


def summarize_tool_output(tool_name: str, output: Any) -> str:
    """Generate a human-readable summary of tool output.

    Args:
        tool_name: Name of the tool.
        output: Tool output dict or None.

    Returns:
        Summary string.
    """
    if not output:
        return "Completed {}".format(tool_name)

    if isinstance(output, dict) and "summary" in output:
        return str(output["summary"])

    return "Completed {}".format(tool_name)


def truncate_output(text: str, max_len: int = 2048) -> str:
    """Truncate a string with an ellipsis marker."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
