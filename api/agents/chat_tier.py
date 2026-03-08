"""Haiku chat tier for simple, fast responses (BL-1011).

Handles quick questions, data lookups, greetings, and help requests
using Claude Haiku. Optimized for low latency (<2s) and low cost.

If the chat tier determines a message needs deeper analysis, it signals
escalation so the router can re-route to the planner.

SSE event format matches the existing graph.py SSEEvent convention.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Generator

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from .graph import SSEEvent

logger = logging.getLogger(__name__)

# Maximum tokens for chat tier responses — keep them concise
_MAX_TOKENS = 512

# Model for chat tier
_CHAT_MODEL = "claude-haiku-4-5-20251001"


def execute_chat_turn(
    message: str,
    page_context: str,
    tool_context: dict,
    conversation_history: list | None = None,
) -> Generator[SSEEvent, None, None]:
    """Handle a simple message with Haiku. Fast, cheap, direct.

    Yields SSEEvent objects for streaming to the client.

    Capabilities:
      - Answer questions about the platform
      - Provide navigation help
      - Simple acknowledgments and greetings
      - Data lookups via tool calls

    If the response indicates escalation is needed (complex request),
    yields an SSEEvent with type="escalation" so the caller can
    re-route to the planner.

    Args:
        message: User message text.
        page_context: Current UI page.
        tool_context: Dict with tenant_id, user_id, page_context.
        conversation_history: Optional prior messages for context.

    Yields:
        SSEEvent objects (chunk, tool_start, tool_result, done, escalation).
    """
    start = time.monotonic()

    system_prompt = _build_system_prompt(page_context, tool_context)
    tools = build_chat_tools(tool_context)

    # Build message list
    lc_messages: list = [SystemMessage(content=system_prompt)]

    if conversation_history:
        for msg in conversation_history[-6:]:  # Keep last 6 for context
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))

    lc_messages.append(HumanMessage(content=message))

    try:
        model = ChatAnthropic(
            model=_CHAT_MODEL,
            temperature=0.3,
            max_tokens=_MAX_TOKENS,
            timeout=10.0,
        )

        # Bind tools if available
        if tools:
            model = model.bind_tools(tools)

        response = model.invoke(lc_messages)

        elapsed_ms = (time.monotonic() - start) * 1000

        # Extract text content
        text = ""
        if isinstance(response.content, str):
            text = response.content
        elif isinstance(response.content, list):
            for block in response.content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text += block.get("text", "")
                elif isinstance(block, str):
                    text += block

        # Handle tool calls if present
        tool_calls = getattr(response, "tool_calls", None) or []
        tool_results = []

        for tc in tool_calls:
            tool_name = tc.get("name", "")
            tool_args = tc.get("args", {})

            yield SSEEvent(
                type="tool_start",
                data={"tool_name": tool_name, "input_args": tool_args},
            )

            result = _execute_tool(tool_name, tool_args, tool_context)
            tool_results.append(result)

            yield SSEEvent(
                type="tool_result",
                data={
                    "tool_name": tool_name,
                    "output_data": result,
                    "status": "error" if "error" in result else "success",
                },
            )

        # If tools were called, make a follow-up call with results
        if tool_calls and tool_results:
            # Build tool result messages for the follow-up
            lc_messages.append(response)
            for tc, result in zip(tool_calls, tool_results):
                from langchain_core.messages import ToolMessage

                lc_messages.append(
                    ToolMessage(
                        content=json.dumps(result),
                        tool_call_id=tc.get("id", ""),
                    )
                )

            # Second call without tools to get the final response
            followup_model = ChatAnthropic(
                model=_CHAT_MODEL,
                temperature=0.3,
                max_tokens=_MAX_TOKENS,
                timeout=10.0,
            )
            followup = followup_model.invoke(lc_messages)
            text = (
                followup.content
                if isinstance(followup.content, str)
                else str(followup.content)
            )

        # Check for escalation signal in the response
        if '{"escalate": true}' in text or '{"escalate":true}' in text:
            # Strip the escalation marker from visible text
            clean_text = text.replace('{"escalate": true}', "").replace(
                '{"escalate":true}', ""
            )
            clean_text = clean_text.strip()

            if clean_text:
                yield SSEEvent(
                    type="chunk",
                    data={"text": clean_text},
                )

            yield SSEEvent(
                type="escalation",
                data={"reason": "chat_tier_self_escalation"},
            )
        else:
            # Normal response — yield as a single chunk
            if text:
                yield SSEEvent(
                    type="chunk",
                    data={"text": text},
                )

        # Estimate cost
        usage = getattr(response, "usage_metadata", None) or {}
        input_tokens = usage.get("input_tokens", 0) if isinstance(usage, dict) else 0
        output_tokens = usage.get("output_tokens", 0) if isinstance(usage, dict) else 0

        yield SSEEvent(
            type="done",
            data={
                "tool_calls": [{"tool_name": tc.get("name", "")} for tc in tool_calls],
                "model": _CHAT_MODEL,
                "total_input_tokens": input_tokens,
                "total_output_tokens": output_tokens,
                "total_cost_usd": str(_estimate_cost(input_tokens, output_tokens)),
                "tier": "chat",
            },
        )

    except Exception as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.exception("Chat tier error (%.0fms): %s", elapsed_ms, exc)
        yield SSEEvent(
            type="chunk",
            data={
                "text": "I'm having trouble processing that right now. "
                "Could you try rephrasing your question?"
            },
        )
        yield SSEEvent(
            type="done",
            data={
                "tool_calls": [],
                "model": _CHAT_MODEL,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost_usd": "0",
                "tier": "chat",
                "error": str(exc),
            },
        )


def _build_system_prompt(page_context: str, tool_context: dict) -> str:
    """Build a minimal system prompt for the chat tier."""
    return (
        "You are a helpful assistant for the leadgen platform.\n"
        "The user is on the {page} page.\n\n"
        "Rules:\n"
        "- Be concise and direct (2-3 sentences max)\n"
        "- For data questions, use the available tools to look up real data\n"
        "- If the user asks for something complex (strategy work, research, "
        'multi-step analysis), say "Let me hand this off to the strategy team" '
        'and include {{"escalate": true}} at the end of your response\n'
        "- Never make up data - if you don't have it, say so\n"
        "- Be friendly and professional"
    ).format(page=page_context or "unknown")


def build_chat_tools(tool_context: dict) -> list:
    """Build the minimal tool set for the chat tier.

    Only data lookup and navigation -- no strategy editing.

    Returns:
        List of tool definitions in LangChain format.
    """
    tools = []

    # Only add tools if we have a tenant context (authenticated user)
    if not tool_context.get("tenant_id"):
        return tools

    tools.append(
        {
            "name": "data_lookup",
            "description": (
                "Look up data from the database. Can query: contact count, "
                "company count, batch list, message count, ICP tier summary."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "enum": [
                            "contact_count",
                            "company_count",
                            "batch_list",
                            "message_count",
                            "icp_summary",
                        ],
                    },
                    "filters": {
                        "type": "object",
                        "description": (
                            'Optional filters (e.g., {"status": "enriched"})'
                        ),
                    },
                },
                "required": ["query_type"],
            },
        }
    )

    tools.append(
        {
            "name": "navigate_suggestion",
            "description": (
                "Suggest the user navigate to a different page. Use when the "
                "user's question would be better served on another page."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "target_page": {
                        "type": "string",
                        "enum": [
                            "playbook",
                            "contacts",
                            "companies",
                            "messages",
                            "campaigns",
                            "import",
                            "enrich",
                        ],
                    },
                    "reason": {"type": "string"},
                },
                "required": ["target_page", "reason"],
            },
        }
    )

    return tools


def _execute_tool(tool_name: str, tool_args: dict, tool_context: dict) -> dict:
    """Execute a chat tier tool call.

    Routes to the appropriate handler based on tool name.
    """
    if tool_name == "data_lookup":
        return execute_data_lookup(
            query_type=tool_args.get("query_type", ""),
            filters=tool_args.get("filters", {}),
            tool_context=tool_context,
        )
    elif tool_name == "navigate_suggestion":
        return {
            "suggestion": "navigate",
            "target_page": tool_args.get("target_page", ""),
            "reason": tool_args.get("reason", ""),
        }
    else:
        return {"error": "Unknown tool: {}".format(tool_name)}


def execute_data_lookup(query_type: str, filters: dict, tool_context: dict) -> dict:
    """Execute a data lookup query against the database.

    Uses the existing SQLAlchemy models. Requires Flask app context.

    Args:
        query_type: Type of lookup (contact_count, company_count, etc.).
        filters: Optional filter dict.
        tool_context: Must contain tenant_id.

    Returns:
        Dict with query results.
    """
    tenant_id = tool_context.get("tenant_id")
    if not tenant_id:
        return {"error": "No tenant context available"}

    try:
        from api.models import Company, Contact, Message

        if query_type == "contact_count":
            count = Contact.query.filter_by(tenant_id=tenant_id).count()
            return {"count": count, "type": "contacts"}

        elif query_type == "company_count":
            count = Company.query.filter_by(tenant_id=tenant_id).count()
            return {"count": count, "type": "companies"}

        elif query_type == "message_count":
            count = Message.query.filter_by(tenant_id=tenant_id).count()
            return {"count": count, "type": "messages"}

        elif query_type == "icp_summary":
            # Count companies by ICP tier
            companies = Company.query.filter_by(tenant_id=tenant_id).all()
            tier_counts: dict[str, int] = {}
            for c in companies:
                tier = getattr(c, "icp_tier", None) or "Unclassified"
                tier_counts[tier] = tier_counts.get(tier, 0) + 1
            return {"tiers": tier_counts, "total": len(companies)}

        elif query_type == "batch_list":
            from api.models import Tag

            tags = Tag.query.filter_by(tenant_id=tenant_id).all()
            return {
                "tags": [{"name": t.name, "id": str(t.id)} for t in tags[:20]],
                "total": len(tags),
            }

        else:
            return {"error": "Unknown query type: {}".format(query_type)}

    except Exception as exc:
        logger.exception("Data lookup failed: %s", exc)
        return {"error": "Data lookup failed: {}".format(str(exc))}


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for Haiku usage."""
    input_cost = (input_tokens / 1_000_000) * 0.80
    output_cost = (output_tokens / 1_000_000) * 4.0
    return round(input_cost + output_cost, 6)
