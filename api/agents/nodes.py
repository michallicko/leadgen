"""Graph node functions for the LangGraph agent.

Each node is a pure function: AgentState → AgentState (partial update).
Nodes handle: model routing, LLM calls, tool execution, halt detection.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any

from .state import AgentState, ToolCallRecord
from .tools import (
    DEFAULT_TOOL_RATE_LIMIT,
    TOOL_RATE_LIMITS,
    execute_tool_call,
)

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 25
MAX_TURN_SECONDS = 120

# Models for multi-model routing
MODEL_HAIKU = "claude-haiku-4-5-20251001"
MODEL_SONNET = "claude-sonnet-4-5-20241022"
MODEL_OPUS = "claude-opus-4-6"


# ---------------------------------------------------------------------------
# Node: route — selects model based on context
# ---------------------------------------------------------------------------


def route_node(state: AgentState) -> dict[str, Any]:
    """Select the appropriate model based on the current context.

    Routing logic:
    - First iteration with strategy phase + empty doc → Sonnet (generation)
    - Subsequent iterations with tool results → Haiku (routing/Q&A)
    - Default → Haiku (cheapest, fast)

    Returns partial state update with 'model' key.
    """
    iteration = state.get("iteration_count", 0)
    phase = state.get("phase", "strategy")

    # On first call in strategy phase, use Sonnet for higher-quality generation
    if iteration == 0 and phase == "strategy":
        return {"model": MODEL_SONNET}

    # For tool result processing, use Haiku (fast routing)
    if iteration > 0:
        return {"model": MODEL_HAIKU}

    # Default
    return {"model": MODEL_HAIKU}


# ---------------------------------------------------------------------------
# Node: call_model — makes the LLM API call
# ---------------------------------------------------------------------------


def call_model_node(state: AgentState, client: Any) -> dict[str, Any]:
    """Call the Anthropic API with current messages and tools.

    Args:
        state: Current agent state.
        client: AnthropicClient instance.

    Returns:
        Partial state update with response content, token usage, etc.
    """
    messages = state.get("messages", [])
    system_prompt = state.get("system_prompt", "")
    tools = state.get("tools", [])
    model = state.get("model", MODEL_HAIKU)
    iteration = state.get("iteration_count", 0)

    # Make the API call
    response = client.query_with_tools(
        messages=messages,
        system_prompt=system_prompt,
        tools=tools,
        model=model,
    )

    # Track token usage
    usage = response.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    prev_input = state.get("total_input_tokens", 0)
    prev_output = state.get("total_output_tokens", 0)
    prev_cost = Decimal(state.get("total_cost_usd", "0"))

    cost = Decimal(str(client._estimate_cost(model, input_tokens, output_tokens)))

    return {
        "content_blocks": response.get("content", []),
        "stop_reason": response.get("stop_reason"),
        "model": response.get("model", model),
        "total_input_tokens": prev_input + input_tokens,
        "total_output_tokens": prev_output + output_tokens,
        "total_cost_usd": str(prev_cost + cost),
        "iteration_count": iteration + 1,
    }


# ---------------------------------------------------------------------------
# Node: execute_tools — runs tool calls from the model response
# ---------------------------------------------------------------------------


def execute_tools_node(state: AgentState) -> dict[str, Any]:
    """Execute tool calls from the model's response.

    Processes all tool_use blocks in content_blocks, executes each tool,
    and appends results to the message history.

    Returns partial state update with updated messages and tool_calls.
    """
    content_blocks = state.get("content_blocks", [])
    messages = list(state.get("messages", []))
    tool_context_dict = state.get("tool_context", {})
    app = state.get("app")
    existing_tool_calls = list(state.get("tool_calls", []))

    # Extract tool_use blocks
    tool_use_blocks = [b for b in content_blocks if b.get("type") == "tool_use"]

    if not tool_use_blocks:
        return {}

    # Append assistant message with content blocks
    messages.append({"role": "assistant", "content": content_blocks})

    # Count existing tool calls for rate limiting
    tool_call_counts: dict[str, int] = {}
    for tc in existing_tool_calls:
        name = tc.get("tool_name", "")
        tool_call_counts[name] = tool_call_counts.get(name, 0) + 1

    # Execute each tool
    tool_results: list[dict[str, Any]] = []
    new_tool_calls: list[ToolCallRecord] = []
    document_changed = state.get("document_changed", False)
    changes_parts: list[str] = []

    for tool_block in tool_use_blocks:
        tool_name = tool_block["name"]
        tool_id = tool_block["id"]
        tool_input = tool_block.get("input", {})

        # Rate-limit check
        max_allowed = TOOL_RATE_LIMITS.get(tool_name, DEFAULT_TOOL_RATE_LIMIT)
        current_count = tool_call_counts.get(tool_name, 0)

        if current_count >= max_allowed:
            error_msg = (
                "Rate limit: {} can be called at most {} times per turn. "
                "Please continue with the information you already have."
            ).format(tool_name, max_allowed)

            new_tool_calls.append(
                ToolCallRecord(
                    tool_name=tool_name,
                    tool_call_id=tool_id,
                    input_args=tool_input,
                    is_error=True,
                    error_message=error_msg,
                    duration_ms=0,
                    status="error",
                )
            )

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": error_msg,
                    "is_error": True,
                }
            )
            continue

        tool_call_counts[tool_name] = current_count + 1

        # Execute
        result = execute_tool_call(tool_name, tool_input, tool_context_dict, app=app)

        new_tool_calls.append(
            ToolCallRecord(
                tool_name=tool_name,
                tool_call_id=tool_id,
                input_args=tool_input,
                output=result["output"],
                is_error=result["is_error"],
                error_message=result["error_message"],
                duration_ms=result["duration_ms"],
                status="error" if result["is_error"] else "success",
            )
        )

        # Check for document changes
        STRATEGY_EDIT_TOOLS = {
            "update_strategy_section",
            "set_extracted_field",
            "append_to_section",
        }
        if tool_name in STRATEGY_EDIT_TOOLS and not result["is_error"]:
            document_changed = True
            changes_parts.append(tool_name.replace("_", " "))

        # Build tool_result message for Claude
        if result["is_error"]:
            result_content = result["error_message"] or "Tool execution failed"
        else:
            try:
                result_content = json.dumps(result["output"])
            except (TypeError, ValueError):
                result_content = str(result["output"])

        tool_results.append(
            {
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": result_content,
                "is_error": result["is_error"],
            }
        )

    # Append tool results as user message
    messages.append({"role": "user", "content": tool_results})

    # Build changes summary
    changes_summary = state.get("changes_summary")
    if changes_parts:
        if changes_summary:
            changes_summary += ", " + ", ".join(changes_parts)
        else:
            changes_summary = ", ".join(changes_parts)

    return {
        "messages": messages,
        "tool_calls": existing_tool_calls + new_tool_calls,
        "document_changed": document_changed,
        "changes_summary": changes_summary,
    }


# ---------------------------------------------------------------------------
# Conditional edges
# ---------------------------------------------------------------------------


def should_continue(state: AgentState) -> str:
    """Determine the next step after model call.

    Returns:
        "execute_tools" if there are tool calls to process.
        "end" if the model is done (no tool calls).
        "timeout" if we exceeded iteration or time limits.
    """
    stop_reason = state.get("stop_reason")
    content_blocks = state.get("content_blocks", [])
    iteration = state.get("iteration_count", 0)

    # Check iteration limit
    if iteration >= MAX_TOOL_ITERATIONS:
        return "end"

    # Check for tool_use blocks
    tool_use_blocks = [b for b in content_blocks if b.get("type") == "tool_use"]

    if stop_reason == "tool_use" and tool_use_blocks:
        return "execute_tools"

    return "end"


def after_tools(state: AgentState) -> str:
    """Determine next step after tool execution.

    Returns:
        "call_model" to continue the loop (feed tool results back).
        "halt" if the agent should pause for user input.
        "end" if we should stop.
    """
    if state.get("should_halt", False):
        return "halt"

    iteration = state.get("iteration_count", 0)
    if iteration >= MAX_TOOL_ITERATIONS:
        return "end"

    return "call_model"
