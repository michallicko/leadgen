"""Core graph utilities and SSE event type.

Provides the SSEEvent dataclass and helper functions used by all
subgraphs and the orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass


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
