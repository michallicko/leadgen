"""Enrichment Agent subgraph — coordinates enrichment operations.

This subgraph handles enrichment tool calls from the Research Agent,
coordinating which enrichers to run and in what order based on the
stage dependency graph.

Tools bound (6): enrich_company_news, enrich_company_signals,
enrich_contact_social, enrich_contact_career, enrich_contact_details,
check_enrichment_status.

Model: Haiku for coordination, can be escalated to Sonnet.
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

MAX_ENRICHMENT_ITERATIONS = 20

# Enrichment-specific tool names
ENRICHMENT_TOOL_NAMES = frozenset(
    [
        "enrich_company_news",
        "enrich_company_signals",
        "enrich_contact_social",
        "enrich_contact_career",
        "enrich_contact_details",
        "check_enrichment_status",
        "estimate_enrichment_cost",
        "start_enrichment",
    ]
)

# Focused system prompt
ENRICHMENT_AGENT_PROMPT = """You are an enrichment coordinator. Your job is to run data enrichment on companies and contacts.

RULES:
- Use enrich_company_news for news & PR data on a company.
- Use enrich_company_signals for strategic signals (hiring, AI adoption, growth).
- Use enrich_contact_social for social media and online presence.
- Use enrich_contact_career for career history and previous companies.
- Use enrich_contact_details for email, phone, LinkedIn, and profile photo.
- Use check_enrichment_status to monitor a running enrichment pipeline.
- Use estimate_enrichment_cost before bulk enrichment to show costs.
- Use start_enrichment only after user confirms the cost estimate.
- Company enrichment (news, signals) requires a company_id.
- Contact enrichment (social, career, details) requires a contact_id.
- After enrichment, summarize what was found.
- Max 150 words in conversational responses."""


def _get_enrichment_tool_defs() -> list[dict]:
    """Get Claude API format tool definitions for enrichment tools only."""
    defs = []
    for name in ENRICHMENT_TOOL_NAMES:
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


def enrichment_agent_node(state: AgentState) -> dict:
    """Call the LLM with enrichment-focused prompt and tools."""
    writer = get_stream_writer()
    model_name = state.get("model", "claude-haiku-4-5-20251001")

    model = ChatAnthropic(
        model=model_name,
        temperature=0.2,
        max_tokens=4096,
    )

    tool_defs = _get_enrichment_tool_defs()
    if tool_defs:
        model = model.bind_tools(tool_defs)

    messages = list(state["messages"])
    if not messages or not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=ENRICHMENT_AGENT_PROMPT))

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
        "active_agent": "enrichment",
    }


def enrichment_tools_node(state: AgentState) -> dict:
    """Execute enrichment tool calls."""
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

        if tool_name not in ENRICHMENT_TOOL_NAMES:
            error_msg = "Tool '{}' not available in enrichment agent".format(tool_name)
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

            tool_messages.append(
                ToolMessage(content=result_str or "OK", tool_call_id=tool_id)
            )

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.exception("Enrichment tool '%s' failed: %s", tool_name, exc)
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


def enrichment_should_continue(state: AgentState) -> Literal["tools", "end"]:
    """Decide whether to continue the enrichment agent loop."""
    messages = state["messages"]
    if not messages:
        return "end"

    last_message = messages[-1]
    iteration = state.get("iteration", 0)

    if iteration >= MAX_ENRICHMENT_ITERATIONS:
        logger.warning(
            "Enrichment agent reached max iterations (%d)",
            MAX_ENRICHMENT_ITERATIONS,
        )
        return "end"

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"

    return "end"


def build_enrichment_subgraph() -> StateGraph:
    """Build and compile the enrichment agent subgraph."""
    graph = StateGraph(AgentState)

    graph.add_node("enrichment_agent", enrichment_agent_node)
    graph.add_node("enrichment_tools", enrichment_tools_node)

    graph.set_entry_point("enrichment_agent")

    graph.add_conditional_edges(
        "enrichment_agent",
        enrichment_should_continue,
        {
            "tools": "enrichment_tools",
            "end": END,
        },
    )

    graph.add_edge("enrichment_tools", "enrichment_agent")

    return graph.compile()
