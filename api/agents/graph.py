"""Core graph utilities and SSE event type.

Provides the SSEEvent dataclass, helper functions used by all
subgraphs and the orchestrator, and the ``execute_graph_turn``
bridge that converts the LangGraph streaming interface into the
SSEEvent generator expected by the route handlers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Generator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


@dataclass
class SSEEvent:
    """A single SSE event yielded by the agent graph via stream writer."""

    type: str
    data: dict


def _truncate(text: str, max_len: int = 2048) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _summarize_output(tool_name: str, output) -> str:
    if not output:
        return "Completed {}".format(tool_name)
    if isinstance(output, dict) and "summary" in output:
        return str(output["summary"])
    return "Completed {}".format(tool_name)


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
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
# Message conversion helpers
# ---------------------------------------------------------------------------


def _anthropic_to_langchain(messages: list[dict]) -> list:
    """Convert Anthropic API message dicts to LangChain message objects."""
    lc_messages: list = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))
    return lc_messages


# ---------------------------------------------------------------------------
# Bridge: execute_graph_turn
# ---------------------------------------------------------------------------


def execute_graph_turn(
    *,
    system_prompt: str,
    messages: list[dict],
    tool_context: dict,
    page_context: str = "",
    app=None,
) -> Generator[SSEEvent, None, None]:
    """Run one agent turn through the LangGraph pipeline orchestrator.

    This is the single entry point called by both the streaming and sync
    route handlers.  It builds the LangGraph state, streams the compiled
    pipeline graph, and yields ``SSEEvent`` objects with the same shape
    the route handlers already expect (chunk, tool_start, tool_result,
    section_update, intent_classified, done, etc.).

    Args:
        system_prompt: The assembled system prompt string.
        messages: Anthropic API format message dicts.
        tool_context: Dict with tenant_id, user_id, document_id, turn_id.
        page_context: Current UI page context (strategy, contacts, …).
        app: Flask app object (needed for DB access inside the generator).

    Yields:
        SSEEvent objects.
    """
    from .pipeline import build_pipeline_graph

    # Convert messages to LangChain format and prepend system prompt
    lc_messages = [SystemMessage(content=system_prompt)]
    lc_messages.extend(_anthropic_to_langchain(messages))

    # Inject Flask app reference so tool handlers can get an app context
    tc = dict(tool_context)
    if app is not None:
        tc["_app"] = app

    initial_state = {
        "messages": lc_messages,
        "tool_context": tc,
        "iteration": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cost_usd": "0",
        "model": "",
        "intent": None,
        "active_agent": None,
        "research_results": None,
        "section_completeness": None,
        "pipeline_phase": page_context or None,
        "pipeline_phases_complete": None,
        "pipeline_context": None,
    }

    graph = build_pipeline_graph()
    final_state = None

    for mode, event in graph.stream(initial_state, stream_mode=["custom", "values"]):
        if mode == "custom" and isinstance(event, SSEEvent):
            yield event
        elif mode == "values":
            final_state = event

    # Build and yield the done event from accumulated state
    if final_state is None:
        final_state = initial_state

    total_input = final_state.get("total_input_tokens", 0)
    total_output = final_state.get("total_output_tokens", 0)
    total_cost = final_state.get("total_cost_usd", "0")
    model = final_state.get("model", "") or "claude-haiku-4-5-20251001"

    yield SSEEvent(
        type="done",
        data={
            "tool_calls": [],
            "model": model,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cost_usd": str(total_cost),
        },
    )
