"""Agentic execution loop for the AI chat.

Implements the tool-use loop as a generator that yields SSE events.
The route handler consumes this generator and converts each SSEEvent
into wire-format SSE, decoupling execution from transport.

Usage:
    for event in execute_agent_turn(client, system_prompt, messages, ...):
        # event.type: "tool_start" | "tool_result" | "chunk" | "done"
        send_sse(event)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .tool_registry import get_tool

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 10


@dataclass
class SSEEvent:
    """A single SSE event yielded by the agent executor."""

    type: str  # "tool_start", "tool_result", "chunk", "done"
    data: dict


@dataclass
class ToolExecutionRecord:
    """Internal record of a single tool execution."""

    tool_name: str
    tool_call_id: str
    input_args: dict
    output: Optional[dict] = None
    is_error: bool = False
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None


def _truncate(text, max_len=500):
    """Truncate a string with an ellipsis marker."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _summarize_output(tool_name, output):
    """Generate a human-readable summary of tool output.

    Each tool spec defines its own display text. For now, return a
    generic summary based on the tool name and output keys.
    """
    if not output:
        return "Completed {}".format(tool_name)

    # If the output has a 'summary' key, use it directly
    if isinstance(output, dict) and "summary" in output:
        return str(output["summary"])

    return "Completed {}".format(tool_name)


def _execute_tool(tool_name, tool_input, tool_context):
    """Execute a single tool and return a ToolExecutionRecord.

    All exceptions are caught and converted to error records so the
    agentic loop can continue and Claude can handle the error gracefully.
    """
    start = time.monotonic()
    tool_def = get_tool(tool_name)

    if tool_def is None:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return ToolExecutionRecord(
            tool_name=tool_name,
            tool_call_id="",
            input_args=tool_input,
            is_error=True,
            error_message="Unknown tool: {}".format(tool_name),
            duration_ms=elapsed_ms,
        )

    try:
        result = tool_def.handler(tool_input, tool_context)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return ToolExecutionRecord(
            tool_name=tool_name,
            tool_call_id="",
            input_args=tool_input,
            output=result,
            is_error=False,
            duration_ms=elapsed_ms,
        )
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.exception("Tool '%s' failed: %s", tool_name, exc)
        return ToolExecutionRecord(
            tool_name=tool_name,
            tool_call_id="",
            input_args=tool_input,
            is_error=True,
            error_message=str(exc),
            duration_ms=elapsed_ms,
        )


def execute_agent_turn(
    client,
    system_prompt,
    messages,
    tools,
    tool_context,
):
    """Execute a full agent turn with tool-use loop.

    This is a generator that yields SSEEvent objects as the loop progresses:
      - tool_start: when a tool call begins
      - tool_result: when a tool call completes (with status, summary, duration_ms)
      - chunk: streamed text from the final response
      - done: final event with tool_calls summary and cost totals

    The caller (route handler) converts these into SSE wire format.

    Args:
        client: AnthropicClient instance.
        system_prompt: System prompt string.
        messages: List of message dicts (mutated in place to append
            assistant + tool_result messages during the loop).
        tools: List of tool definitions in Claude API format.
        tool_context: ToolContext with tenant_id, user_id, document_id.

    Yields:
        SSEEvent objects.
    """
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost_usd = Decimal("0")
    tool_executions = []

    for iteration in range(MAX_TOOL_ITERATIONS):
        response = client.query_with_tools(
            messages=messages,
            system_prompt=system_prompt,
            tools=tools,
        )

        # Track token usage
        usage = response.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        total_input_tokens += input_tokens
        total_output_tokens += output_tokens
        model = response.get("model", client.default_model)
        total_cost_usd += Decimal(
            str(client._estimate_cost(model, input_tokens, output_tokens))
        )

        content_blocks = response.get("content", [])
        stop_reason = response.get("stop_reason")

        # Extract text and tool_use blocks
        text_parts = []
        tool_use_blocks = []
        for block in content_blocks:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_use_blocks.append(block)

        # If no tool calls, we're done -- yield final text and done event
        if stop_reason != "tool_use" or not tool_use_blocks:
            final_text = "".join(text_parts)
            if final_text:
                yield SSEEvent(type="chunk", data={"text": final_text})

            yield SSEEvent(
                type="done",
                data={
                    "tool_calls": [
                        {
                            "tool_name": e.tool_name,
                            "status": "error" if e.is_error else "success",
                        }
                        for e in tool_executions
                    ],
                    "total_input_tokens": total_input_tokens,
                    "total_output_tokens": total_output_tokens,
                    "total_cost_usd": str(total_cost_usd),
                },
            )
            return

        # Append assistant message with all content blocks
        messages.append({"role": "assistant", "content": content_blocks})

        # Execute each tool call and build tool_result messages
        tool_results = []
        for tool_block in tool_use_blocks:
            tool_name = tool_block["name"]
            tool_id = tool_block["id"]
            tool_input = tool_block.get("input", {})

            # Yield tool_start event
            yield SSEEvent(
                type="tool_start",
                data={
                    "tool_name": tool_name,
                    "tool_call_id": tool_id,
                },
            )

            # Execute the tool
            exec_record = _execute_tool(tool_name, tool_input, tool_context)
            exec_record.tool_call_id = tool_id
            tool_executions.append(exec_record)

            # Yield tool_result event
            output_str = ""
            if exec_record.output is not None:
                try:
                    output_str = json.dumps(exec_record.output)
                except (TypeError, ValueError):
                    output_str = str(exec_record.output)

            yield SSEEvent(
                type="tool_result",
                data={
                    "tool_call_id": tool_id,
                    "status": "error" if exec_record.is_error else "success",
                    "summary": exec_record.error_message
                    if exec_record.is_error
                    else _summarize_output(tool_name, exec_record.output),
                    "output": _truncate(output_str, 500),
                    "duration_ms": exec_record.duration_ms,
                },
            )

            # Build tool_result message for Claude
            if exec_record.is_error:
                result_content = exec_record.error_message or "Tool execution failed"
            else:
                try:
                    result_content = json.dumps(exec_record.output)
                except (TypeError, ValueError):
                    result_content = str(exec_record.output)

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": result_content,
                    "is_error": exec_record.is_error,
                }
            )

        # Append tool results as a user message
        messages.append({"role": "user", "content": tool_results})

    # Exhausted iterations -- yield a warning and done
    yield SSEEvent(
        type="chunk",
        data={
            "text": "I've reached the maximum number of actions for this turn. "
            "Please send another message to continue.",
        },
    )
    yield SSEEvent(
        type="done",
        data={
            "tool_calls": [
                {
                    "tool_name": e.tool_name,
                    "status": "error" if e.is_error else "success",
                }
                for e in tool_executions
            ],
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_cost_usd": str(total_cost_usd),
        },
    )
