"""LangGraph StateGraph definition for the agent.

Defines the graph topology and compiles it into a runnable.
The graph implements the same tool-use loop as the legacy agent_executor.py
but with structured state management and extensibility for halt gates.

Graph structure:
    START → route → call_model → check_tools
                                    ├─ (has tools) → execute_tools → after_tools
                                    │                                   ├─ (halt) → END
                                    │                                   └─ (continue) → call_model
                                    └─ (no tools) → END
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Generator

from .nodes import (
    after_tools,
    call_model_node,
    execute_tools_node,
    route_node,
    should_continue,
)
from .state import AgentState, create_initial_state
from .streaming import (
    legacy_chunk,
    legacy_done,
    legacy_tool_result,
    legacy_tool_start,
    run_finished,
    run_started,
    state_delta,
    text_message_content,
    text_message_end,
    text_message_start,
    tool_call_args,
    tool_call_end,
    tool_call_start,
)
from .tools import summarize_tool_output, truncate_output

logger = logging.getLogger(__name__)


def create_agent_graph():
    """Create the LangGraph StateGraph for the agent.

    Note: This returns a description of the graph structure, not a compiled
    LangGraph object. The actual execution is done by execute_agent_graph()
    which implements the same loop pattern as a generator yielding SSE events.

    This function exists as the public API entry point and could be replaced
    with an actual LangGraph StateGraph when langgraph is added as a dependency.

    Returns:
        A callable that represents the agent graph.
    """
    return execute_agent_graph


def execute_agent_graph(
    *,
    client: Any,
    system_prompt: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_context: dict[str, Any],
    phase: str = "strategy",
    app: Any = None,
    use_agui: bool = True,
) -> Generator[str, None, None]:
    """Execute the agent graph as a generator yielding SSE events.

    This implements the LangGraph-style execution pattern as a generator,
    following the same node sequence as the graph:
        route → call_model → check_tools → [execute_tools → after_tools]*

    Yields AG-UI protocol events when use_agui=True, or legacy events
    when use_agui=False.

    Args:
        client: AnthropicClient instance.
        system_prompt: System prompt string.
        messages: Conversation messages in Anthropic API format.
        tools: Tool definitions in Claude API format.
        tool_context: Dict with tenant_id, user_id, document_id, turn_id.
        phase: Current playbook phase.
        app: Flask app for DB access.
        use_agui: Whether to emit AG-UI events (True) or legacy events (False).

    Yields:
        SSE-formatted strings.
    """
    run_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    # Initialize state
    state: AgentState = create_initial_state(
        messages=list(messages),  # Copy to avoid mutation
        system_prompt=system_prompt,
        tools=tools,
        tool_context=tool_context,
        phase=phase,
        model="claude-haiku-4-5-20251001",
        run_id=run_id,
        app=app,
    )

    # Emit RUN_STARTED
    if use_agui:
        yield run_started(run_id).to_sse()
    # No legacy equivalent for run_started

    text_started = False

    for _iteration in range(25):  # MAX_TOOL_ITERATIONS
        # Node: route
        route_update = route_node(state)
        state.update(route_update)

        # Node: call_model
        model_update = call_model_node(state, client)
        state.update(model_update)

        # Extract text and tool blocks
        content_blocks = state.get("content_blocks", [])

        text_parts = []
        tool_use_blocks = []
        for block in content_blocks:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_use_blocks.append(block)

        # Check: should we continue with tools?
        decision = should_continue(state)

        if decision == "end":
            # Final text response
            final_text = "".join(text_parts)
            if final_text:
                if use_agui:
                    if not text_started:
                        yield text_message_start(message_id).to_sse()
                        text_started = True
                    yield text_message_content(message_id, final_text).to_sse()
                    yield text_message_end(message_id).to_sse()
                else:
                    yield legacy_chunk(final_text)

            # Emit document change state delta
            if state.get("document_changed") and use_agui:
                yield state_delta(
                    [
                        {"op": "replace", "path": "/document_changed", "value": True},
                        {
                            "op": "replace",
                            "path": "/changes_summary",
                            "value": state.get("changes_summary"),
                        },
                    ]
                ).to_sse()

            # Emit RUN_FINISHED / done
            tool_calls_summary = _build_tool_calls_summary(state)

            if use_agui:
                yield run_finished(
                    run_id=run_id,
                    tool_calls=tool_calls_summary,
                    model=state.get("model", ""),
                    total_input_tokens=state.get("total_input_tokens", 0),
                    total_output_tokens=state.get("total_output_tokens", 0),
                    total_cost_usd=state.get("total_cost_usd", "0"),
                ).to_sse()
            else:
                yield legacy_done(
                    message_id=message_id,
                    tool_calls=tool_calls_summary,
                    model=state.get("model", ""),
                    total_input_tokens=state.get("total_input_tokens", 0),
                    total_output_tokens=state.get("total_output_tokens", 0),
                    total_cost_usd=state.get("total_cost_usd", "0"),
                    document_changed=state.get("document_changed", False),
                    changes_summary=state.get("changes_summary"),
                )
            return

        # We have tool calls — emit text first if any
        text_before_tools = "".join(text_parts)
        if text_before_tools:
            if use_agui:
                if not text_started:
                    yield text_message_start(message_id).to_sse()
                    text_started = True
                yield text_message_content(message_id, text_before_tools).to_sse()
            else:
                yield legacy_chunk(text_before_tools)

        # Emit tool_start events before execution
        for tool_block in tool_use_blocks:
            t_name = tool_block["name"]
            t_id = tool_block["id"]
            t_input = tool_block.get("input", {})

            if use_agui:
                yield tool_call_start(t_id, t_name).to_sse()
                try:
                    args_str = json.dumps(t_input)
                except (TypeError, ValueError):
                    args_str = str(t_input)
                yield tool_call_args(t_id, args_str).to_sse()
            else:
                yield legacy_tool_start(t_name, t_id, t_input)

        # Node: execute_tools
        tools_update = execute_tools_node(state)
        state.update(tools_update)

        # Emit tool_result/tool_call_end events for new tool calls
        all_tool_calls = state.get("tool_calls", [])
        # The new ones are at the end
        new_calls = all_tool_calls[len(all_tool_calls) - len(tool_use_blocks) :]

        for tc in new_calls:
            t_name = tc.get("tool_name", "")
            t_id = tc.get("tool_call_id", "")
            is_error = tc.get("is_error", False)
            status = "error" if is_error else "success"
            summary = (
                tc.get("error_message", "")
                if is_error
                else summarize_tool_output(t_name, tc.get("output"))
            )
            duration_ms = tc.get("duration_ms", 0)

            if use_agui:
                yield tool_call_end(
                    t_id, t_name, status, summary, duration_ms or 0
                ).to_sse()
            else:
                output_str = ""
                if tc.get("output") is not None:
                    try:
                        output_str = json.dumps(tc["output"])
                    except (TypeError, ValueError):
                        output_str = str(tc["output"])

                yield legacy_tool_result(
                    t_id,
                    t_name,
                    status,
                    summary,
                    truncate_output(output_str, 2048),
                    duration_ms or 0,
                )

        # Check after_tools decision
        next_step = after_tools(state)
        if next_step == "halt" or next_step == "end":
            # Emit done/run_finished
            tool_calls_summary = _build_tool_calls_summary(state)

            if use_agui:
                if text_started:
                    yield text_message_end(message_id).to_sse()
                yield run_finished(
                    run_id=run_id,
                    tool_calls=tool_calls_summary,
                    model=state.get("model", ""),
                    total_input_tokens=state.get("total_input_tokens", 0),
                    total_output_tokens=state.get("total_output_tokens", 0),
                    total_cost_usd=state.get("total_cost_usd", "0"),
                ).to_sse()
            else:
                yield legacy_done(
                    message_id=message_id,
                    tool_calls=tool_calls_summary,
                    model=state.get("model", ""),
                    total_input_tokens=state.get("total_input_tokens", 0),
                    total_output_tokens=state.get("total_output_tokens", 0),
                    total_cost_usd=state.get("total_cost_usd", "0"),
                    document_changed=state.get("document_changed", False),
                    changes_summary=state.get("changes_summary"),
                )
            return

        # Continue loop — call_model again with tool results

    # Exhausted iterations
    timeout_text = (
        "I've reached the maximum number of actions for this turn. "
        "Please send another message to continue."
    )
    if use_agui:
        if not text_started:
            yield text_message_start(message_id).to_sse()
        yield text_message_content(message_id, timeout_text).to_sse()
        yield text_message_end(message_id).to_sse()
        yield run_finished(
            run_id=run_id,
            tool_calls=_build_tool_calls_summary(state),
            model=state.get("model", ""),
            total_input_tokens=state.get("total_input_tokens", 0),
            total_output_tokens=state.get("total_output_tokens", 0),
            total_cost_usd=state.get("total_cost_usd", "0"),
        ).to_sse()
    else:
        yield legacy_chunk(timeout_text)
        yield legacy_done(
            message_id=message_id,
            tool_calls=_build_tool_calls_summary(state),
            model=state.get("model", ""),
            total_input_tokens=state.get("total_input_tokens", 0),
            total_output_tokens=state.get("total_output_tokens", 0),
            total_cost_usd=state.get("total_cost_usd", "0"),
            document_changed=state.get("document_changed", False),
            changes_summary=state.get("changes_summary"),
        )


def _build_tool_calls_summary(state: AgentState) -> list[dict[str, Any]]:
    """Build the tool calls summary for the done/run_finished event."""
    tool_calls = state.get("tool_calls", [])
    return [
        {
            "tool_name": tc.get("tool_name", ""),
            "tool_call_id": tc.get("tool_call_id", ""),
            "status": "error" if tc.get("is_error") else "success",
            "input_args": tc.get("input_args", {}),
            "output_data": tc.get("output"),
            "error_message": tc.get("error_message"),
            "duration_ms": tc.get("duration_ms"),
        }
        for tc in tool_calls
    ]
