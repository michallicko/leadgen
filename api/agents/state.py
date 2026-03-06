"""Typed state schema for the LangGraph agent.

AgentState is the single source of truth for the agent's execution context.
All node functions read from and write to this state.
"""

from __future__ import annotations

from typing import Any, TypedDict


class ToolCallRecord(TypedDict, total=False):
    """Record of a single tool execution within the agent turn."""

    tool_name: str
    tool_call_id: str
    input_args: dict[str, Any]
    output: dict[str, Any] | None
    is_error: bool
    error_message: str | None
    duration_ms: int | None
    status: str  # "running", "success", "error"


class AgentState(TypedDict, total=False):
    """Full state passed through the LangGraph StateGraph.

    Fields:
        messages: Conversation messages in Anthropic API format.
            Each entry is a dict with 'role' and 'content'.
        phase: Current playbook phase (strategy, contacts, messages, campaign).
        model: Current model ID being used for generation.
        tool_calls: List of tool execution records from this turn.
        iteration_count: Number of model calls in this turn (for loop guard).
        total_input_tokens: Cumulative input tokens used this turn.
        total_output_tokens: Cumulative output tokens used this turn.
        total_cost_usd: Cumulative cost in USD as string (Decimal precision).
        should_halt: Whether the agent should halt and wait for user input.
        halt_reason: Human-readable reason for halting (shown to user).
        document_changed: Whether strategy document was modified this turn.
        changes_summary: Summary of document changes (for STATE_DELTA).
        run_id: Unique identifier for this agent run.
        system_prompt: Assembled system prompt (layered).
        tools: Tool definitions in Claude API format (phase-filtered).
        tool_context: ToolContext dict for tool execution.
        stop_reason: Last API response stop_reason.
        content_blocks: Last API response content blocks.
        app: Flask app reference for DB access in tool handlers.
    """

    messages: list[dict[str, Any]]
    phase: str
    model: str
    tool_calls: list[ToolCallRecord]
    iteration_count: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: str
    should_halt: bool
    halt_reason: str | None
    document_changed: bool
    changes_summary: str | None
    run_id: str
    system_prompt: str
    tools: list[dict[str, Any]]
    tool_context: dict[str, Any]
    stop_reason: str | None
    content_blocks: list[dict[str, Any]]
    app: Any  # Flask app — not serializable, passed by reference


def create_initial_state(
    *,
    messages: list[dict[str, Any]],
    system_prompt: str,
    tools: list[dict[str, Any]],
    tool_context: dict[str, Any],
    phase: str = "strategy",
    model: str = "claude-haiku-4-5-20251001",
    run_id: str = "",
    app: Any = None,
) -> AgentState:
    """Create a fresh AgentState for a new agent turn.

    Args:
        messages: Conversation history in Anthropic API format.
        system_prompt: Pre-assembled system prompt string.
        tools: Tool definitions in Claude API format.
        tool_context: Dict with tenant_id, user_id, document_id, turn_id.
        phase: Current playbook phase.
        model: Default model for first call.
        run_id: Unique run identifier.
        app: Flask app for DB access.

    Returns:
        Initialized AgentState dict.
    """
    return AgentState(
        messages=messages,
        phase=phase,
        model=model,
        tool_calls=[],
        iteration_count=0,
        total_input_tokens=0,
        total_output_tokens=0,
        total_cost_usd="0",
        should_halt=False,
        halt_reason=None,
        document_changed=False,
        changes_summary=None,
        run_id=run_id,
        system_prompt=system_prompt,
        tools=tools,
        tool_context=tool_context,
        stop_reason=None,
        content_blocks=[],
        app=app,
    )
