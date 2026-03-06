"""Research Agent subgraph — focused on research and data discovery.

This subgraph handles web searches, company research, contact/company
queries, and enrichment analysis. Results are stored in shared state
for consumption by other agents (e.g., Strategy Agent).

Tools bound (7): web_search, research_own_company, count_contacts,
count_companies, list_contacts, filter_contacts,
analyze_enrichment_insights.

Model: Haiku for simple queries, can be escalated to Sonnet.
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

MAX_RESEARCH_ITERATIONS = 15

# Research-specific tool names
RESEARCH_TOOL_NAMES = frozenset(
    [
        "web_search",
        "research_own_company",
        "count_contacts",
        "count_companies",
        "list_contacts",
        "filter_contacts",
        "analyze_enrichment_insights",
    ]
)

# Focused system prompt (~150 tokens)
RESEARCH_AGENT_PROMPT = """You are a research analyst. Your job is to find, analyze, and synthesize information.

RULES:
- Use research_own_company for deep company intelligence (cached if already run).
- Use web_search for market trends, competitor info, and current data. Max 3 searches per turn.
- Use count_contacts/count_companies for CRM data queries.
- Use list_contacts for detailed contact information.
- Use filter_contacts to find contacts matching specific criteria.
- Use analyze_enrichment_insights for enrichment data analysis.
- Be concise: summarize findings in bullet points.
- After research, state what you found and suggest next steps.
- Max 150 words in conversational responses."""


def _get_research_tool_defs() -> list[dict]:
    """Get Claude API format tool definitions for research tools only."""
    defs = []
    for name in RESEARCH_TOOL_NAMES:
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


def research_agent_node(state: AgentState) -> dict:
    """Call the LLM with research-focused prompt and tools."""
    writer = get_stream_writer()
    model_name = state.get("model", "claude-haiku-4-5-20251001")

    model = ChatAnthropic(
        model=model_name,
        temperature=0.3,
        max_tokens=4096,
    )

    tool_defs = _get_research_tool_defs()
    if tool_defs:
        model = model.bind_tools(tool_defs)

    messages = list(state["messages"])
    # Ensure system message is first
    if not messages or not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=RESEARCH_AGENT_PROMPT))

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
        "active_agent": "research",
    }


def research_tools_node(state: AgentState) -> dict:
    """Execute research tool calls and store results in shared state."""
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
    # Accumulate research results for shared state
    accumulated_results = dict(state.get("research_results") or {})

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_id = tool_call["id"]
        tool_input = tool_call.get("args", {})

        # Only allow research tools
        if tool_name not in RESEARCH_TOOL_NAMES:
            error_msg = "Tool '{}' not available in research agent".format(tool_name)
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

            # Store results in shared state for other agents
            if result:
                accumulated_results[tool_name] = {
                    "data": result,
                    "timestamp": time.time(),
                    "input": tool_input,
                }

            tool_messages.append(
                ToolMessage(content=result_str or "OK", tool_call_id=tool_id)
            )

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.exception("Research tool '%s' failed: %s", tool_name, exc)
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

    return {
        "messages": tool_messages,
        "research_results": accumulated_results,
    }


def research_should_continue(state: AgentState) -> Literal["tools", "end"]:
    """Decide whether to continue the research agent loop."""
    messages = state["messages"]
    if not messages:
        return "end"

    last_message = messages[-1]
    iteration = state.get("iteration", 0)

    if iteration >= MAX_RESEARCH_ITERATIONS:
        logger.warning(
            "Research agent reached max iterations (%d)", MAX_RESEARCH_ITERATIONS
        )
        return "end"

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"

    return "end"


def build_research_subgraph() -> StateGraph:
    """Build and compile the research agent subgraph."""
    graph = StateGraph(AgentState)

    graph.add_node("research_agent", research_agent_node)
    graph.add_node("research_tools", research_tools_node)

    graph.set_entry_point("research_agent")

    graph.add_conditional_edges(
        "research_agent",
        research_should_continue,
        {
            "tools": "research_tools",
            "end": END,
        },
    )

    graph.add_edge("research_tools", "research_agent")

    return graph.compile()
