"""Bridge between route handlers and the deterministic planner graph.

Provides the entry point for starting and resuming plan execution,
plus in-memory plan state persistence (upgradeable to Redis/DB later).
"""

from __future__ import annotations

import logging
from typing import Generator, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from .graph import SSEEvent
from .planner import build_planner_graph

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Plan state persistence (in-memory for now)
# ---------------------------------------------------------------------------

_active_plans: dict[str, dict] = {}  # keyed by thread_id


def get_active_plan(thread_id: str) -> Optional[dict]:
    """Retrieve the active plan state for a thread."""
    return _active_plans.get(thread_id)


def save_active_plan(thread_id: str, state: dict) -> None:
    """Persist the active plan state for a thread."""
    _active_plans[thread_id] = state


def clear_active_plan(thread_id: str) -> None:
    """Remove the active plan state for a thread."""
    _active_plans.pop(thread_id, None)


def list_active_plans() -> dict[str, str]:
    """Return a mapping of thread_id -> plan_id for all active plans."""
    return {
        tid: state.get("plan_id", "unknown") for tid, state in _active_plans.items()
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def execute_planner_turn(
    message: str,
    plan_config: dict,
    tool_context: dict,
    existing_state: Optional[dict] = None,
    system_prompt: str = "",
) -> Generator[SSEEvent, None, None]:
    """Execute a planner turn, yielding SSEEvent objects for streaming.

    If existing_state is provided, resume an active plan by injecting
    the new message as an interrupt. Otherwise, start a new plan.

    Args:
        message: The user message triggering/resuming the plan.
        plan_config: Serialized Plan dict.
        tool_context: ToolContext-like dict with tenant_id, user_id, etc.
        existing_state: Previously saved planner state for resumption.
        system_prompt: Optional system prompt to prepend.

    Yields:
        SSEEvent objects for streaming to the client.
    """
    graph = build_planner_graph(plan_config)

    if existing_state is not None:
        # Resume: inject the new message as an interrupt
        initial_state = dict(existing_state)
        initial_state["is_interrupted"] = True
        initial_state["interrupt_message"] = message
        # Add the new message to conversation history
        msgs = list(initial_state.get("messages", []))
        msgs.append(HumanMessage(content=message))
        initial_state["messages"] = msgs
    else:
        # Start fresh
        lc_messages = []
        if system_prompt:
            lc_messages.append(SystemMessage(content=system_prompt))
        lc_messages.append(HumanMessage(content=message))

        phases = plan_config.get("phases", [])
        initial_state = {
            "messages": lc_messages,
            "tool_context": tool_context,
            "plan_id": plan_config.get("id", ""),
            "plan_config": plan_config,
            "current_phase": phases[0] if phases else "",
            "phase_index": 0,
            "phase_results": {},
            "research_data": {},
            "user_corrections": [],
            "section_completeness": {},
            "is_interrupted": False,
            "interrupt_message": "",
            "interrupt_type": "",
            "findings": [],
            "iteration": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost_usd": "0",
            "model": "",
        }

    final_state = None

    for mode, event in graph.stream(initial_state, stream_mode=["custom", "values"]):
        if mode == "custom" and isinstance(event, SSEEvent):
            yield event
        elif mode == "values":
            final_state = event

    # Build and yield the done event
    if final_state is None:
        final_state = initial_state

    total_input = final_state.get("total_input_tokens", 0)
    total_output = final_state.get("total_output_tokens", 0)
    total_cost = final_state.get("total_cost_usd", "0")
    model = final_state.get("model", "") or "planner"

    yield SSEEvent(
        type="done",
        data={
            "tool_calls": [],
            "model": model,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cost_usd": str(total_cost),
            "plan_id": final_state.get("plan_id", ""),
            "phases_completed": list(
                k
                for k, v in (final_state.get("phase_results") or {}).items()
                if isinstance(v, dict) and v.get("status") == "complete"
            ),
        },
    )
