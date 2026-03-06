"""AG-UI event formatting for SSE wire protocol.

Maps internal SSEEvent objects to AG-UI compliant JSON payloads
for the frontend. AG-UI events follow the standard taxonomy:
  RUN_STARTED, TEXT_MESSAGE_*, TOOL_CALL_*, STATE_DELTA, RUN_FINISHED

Custom extensions (prefixed with CUSTOM:) are used for app-specific
events like research_status and thinking_status.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any, Optional


# AG-UI event type constants
RUN_STARTED = "RUN_STARTED"
RUN_FINISHED = "RUN_FINISHED"
TEXT_MESSAGE_START = "TEXT_MESSAGE_START"
TEXT_MESSAGE_CONTENT = "TEXT_MESSAGE_CONTENT"
TEXT_MESSAGE_END = "TEXT_MESSAGE_END"
TOOL_CALL_START = "TOOL_CALL_START"
TOOL_CALL_ARGS = "TOOL_CALL_ARGS"
TOOL_CALL_END = "TOOL_CALL_END"
STATE_DELTA = "STATE_DELTA"
STATE_SNAPSHOT = "STATE_SNAPSHOT"

# Custom extensions
CUSTOM_RESEARCH_STATUS = "CUSTOM:research_status"
CUSTOM_THINKING_STATUS = "CUSTOM:thinking_status"


@dataclass
class AGUIEvent:
    """An AG-UI protocol event ready for SSE serialization."""

    type: str
    data: dict[str, Any]

    def to_sse(self) -> str:
        """Serialize to SSE wire format (data: JSON\\n\\n)."""
        payload = {"type": self.type, **self.data}
        return "data: {}\n\n".format(json.dumps(payload))


def run_started(thread_id: str, run_id: Optional[str] = None) -> AGUIEvent:
    """Emit when the agent begins processing a turn."""
    return AGUIEvent(
        type=RUN_STARTED,
        data={
            "threadId": thread_id,
            "runId": run_id or str(uuid.uuid4()),
        },
    )


def run_finished(thread_id: str, run_id: str) -> AGUIEvent:
    """Emit when the agent completes a turn."""
    return AGUIEvent(
        type=RUN_FINISHED,
        data={
            "threadId": thread_id,
            "runId": run_id,
        },
    )


def text_message_start(message_id: str) -> AGUIEvent:
    """Emit when the agent starts streaming text."""
    return AGUIEvent(
        type=TEXT_MESSAGE_START,
        data={"messageId": message_id},
    )


def text_message_content(message_id: str, delta: str) -> AGUIEvent:
    """Emit a text chunk from the agent."""
    return AGUIEvent(
        type=TEXT_MESSAGE_CONTENT,
        data={"messageId": message_id, "delta": delta},
    )


def text_message_end(message_id: str) -> AGUIEvent:
    """Emit when the agent finishes streaming text."""
    return AGUIEvent(
        type=TEXT_MESSAGE_END,
        data={"messageId": message_id},
    )


def tool_call_start(
    tool_call_id: str,
    tool_name: str,
    tool_input: Optional[dict] = None,
) -> AGUIEvent:
    """Emit when the agent begins a tool call."""
    return AGUIEvent(
        type=TOOL_CALL_START,
        data={
            "toolCallId": tool_call_id,
            "toolCallName": tool_name,
            "input": tool_input or {},
        },
    )


def tool_call_end(
    tool_call_id: str,
    tool_name: str,
    status: str,
    summary: str,
    output: str = "",
    duration_ms: int = 0,
) -> AGUIEvent:
    """Emit when a tool call completes."""
    return AGUIEvent(
        type=TOOL_CALL_END,
        data={
            "toolCallId": tool_call_id,
            "toolCallName": tool_name,
            "status": status,
            "summary": summary,
            "output": output,
            "durationMs": duration_ms,
        },
    )


def state_delta(delta: dict[str, Any]) -> AGUIEvent:
    """Emit an incremental state update (e.g., section content change)."""
    return AGUIEvent(
        type=STATE_DELTA,
        data={"delta": delta},
    )


def state_snapshot(snapshot: dict[str, Any]) -> AGUIEvent:
    """Emit a full state snapshot."""
    return AGUIEvent(
        type=STATE_SNAPSHOT,
        data={"snapshot": snapshot},
    )


def research_status(status: str, domain: str, message: str) -> AGUIEvent:
    """Emit research polling status (custom extension)."""
    return AGUIEvent(
        type=CUSTOM_RESEARCH_STATUS,
        data={
            "status": status,
            "domain": domain,
            "message": message,
        },
    )


# ---------------------------------------------------------------------------
# Mapping helpers: SSEEvent (internal) → AG-UI events
# ---------------------------------------------------------------------------


def sse_to_agui(sse_type: str, sse_data: dict, run_id: str = "") -> list[AGUIEvent]:
    """Convert an internal SSEEvent to one or more AG-UI events.

    This bridges the LangGraph graph's custom SSE events to the AG-UI
    protocol. Used during the transition period and for the main
    streaming endpoint.

    Args:
        sse_type: Internal event type (chunk, tool_start, tool_result, etc.)
        sse_data: Event data dict
        run_id: Current run ID for message correlation

    Returns:
        List of AGUIEvent objects (usually 1, sometimes 2 for compound events)
    """
    msg_id = run_id  # Use run_id as message_id for now

    if sse_type == "chunk":
        return [
            AGUIEvent(
                type=TEXT_MESSAGE_CONTENT,
                data={"messageId": msg_id, "delta": sse_data.get("text", "")},
            )
        ]

    elif sse_type == "tool_start":
        return [
            AGUIEvent(
                type=TOOL_CALL_START,
                data={
                    "toolCallId": sse_data.get("tool_call_id", ""),
                    "toolCallName": sse_data.get("tool_name", ""),
                    "input": sse_data.get("input", {}),
                },
            )
        ]

    elif sse_type == "tool_result":
        return [
            AGUIEvent(
                type=TOOL_CALL_END,
                data={
                    "toolCallId": sse_data.get("tool_call_id", ""),
                    "toolCallName": sse_data.get("tool_name", ""),
                    "status": sse_data.get("status", "success"),
                    "summary": sse_data.get("summary", ""),
                    "output": sse_data.get("output", ""),
                    "durationMs": sse_data.get("duration_ms", 0),
                },
            )
        ]

    elif sse_type == "section_update":
        return [
            AGUIEvent(
                type=STATE_DELTA,
                data={
                    "delta": {
                        "section": sse_data.get("section", ""),
                        "content": sse_data.get("content", ""),
                        "action": sse_data.get("action", "update"),
                    }
                },
            )
        ]

    elif sse_type == "section_content_start":
        return [
            AGUIEvent(
                type=TEXT_MESSAGE_START,
                data={
                    "messageId": "{}_section".format(msg_id),
                    "section": sse_data.get("section", ""),
                },
            )
        ]

    elif sse_type == "section_content_chunk":
        return [
            AGUIEvent(
                type=TEXT_MESSAGE_CONTENT,
                data={
                    "messageId": "{}_section".format(msg_id),
                    "delta": sse_data.get("text", ""),
                },
            )
        ]

    elif sse_type == "section_content_done":
        return [
            AGUIEvent(
                type=TEXT_MESSAGE_END,
                data={
                    "messageId": "{}_section".format(msg_id),
                    "section": sse_data.get("section", ""),
                },
            )
        ]

    elif sse_type == "done":
        return [
            AGUIEvent(
                type=RUN_FINISHED,
                data={
                    "threadId": "",
                    "runId": run_id,
                    # Include legacy fields for backward compat
                    "tool_calls": sse_data.get("tool_calls", []),
                    "model": sse_data.get("model", ""),
                    "total_input_tokens": sse_data.get("total_input_tokens", 0),
                    "total_output_tokens": sse_data.get("total_output_tokens", 0),
                    "total_cost_usd": sse_data.get("total_cost_usd", "0"),
                },
            )
        ]

    # Pass through unknown types
    return [AGUIEvent(type=sse_type, data=sse_data)]
