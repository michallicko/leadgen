"""LangGraph StateGraph for the strategy agent.

Replaces the while-loop in agent_executor.py with a declarative graph:
  - "agent" node: calls Claude via ChatAnthropic
  - "tools" node: executes tool calls
  - Conditional edges route between agent/tools/END based on stop_reason

The graph is compiled once and invoked per chat turn. SSE events are
yielded via stream_mode="custom" using get_stream_writer().
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SSEEvent:
    """A single SSE event yielded by the agent graph via stream writer."""

    type: str
    data: dict


def _truncate(text, max_len=2048):
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _summarize_output(tool_name, output):
    if not output:
        return "Completed {}".format(tool_name)
    if isinstance(output, dict) and "summary" in output:
        return str(output["summary"])
    return "Completed {}".format(tool_name)


def _estimate_cost(model, input_tokens, output_tokens):
    MODEL_PRICING = {
        "claude-haiku-4-5-20251001": {"input_per_m": 0.80, "output_per_m": 4.0},
        "claude-sonnet-4-5-20241022": {"input_per_m": 3.0, "output_per_m": 15.0},
        "claude-opus-4-6": {"input_per_m": 15.0, "output_per_m": 75.0},
    }
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["claude-haiku-4-5-20251001"])
    input_cost = (input_tokens / 1_000_000) * pricing["input_per_m"]
    output_cost = (output_tokens / 1_000_000) * pricing["output_per_m"]
    return round(input_cost + output_cost, 6)
