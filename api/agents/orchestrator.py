"""Top-level orchestrator graph for multi-agent routing.

The orchestrator classifies user intent and routes to the appropriate
specialist subgraph. It manages context distribution and result synthesis.

Flow:
  User message -> classify_intent -> route_to_agent
                                        |
      +----------+----------+----------+----------+----------+
      |          |          |          |          |          |
  strategy  research  enrichment  outreach    copilot  passthrough
      |          |          |          |          |          |
      +----------+----------+----------+----------+----------+
                                        |
                                    synthesize -> END

Supported intents: strategy_edit, research, enrichment, outreach, copilot.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from langchain_core.messages import HumanMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph

from .graph import SSEEvent
from .intent import classify_intent
from .state import AgentState
from .subgraphs.copilot import build_copilot_subgraph

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Orchestrator nodes
# ---------------------------------------------------------------------------


def classify_node(state: AgentState) -> dict:
    """Classify user intent from the last human message."""
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
        return {"intent": "copilot"}

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


def copilot_node(state: AgentState) -> dict:
    """Run the copilot subgraph for quick questions and data lookups."""
    graph = build_copilot_subgraph()
    writer = get_stream_writer()

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
        "active_agent": "copilot",
    }


def strategy_node(state: AgentState) -> dict:
    """Run the strategy subgraph.

    Imports lazily to avoid circular deps when strategy subgraph
    is not yet merged to this branch.
    """
    try:
        from .subgraphs.strategy import build_strategy_subgraph

        graph = build_strategy_subgraph()
    except ImportError:
        logger.warning("Strategy subgraph not available, falling back to copilot")
        return copilot_node(state)

    writer = get_stream_writer()

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
    try:
        from .subgraphs.research import build_research_subgraph

        graph = build_research_subgraph()
    except ImportError:
        logger.warning("Research subgraph not available, falling back to copilot")
        return copilot_node(state)

    writer = get_stream_writer()

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


def enrichment_node(state: AgentState) -> dict:
    """Run the enrichment subgraph."""
    try:
        from .subgraphs.enrichment import build_enrichment_subgraph

        graph = build_enrichment_subgraph()
    except ImportError:
        logger.warning("Enrichment subgraph not available, falling back to copilot")
        return copilot_node(state)

    writer = get_stream_writer()

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
        "active_agent": "enrichment",
    }


def outreach_node(state: AgentState) -> dict:
    """Run the outreach subgraph."""
    try:
        from .subgraphs.outreach import build_outreach_subgraph

        graph = build_outreach_subgraph()
    except ImportError:
        logger.warning("Outreach subgraph not available, falling back to copilot")
        return copilot_node(state)

    writer = get_stream_writer()

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


def passthrough_node(state: AgentState) -> dict:
    """Passthrough for intents not yet handled by specialist agents."""
    return copilot_node(state)


# ---------------------------------------------------------------------------
# Routing logic
# ---------------------------------------------------------------------------


def route_to_agent(
    state: AgentState,
) -> Literal[
    "strategy_node",
    "research_node",
    "enrichment_node",
    "outreach_node",
    "copilot_node",
    "passthrough_node",
]:
    """Route to the appropriate specialist based on classified intent."""
    intent = state.get("intent", "copilot")

    routing = {
        "strategy_edit": "strategy_node",
        "research": "research_node",
        "enrichment": "enrichment_node",
        "outreach": "outreach_node",
        "copilot": "copilot_node",
    }

    target = routing.get(intent, "copilot_node")
    logger.info("Routing intent '%s' to %s", intent, target)
    return target


# ---------------------------------------------------------------------------
# Orchestrator graph construction
# ---------------------------------------------------------------------------


def build_orchestrator_graph() -> Any:
    """Build and compile the top-level orchestrator graph.

    Routes user messages to specialist subgraphs based on intent
    classification. Falls back to copilot for unrecognized intents.

    Returns:
        Compiled LangGraph StateGraph.
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("classify", classify_node)
    graph.add_node("strategy_node", strategy_node)
    graph.add_node("research_node", research_node)
    graph.add_node("enrichment_node", enrichment_node)
    graph.add_node("outreach_node", outreach_node)
    graph.add_node("copilot_node", copilot_node)
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
            "enrichment_node": "enrichment_node",
            "outreach_node": "outreach_node",
            "copilot_node": "copilot_node",
            "passthrough_node": "passthrough_node",
        },
    )

    # All specialists go to END
    graph.add_edge("strategy_node", END)
    graph.add_edge("research_node", END)
    graph.add_edge("enrichment_node", END)
    graph.add_edge("outreach_node", END)
    graph.add_edge("copilot_node", END)
    graph.add_edge("passthrough_node", END)

    return graph.compile()
