"""Handle each type of user interruption during plan execution (BL-1018).

Provides handler functions for the four interrupt types (correction,
stop, question, redirect) and a ``process_interrupt`` entry point
that the planner's ``check_interrupt_node`` delegates to.
"""

from __future__ import annotations

import logging
from typing import Any

from .planner_state import PlannerState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase matching for redirects
# ---------------------------------------------------------------------------

# Keywords that map to known plan phases
_PHASE_KEYWORDS: dict[str, list[str]] = {
    "research_company": ["company", "website", "about them", "their business"],
    "research_market": [
        "market",
        "competitor",
        "competitors",
        "industry",
        "segment",
        "dach",
        "region",
    ],
    "build_strategy": [
        "strategy",
        "icp",
        "persona",
        "positioning",
        "messaging",
        "value prop",
    ],
    "review_and_score": ["review", "score", "quality", "evaluate", "assess"],
}


def _find_target_phase(redirect_text: str, phases: list[str]) -> str | None:
    """Find the best matching phase for a redirect request.

    Returns the phase name if found, or None if no match.
    """
    lower = redirect_text.lower()
    for phase, keywords in _PHASE_KEYWORDS.items():
        if phase in phases and any(kw in lower for kw in keywords):
            return phase
    return None


# ---------------------------------------------------------------------------
# Individual handlers
# ---------------------------------------------------------------------------


def handle_correction(state: PlannerState, classification: dict) -> dict[str, Any]:
    """Handle a user correction.

    1. Add correction to user_corrections list
    2. Clear interrupt flags
    3. Resume from current phase with updated context

    The correction text is stored so phase handlers can incorporate
    it into subsequent LLM prompts and research queries.
    """
    correction_text = classification.get("extracted_info", {}).get("correction", "")
    if not correction_text:
        correction_text = classification.get("extracted_info", {}).get(
            "correction", str(classification)
        )

    existing = list(state.get("user_corrections") or [])
    existing.append(correction_text)

    logger.info("Interrupt handler: correction recorded (total=%d)", len(existing))

    return {
        "user_corrections": existing,
        "is_interrupted": False,
        "interrupt_type": "correction",
        "interrupt_message": "",
    }


def handle_stop(state: PlannerState, classification: dict) -> dict[str, Any]:
    """Handle a stop request.

    Sets interrupt_type to "stop" which the interrupt_router will
    use to route to END, halting plan execution. The completed
    phases are preserved in phase_results for resumption later.
    """
    completed_phases = [
        phase
        for phase, result in (state.get("phase_results") or {}).items()
        if isinstance(result, dict) and result.get("status") == "complete"
    ]

    logger.info(
        "Interrupt handler: stop requested (completed phases: %s)",
        completed_phases,
    )

    return {
        "is_interrupted": False,
        "interrupt_type": "stop",
        # interrupt_router sees type=stop and routes to END
    }


def handle_question(state: PlannerState, classification: dict) -> dict[str, Any]:
    """Handle a mid-plan question.

    Clears interrupt flags so the plan resumes execution from
    the current phase. The question answer is emitted as an SSE
    event by the check_interrupt_node before this handler returns.
    """
    question = classification.get("extracted_info", {}).get("question", "")

    logger.info("Interrupt handler: question (plan will resume) — %s", question[:80])

    return {
        "is_interrupted": False,
        "interrupt_type": "question",
        "interrupt_message": "",
    }


def handle_redirect(state: PlannerState, classification: dict) -> dict[str, Any]:
    """Handle a redirect request (change focus/priority).

    Attempts to find the target phase and jump to it by updating
    phase_index. If no matching phase is found, records the redirect
    as a correction so subsequent phases pick it up.
    """
    new_focus = classification.get("extracted_info", {}).get("new_focus", "")
    phase_hint = classification.get("extracted_info", {}).get("phase_hint", "")

    plan_config = state.get("plan_config") or {}
    phases = plan_config.get("phases", [])
    current_index = state.get("phase_index", 0)

    # Try phase_hint first (from Haiku), then keyword matching
    target_phase = None
    if phase_hint and phase_hint in phases:
        target_phase = phase_hint
    else:
        target_phase = _find_target_phase(new_focus, phases)

    existing_corrections = list(state.get("user_corrections") or [])
    existing_corrections.append(f"REDIRECT: {new_focus}")

    updates: dict[str, Any] = {
        "is_interrupted": False,
        "interrupt_type": "redirect",
        "interrupt_message": "",
        "user_corrections": existing_corrections,
    }

    if target_phase:
        target_index = phases.index(target_phase)
        if target_index > current_index:
            # Jump forward — skip intermediate phases
            updates["phase_index"] = target_index - 1  # advance_phase will +1
            updates["current_phase"] = target_phase
            logger.info(
                "Interrupt handler: redirect to phase '%s' (index %d)",
                target_phase,
                target_index,
            )
        else:
            logger.info(
                "Interrupt handler: redirect target '%s' already passed, "
                "recording as correction",
                target_phase,
            )
    else:
        logger.info(
            "Interrupt handler: redirect with no matching phase, "
            "recording as correction"
        )

    return updates


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

_HANDLERS = {
    "correction": handle_correction,
    "stop": handle_stop,
    "question": handle_question,
    "redirect": handle_redirect,
}


def process_interrupt(state: PlannerState) -> dict[str, Any]:
    """Main entry point for interrupt processing.

    Called by the planner's check_interrupt_node. Classifies the
    interrupt message and dispatches to the appropriate handler.

    Args:
        state: Current PlannerState with is_interrupted=True.

    Returns:
        State updates dict to merge back into PlannerState.
    """
    from .interrupt_classifier import classify_interrupt

    message = state.get("interrupt_message", "")
    current_phase = state.get("current_phase", "")
    plan_config = state.get("plan_config") or {}

    if not message:
        logger.warning("process_interrupt called with empty message")
        return {
            "is_interrupted": False,
            "interrupt_type": "correction",
            "interrupt_message": "",
            "user_corrections": list(state.get("user_corrections") or [])
            + ["(empty interrupt)"],
        }

    classification = classify_interrupt(message, current_phase, plan_config)

    logger.info(
        "Interrupt processed: type=%s, confidence=%.2f",
        classification.type,
        classification.confidence,
    )

    handler = _HANDLERS.get(classification.type, handle_correction)
    return handler(state, classification.__dict__)
