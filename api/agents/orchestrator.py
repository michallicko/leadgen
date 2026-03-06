"""Top-level orchestrator graph for multi-agent routing.

The orchestrator classifies user intent and routes to the appropriate
specialist subgraph (Strategy, Research, Outreach) or handles quick
answers directly. It manages context distribution and result synthesis.

Flow:
  User message -> classify_intent -> route_to_agent
                                        |
      +------------+-------------+------+----------+-----------+
      |            |             |                  |           |
  strategy    research    quick_response    passthrough    outreach
      |            |             |                  |           |
      +------------+-------------+------+----------+-----------+
                                        |
                                    synthesize -> END
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any, Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph

from .graph import SSEEvent, _estimate_cost
from .intent import classify_intent
from .state import AgentState
from .subgraphs.outreach import build_outreach_subgraph
from .subgraphs.research import build_research_subgraph
from .subgraphs.strategy import build_strategy_subgraph

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Orchestrator nodes
# ---------------------------------------------------------------------------


def classify_node(state: AgentState) -> dict:
    """Classify user intent from the last human message.

    Uses the intent classifier (keyword fast path + Haiku fallback)
    to determine which specialist agent should handle the request.
    """
    writer = get_stream_writer()
    messages = state["messages"]

    # Find the last human message
    user_message = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            user_message = (
                msg.content if isinstance(msg.content, str) else str(msg.content)
            )
            break

    if not user_message:
        return {"intent": "quick_answer"}

    intent, latency_ms = classify_intent(user_message)

    writer(
        SSEEvent(
            type="intent_classified",
            data={
                "intent": intent,
                "latency_ms": round(latency_ms, 1),
            },
        )
    )

    logger.info("Orchestrator classified intent: %s (%.0fms)", intent, latency_ms)

    return {"intent": intent, "iteration": 0}


def strategy_node(state: AgentState) -> dict:
    """Run the strategy subgraph."""
    graph = build_strategy_subgraph()
    writer = get_stream_writer()

    # Stream with both custom (SSE) and values (state) modes in a single pass
    result_state = None
    for mode, event in graph.stream(state, stream_mode=["custom", "values"]):
        if mode == "custom" and isinstance(event, SSEEvent):
            writer(event)
        elif mode == "values":
            result_state = event

    if result_state is None:
        result_state = {}

    return {
        "messages": result_state.get("messages", []),
        "total_input_tokens": result_state.get("total_input_tokens", 0),
        "total_output_tokens": result_state.get("total_output_tokens", 0),
        "total_cost_usd": result_state.get("total_cost_usd", "0"),
        "active_agent": "strategy",
        "section_completeness": result_state.get("section_completeness"),
    }


def research_node(state: AgentState) -> dict:
    """Run the research subgraph."""
    graph = build_research_subgraph()
    writer = get_stream_writer()

    # Stream with both custom (SSE) and values (state) modes in a single pass
    result_state = None
    for mode, event in graph.stream(state, stream_mode=["custom", "values"]):
        if mode == "custom" and isinstance(event, SSEEvent):
            writer(event)
        elif mode == "values":
            result_state = event

    if result_state is None:
        result_state = {}

    return {
        "messages": result_state.get("messages", []),
        "total_input_tokens": result_state.get("total_input_tokens", 0),
        "total_output_tokens": result_state.get("total_output_tokens", 0),
        "total_cost_usd": result_state.get("total_cost_usd", "0"),
        "active_agent": "research",
        "research_results": result_state.get("research_results"),
    }


def outreach_node(state: AgentState) -> dict:
    """Run the outreach subgraph."""
    graph = build_outreach_subgraph()
    writer = get_stream_writer()

    # Stream with both custom (SSE) and values (state) modes in a single pass
    result_state = None
    for mode, event in graph.stream(state, stream_mode=["custom", "values"]):
        if mode == "custom" and isinstance(event, SSEEvent):
            writer(event)
        elif mode == "values":
            result_state = event

    if result_state is None:
        result_state = {}

    return {
        "messages": result_state.get("messages", []),
        "total_input_tokens": result_state.get("total_input_tokens", 0),
        "total_output_tokens": result_state.get("total_output_tokens", 0),
        "total_cost_usd": result_state.get("total_cost_usd", "0"),
        "active_agent": "outreach",
    }


def quick_response_node(state: AgentState) -> dict:
    """Handle quick answers directly with Haiku (no tools needed)."""
    writer = get_stream_writer()
    model_name = "claude-haiku-4-5-20251001"

    model = ChatAnthropic(
        model=model_name,
        temperature=0.4,
        max_tokens=2048,
    )

    messages = list(state["messages"])

    # Add a minimal system message for quick responses
    quick_prompt = (
        "You are a concise GTM strategist. Answer briefly (max 150 words). "
        "Be direct and action-oriented. Use bullet points."
    )

    # Add research context if available
    research_results = state.get("research_results")
    if research_results:
        quick_prompt += (
            "\n\nResearch context available:\n"
            + json.dumps(research_results, indent=2, default=str)[:2000]
        )

    if not messages or not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=quick_prompt))

    response = model.invoke(messages)

    # Track usage
    usage = getattr(response, "usage_metadata", None) or {}
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cost = _estimate_cost(model_name, input_tokens, output_tokens)

    new_total_input = state.get("total_input_tokens", 0) + input_tokens
    new_total_output = state.get("total_output_tokens", 0) + output_tokens
    new_total_cost = str(Decimal(state.get("total_cost_usd", "0")) + Decimal(str(cost)))

    # Emit text
    if response.content and isinstance(response.content, str):
        writer(SSEEvent(type="chunk", data={"text": response.content}))
    elif response.content and isinstance(response.content, list):
        for block in response.content:
            if isinstance(block, dict) and block.get("type") == "text":
                writer(SSEEvent(type="chunk", data={"text": block["text"]}))

    return {
        "messages": [response],
        "total_input_tokens": new_total_input,
        "total_output_tokens": new_total_output,
        "total_cost_usd": new_total_cost,
        "active_agent": "quick",
    }


def passthrough_node(state: AgentState) -> dict:
    """Passthrough for intents not yet handled by specialist agents.

    Currently handles 'campaign' intent by falling back to the
    quick_response behavior. This node is a placeholder for
    future Campaign management subgraphs.
    """
    return quick_response_node(state)


# ---------------------------------------------------------------------------
# Routing logic
# ---------------------------------------------------------------------------


def route_to_agent(
    state: AgentState,
) -> Literal[
    "strategy_node",
    "research_node",
    "outreach_node",
    "quick_response_node",
    "passthrough_node",
]:
    """Route to the appropriate specialist based on classified intent."""
    intent = state.get("intent", "quick_answer")

    routing = {
        "strategy_edit": "strategy_node",
        "research": "research_node",
        "quick_answer": "quick_response_node",
        "campaign": "passthrough_node",
        "outreach": "outreach_node",
    }

    target = routing.get(intent, "quick_response_node")
    logger.info("Routing intent '%s' to %s", intent, target)
    return target


# ---------------------------------------------------------------------------
# Orchestrator graph construction
# ---------------------------------------------------------------------------


def build_orchestrator_graph() -> Any:
    """Build and compile the top-level orchestrator graph.

    The orchestrator classifies intent, routes to the correct specialist
    subgraph, and returns the result. Each specialist agent handles its
    own tool loop internally.

    Returns:
        Compiled LangGraph StateGraph.
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("classify", classify_node)
    graph.add_node("strategy_node", strategy_node)
    graph.add_node("research_node", research_node)
    graph.add_node("outreach_node", outreach_node)
    graph.add_node("quick_response_node", quick_response_node)
    graph.add_node("passthrough_node", passthrough_node)

    # Entry point: always classify first
    graph.set_entry_point("classify")

    # Route from classify to specialist
    graph.add_conditional_edges(
        "classify",
        route_to_agent,
        {
            "strategy_node": "strategy_node",
            "research_node": "research_node",
            "outreach_node": "outreach_node",
            "quick_response_node": "quick_response_node",
            "passthrough_node": "passthrough_node",
        },
    )

    # All specialists go to END
    graph.add_edge("strategy_node", END)
    graph.add_edge("research_node", END)
    graph.add_edge("outreach_node", END)
    graph.add_edge("quick_response_node", END)
    graph.add_edge("passthrough_node", END)

    return graph.compile()
