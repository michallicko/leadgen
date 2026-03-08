"""Deterministic planner as LangGraph state machine (BL-1009).

Executes plan phases as a state machine — code orchestration, NOT
LLM-driven. Sonnet is only called at decision points the state
machine cannot resolve deterministically.

The planner loads a Plan config and walks through its phases list
in order. Each phase maps to a deterministic handler function that
orchestrates tool calls, emits SSE events, and accumulates results.

Phase handlers are STUBS for now — they emit mock findings and
return mock data so the planner flow can be tested end-to-end.
Full implementations arrive with BL-1012 (Opus) and BL-1013 (Research).

This module does NOT replace pipeline.py — it is a new alternative
path activated when a plan is loaded.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph

from .graph import SSEEvent
from .planner_state import PlannerState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Interrupt classification
# ---------------------------------------------------------------------------


def classify_interrupt(message: str) -> str:
    """Classify a user interrupt type using keyword matching.

    Returns one of: stop, redirect, question, correction (default).
    A Haiku fallback can be added later for ambiguous cases.
    """
    lower = message.lower().strip()

    if any(w in lower for w in ["stop", "cancel", "abort", "wrong", "wait", "hold on"]):
        return "stop"
    if any(
        w in lower for w in ["actually", "instead", "focus on", "switch to", "skip"]
    ):
        return "redirect"
    if "?" in lower or any(
        lower.startswith(w) for w in ["what", "how", "why", "where", "when", "show me"]
    ):
        return "question"
    # Default: treat as correction
    return "correction"


# ---------------------------------------------------------------------------
# Phase handlers (stubs — full implementation in BL-1012, BL-1013)
# ---------------------------------------------------------------------------


def _run_research_company(state: PlannerState, writer) -> dict:
    """Stub: research the target company from plan config.

    Full implementation will:
    1. Get primary_source from plan config
    2. Call web_research tool to fetch website
    3. Emit research_finding events as facts are discovered
    4. Store parsed website data in state.research_data
    """
    plan = state["plan_config"]
    plan_name = plan.get("name", "unknown")

    writer(
        SSEEvent(
            type="research_finding",
            data={
                "action": "research_company",
                "finding": f"Starting company research for plan '{plan_name}'...",
                "step": 1,
            },
        )
    )

    # Mock research data
    research = dict(state.get("research_data") or {})
    research["company"] = {
        "source": plan.get("research_requirements", {}).get(
            "primary_source", "website"
        ),
        "status": "stub_complete",
        "facts": ["Company data would be fetched here"],
    }

    writer(
        SSEEvent(
            type="research_finding",
            data={
                "action": "research_company",
                "finding": "Company research complete (stub).",
                "step": 2,
            },
        )
    )

    findings = list(state.get("findings") or [])
    findings.append(
        {
            "phase": "research_company",
            "action": "research_company",
            "status": "stub_complete",
        }
    )

    return {
        "research_data": research,
        "findings": findings,
        "phase_results": {
            **state.get("phase_results", {}),
            "research_company": {"status": "complete", "data": research["company"]},
        },
    }


def _run_research_market(state: PlannerState, writer) -> dict:
    """Stub: research market and competitors.

    Full implementation will:
    1. Search for competitors (web search)
    2. Search for market segment data
    3. Cross-check findings against website data
    4. Apply cross_check_policy from plan config
    """
    plan = state["plan_config"]
    cross_check = plan.get("research_requirements", {}).get(
        "cross_check_policy", "verify"
    )

    writer(
        SSEEvent(
            type="research_finding",
            data={
                "action": "research_market",
                "finding": f"Starting market research (policy: {cross_check})...",
                "step": 1,
            },
        )
    )

    research = dict(state.get("research_data") or {})
    research["market"] = {
        "cross_check_policy": cross_check,
        "status": "stub_complete",
        "competitors": ["Competitor data would be fetched here"],
    }

    writer(
        SSEEvent(
            type="research_finding",
            data={
                "action": "research_market",
                "finding": "Market research complete (stub).",
                "step": 2,
            },
        )
    )

    findings = list(state.get("findings") or [])
    findings.append(
        {
            "phase": "research_market",
            "action": "research_market",
            "status": "stub_complete",
        }
    )

    return {
        "research_data": research,
        "findings": findings,
        "phase_results": {
            **state.get("phase_results", {}),
            "research_market": {"status": "complete", "data": research["market"]},
        },
    }


def _run_build_strategy(state: PlannerState, writer) -> dict:
    """Stub: build strategy sections using research data.

    Full implementation will:
    1. For each section in scoring_rubric.sections
    2. Assemble context (research_data + user_corrections + existing sections)
    3. Call specialist tool (Opus) to write the section
    4. Stream section content to editor via typewriter events
    5. Call specialist for quality scoring
    """
    plan = state["plan_config"]
    rubric = plan.get("scoring_rubric", {})
    sections = rubric.get("sections", [])

    writer(
        SSEEvent(
            type="research_finding",
            data={
                "action": "build_strategy",
                "finding": f"Building strategy ({len(sections)} sections)...",
                "step": 1,
            },
        )
    )

    completeness = dict(state.get("section_completeness") or {})
    for section in sections:
        section_name = (
            section if isinstance(section, str) else section.get("name", "unknown")
        )
        completeness[section_name] = True

    writer(
        SSEEvent(
            type="research_finding",
            data={
                "action": "build_strategy",
                "finding": f"Strategy draft complete ({len(sections)} sections filled, stub).",
                "step": 2,
            },
        )
    )

    findings = list(state.get("findings") or [])
    findings.append(
        {
            "phase": "build_strategy",
            "action": "build_strategy",
            "status": "stub_complete",
        }
    )

    return {
        "section_completeness": completeness,
        "findings": findings,
        "phase_results": {
            **state.get("phase_results", {}),
            "build_strategy": {"status": "complete", "sections_filled": len(sections)},
        },
    }


def _run_review_and_score(state: PlannerState, writer) -> dict:
    """Stub: review and score the completed strategy.

    Full implementation will:
    1. Call specialist (Opus) for full strategy quality evaluation
    2. Emit quality scores per section
    3. Generate improvement suggestions
    4. Emit quick_actions (score, navigate to contacts)
    """
    writer(
        SSEEvent(
            type="research_finding",
            data={
                "action": "review_and_score",
                "finding": "Reviewing strategy quality...",
                "step": 1,
            },
        )
    )

    completeness = state.get("section_completeness") or {}
    filled = sum(1 for v in completeness.values() if v)
    total = len(completeness) if completeness else 1
    score = round((filled / total) * 100) if total else 0

    writer(
        SSEEvent(
            type="research_finding",
            data={
                "action": "review_and_score",
                "finding": f"Strategy quality score: {score}/100 (stub).",
                "step": 2,
            },
        )
    )

    findings = list(state.get("findings") or [])
    findings.append(
        {
            "phase": "review_and_score",
            "action": "review_and_score",
            "status": "stub_complete",
            "score": score,
        }
    )

    return {
        "findings": findings,
        "phase_results": {
            **state.get("phase_results", {}),
            "review_and_score": {"status": "complete", "score": score},
        },
    }


# Phase handler registry
PHASE_HANDLERS: dict[str, Any] = {
    "research_company": _run_research_company,
    "research_market": _run_research_market,
    "build_strategy": _run_build_strategy,
    "review_and_score": _run_review_and_score,
}


# ---------------------------------------------------------------------------
# Graph node functions
# ---------------------------------------------------------------------------


def initialize_node(state: PlannerState) -> dict:
    """Load plan config into state, set current phase to first phase."""
    writer = get_stream_writer()
    plan = state["plan_config"]
    phases = plan.get("phases", [])
    plan_name = plan.get("name", "Unknown Plan")

    writer(
        SSEEvent(
            type="phase_start",
            data={"phase": "initialize", "plan_name": plan_name},
        )
    )

    logger.info("Planner initialized: plan=%s, phases=%s", plan.get("id"), phases)

    first_phase = phases[0] if phases else ""
    return {
        "current_phase": first_phase,
        "phase_index": 0,
        "phase_results": {},
        "research_data": state.get("research_data") or {},
        "user_corrections": state.get("user_corrections") or [],
        "section_completeness": state.get("section_completeness") or {},
        "findings": state.get("findings") or [],
        "is_interrupted": False,
        "interrupt_message": "",
        "interrupt_type": "",
        "iteration": 0,
    }


def execute_phase_node(state: PlannerState) -> dict:
    """Dispatch to the phase-specific handler based on current_phase.

    Each handler is deterministic orchestration code that may call tools
    and emit SSE events. If no handler exists for the phase, it is
    skipped with a warning.
    """
    writer = get_stream_writer()
    current_phase = state.get("current_phase", "")

    if not current_phase:
        logger.warning("execute_phase_node called with empty current_phase")
        return {}

    writer(
        SSEEvent(
            type="phase_start",
            data={"phase": current_phase},
        )
    )

    handler = PHASE_HANDLERS.get(current_phase)
    if handler is None:
        logger.warning("No handler for phase '%s', skipping", current_phase)
        writer(
            SSEEvent(
                type="research_finding",
                data={
                    "action": current_phase,
                    "finding": f"Phase '{current_phase}' has no handler yet (skipped).",
                    "step": 0,
                },
            )
        )
        findings = list(state.get("findings") or [])
        findings.append(
            {"phase": current_phase, "action": "skip", "status": "no_handler"}
        )
        return {
            "findings": findings,
            "phase_results": {
                **state.get("phase_results", {}),
                current_phase: {"status": "skipped", "data": None},
            },
        }

    result = handler(state, writer)
    return result


def check_interrupt_node(state: PlannerState) -> dict:
    """Check if the user interrupted mid-plan and classify the interrupt.

    Delegates to the full interrupt processing pipeline (BL-1018)
    which handles classification (keyword + Haiku) and type-specific
    handling (correction, stop, question, redirect).
    """
    if not state.get("is_interrupted"):
        return {"is_interrupted": False, "interrupt_type": ""}

    from .interrupt_handlers import process_interrupt

    message = state.get("interrupt_message", "")
    logger.info("Planner interrupt detected, delegating to handler: '%s'", message[:80])

    writer = get_stream_writer()
    writer(
        SSEEvent(
            type="interrupt_received",
            data={"message": message[:200]},
        )
    )

    result = process_interrupt(state)

    # Emit acknowledgment based on interrupt type
    itype = result.get("interrupt_type", "")
    if itype == "stop":
        completed = [
            phase
            for phase, res in (state.get("phase_results") or {}).items()
            if isinstance(res, dict) and res.get("status") == "complete"
        ]
        writer(
            SSEEvent(
                type="interrupt_handled",
                data={
                    "action": "stop",
                    "completed_phases": completed,
                    "message": "Plan execution stopped.",
                },
            )
        )
    elif itype == "question":
        writer(
            SSEEvent(
                type="interrupt_handled",
                data={
                    "action": "question",
                    "message": "Noted your question. Resuming plan.",
                },
            )
        )
    elif itype == "correction":
        writer(
            SSEEvent(
                type="interrupt_handled",
                data={
                    "action": "correction",
                    "message": "Correction noted. Continuing with updated context.",
                },
            )
        )
    elif itype == "redirect":
        writer(
            SSEEvent(
                type="interrupt_handled",
                data={
                    "action": "redirect",
                    "message": "Redirecting plan focus.",
                },
            )
        )

    return result


def advance_phase_node(state: PlannerState) -> dict:
    """Increment phase_index and advance to the next phase.

    If all phases are done, current_phase is set to empty string
    which will cause phase_router to route to END.
    """
    plan = state["plan_config"]
    phases = plan.get("phases", [])
    next_index = state.get("phase_index", 0) + 1

    if next_index >= len(phases):
        logger.info("Planner completed all %d phases", len(phases))
        return {
            "phase_index": next_index,
            "current_phase": "",
            "iteration": state.get("iteration", 0) + 1,
        }

    next_phase = phases[next_index]
    logger.info("Planner advancing to phase %d: %s", next_index, next_phase)
    return {
        "phase_index": next_index,
        "current_phase": next_phase,
        "iteration": state.get("iteration", 0) + 1,
    }


def decision_point_node(state: PlannerState) -> dict:
    """Called when a phase handler cannot proceed deterministically.

    This is the ONLY node that calls an LLM (Sonnet) for a decision.
    Currently a stub — returns to execute_phase to continue.
    """
    writer = get_stream_writer()
    current_phase = state.get("current_phase", "")

    writer(
        SSEEvent(
            type="research_finding",
            data={
                "action": "decision_point",
                "finding": f"Decision point reached in phase '{current_phase}' (stub — auto-continuing).",
                "step": 0,
            },
        )
    )

    logger.info("Decision point in phase '%s' (stub, auto-continuing)", current_phase)
    return {}


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------


def phase_router(
    state: PlannerState,
) -> Literal["check_interrupt", "advance_phase", "decision_point"]:
    """Route after execute_phase: check for interrupts, then advance.

    In future, phases can set a flag to route to decision_point
    when they cannot proceed. For now, always check interrupt then advance.
    """
    if state.get("is_interrupted"):
        return "check_interrupt"
    return "advance_phase"


def interrupt_router(
    state: PlannerState,
) -> Literal["execute_phase", "__end__"]:
    """Route after check_interrupt based on interrupt type."""
    itype = state.get("interrupt_type", "")

    if itype == "stop":
        return "__end__"

    # correction, question, redirect all resume execution
    return "execute_phase"


def advance_router(
    state: PlannerState,
) -> Literal["execute_phase", "__end__"]:
    """Route after advance_phase: continue if phases remain, else END."""
    current_phase = state.get("current_phase", "")
    if not current_phase:
        return "__end__"
    return "execute_phase"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_planner_graph(plan_config: dict) -> Any:
    """Build a deterministic planner graph from a plan config.

    Args:
        plan_config: Serialized Plan dict with id, name, phases, etc.

    Returns:
        Compiled LangGraph StateGraph ready for streaming.
    """
    graph = StateGraph(PlannerState)

    graph.add_node("initialize", initialize_node)
    graph.add_node("execute_phase", execute_phase_node)
    graph.add_node("check_interrupt", check_interrupt_node)
    graph.add_node("advance_phase", advance_phase_node)
    graph.add_node("decision_point", decision_point_node)

    graph.set_entry_point("initialize")
    graph.add_edge("initialize", "execute_phase")

    graph.add_conditional_edges(
        "execute_phase",
        phase_router,
        {
            "check_interrupt": "check_interrupt",
            "advance_phase": "advance_phase",
            "decision_point": "decision_point",
        },
    )

    graph.add_conditional_edges(
        "check_interrupt",
        interrupt_router,
        {
            "execute_phase": "execute_phase",
            "__end__": END,
        },
    )

    graph.add_conditional_edges(
        "advance_phase",
        advance_router,
        {
            "execute_phase": "execute_phase",
            "__end__": END,
        },
    )

    graph.add_edge("decision_point", "execute_phase")

    return graph.compile()
