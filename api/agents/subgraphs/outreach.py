"""Outreach Agent subgraph — focused on message generation and personalization.

This subgraph handles all outreach-related tasks: generating personalized
messages, creating A/B variants, managing message status, and listing
existing messages for contacts.

Tools bound (5): generate_message, list_messages, update_message,
get_message_templates, generate_variants.

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

MAX_OUTREACH_ITERATIONS = 15

# Outreach-specific tool names (all from message_tools.py)
OUTREACH_TOOL_NAMES = frozenset(
    [
        "generate_message",
        "list_messages",
        "update_message",
        "get_message_templates",
        "generate_variants",
    ]
)

# Focused system prompt (~200 tokens)
OUTREACH_AGENT_PROMPT = """You are an outreach message specialist. Your job is to generate, refine, and manage personalized outreach messages for B2B contacts.

RULES:
- Use generate_message to create personalized outreach for a contact. Always include contact_id.
- Use generate_variants to create A/B test variants of an existing message with a different angle or tone.
- Use list_messages to review existing messages for a contact or batch.
- Use update_message to edit, approve, or reject messages.
- Use get_message_templates to see available message frameworks before generating.
- Reference enrichment data and strategy context to personalize messages.
- Be concise and action-oriented: generate the message, then summarize what you created.
- Messages should be professional, personalized, and avoid generic sales language.
- Max 150 words in conversational responses. Lead with the action taken."""


def _get_outreach_tool_defs() -> list[dict]:
    """Get Claude API format tool definitions for outreach tools only."""
    defs = []
    for name in OUTREACH_TOOL_NAMES:
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


def outreach_agent_node(state: AgentState) -> dict:
    """Call the LLM with outreach-focused prompt and tools."""
    writer = get_stream_writer()
    model_name = "claude-sonnet-4-5-20241022"

    model = ChatAnthropic(
        model=model_name,
        temperature=0.5,
        max_tokens=8192,
    )

    tool_defs = _get_outreach_tool_defs()
    if tool_defs:
        model = model.bind_tools(tool_defs)

    # Build system message with strategy context if available
    system_parts = [OUTREACH_AGENT_PROMPT]

    research_results = state.get("research_results")
    if research_results:
        system_parts.append(
            "\n\n--- Research Context ---\n"
            + json.dumps(research_results, indent=2, default=str)[:4000]
            + "\n--- End Research Context ---"
        )

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
        "active_agent": "outreach",
    }


def outreach_tools_node(state: AgentState) -> dict:
    """Execute outreach tool calls from the last AI message."""
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

        # Only allow outreach tools
        if tool_name not in OUTREACH_TOOL_NAMES:
            error_msg = "Tool '{}' not available in outreach agent".format(tool_name)
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

            # Emit message_generated event for UI updates
            if tool_name == "generate_message" and result and result.get("id"):
                writer(
                    SSEEvent(
                        type="message_generated",
                        data={
                            "message_id": result.get("id"),
                            "contact_id": result.get("contact_id", ""),
                            "channel": result.get("channel", ""),
                            "status": result.get("status", "draft"),
                        },
                    )
                )

            tool_messages.append(
                ToolMessage(content=result_str or "OK", tool_call_id=tool_id)
            )

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.exception("Outreach tool '%s' failed: %s", tool_name, exc)
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


def outreach_should_continue(state: AgentState) -> Literal["tools", "end"]:
    """Decide whether to continue the outreach agent loop."""
    messages = state["messages"]
    if not messages:
        return "end"

    last_message = messages[-1]
    iteration = state.get("iteration", 0)

    if iteration >= MAX_OUTREACH_ITERATIONS:
        logger.warning(
            "Outreach agent reached max iterations (%d)", MAX_OUTREACH_ITERATIONS
        )
        return "end"

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"

    return "end"


def build_outreach_subgraph() -> StateGraph:
    """Build and compile the outreach agent subgraph."""
    graph = StateGraph(AgentState)

    graph.add_node("outreach_agent", outreach_agent_node)
    graph.add_node("outreach_tools", outreach_tools_node)

    graph.set_entry_point("outreach_agent")

    graph.add_conditional_edges(
        "outreach_agent",
        outreach_should_continue,
        {
            "tools": "outreach_tools",
            "end": END,
        },
    )

    graph.add_edge("outreach_tools", "outreach_agent")

    return graph.compile()
