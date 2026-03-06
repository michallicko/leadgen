"""LangGraph event → AG-UI SSE adapter.

Converts internal agent events into AG-UI protocol SSE events.
Also supports legacy SSE format for backward compatibility.

AG-UI event types:
    RUN_STARTED          — Agent turn begins
    RUN_FINISHED         — Agent turn ends
    TEXT_MESSAGE_START   — Assistant begins speaking
    TEXT_MESSAGE_CONTENT — Text chunk from assistant
    TEXT_MESSAGE_END     — Assistant finishes speaking
    TOOL_CALL_START      — Tool execution begins
    TOOL_CALL_ARGS       — Tool input arguments (streamed)
    TOOL_CALL_END        — Tool execution completes
    STATE_DELTA          — Shared state change (JSON Patch format)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class AGUIEvent:
    """A single AG-UI protocol event for SSE transport."""

    type: str
    data: dict[str, Any]

    def to_sse(self) -> str:
        """Serialize to SSE wire format."""
        return "data: {}\n\n".format(json.dumps({"type": self.type, **self.data}))


# ---------------------------------------------------------------------------
# AG-UI event constructors
# ---------------------------------------------------------------------------


def run_started(run_id: str, thread_id: str = "") -> AGUIEvent:
    """Emit RUN_STARTED event."""
    return AGUIEvent(
        type="RUN_STARTED",
        data={"run_id": run_id, "thread_id": thread_id},
    )


def run_finished(
    run_id: str,
    thread_id: str = "",
    tool_calls: list[dict[str, Any]] | None = None,
    model: str = "",
    total_input_tokens: int = 0,
    total_output_tokens: int = 0,
    total_cost_usd: str = "0",
) -> AGUIEvent:
    """Emit RUN_FINISHED event with usage summary."""
    return AGUIEvent(
        type="RUN_FINISHED",
        data={
            "run_id": run_id,
            "thread_id": thread_id,
            "tool_calls": tool_calls or [],
            "model": model,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_cost_usd": total_cost_usd,
        },
    )


def text_message_start(message_id: str, role: str = "assistant") -> AGUIEvent:
    """Emit TEXT_MESSAGE_START event."""
    return AGUIEvent(
        type="TEXT_MESSAGE_START",
        data={"message_id": message_id, "role": role},
    )


def text_message_content(message_id: str, delta: str) -> AGUIEvent:
    """Emit TEXT_MESSAGE_CONTENT event."""
    return AGUIEvent(
        type="TEXT_MESSAGE_CONTENT",
        data={"message_id": message_id, "delta": delta},
    )


def text_message_end(message_id: str) -> AGUIEvent:
    """Emit TEXT_MESSAGE_END event."""
    return AGUIEvent(
        type="TEXT_MESSAGE_END",
        data={"message_id": message_id},
    )


def tool_call_start(
    tool_call_id: str, tool_name: str, tool_call_type: str = "function"
) -> AGUIEvent:
    """Emit TOOL_CALL_START event."""
    return AGUIEvent(
        type="TOOL_CALL_START",
        data={
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "tool_call_type": tool_call_type,
        },
    )


def tool_call_args(tool_call_id: str, delta: str) -> AGUIEvent:
    """Emit TOOL_CALL_ARGS event with serialized input arguments."""
    return AGUIEvent(
        type="TOOL_CALL_ARGS",
        data={"tool_call_id": tool_call_id, "delta": delta},
    )


def tool_call_end(
    tool_call_id: str,
    tool_name: str = "",
    status: str = "success",
    summary: str = "",
    duration_ms: int = 0,
) -> AGUIEvent:
    """Emit TOOL_CALL_END event with result summary."""
    return AGUIEvent(
        type="TOOL_CALL_END",
        data={
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "status": status,
            "summary": summary,
            "duration_ms": duration_ms,
        },
    )


def state_delta(delta: list[dict[str, Any]]) -> AGUIEvent:
    """Emit STATE_DELTA event with JSON Patch operations.

    Args:
        delta: List of JSON Patch operations, e.g.:
            [{"op": "replace", "path": "/document_changed", "value": true}]
    """
    return AGUIEvent(
        type="STATE_DELTA",
        data={"delta": delta},
    )


# ---------------------------------------------------------------------------
# Legacy event constructors (backward compatibility)
# ---------------------------------------------------------------------------


def legacy_chunk(text: str) -> str:
    """Emit legacy 'chunk' event."""
    return "data: {}\n\n".format(json.dumps({"type": "chunk", "text": text}))


def legacy_tool_start(
    tool_name: str, tool_call_id: str, tool_input: dict[str, Any]
) -> str:
    """Emit legacy 'tool_start' event."""
    return "data: {}\n\n".format(
        json.dumps(
            {
                "type": "tool_start",
                "tool_name": tool_name,
                "tool_call_id": tool_call_id,
                "input": tool_input,
            }
        )
    )


def legacy_tool_result(
    tool_call_id: str,
    tool_name: str,
    status: str,
    summary: str,
    output: str,
    duration_ms: int,
) -> str:
    """Emit legacy 'tool_result' event."""
    return "data: {}\n\n".format(
        json.dumps(
            {
                "type": "tool_result",
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "status": status,
                "summary": summary,
                "output": output,
                "duration_ms": duration_ms,
            }
        )
    )


def legacy_done(
    message_id: str,
    tool_calls: list[dict[str, Any]],
    model: str,
    total_input_tokens: int,
    total_output_tokens: int,
    total_cost_usd: str,
    document_changed: bool = False,
    changes_summary: str | None = None,
) -> str:
    """Emit legacy 'done' event."""
    return "data: {}\n\n".format(
        json.dumps(
            {
                "type": "done",
                "message_id": message_id,
                "tool_calls": tool_calls,
                "model": model,
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "total_cost_usd": total_cost_usd,
                "document_changed": document_changed,
                "changes_summary": changes_summary,
            }
        )
    )
