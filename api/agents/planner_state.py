"""Typed state schema for the deterministic planner graph.

Extends the base AgentState with planner-specific fields for tracking
plan execution: current phase, accumulated research, user corrections,
and interrupt handling.
"""

from __future__ import annotations

from typing import Annotated, Any, Sequence

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class PlannerState(TypedDict):
    """State passed between nodes in the planner graph.

    Inherits the shape of AgentState and adds planner-specific fields
    for deterministic plan execution.

    Base fields (from AgentState):
        messages: Conversation history (LangChain message objects).
        tool_context: Execution context for tool handlers.
        iteration: Current loop iteration.
        total_input_tokens: Accumulated input tokens.
        total_output_tokens: Accumulated output tokens.
        total_cost_usd: Accumulated cost in USD.
        model: Model name used for the turn.

    Planner-specific fields:
        plan_id: Active plan ID.
        plan_config: Full plan config dict (serialized).
        current_phase: Current execution phase name.
        phase_index: Index in plan_config["phases"] list.
        phase_results: Results per phase: {phase_name: {status, data}}.
        research_data: Accumulated research findings across phases.
        user_corrections: User corrections received during execution.
        section_completeness: Which strategy sections are filled.
        is_interrupted: Whether user interrupted mid-plan.
        interrupt_message: The interrupting message content.
        interrupt_type: Classification: correction, stop, question, redirect.
        findings: Accumulated research finding events.
    """

    # Base AgentState fields
    messages: Annotated[Sequence[BaseMessage], add_messages]
    tool_context: dict[str, Any]
    iteration: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: str
    model: str

    # Planner-specific fields
    plan_id: str
    plan_config: dict[str, Any]
    current_phase: str
    phase_index: int
    phase_results: dict[str, Any]
    research_data: dict[str, Any]
    user_corrections: list[str]
    section_completeness: dict[str, bool]
    is_interrupted: bool
    interrupt_message: str
    interrupt_type: str
    findings: list[dict[str, Any]]
