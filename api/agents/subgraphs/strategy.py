"""Strategy Agent subgraph — focused on strategy document editing.

This subgraph handles all strategy-related tasks: writing sections,
updating ICP tiers, setting buyer personas, and tracking assumptions.
It receives research results from shared state for grounding.

Tools bound (8): update_strategy_section, append_to_section,
set_extracted_field, track_assumption, check_readiness,
set_icp_tiers, set_buyer_personas, get_strategy_document.

Model: Sonnet for generation quality.
"""

from __future__ import annotations

import json
import logging
import time
from decimal import Decimal
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph

from ...services.tool_registry import ToolContext, get_tool
from ..graph import SSEEvent, _estimate_cost, _summarize_output, _truncate
from ..state import AgentState

logger = logging.getLogger(__name__)

MAX_STRATEGY_ITERATIONS = 15

# Strategy-specific tool names (all from strategy_tools.py)
STRATEGY_TOOL_NAMES = frozenset(
    [
        "update_strategy_section",
        "append_to_section",
        "set_extracted_field",
        "track_assumption",
        "check_readiness",
        "set_icp_tiers",
        "set_buyer_personas",
        "get_strategy_document",
    ]
)

# Focused system prompt (~200 tokens)
STRATEGY_AGENT_PROMPT = """You are a strategy document editor. Your job is to write, update, and refine GTM strategy sections.

RULES:
- Use update_strategy_section to write/replace section content. NEVER describe changes without calling the tool.
- Use append_to_section to add content without replacing existing text.
- Use set_icp_tiers and set_buyer_personas for structured ICP/persona data (NOT document sections).
- Use check_readiness to assess document completeness.
- Use track_assumption to flag assumptions that need validation.
- Reference research data provided in context to ground your recommendations.
- Be action-oriented: call tools immediately, then summarize what you did.
- Max 150 words in conversational responses. Lead with the action taken.

SECTIONS: Executive Summary, Value Proposition & Messaging, Competitive Positioning, Channel Strategy, Messaging Framework, Metrics & KPIs, 90-Day Action Plan."""


def _get_strategy_tool_defs() -> list[dict]:
    """Get Claude API format tool definitions for strategy tools only."""
    defs = []
    for name in STRATEGY_TOOL_NAMES:
        tool = get_tool(name)
        if tool is not None:
            defs.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                }
            )
    return defs


def strategy_agent_node(state: AgentState) -> dict:
    """Call the LLM with strategy-focused prompt and tools."""
    writer = get_stream_writer()
    model_name = "claude-sonnet-4-5-20241022"

    model = ChatAnthropic(
        model=model_name,
        temperature=0.4,
        max_tokens=8192,
    )

    tool_defs = _get_strategy_tool_defs()
    if tool_defs:
        model = model.bind_tools(tool_defs)

    # Build system message with research context if available
    system_parts = [STRATEGY_AGENT_PROMPT]

    research_results = state.get("research_results")
    if research_results:
        system_parts.append(
            "\n\n--- Research Context ---\n"
            + json.dumps(research_results, indent=2, default=str)[:4000]
            + "\n--- End Research Context ---"
        )

    section_completeness = state.get("section_completeness")
    if section_completeness:
        status_lines = [
            "- {} [{}]".format(name, status)
            for name, status in section_completeness.items()
        ]
        system_parts.append("\n\nSECTION STATUS:\n" + "\n".join(status_lines))

    messages = list(state["messages"])
    # Ensure system message is first
    if not messages or not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content="\n".join(system_parts)))

    response = model.invoke(messages)

    # Track usage
    usage = getattr(response, "usage_metadata", None) or {}
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cost = _estimate_cost(model_name, input_tokens, output_tokens)

    new_total_input = state.get("total_input_tokens", 0) + input_tokens
    new_total_output = state.get("total_output_tokens", 0) + output_tokens
    new_total_cost = str(Decimal(state.get("total_cost_usd", "0")) + Decimal(str(cost)))

    # Emit text chunks
    if (
        response.content
        and isinstance(response.content, str)
        and not response.tool_calls
    ):
        writer(SSEEvent(type="chunk", data={"text": response.content}))
    elif response.content and isinstance(response.content, list):
        for block in response.content:
            if isinstance(block, dict) and block.get("type") == "text":
                writer(SSEEvent(type="chunk", data={"text": block["text"]}))
            elif isinstance(block, str):
                writer(SSEEvent(type="chunk", data={"text": block}))

    return {
        "messages": [response],
        "iteration": state.get("iteration", 0) + 1,
        "total_input_tokens": new_total_input,
        "total_output_tokens": new_total_output,
        "total_cost_usd": new_total_cost,
        "active_agent": "strategy",
    }


def strategy_tools_node(state: AgentState) -> dict:
    """Execute strategy tool calls from the last AI message."""
    writer = get_stream_writer()
    messages = state["messages"]
    last_message = messages[-1]

    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": []}

    tool_context_dict = state.get("tool_context", {})
    tool_ctx = ToolContext(
        tenant_id=tool_context_dict.get("tenant_id", ""),
        user_id=tool_context_dict.get("user_id"),
        document_id=tool_context_dict.get("document_id"),
        turn_id=tool_context_dict.get("turn_id"),
    )

    tool_messages = []

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_id = tool_call["id"]
        tool_input = tool_call.get("args", {})

        # Only allow strategy tools
        if tool_name not in STRATEGY_TOOL_NAMES:
            error_msg = "Tool '{}' not available in strategy agent".format(tool_name)
            writer(
                SSEEvent(
                    type="tool_result",
                    data={
                        "tool_call_id": tool_id,
                        "tool_name": tool_name,
                        "status": "error",
                        "summary": error_msg,
                        "output": "",
                        "duration_ms": 0,
                    },
                )
            )
            tool_messages.append(ToolMessage(content=error_msg, tool_call_id=tool_id))
            continue

        writer(
            SSEEvent(
                type="tool_start",
                data={
                    "tool_name": tool_name,
                    "tool_call_id": tool_id,
                    "input": tool_input,
                },
            )
        )

        start = time.monotonic()
        tool_def = get_tool(tool_name)

        if tool_def is None:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            error_msg = "Unknown tool: {}".format(tool_name)
            writer(
                SSEEvent(
                    type="tool_result",
                    data={
                        "tool_call_id": tool_id,
                        "tool_name": tool_name,
                        "status": "error",
                        "summary": error_msg,
                        "output": "",
                        "duration_ms": elapsed_ms,
                    },
                )
            )
            tool_messages.append(ToolMessage(content=error_msg, tool_call_id=tool_id))
            continue

        try:
            app = tool_context_dict.get("_app")
            if app is not None:
                with app.app_context():
                    result = tool_def.handler(tool_input, tool_ctx)
            else:
                result = tool_def.handler(tool_input, tool_ctx)

            elapsed_ms = int((time.monotonic() - start) * 1000)
            result_str = json.dumps(result) if result else ""

            writer(
                SSEEvent(
                    type="tool_result",
                    data={
                        "tool_call_id": tool_id,
                        "tool_name": tool_name,
                        "status": "success",
                        "summary": _summarize_output(tool_name, result),
                        "output": _truncate(result_str, 2048),
                        "duration_ms": elapsed_ms,
                    },
                )
            )

            # Emit section_update for live document animation
            if tool_name in ("update_strategy_section", "append_to_section") and result:
                section_name = result.get("section", "")
                content_preview = result.get("content_preview", "")
                writer(
                    SSEEvent(
                        type="section_update",
                        data={
                            "section": section_name,
                            "content": content_preview,
                            "action": "update"
                            if tool_name == "update_strategy_section"
                            else "append",
                        },
                    )
                )

            tool_messages.append(
                ToolMessage(content=result_str or "OK", tool_call_id=tool_id)
            )

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.exception("Strategy tool '%s' failed: %s", tool_name, exc)
            error_msg = str(exc)
            writer(
                SSEEvent(
                    type="tool_result",
                    data={
                        "tool_call_id": tool_id,
                        "tool_name": tool_name,
                        "status": "error",
                        "summary": error_msg,
                        "output": "",
                        "duration_ms": elapsed_ms,
                    },
                )
            )
            tool_messages.append(ToolMessage(content=error_msg, tool_call_id=tool_id))

    return {"messages": tool_messages}


def strategy_should_continue(state: AgentState) -> Literal["tools", "end"]:
    """Decide whether to continue the strategy agent loop."""
    messages = state["messages"]
    if not messages:
        return "end"

    last_message = messages[-1]
    iteration = state.get("iteration", 0)

    if iteration >= MAX_STRATEGY_ITERATIONS:
        logger.warning(
            "Strategy agent reached max iterations (%d)", MAX_STRATEGY_ITERATIONS
        )
        return "end"

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"

    return "end"


def build_strategy_subgraph() -> StateGraph:
    """Build and compile the strategy agent subgraph."""
    graph = StateGraph(AgentState)

    graph.add_node("strategy_agent", strategy_agent_node)
    graph.add_node("strategy_tools", strategy_tools_node)

    graph.set_entry_point("strategy_agent")

    graph.add_conditional_edges(
        "strategy_agent",
        strategy_should_continue,
        {
            "tools": "strategy_tools",
            "end": END,
        },
    )

    graph.add_edge("strategy_tools", "strategy_agent")

    return graph.compile()
