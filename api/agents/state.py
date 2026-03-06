"""Typed state schema for the strategy agent graph.

The state flows through LangGraph nodes and edges, accumulating
messages, tool results, and metadata as the agent processes a turn.
"""

from __future__ import annotations

from typing import Annotated, Any, Optional, Sequence

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """State passed between nodes in the strategy agent graph.

    Attributes:
        messages: Conversation history (LangChain message objects).
            Uses add_messages reducer to handle appends and deduplication.
        tool_context: Execution context for tool handlers (tenant_id, etc.).
        iteration: Current loop iteration (for rate limiting / timeout).
        total_input_tokens: Accumulated input tokens across all LLM calls.
        total_output_tokens: Accumulated output tokens across all LLM calls.
        total_cost_usd: Accumulated cost in USD across all LLM calls.
        model: Model name used for the turn.
        intent: Classified intent from the orchestrator
            (strategy_edit, research, quick_answer, campaign).
        active_agent: Which subgraph is currently running.
        research_results: Research agent outputs, shared with other agents.
        section_completeness: Strategy section completeness status.
    """

    messages: Annotated[Sequence[BaseMessage], add_messages]
    tool_context: dict[str, Any]
    iteration: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: str
    model: str
    # Multi-agent orchestration fields
    intent: Optional[str]
    active_agent: Optional[str]
    research_results: Optional[dict]
    section_completeness: Optional[dict]
