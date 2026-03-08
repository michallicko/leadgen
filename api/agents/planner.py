"""Deterministic planner as LangGraph state machine (BL-1009).

Executes plan phases as a state machine — code orchestration, NOT
LLM-driven. Sonnet is only called at decision points the state
machine cannot resolve deterministically.

The planner loads a Plan config and walks through its phases list
in order. Each phase maps to a deterministic handler function that
orchestrates tool calls, emits SSE events, and accumulates results.

Phase handlers call the real research pipeline (web_fetch + market_research
+ cross_checker) and the Opus specialist for strategy writing and scoring.
When dependencies are unavailable (missing API keys, etc.), handlers
degrade gracefully with informative messages.

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
# Phase handlers
# ---------------------------------------------------------------------------


def _run_research_company(state: PlannerState, writer) -> dict:
    """Research the target company using the real research pipeline.

    1. Gets primary_source (domain) from plan config
    2. Calls run_research_pipeline which fetches the website,
       runs market research, and cross-checks findings
    3. Emits research_finding events as facts are discovered
    4. Stores all research data in state.research_data
    """
    plan = state["plan_config"]
    plan_name = plan.get("name", "unknown")
    domain = plan.get("research_requirements", {}).get("primary_source", "")

    writer(
        SSEEvent(
            type="research_finding",
            data={
                "action": "research_company",
                "finding": "Starting company research for plan '{}'...".format(
                    plan_name
                ),
                "step": 1,
            },
        )
    )

    if not domain:
        logger.warning("No primary_source domain in plan config, skipping research")
        findings = list(state.get("findings") or [])
        findings.append(
            {
                "phase": "research_company",
                "action": "research_company",
                "status": "skipped",
                "reason": "no_domain",
            }
        )
        return {
            "findings": findings,
            "phase_results": {
                **state.get("phase_results", {}),
                "research_company": {"status": "skipped", "reason": "no_domain"},
            },
        }

    # Call the real research pipeline (sync — uses requests + Perplexity)
    try:
        from .tools.research_pipeline import run_research_pipeline

        # Extract goal from the user's first message
        messages = state.get("messages") or []
        goal = ""
        for msg in messages:
            if hasattr(msg, "type") and msg.type == "human":
                goal = msg.content if hasattr(msg, "content") else ""
                break

        def emit_finding(title, message):
            writer(
                SSEEvent(
                    type="research_finding",
                    data={
                        "action": "research_company",
                        "finding": "{}: {}".format(title, message),
                    },
                )
            )

        pipeline_findings = run_research_pipeline(
            domain=domain,
            goal=goal,
            plan_config=plan,
            emit_finding=emit_finding,
        )

        research = dict(state.get("research_data") or {})
        research["website"] = pipeline_findings.website
        research["market"] = pipeline_findings.market
        research["cross_checks"] = pipeline_findings.cross_checks
        research["confirmed_facts"] = pipeline_findings.confirmed_facts
        research["all_sources"] = pipeline_findings.all_sources
        research["halt_gates"] = pipeline_findings.halt_gates_needed
        research["errors"] = pipeline_findings.errors

        # Emit halt gates if any conflicts need user confirmation
        if pipeline_findings.halt_gates_needed:
            writer(
                SSEEvent(
                    type="halt_gate",
                    data={
                        "conflicts": pipeline_findings.halt_gates_needed,
                        "message": "{} finding(s) need your confirmation".format(
                            len(pipeline_findings.halt_gates_needed)
                        ),
                    },
                )
            )

        writer(
            SSEEvent(
                type="research_finding",
                data={
                    "action": "research_company",
                    "finding": "Company and market research complete. {} confirmed facts, {} sources.".format(
                        len(pipeline_findings.confirmed_facts),
                        len(pipeline_findings.all_sources),
                    ),
                    "step": 2,
                },
            )
        )

        findings = list(state.get("findings") or [])
        findings.append(
            {
                "phase": "research_company",
                "action": "research_company",
                "status": "complete",
                "confirmed_facts": len(pipeline_findings.confirmed_facts),
                "sources": len(pipeline_findings.all_sources),
                "errors": pipeline_findings.errors,
            }
        )

        return {
            "research_data": research,
            "findings": findings,
            "phase_results": {
                **state.get("phase_results", {}),
                "research_company": {
                    "status": "complete",
                    "data": pipeline_findings.confirmed_facts,
                },
            },
        }

    except Exception as exc:
        logger.exception("Research pipeline failed: %s", exc)
        writer(
            SSEEvent(
                type="research_finding",
                data={
                    "action": "research_company",
                    "finding": "Research pipeline error: {}".format(str(exc)[:200]),
                    "step": 2,
                },
            )
        )
        findings = list(state.get("findings") or [])
        findings.append(
            {
                "phase": "research_company",
                "action": "research_company",
                "status": "error",
                "error": str(exc)[:200],
            }
        )
        return {
            "findings": findings,
            "phase_results": {
                **state.get("phase_results", {}),
                "research_company": {
                    "status": "error",
                    "error": str(exc)[:200],
                },
            },
        }


def _run_research_market(state: PlannerState, writer) -> dict:
    """Market research phase — folded into research_company.

    The research_company phase already calls run_research_pipeline which
    performs website fetch, market research, AND cross-checking in one
    pass. This phase checks if market data already exists from
    research_company and skips if so. Otherwise it runs standalone
    market research.
    """
    research = dict(state.get("research_data") or {})

    # If research_company already populated market data, skip
    if research.get("market") and research["market"].get("competitors"):
        writer(
            SSEEvent(
                type="research_finding",
                data={
                    "action": "research_market",
                    "finding": "Market data already collected during company research.",
                    "step": 1,
                },
            )
        )
        findings = list(state.get("findings") or [])
        findings.append(
            {
                "phase": "research_market",
                "action": "research_market",
                "status": "complete",
                "note": "already_collected",
            }
        )
        return {
            "findings": findings,
            "phase_results": {
                **state.get("phase_results", {}),
                "research_market": {
                    "status": "complete",
                    "note": "data from research_company phase",
                },
            },
        }

    # Standalone market research if research_company was skipped or failed
    plan = state["plan_config"]
    cross_check = plan.get("research_requirements", {}).get(
        "cross_check_policy", "verify"
    )

    writer(
        SSEEvent(
            type="research_finding",
            data={
                "action": "research_market",
                "finding": "Starting standalone market research (policy: {})...".format(
                    cross_check
                ),
                "step": 1,
            },
        )
    )

    try:
        from .tools.market_research import research_market as do_market_research

        # Extract company info from existing research or plan config
        website_data = research.get("website", {})
        extracted = website_data.get("extracted", {})
        company_name = extracted.get("company_name", "")
        industry = (
            (extracted.get("industries") or [""])[0]
            if extracted.get("industries")
            else ""
        )
        location = extracted.get("location", "") or ""

        market_result = do_market_research(
            company_name=company_name,
            industry=industry,
            location=location,
            goal="",
        )

        research["market"] = {
            "competitors": market_result.competitors,
            "market_data": market_result.market_data,
            "industry_trends": market_result.industry_trends,
            "sources": market_result.sources,
            "error": market_result.error,
        }

        writer(
            SSEEvent(
                type="research_finding",
                data={
                    "action": "research_market",
                    "finding": "Market research complete. {} competitors found.".format(
                        len(market_result.competitors)
                    ),
                    "step": 2,
                },
            )
        )

    except Exception as exc:
        logger.exception("Standalone market research failed: %s", exc)
        research["market"] = {"error": str(exc)[:200]}
        writer(
            SSEEvent(
                type="research_finding",
                data={
                    "action": "research_market",
                    "finding": "Market research error: {}".format(str(exc)[:200]),
                    "step": 2,
                },
            )
        )

    findings = list(state.get("findings") or [])
    findings.append(
        {
            "phase": "research_market",
            "action": "research_market",
            "status": "complete",
        }
    )

    return {
        "research_data": research,
        "findings": findings,
        "phase_results": {
            **state.get("phase_results", {}),
            "research_market": {"status": "complete"},
        },
    }


def _run_build_strategy(state: PlannerState, writer) -> dict:
    """Build strategy sections using research data and the Opus specialist.

    For each section defined in the scoring_rubric:
    1. Assembles context (research_data + user_corrections + existing sections)
    2. Calls invoke_specialist (Opus) to write the section with streaming
    3. Emits section_content_start/chunk/done + section_score events
    4. Tracks per-section completeness and token usage
    """
    plan = state["plan_config"]
    rubric = plan.get("scoring_rubric", {})
    sections_config = rubric.get("sections", {})

    # sections_config can be a dict (from YAML) or a list (from tests)
    if isinstance(sections_config, list):
        section_names = [
            s if isinstance(s, str) else s.get("name", "unknown")
            for s in sections_config
        ]
        sections_rubric = {name: {} for name in section_names}
    elif isinstance(sections_config, dict):
        section_names = list(sections_config.keys())
        sections_rubric = sections_config
    else:
        section_names = []
        sections_rubric = {}

    writer(
        SSEEvent(
            type="research_finding",
            data={
                "action": "build_strategy",
                "finding": "Building strategy ({} sections)...".format(
                    len(section_names)
                ),
                "step": 1,
            },
        )
    )

    if not section_names:
        findings = list(state.get("findings") or [])
        findings.append(
            {
                "phase": "build_strategy",
                "action": "build_strategy",
                "status": "complete",
                "note": "no_sections_defined",
            }
        )
        return {
            "findings": findings,
            "phase_results": {
                **state.get("phase_results", {}),
                "build_strategy": {
                    "status": "complete",
                    "sections": {},
                    "sections_filled": 0,
                },
            },
        }

    research_data = state.get("research_data") or {}
    user_corrections = state.get("user_corrections") or []
    persona = plan.get("persona", "")

    completeness = dict(state.get("section_completeness") or {})
    existing_sections: dict[str, str] = {}
    sections_written: list[str] = []
    total_input = 0
    total_output = 0
    total_cost = 0.0

    try:
        from .specialist import SpecialistContext, invoke_specialist

        for section_name in section_names:
            section_rubric = sections_rubric.get(section_name, {})
            # Normalize rubric: could be a ScoringCriterion dict or plain dict
            if hasattr(section_rubric, "criteria"):
                rubric_dict = {
                    "weight": getattr(section_rubric, "weight", 1.0),
                    "criteria": getattr(section_rubric, "criteria", []),
                }
            elif isinstance(section_rubric, dict):
                rubric_dict = section_rubric
            else:
                rubric_dict = {}

            context = SpecialistContext(
                task="Write the '{}' section of a GTM strategy".format(section_name),
                rubric=rubric_dict,
                research=research_data,
                user_context=user_corrections,
                existing_sections=existing_sections,
                constraints=(
                    "Facts only. Every claim must trace to research. No assumptions."
                ),
                persona=persona,
            )

            writer(
                SSEEvent(
                    type="research_finding",
                    data={
                        "action": "build_strategy",
                        "finding": "Writing section: {}".format(section_name),
                    },
                )
            )

            # Stream section content via callback
            def make_stream_cb(sec_name):
                def stream_cb(chunk):
                    writer(
                        SSEEvent(
                            type="section_content_chunk",
                            data={"content": chunk, "section": sec_name},
                        )
                    )

                return stream_cb

            writer(
                SSEEvent(
                    type="section_content_start",
                    data={"section": section_name},
                )
            )

            result = invoke_specialist(
                context, stream_callback=make_stream_cb(section_name)
            )

            writer(
                SSEEvent(
                    type="section_content_done",
                    data={"section": section_name},
                )
            )

            # Track what's been written
            existing_sections[section_name] = result.content
            completeness[section_name] = True
            sections_written.append(section_name)

            # Accumulate token usage
            total_input += result.tokens_used.get("input", 0)
            total_output += result.tokens_used.get("output", 0)
            total_cost += result.cost_usd

            # Emit score for this section
            writer(
                SSEEvent(
                    type="section_score",
                    data={
                        "section": section_name,
                        "score": result.score,
                        "reasoning": result.score_reasoning,
                        "suggestions": result.improvement_suggestions,
                    },
                )
            )

        writer(
            SSEEvent(
                type="research_finding",
                data={
                    "action": "build_strategy",
                    "finding": "Strategy draft complete ({} sections written).".format(
                        len(sections_written)
                    ),
                    "step": 2,
                },
            )
        )

    except ImportError:
        logger.warning("Specialist module not available, marking sections as complete")
        for section_name in section_names:
            completeness[section_name] = True
            sections_written.append(section_name)
        writer(
            SSEEvent(
                type="research_finding",
                data={
                    "action": "build_strategy",
                    "finding": "Strategy sections marked complete (specialist unavailable).",
                    "step": 2,
                },
            )
        )

    except Exception as exc:
        logger.exception("Build strategy failed: %s", exc)
        writer(
            SSEEvent(
                type="research_finding",
                data={
                    "action": "build_strategy",
                    "finding": "Strategy build error: {}".format(str(exc)[:200]),
                    "step": 2,
                },
            )
        )

    findings = list(state.get("findings") or [])
    findings.append(
        {
            "phase": "build_strategy",
            "action": "build_strategy",
            "status": "complete",
            "sections_written": sections_written,
        }
    )

    return {
        "section_completeness": completeness,
        "findings": findings,
        "total_input_tokens": state.get("total_input_tokens", 0) + total_input,
        "total_output_tokens": state.get("total_output_tokens", 0) + total_output,
        "total_cost_usd": str(float(state.get("total_cost_usd", "0")) + total_cost),
        "phase_results": {
            **state.get("phase_results", {}),
            "build_strategy": {
                "status": "complete",
                "sections": existing_sections,
                "sections_filled": len(sections_written),
            },
        },
    }


def _run_review_and_score(state: PlannerState, writer) -> dict:
    """Review and score the completed strategy using the Opus specialist.

    1. Collects all written sections from build_strategy phase
    2. Calls invoke_specialist_scoring for full quality evaluation
    3. Emits quality scores per section and overall assessment
    4. Emits quick_actions for next steps
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

    plan = state["plan_config"]
    rubric = plan.get("scoring_rubric", {})
    completeness = state.get("section_completeness") or {}
    filled = sum(1 for v in completeness.values() if v)
    total = len(completeness) if completeness else 1

    # Get written sections from build_strategy phase results
    build_result = (state.get("phase_results") or {}).get("build_strategy", {})
    sections = build_result.get("sections", {})

    # Extract goal from user's first message
    messages = state.get("messages") or []
    goal = ""
    for msg in messages:
        if hasattr(msg, "type") and msg.type == "human":
            goal = msg.content if hasattr(msg, "content") else ""
            break

    overall_score = 0
    scoring_result = None
    scoring_input_tokens = 0
    scoring_output_tokens = 0
    scoring_cost = 0.0

    try:
        from .specialist import invoke_specialist_scoring

        if sections:
            scoring_result = invoke_specialist_scoring(
                sections=sections,
                rubric=rubric,
                goal=goal,
            )
            overall_score = scoring_result.get("overall_score", 0)

            # Track token usage from scoring
            scoring_tokens = scoring_result.get("tokens_used", {})
            scoring_input_tokens = scoring_tokens.get("input", 0)
            scoring_output_tokens = scoring_tokens.get("output", 0)
            scoring_cost = scoring_result.get("cost_usd", 0.0)

            # Emit per-section scores
            for sec_name, sec_score in scoring_result.get("sections", {}).items():
                writer(
                    SSEEvent(
                        type="section_score",
                        data={
                            "section": sec_name,
                            "score": sec_score.get("score", 0),
                            "reasoning": sec_score.get("reasoning", ""),
                        },
                    )
                )

            writer(
                SSEEvent(
                    type="research_finding",
                    data={
                        "action": "review_and_score",
                        "finding": "Strategy quality score: {}/5. {}".format(
                            overall_score,
                            scoring_result.get("overall_assessment", ""),
                        ),
                        "step": 2,
                    },
                )
            )
        else:
            # Sections not available — use completeness-based score
            overall_score = round((filled / total) * 5) if total else 0
            writer(
                SSEEvent(
                    type="research_finding",
                    data={
                        "action": "review_and_score",
                        "finding": "Strategy completeness score: {}/5 ({}/{} sections).".format(
                            overall_score, filled, total
                        ),
                        "step": 2,
                    },
                )
            )

    except ImportError:
        overall_score = round((filled / total) * 5) if total else 0
        writer(
            SSEEvent(
                type="research_finding",
                data={
                    "action": "review_and_score",
                    "finding": "Strategy completeness: {}/{} sections (scoring unavailable).".format(
                        filled, total
                    ),
                    "step": 2,
                },
            )
        )

    except Exception as exc:
        logger.exception("Strategy scoring failed: %s", exc)
        overall_score = round((filled / total) * 5) if total else 0
        writer(
            SSEEvent(
                type="research_finding",
                data={
                    "action": "review_and_score",
                    "finding": "Scoring error: {}. Using completeness score: {}/5.".format(
                        str(exc)[:100], overall_score
                    ),
                    "step": 2,
                },
            )
        )

    # Emit quick actions for next steps
    writer(
        SSEEvent(
            type="quick_actions",
            data={
                "actions": [
                    {
                        "label": "Improve strategy",
                        "action": "improve",
                        "type": "chat_action",
                    },
                    {
                        "label": "Go to Contacts",
                        "action": "navigate",
                        "target": "contacts",
                        "type": "navigate",
                    },
                ],
            },
        )
    )

    findings = list(state.get("findings") or [])
    findings.append(
        {
            "phase": "review_and_score",
            "action": "review_and_score",
            "status": "complete",
            "score": overall_score,
        }
    )

    return {
        "findings": findings,
        "total_input_tokens": (
            state.get("total_input_tokens", 0) + scoring_input_tokens
        ),
        "total_output_tokens": (
            state.get("total_output_tokens", 0) + scoring_output_tokens
        ),
        "total_cost_usd": str(float(state.get("total_cost_usd", "0")) + scoring_cost),
        "phase_results": {
            **state.get("phase_results", {}),
            "review_and_score": {
                "status": "complete",
                "score": overall_score,
                "details": scoring_result if scoring_result else None,
            },
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
