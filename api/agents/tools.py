"""Bridge between existing tool_registry handlers and LangGraph tools.

Wraps each ToolDefinition from the tool_registry into a LangGraph-compatible
tool using langchain_core's StructuredTool. This allows the existing tool
handlers to work within LangGraph without modification.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import StructuredTool

from ..services.tool_registry import TOOL_REGISTRY, ToolContext

logger = logging.getLogger(__name__)


def _make_handler(tool_def, tool_context_holder: list):
    """Create a handler function that bridges ToolDefinition to LangGraph.

    The tool_context_holder is a mutable list containing a single ToolContext
    object, set by the graph before tool execution. This avoids closure issues
    with mutable state.
    """

    def handler(**kwargs) -> str:
        ctx = (
            tool_context_holder[0]
            if tool_context_holder
            else ToolContext(tenant_id="")
        )
        try:
            result = tool_def.handler(kwargs, ctx)
            return json.dumps(result)
        except Exception as exc:
            logger.exception("Tool '%s' failed: %s", tool_def.name, exc)
            return json.dumps({"error": str(exc)})

    handler.__name__ = tool_def.name
    handler.__doc__ = tool_def.description
    return handler


def build_langchain_tools(
    tool_context_holder: list,
    app=None,
) -> list[StructuredTool]:
    """Convert all registered tools into LangGraph-compatible StructuredTools.

    Args:
        tool_context_holder: A mutable list containing a single ToolContext.
            Updated before each tool execution to carry tenant/user/doc context.
        app: Flask app for app context when running in SSE generator.

    Returns:
        List of StructuredTool objects ready for LangGraph.
    """
    lc_tools = []

    for name, tool_def in TOOL_REGISTRY.items():
        # Build args_schema from the tool's input_schema
        properties = tool_def.input_schema.get("properties", {})
        required = tool_def.input_schema.get("required", [])

        # Create the handler with app context wrapper if needed
        base_handler = _make_handler(tool_def, tool_context_holder)

        if app is not None:

            def handler_with_ctx(app=app, base=base_handler, **kwargs):
                with app.app_context():
                    return base(**kwargs)

            func = handler_with_ctx
        else:
            func = base_handler

        func.__name__ = tool_def.name
        func.__doc__ = tool_def.description

        lc_tool = StructuredTool.from_function(
            func=func,
            name=tool_def.name,
            description=tool_def.description,
            args_schema=None,  # Use auto-inferred from function signature
        )

        # Override the args_schema with the tool's JSON schema for proper
        # tool calling format. LangGraph/LangChain uses this to generate
        # the tool definitions sent to the model.
        if properties:
            lc_tool.args_schema = _build_pydantic_model(name, properties, required)

        lc_tools.append(lc_tool)

    return lc_tools


def _build_pydantic_model(tool_name: str, properties: dict, required: list) -> Any:
    """Build a Pydantic model from JSON Schema properties for tool args.

    This creates a dynamic Pydantic model that LangChain uses to generate
    tool definitions for the Claude API.
    """
    from pydantic import create_model

    fields = {}
    for prop_name, prop_def in properties.items():
        prop_type = prop_def.get("type", "string")
        is_required = prop_name in required

        # Map JSON Schema types to Python types
        type_map = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        python_type = type_map.get(prop_type, Any)

        if is_required:
            fields[prop_name] = (python_type, ...)
        else:
            fields[prop_name] = (python_type, None)

    model = create_model(
        "{}Args".format(tool_name.title().replace("_", "")),
        **fields,
    )
    return model
