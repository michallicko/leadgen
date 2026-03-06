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

MAX_TOOL_ITERATIONS = 25
MAX_TURN_SECONDS = 180  # Hard timeout for the entire agent turn

# Per-turn rate limits by tool name.  Tools not listed here get the default.
TOOL_RATE_LIMITS: dict[str, int] = {
    "web_search": 5,
}
DEFAULT_TOOL_RATE_LIMIT = 15  # max calls per tool per turn


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


def _truncate(text, max_len=2048):
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


def _build_done_data(
    tool_executions, model, total_input_tokens, total_output_tokens, total_cost_usd
):
    """Build the payload for a 'done' SSE event.

    Includes tool call summaries, token totals, and metadata about
    external tool costs (e.g. Perplexity web_search calls).
    """
    external_tool_costs = [
        {
            "tool_name": e.tool_name,
            "provider": "perplexity" if e.tool_name == "web_search" else None,
        }
        for e in tool_executions
        if e.tool_name == "web_search" and not e.is_error
    ]

    return {
        "tool_calls": [
            {
                "tool_name": e.tool_name,
                "tool_call_id": e.tool_call_id,
                "status": "error" if e.is_error else "success",
                "input_args": e.input_args,
                "output_data": e.output,
                "error_message": e.error_message,
                "duration_ms": e.duration_ms,
            }
            for e in tool_executions
        ],
        "model": model,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_cost_usd": str(total_cost_usd),
        "external_tool_costs": external_tool_costs,
    }


def _execute_tool(tool_name, tool_input, tool_context, app=None):
    """Execute a single tool and return a ToolExecutionRecord.

    All exceptions are caught and converted to error records so the
    agentic loop can continue and Claude can handle the error gracefully.

    If ``app`` is provided, the tool handler runs inside an app context
    (needed when executing inside an SSE generator where Flask's request
    context has already been torn down).
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
        if app is not None:
            with app.app_context():
                result = tool_def.handler(tool_input, tool_context)
        else:
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
    app=None,
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
        app: Flask app object. When provided, tool handlers execute inside
            an application context (required for SSE generators in gunicorn).

    Yields:
        SSEEvent objects.
    """
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost_usd = Decimal("0")
    tool_executions = []
    tool_call_counts: dict[str, int] = {}  # per-tool rate limit counter
    model = client.default_model
    turn_start = time.monotonic()

    for iteration in range(MAX_TOOL_ITERATIONS):
        # Check overall turn timeout
        elapsed = time.monotonic() - turn_start
        if elapsed > MAX_TURN_SECONDS:
            logger.warning(
                "Agent turn timed out after %.0fs (%d iterations)",
                elapsed,
                iteration,
            )
            yield SSEEvent(
                type="chunk",
                data={
                    "text": "I ran out of time for this turn. "
                    "Here's what I've completed so far. "
                    "Send another message to continue.",
                },
            )
            yield SSEEvent(
                type="done",
                data=_build_done_data(
                    tool_executions,
                    model,
                    total_input_tokens,
                    total_output_tokens,
                    total_cost_usd,
                ),
            )
            return

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

        # If no tool calls, check for continuation before finishing
        if stop_reason != "tool_use" or not tool_use_blocks:
            final_text = "".join(text_parts)

            # Check if this is a strategy generation turn that stopped
            # before completing all sections. Nudge it to continue.
            sections_written = sum(
                1
                for e in tool_executions
                if e.tool_name in ("update_strategy_section", "append_to_section")
                and not e.is_error
            )
            research_tools_used = any(
                e.tool_name in ("web_search", "research_own_company")
                for e in tool_executions
            )

            if research_tools_used and sections_written == 0 and iteration < 3:
                # AI researched but didn't write any sections. Nudge.
                nudge = (
                    "Start with your opening and research validation, then "
                    "write sections one by one using update_strategy_section."
                )
            elif 0 < sections_written < 7 and iteration < 5:
                # AI wrote some sections but stopped. Nudge to continue.
                nudge = (
                    "Continue writing the next strategy section. "
                    "You've completed {} of 7.".format(sections_written)
                )
            else:
                nudge = None

            if nudge is not None:
                if final_text:
                    yield SSEEvent(type="chunk", data={"text": final_text})
                messages.append({"role": "assistant", "content": content_blocks})
                messages.append({"role": "user", "content": nudge})
                continue  # Re-enter the agentic loop

            # No continuation needed — yield final text and done event
            if final_text:
                yield SSEEvent(type="chunk", data={"text": final_text})

            yield SSEEvent(
                type="done",
                data=_build_done_data(
                    tool_executions,
                    model,
                    total_input_tokens,
                    total_output_tokens,
                    total_cost_usd,
                ),
            )
            return

        # Yield any intermediate text (AI reasoning between tool calls)
        # so the frontend can display it as streaming text.
        intermediate_text = "".join(text_parts)
        if intermediate_text:
            yield SSEEvent(type="chunk", data={"text": intermediate_text})

        # Append assistant message with all content blocks
        messages.append({"role": "assistant", "content": content_blocks})

        # Execute each tool call and build tool_result messages
        tool_results = []
        for tool_block in tool_use_blocks:
            tool_name = tool_block["name"]
            tool_id = tool_block["id"]
            tool_input = tool_block.get("input", {})

            # Yield tool_start event (includes input for THINK UI)
            yield SSEEvent(
                type="tool_start",
                data={
                    "tool_name": tool_name,
                    "tool_call_id": tool_id,
                    "input": tool_input,
                },
            )

            # Rate-limit check
            max_allowed = TOOL_RATE_LIMITS.get(tool_name, DEFAULT_TOOL_RATE_LIMIT)
            current_count = tool_call_counts.get(tool_name, 0)
            if current_count >= max_allowed:
                exec_record = ToolExecutionRecord(
                    tool_name=tool_name,
                    tool_call_id=tool_id,
                    input_args=tool_input,
                    is_error=True,
                    error_message=(
                        "Rate limit: {} can be called at most {} times per turn. "
                        "Please continue with the information you already have."
                    ).format(tool_name, max_allowed),
                    duration_ms=0,
                )
                tool_executions.append(exec_record)

                yield SSEEvent(
                    type="tool_result",
                    data={
                        "tool_call_id": tool_id,
                        "tool_name": tool_name,
                        "status": "error",
                        "summary": exec_record.error_message,
                        "output": "",
                        "duration_ms": 0,
                    },
                )

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": exec_record.error_message,
                        "is_error": True,
                    }
                )
                continue

            tool_call_counts[tool_name] = current_count + 1

            # Execute the tool (with app context for DB access)
            exec_record = _execute_tool(tool_name, tool_input, tool_context, app=app)
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
                    "tool_name": tool_name,
                    "status": "error" if exec_record.is_error else "success",
                    "summary": exec_record.error_message
                    if exec_record.is_error
                    else _summarize_output(tool_name, exec_record.output),
                    "output": _truncate(output_str, 2048),
                    "duration_ms": exec_record.duration_ms,
                },
            )

            # Emit section_update for live document animation
            if (
                tool_name in ("update_strategy_section", "append_to_section")
                and not exec_record.is_error
                and exec_record.output
            ):
                section_name = exec_record.output.get("section", "")
                content_preview = exec_record.output.get("content_preview", "")

                yield SSEEvent(
                    type="section_update",
                    data={
                        "section": section_name,
                        "content": content_preview,
                        "action": "update"
                        if tool_name == "update_strategy_section"
                        else "append",
                    },
                )

                # Stream section content character-by-character for
                # typewriter effect on the frontend.
                if content_preview:
                    yield SSEEvent(
                        type="section_content_start",
                        data={"section": section_name},
                    )
                    chunk_size = 10
                    for i in range(0, len(content_preview), chunk_size):
                        yield SSEEvent(
                            type="section_content_chunk",
                            data={"text": content_preview[i : i + chunk_size]},
                        )
                    yield SSEEvent(
                        type="section_content_done",
                        data={"section": section_name},
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
        data=_build_done_data(
            tool_executions,
            model,
            total_input_tokens,
            total_output_tokens,
            total_cost_usd,
        ),
    )
