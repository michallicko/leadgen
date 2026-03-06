"""LangGraph StateGraph for the strategy agent.

Replaces the while-loop in agent_executor.py with a declarative graph:
  - "agent" node: calls Claude via ChatAnthropic
  - "tools" node: executes tool calls
  - Conditional edges route between agent/tools/END based on stop_reason

The graph is compiled once and invoked per chat turn. SSE events are
yielded via stream_mode="custom" using get_stream_writer().
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph

from ..services.tool_registry import ToolContext, get_tool, get_tools_for_api
from .state import AgentState

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 25
MAX_TURN_SECONDS = 180

# Per-turn rate limits by tool name
TOOL_RATE_LIMITS: dict[str, int] = {
    "web_search": 5,
}
DEFAULT_TOOL_RATE_LIMIT = 15


@dataclass
class SSEEvent:
    """A single SSE event yielded by the agent graph via stream writer."""

    type: str
    data: dict


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------


def agent_node(state: AgentState) -> dict:
    """Call the LLM with current messages and tools.

    Returns the AI response as a message to be appended to state.
    Also tracks token usage and cost.
    """
    writer = get_stream_writer()
    model_name = state.get("model", "claude-haiku-4-5-20251001")

    # Build ChatAnthropic model
    model = ChatAnthropic(
        model=model_name,
        temperature=0.4,
        max_tokens=8192,
    )

    # Bind tools using Claude API format dicts — ChatAnthropic
    # supports raw dicts with {name, description, input_schema} keys
    tool_defs = get_tools_for_api()
    if tool_defs:
        model = model.bind_tools(tool_defs)

    # Invoke the model
    messages = list(state["messages"])
    response = model.invoke(messages)

    # Track usage from response metadata
    usage = getattr(response, "usage_metadata", None) or {}
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cost = _estimate_cost(model_name, input_tokens, output_tokens)

    new_total_input = state.get("total_input_tokens", 0) + input_tokens
    new_total_output = state.get("total_output_tokens", 0) + output_tokens
    new_total_cost = str(Decimal(state.get("total_cost_usd", "0")) + Decimal(str(cost)))

    # Emit intermediate text as SSE chunks
    has_text = response.content and isinstance(response.content, str)
    if has_text and not response.tool_calls:
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
    }


def tools_node(state: AgentState) -> dict:
    """Execute tool calls from the last AI message.

    Processes each tool_use block, executes the handler, and yields
    tool_start/tool_result SSE events. Returns ToolMessages for the
    next agent iteration.
    """
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

        # Emit tool_start
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
            # Get Flask app for app context if available
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

                # Stream section content for typewriter effect
                if content_preview:
                    writer(
                        SSEEvent(
                            type="section_content_start",
                            data={"section": section_name},
                        )
                    )
                    chunk_size = 10
                    for i in range(0, len(content_preview), chunk_size):
                        writer(
                            SSEEvent(
                                type="section_content_chunk",
                                data={"text": content_preview[i : i + chunk_size]},
                            )
                        )
                    writer(
                        SSEEvent(
                            type="section_content_done",
                            data={"section": section_name},
                        )
                    )

            tool_messages.append(
                ToolMessage(content=result_str or "OK", tool_call_id=tool_id)
            )

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.exception("Tool '%s' failed: %s", tool_name, exc)
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


# ---------------------------------------------------------------------------
# Routing logic
# ---------------------------------------------------------------------------


def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """Decide whether to route to tools node or end the turn."""
    messages = state["messages"]
    if not messages:
        return "end"

    last_message = messages[-1]
    iteration = state.get("iteration", 0)

    # Check iteration limit
    if iteration >= MAX_TOOL_ITERATIONS:
        logger.warning("Agent reached max iterations (%d)", MAX_TOOL_ITERATIONS)
        return "end"

    # Check for tool calls
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"

    return "end"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_strategy_graph() -> StateGraph:
    """Build and compile the strategy agent graph."""
    graph = StateGraph(AgentState)

    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)

    graph.set_entry_point("agent")

    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END,
        },
    )

    graph.add_edge("tools", "agent")

    return graph.compile()


# ---------------------------------------------------------------------------
# System prompt building with layered caching
# ---------------------------------------------------------------------------


def build_system_messages(
    company_name: str,
    document,
    enrichment_data: Optional[dict] = None,
    phase: Optional[str] = None,
    page_context: Optional[str] = None,
    tenant=None,
) -> list:
    """Build system messages with prompt layering for cache efficiency.

    Constructs a SystemMessage with content blocks structured for
    Anthropic prompt caching:
      - Layer 0: Identity + capabilities (static, ~1300 tokens, cached)
      - Layer 2: Dynamic context (changes per call, not cached)

    Args:
        company_name: Tenant's company name for role definition.
        document: StrategyDocument model instance.
        enrichment_data: Optional company enrichment data dict.
        phase: Phase string (strategy, contacts, messages, campaign).
        page_context: Current page name the user is viewing.
        tenant: Tenant model instance for language settings.

    Returns:
        List containing a single SystemMessage with structured content blocks.
    """
    from .prompts.identity import build_identity_blocks
    from .prompts.context import build_context_block

    # Layer 0: Static identity blocks (with cache_control markers)
    identity_blocks = build_identity_blocks(company_name)

    # Layer 2: Dynamic context block (no caching)
    context_block = build_context_block(
        document=document,
        enrichment_data=enrichment_data,
        phase=phase,
        page_context=page_context,
        tenant=tenant,
    )

    # Combine into a single system message with multiple content blocks
    all_blocks = identity_blocks + [context_block]

    return [SystemMessage(content=all_blocks)]


# ---------------------------------------------------------------------------
# Execution entry point (replaces execute_agent_turn)
# ---------------------------------------------------------------------------


def execute_graph_turn(
    system_prompt: str,
    messages: list[dict],
    tool_context: ToolContext,
    model: str = "claude-haiku-4-5-20251001",
    app=None,
    system_messages: Optional[list] = None,
):
    """Execute a full agent turn using the LangGraph strategy graph.

    This is a generator that yields SSEEvent objects, matching the
    interface of the old execute_agent_turn() function.

    Args:
        system_prompt: System prompt string (legacy fallback).
        messages: List of message dicts in Anthropic format.
        tool_context: ToolContext with tenant_id, user_id, document_id.
        model: Model name for the LLM.
        app: Flask app for database access in tool handlers.
        system_messages: Pre-built LangChain SystemMessage list with
            layered content blocks. If provided, takes precedence over
            system_prompt string.

    Yields:
        SSEEvent objects (tool_start, tool_result, chunk, done).
    """
    graph = build_strategy_graph()

    # Convert Anthropic-format messages to LangChain messages
    if system_messages:
        lc_messages = list(system_messages)
    else:
        lc_messages = [SystemMessage(content=system_prompt)]

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "user":
            if isinstance(content, list):
                for block in content:
                    if block.get("type") == "tool_result":
                        lc_messages.append(
                            ToolMessage(
                                content=block.get("content", ""),
                                tool_call_id=block.get("tool_use_id", ""),
                            )
                        )
                    else:
                        lc_messages.append(HumanMessage(content=str(content)))
                        break
            else:
                lc_messages.append(HumanMessage(content=str(content)))
        elif role == "assistant":
            if isinstance(content, list):
                text_parts = []
                tool_calls = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_use":
                            tool_calls.append(
                                {
                                    "name": block.get("name", ""),
                                    "args": block.get("input", {}),
                                    "id": block.get("id", ""),
                                }
                            )
                ai_msg = AIMessage(
                    content="".join(text_parts),
                    tool_calls=tool_calls if tool_calls else [],
                )
                lc_messages.append(ai_msg)
            else:
                lc_messages.append(AIMessage(content=str(content)))

    # Build initial state
    initial_state: AgentState = {
        "messages": lc_messages,
        "tool_context": {
            "tenant_id": str(tool_context.tenant_id) if tool_context.tenant_id else "",
            "user_id": str(tool_context.user_id) if tool_context.user_id else None,
            "document_id": (
                str(tool_context.document_id) if tool_context.document_id else None
            ),
            "turn_id": tool_context.turn_id,
            "_app": app,
        },
        "iteration": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cost_usd": "0",
        "model": model,
    }

    # Stream the graph execution, collecting custom SSE events
    tool_executions = []
    turn_start = time.monotonic()

    try:
        for event in graph.stream(
            initial_state,
            stream_mode="custom",
        ):
            if isinstance(event, SSEEvent):
                # Track tool executions for the done event
                if event.type == "tool_result":
                    tool_executions.append(event.data)

                # Check turn timeout
                elapsed = time.monotonic() - turn_start
                if elapsed > MAX_TURN_SECONDS:
                    logger.warning("Agent turn timed out after %.0fs", elapsed)
                    yield SSEEvent(
                        type="chunk",
                        data={
                            "text": "I ran out of time for this turn. "
                            "Here's what I've completed so far. "
                            "Send another message to continue.",
                        },
                    )
                    break

                yield event

    except Exception as exc:
        logger.exception("Graph execution error: %s", exc)
        yield SSEEvent(
            type="chunk",
            data={"text": "An error occurred: {}".format(str(exc))},
        )

    # Yield the final done event with accumulated metadata
    yield SSEEvent(
        type="done",
        data={
            "tool_calls": [
                {
                    "tool_name": tc.get("tool_name", ""),
                    "tool_call_id": tc.get("tool_call_id", ""),
                    "status": tc.get("status", "success"),
                    "input_args": tc.get("input", {}),
                    "output_data": tc.get("output", ""),
                    "error_message": (
                        tc.get("summary", "") if tc.get("status") == "error" else None
                    ),
                    "duration_ms": tc.get("duration_ms", 0),
                }
                for tc in tool_executions
            ],
            "model": model,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost_usd": "0",
        },
    )


# ---------------------------------------------------------------------------
# Helpers (carried over from agent_executor.py)
# ---------------------------------------------------------------------------


def _truncate(text, max_len=2048):
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _summarize_output(tool_name, output):
    if not output:
        return "Completed {}".format(tool_name)
    if isinstance(output, dict) and "summary" in output:
        return str(output["summary"])
    return "Completed {}".format(tool_name)


def _estimate_cost(model, input_tokens, output_tokens):
    MODEL_PRICING = {
        "claude-haiku-4-5-20251001": {"input_per_m": 0.80, "output_per_m": 4.0},
        "claude-sonnet-4-5-20241022": {"input_per_m": 3.0, "output_per_m": 15.0},
        "claude-opus-4-6": {"input_per_m": 15.0, "output_per_m": 75.0},
    }
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["claude-haiku-4-5-20251001"])
    input_cost = (input_tokens / 1_000_000) * pricing["input_per_m"]
    output_cost = (output_tokens / 1_000_000) * pricing["output_per_m"]
    return round(input_cost + output_cost, 6)


# ---------------------------------------------------------------------------
# Orchestrated execution entry point (multi-agent routing)
# ---------------------------------------------------------------------------


def execute_orchestrated_turn(
    system_prompt: str,
    messages: list[dict],
    tool_context: ToolContext,
    model: str = "claude-haiku-4-5-20251001",
    app=None,
    system_messages: Optional[list] = None,
):
    """Execute a turn using the multi-agent orchestrator.

    Routes user messages to specialist subgraphs (Strategy, Research)
    based on intent classification. Falls back to quick_response for
    simple queries.

    Same interface as execute_graph_turn() — yields SSEEvent objects.

    Args:
        system_prompt: System prompt string (legacy fallback).
        messages: List of message dicts in Anthropic format.
        tool_context: ToolContext with tenant_id, user_id, document_id.
        model: Model name for the LLM.
        app: Flask app for database access in tool handlers.
        system_messages: Pre-built LangChain SystemMessage list.

    Yields:
        SSEEvent objects (intent_classified, tool_start, tool_result, chunk, done).
    """
    from .orchestrator import build_orchestrator_graph

    graph = build_orchestrator_graph()

    # Convert Anthropic-format messages to LangChain messages
    if system_messages:
        lc_messages = list(system_messages)
    else:
        lc_messages = [SystemMessage(content=system_prompt)]

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "user":
            if isinstance(content, list):
                for block in content:
                    if block.get("type") == "tool_result":
                        lc_messages.append(
                            ToolMessage(
                                content=block.get("content", ""),
                                tool_call_id=block.get("tool_use_id", ""),
                            )
                        )
                    else:
                        lc_messages.append(HumanMessage(content=str(content)))
                        break
            else:
                lc_messages.append(HumanMessage(content=str(content)))
        elif role == "assistant":
            if isinstance(content, list):
                text_parts = []
                tool_calls = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_use":
                            tool_calls.append(
                                {
                                    "name": block.get("name", ""),
                                    "args": block.get("input", {}),
                                    "id": block.get("id", ""),
                                }
                            )
                ai_msg = AIMessage(
                    content="".join(text_parts),
                    tool_calls=tool_calls if tool_calls else [],
                )
                lc_messages.append(ai_msg)
            else:
                lc_messages.append(AIMessage(content=str(content)))

    # Build initial state with orchestrator fields
    initial_state: AgentState = {
        "messages": lc_messages,
        "tool_context": {
            "tenant_id": str(tool_context.tenant_id) if tool_context.tenant_id else "",
            "user_id": str(tool_context.user_id) if tool_context.user_id else None,
            "document_id": (
                str(tool_context.document_id) if tool_context.document_id else None
            ),
            "turn_id": tool_context.turn_id,
            "_app": app,
        },
        "iteration": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cost_usd": "0",
        "model": model,
        "intent": None,
        "active_agent": None,
        "research_results": None,
        "section_completeness": None,
    }

    # Stream the orchestrator execution
    tool_executions = []
    turn_start = time.monotonic()

    try:
        for event in graph.stream(
            initial_state,
            stream_mode="custom",
        ):
            if isinstance(event, SSEEvent):
                if event.type == "tool_result":
                    tool_executions.append(event.data)

                elapsed = time.monotonic() - turn_start
                if elapsed > MAX_TURN_SECONDS:
                    logger.warning("Orchestrated turn timed out after %.0fs", elapsed)
                    yield SSEEvent(
                        type="chunk",
                        data={
                            "text": "I ran out of time for this turn. "
                            "Here's what I've completed so far. "
                            "Send another message to continue.",
                        },
                    )
                    break

                yield event

    except Exception as exc:
        logger.exception("Orchestrator execution error: %s", exc)
        yield SSEEvent(
            type="chunk",
            data={"text": "An error occurred: {}".format(str(exc))},
        )

    # Yield the final done event
    yield SSEEvent(
        type="done",
        data={
            "tool_calls": [
                {
                    "tool_name": tc.get("tool_name", ""),
                    "tool_call_id": tc.get("tool_call_id", ""),
                    "status": tc.get("status", "success"),
                    "input_args": tc.get("input", {}),
                    "output_data": tc.get("output", ""),
                    "error_message": (
                        tc.get("summary", "") if tc.get("status") == "error" else None
                    ),
                    "duration_ms": tc.get("duration_ms", 0),
                }
                for tc in tool_executions
            ],
            "model": model,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost_usd": "0",
        },
    )
