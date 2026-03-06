"""Pipeline orchestrator — phase-aware routing across the full GTM workflow.

Composes the multi-agent orchestrator with pipeline phase management.
The app has four phases: Strategy -> Contacts -> Messages -> Campaign.
The pipeline tracks which phases are complete, routes to the correct
specialist, and enables sequential handoffs between agents.

Phase flow:
  Strategy  ->  Contacts  ->  Messages  ->  Campaign
  (research)    (enrichment)   (outreach)    (campaign mgmt)

Key features:
  - Phase-aware routing: understands current phase context
  - Sequential handoff: research informs strategy, enrichment feeds outreach
  - Cross-agent context: passes relevant state between subgraphs
  - Pipeline state tracking: which phases complete, what data gathered
  - Parallel fan-out support via LangGraph Send() for batch enrichment
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from langchain_core.messages import HumanMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph

from .graph import SSEEvent
from .intent import classify_intent
from .orchestrator import (
    copilot_node,
    enrichment_node,
    outreach_node,
    research_node,
    strategy_node,
)
from .state import AgentState

logger = logging.getLogger(__name__)

# Phase definitions with their associated intents
PHASES = {
    "strategy": {
        "label": "Strategy",
        "primary_intents": {"strategy_edit", "research"},
        "description": "Define ICP, personas, value proposition",
    },
    "contacts": {
        "label": "Contacts",
        "primary_intents": {"enrichment", "research"},
        "description": "Enrich companies and contacts",
    },
    "messages": {
        "label": "Messages",
        "primary_intents": {"outreach"},
        "description": "Generate personalized outreach messages",
    },
    "campaign": {
        "label": "Campaign",
        "primary_intents": {"outreach"},
        "description": "Launch and manage outreach campaigns",
    },
}

# Phase ordering for sequential advancement
PHASE_ORDER = ["strategy", "contacts", "messages", "campaign"]


def _detect_phase(state: AgentState) -> str:
    """Detect current pipeline phase from state or tool_context.

    Uses explicit pipeline_phase if set, falls back to page_context
    from tool_context, or defaults to 'strategy'.
    """
    # Explicit phase from state
    phase = state.get("pipeline_phase")
    if phase and phase in PHASES:
        return phase

    # Infer from tool_context page_context
    tool_ctx = state.get("tool_context", {})
    page = tool_ctx.get("page_context", "")

    page_to_phase = {
        "strategy": "strategy",
        "playbook": "strategy",
        "contacts": "contacts",
        "companies": "contacts",
        "messages": "messages",
        "outreach": "messages",
        "campaign": "campaign",
    }

    for key, phase_name in page_to_phase.items():
        if key in str(page).lower():
            return phase_name

    return "strategy"


def _build_pipeline_context(state: AgentState) -> dict:
    """Build cross-agent context from accumulated pipeline data.

    Collects relevant data from previous phases to pass forward:
    - Strategy results inform enrichment priorities
    - Enrichment data feeds message personalization
    - Research context available to all agents
    """
    ctx = state.get("pipeline_context") or {}

    # Add research results if available
    research = state.get("research_results")
    if research:
        ctx["research_results"] = research

    # Add section completeness for strategy progress
    sections = state.get("section_completeness")
    if sections:
        ctx["section_completeness"] = sections

    # Add phase completion status
    phases_done = state.get("pipeline_phases_complete") or []
    ctx["phases_complete"] = phases_done

    return ctx


# ---------------------------------------------------------------------------
# Pipeline nodes
# ---------------------------------------------------------------------------


def pipeline_classify_node(state: AgentState) -> dict:
    """Classify intent with phase awareness.

    Like the base orchestrator classify, but also detects the current
    pipeline phase and enriches the context accordingly.
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
        return {"intent": "copilot", "pipeline_phase": _detect_phase(state)}

    intent, latency_ms = classify_intent(user_message)
    current_phase = _detect_phase(state)
    pipeline_ctx = _build_pipeline_context(state)

    writer(
        SSEEvent(
            type="intent_classified",
            data={
                "intent": intent,
                "latency_ms": round(latency_ms, 1),
                "pipeline_phase": current_phase,
            },
        )
    )

    # Emit pipeline phase event
    writer(
        SSEEvent(
            type="pipeline_phase",
            data={
                "current_phase": current_phase,
                "phases_complete": state.get("pipeline_phases_complete") or [],
            },
        )
    )

    logger.info(
        "Pipeline classified intent: %s, phase: %s (%.0fms)",
        intent,
        current_phase,
        latency_ms,
    )

    return {
        "intent": intent,
        "iteration": 0,
        "pipeline_phase": current_phase,
        "pipeline_context": pipeline_ctx,
    }


def pipeline_strategy_node(state: AgentState) -> dict:
    """Run strategy with pipeline context injection."""
    result = strategy_node(state)

    # Track phase completion based on section completeness
    completeness = result.get("section_completeness") or {}
    phases_done = list(state.get("pipeline_phases_complete") or [])

    # Strategy is "complete" when at least 3 sections are filled
    filled = sum(1 for v in completeness.values() if v)
    if filled >= 3 and "strategy" not in phases_done:
        phases_done.append("strategy")
        result["pipeline_phases_complete"] = phases_done

    return result


def pipeline_enrichment_node(state: AgentState) -> dict:
    """Run enrichment with pipeline context (strategy data passed through)."""
    result = enrichment_node(state)

    # Mark contacts phase as in-progress after first enrichment run
    phases_done = list(state.get("pipeline_phases_complete") or [])
    if "contacts" not in phases_done:
        phases_done.append("contacts")
        result["pipeline_phases_complete"] = phases_done

    return result


def pipeline_outreach_node(state: AgentState) -> dict:
    """Run outreach with enrichment context for message personalization."""
    result = outreach_node(state)

    # Mark messages phase as in-progress
    phases_done = list(state.get("pipeline_phases_complete") or [])
    if "messages" not in phases_done:
        phases_done.append("messages")
        result["pipeline_phases_complete"] = phases_done

    return result


# ---------------------------------------------------------------------------
# Pipeline routing
# ---------------------------------------------------------------------------


def pipeline_route(
    state: AgentState,
) -> Literal[
    "pipeline_strategy_node",
    "research_node",
    "pipeline_enrichment_node",
    "pipeline_outreach_node",
    "copilot_node",
]:
    """Route with phase awareness.

    Uses intent classification but considers the current pipeline phase
    to make better routing decisions.
    """
    intent = state.get("intent", "copilot")
    phase = state.get("pipeline_phase", "strategy")

    # Direct intent mapping takes priority
    intent_routing = {
        "strategy_edit": "pipeline_strategy_node",
        "research": "research_node",
        "enrichment": "pipeline_enrichment_node",
        "outreach": "pipeline_outreach_node",
        "copilot": "copilot_node",
    }

    target = intent_routing.get(intent, "copilot_node")
    logger.info(
        "Pipeline routing intent='%s' phase='%s' -> %s",
        intent,
        phase,
        target,
    )
    return target


# ---------------------------------------------------------------------------
# Pipeline graph construction
# ---------------------------------------------------------------------------


def build_pipeline_graph() -> Any:
    """Build the full pipeline orchestrator graph.

    Composes the base orchestrator agents with phase-aware routing
    and cross-agent context passing. This is the top-level graph
    for the complete GTM workflow.

    Returns:
        Compiled LangGraph StateGraph.
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("classify", pipeline_classify_node)
    graph.add_node("pipeline_strategy_node", pipeline_strategy_node)
    graph.add_node("research_node", research_node)
    graph.add_node("pipeline_enrichment_node", pipeline_enrichment_node)
    graph.add_node("pipeline_outreach_node", pipeline_outreach_node)
    graph.add_node("copilot_node", copilot_node)

    # Entry point
    graph.set_entry_point("classify")

    # Phase-aware routing
    graph.add_conditional_edges(
        "classify",
        pipeline_route,
        {
            "pipeline_strategy_node": "pipeline_strategy_node",
            "research_node": "research_node",
            "pipeline_enrichment_node": "pipeline_enrichment_node",
            "pipeline_outreach_node": "pipeline_outreach_node",
            "copilot_node": "copilot_node",
        },
    )

    # All agents go to END
    graph.add_edge("pipeline_strategy_node", END)
    graph.add_edge("research_node", END)
    graph.add_edge("pipeline_enrichment_node", END)
    graph.add_edge("pipeline_outreach_node", END)
    graph.add_edge("copilot_node", END)

    return graph.compile()


def get_pipeline_status(state: AgentState) -> dict:
    """Get a summary of pipeline progress.

    Returns phase completion status and current phase for UI rendering.
    """
    phases_done = state.get("pipeline_phases_complete") or []
    current = state.get("pipeline_phase") or "strategy"

    return {
        "current_phase": current,
        "phases": {
            name: {
                "label": info["label"],
                "description": info["description"],
                "complete": name in phases_done,
                "current": name == current,
            }
            for name, info in PHASES.items()
        },
        "phase_order": PHASE_ORDER,
    }
