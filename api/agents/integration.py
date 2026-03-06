"""Integration module for wiring LangGraph agent into Flask routes.

This module provides the feature flag check and the streaming response
function that playbook_routes.py can call. It is designed to be imported
without modifying playbook_routes.py — the route file just needs to add
a conditional import and call.

Usage in playbook_routes.py:
    from ..agents.integration import is_langgraph_enabled, stream_langgraph_response

    if is_langgraph_enabled() and tools:
        return stream_langgraph_response(
            client, system_prompt, messages, tools,
            tenant_id, doc_id, user_msg, user_id, app, phase,
        )
    else:
        # ... existing code path ...
"""

from __future__ import annotations

import json
import logging
import os
import uuid as _uuid
from typing import Any

logger = logging.getLogger(__name__)


def is_langgraph_enabled() -> bool:
    """Check if the LangGraph agent is enabled via feature flag.

    Reads LANGGRAPH_ENABLED environment variable.
    Returns True if set to '1', 'true', or 'yes' (case-insensitive).
    """
    return os.environ.get("LANGGRAPH_ENABLED", "").lower() in (
        "1",
        "true",
        "yes",
    )


def stream_langgraph_response(
    client: Any,
    system_prompt: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tenant_id: str,
    doc_id: str,
    user_msg: Any,
    user_id: str | None,
    app: Any,
    phase: str = "strategy",
) -> Any:
    """Create a Flask streaming Response using the LangGraph agent.

    This is the drop-in replacement for _stream_agent_response() in
    playbook_routes.py. It uses the LangGraph graph executor and emits
    AG-UI protocol events.

    Args:
        client: AnthropicClient instance.
        system_prompt: System prompt string.
        messages: Conversation messages.
        tools: Tool definitions in Claude API format.
        tenant_id: Tenant UUID string.
        doc_id: Document UUID string.
        user_msg: StrategyChatMessage instance (user's message).
        user_id: User UUID string or None.
        app: Flask app for DB access.
        phase: Current playbook phase.

    Returns:
        Flask Response with SSE streaming.
    """
    from flask import Response

    from ..models import StrategyChatMessage, ToolExecution, db
    from ..services.llm_logger import log_llm_usage
    from .graph import execute_agent_graph

    turn_id = str(_uuid.uuid4())

    tool_context = {
        "tenant_id": str(tenant_id),
        "user_id": str(user_id) if user_id else None,
        "document_id": str(doc_id) if doc_id else None,
        "turn_id": turn_id,
    }

    def generate():
        full_text = []
        msg_id = None
        final_tool_calls = []
        final_model = ""
        final_input_tokens = 0
        final_output_tokens = 0
        final_cost = "0"
        try:
            for sse_line in execute_agent_graph(
                client=client,
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
                tool_context=tool_context,
                phase=phase,
                app=app,
                use_agui=True,
            ):
                # Forward the SSE line to the client
                yield sse_line

                # Parse for state tracking (we need to save to DB after)
                try:
                    if sse_line.startswith("data: "):
                        payload = json.loads(sse_line[6:].strip())
                        evt_type = payload.get("type", "")

                        if evt_type == "TEXT_MESSAGE_CONTENT":
                            full_text.append(payload.get("delta", ""))

                        elif evt_type == "RUN_FINISHED":
                            final_tool_calls = payload.get("tool_calls", [])
                            final_model = payload.get("model", "")
                            final_input_tokens = payload.get("total_input_tokens", 0)
                            final_output_tokens = payload.get("total_output_tokens", 0)
                            final_cost = payload.get("total_cost_usd", "0")

                        # STATE_DELTA events are forwarded to the
                        # client via the SSE line above — no server-side
                        # tracking needed.
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass  # Skip unparseable lines

        except Exception as e:
            logger.exception("LangGraph agent error: %s", e)
            yield "data: {}\n\n".format(
                json.dumps({"type": "error", "message": str(e)})
            )
            return

        # Save assistant message to DB
        assistant_content = "".join(full_text)
        with app.app_context():
            extra = {
                "tool_calls": final_tool_calls,
                "llm_calls": len(final_tool_calls) + 1,
                "total_input_tokens": final_input_tokens,
                "total_output_tokens": final_output_tokens,
                "total_cost_usd": final_cost,
                "langgraph": True,
            }

            assistant_msg = StrategyChatMessage(
                tenant_id=tenant_id,
                document_id=doc_id,
                role="assistant",
                content=assistant_content,
                extra=extra,
            )
            db.session.add(assistant_msg)
            db.session.flush()
            msg_id = assistant_msg.id

            # Log tool executions
            for tc in final_tool_calls:
                tool_exec = ToolExecution(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    document_id=doc_id,
                    chat_message_id=msg_id,
                    tool_name=tc.get("tool_name", ""),
                    input_args=tc.get("input_args", {}),
                    output_data=tc.get("output_data", {}),
                    is_error=tc.get("status") == "error",
                    error_message=tc.get("error_message"),
                    duration_ms=tc.get("duration_ms"),
                )
                db.session.add(tool_exec)

            # Log aggregated LLM usage
            log_llm_usage(
                tenant_id=tenant_id,
                operation="playbook_chat",
                model=final_model or client.default_model,
                input_tokens=final_input_tokens,
                output_tokens=final_output_tokens,
                user_id=user_id,
                metadata={
                    "agent_turn": True,
                    "tool_calls": len(final_tool_calls),
                    "langgraph": True,
                },
            )

            db.session.commit()

    # Commit the user message before entering the generator

    db.session.commit()

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
