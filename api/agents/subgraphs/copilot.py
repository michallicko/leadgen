"""Copilot Agent subgraph — lightweight assistant for quick questions.

Answers "how do I..." questions, explains previous operations,
provides quick data lookups, and handles simple queries that don't
need a full specialist agent.

Tools bound (4): get_contact_info, get_company_info, get_pipeline_status,
get_recent_activity.

Model: Haiku for speed (< 2s response time target).
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

from ...tools.copilot_tools import COPILOT_TOOL_DEFINITIONS, COPILOT_TOOL_NAMES
from ..graph import SSEEvent, _estimate_cost, _summarize_output, _truncate
from ..state import AgentState

logger = logging.getLogger(__name__)

MAX_COPILOT_ITERATIONS = 8

COPILOT_AGENT_PROMPT = """You are a helpful copilot for a B2B lead generation platform. Answer quickly and concisely.

CAPABILITIES:
- Look up contact and company information
- Check pipeline status and enrichment progress
- Show recent activity and operations
- Explain how features work
- Answer questions about the app

RULES:
- Be concise: max 100 words in responses
- Use bullet points for lists
- If the user asks something that needs strategy editing, research, enrichment, or outreach, say "This needs the [Strategy/Research/Enrichment/Outreach] agent. Please rephrase your request to include that intent."
- For data lookups, use the available tools before answering
- Always reference specific data when available"""


def _get_copilot_tool_defs() -> list[dict]:
    """Get Claude API format tool definitions for copilot tools only."""
    defs = []
    for tool_def in COPILOT_TOOL_DEFINITIONS:
        defs.append(
            {
                "name": tool_def["name"],
                "description": tool_def["description"],
                "input_schema": tool_def["input_schema"],
            }
        )
    return defs


def _get_copilot_handler(tool_name: str):
    """Get the handler function for a copilot tool."""
    for tool_def in COPILOT_TOOL_DEFINITIONS:
        if tool_def["name"] == tool_name:
            return tool_def["handler"]
    return None


def copilot_agent_node(state: AgentState) -> dict:
    """Call Haiku with copilot-focused prompt and read-only tools."""
    writer = get_stream_writer()
    model_name = "claude-haiku-4-5-20251001"

    model = ChatAnthropic(
        model=model_name,
        temperature=0.3,
        max_tokens=2048,
    )

    tool_defs = _get_copilot_tool_defs()
    if tool_defs:
        model = model.bind_tools(tool_defs)

    messages = list(state["messages"])
    if not messages or not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=COPILOT_AGENT_PROMPT))

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
        "active_agent": "copilot",
    }


def copilot_tools_node(state: AgentState) -> dict:
    """Execute copilot tool calls (read-only) from the last AI message."""
    writer = get_stream_writer()
    messages = state["messages"]
    last_message = messages[-1]

    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": []}

    tool_context_dict = state.get("tool_context", {})

    # Build a lightweight context object for tool handlers
    class _CopilotContext:
        def __init__(self, tenant_id: str):
            self.tenant_id = tenant_id

    tool_ctx = _CopilotContext(
        tenant_id=tool_context_dict.get("tenant_id", ""),
    )

    tool_messages = []

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_id = tool_call["id"]
        tool_input = tool_call.get("args", {})

        if tool_name not in COPILOT_TOOL_NAMES:
            error_msg = "Tool '{}' not available in copilot agent".format(tool_name)
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
        handler = _get_copilot_handler(tool_name)

        if handler is None:
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
                    result = handler(tool_input, tool_ctx)
            else:
                result = handler(tool_input, tool_ctx)

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

            tool_messages.append(
                ToolMessage(content=result_str or "OK", tool_call_id=tool_id)
            )

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.exception("Copilot tool '%s' failed: %s", tool_name, exc)
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


def copilot_should_continue(state: AgentState) -> Literal["tools", "end"]:
    """Decide whether to continue the copilot agent loop."""
    messages = state["messages"]
    if not messages:
        return "end"

    last_message = messages[-1]
    iteration = state.get("iteration", 0)

    if iteration >= MAX_COPILOT_ITERATIONS:
        logger.warning(
            "Copilot agent reached max iterations (%d)", MAX_COPILOT_ITERATIONS
        )
        return "end"

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"

    return "end"


def build_copilot_subgraph():
    """Build and compile the copilot agent subgraph."""
    graph = StateGraph(AgentState)

    graph.add_node("copilot_agent", copilot_agent_node)
    graph.add_node("copilot_tools", copilot_tools_node)

    graph.set_entry_point("copilot_agent")

    graph.add_conditional_edges(
        "copilot_agent",
        copilot_should_continue,
        {
            "tools": "copilot_tools",
            "end": END,
        },
    )

    graph.add_edge("copilot_tools", "copilot_agent")

    return graph.compile()
