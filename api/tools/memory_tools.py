"""Memory tool definitions for the AI agent.

Provides tools for searching long-term memory and saving important insights.
Registered with the AGENT tool registry at app startup.
"""

from __future__ import annotations

import logging

from ..services.memory.embeddings import save_memory, search_memories
from ..services.tool_registry import ToolContext, ToolDefinition

logger = logging.getLogger(__name__)


def search_memory(args: dict, ctx: ToolContext) -> dict:
    """Search long-term memory for relevant past context.

    Retrieves previously saved decisions, preferences, insights, and constraints
    that are relevant to the current query.
    """
    query = args.get("query", "").strip()
    if not query:
        return {"error": "query is required."}

    top_k = min(args.get("top_k", 5), 20)  # Cap at 20
    content_type = args.get("content_type")

    if content_type and content_type not in (
        "decision",
        "preference",
        "insight",
        "constraint",
    ):
        return {
            "error": "Invalid content_type. Use: decision, preference, insight, constraint."
        }

    results = search_memories(
        tenant_id=ctx.tenant_id,
        query=query,
        top_k=top_k,
        content_type=content_type,
    )

    if not results:
        return {"results": [], "message": "No relevant memories found."}

    return {
        "results": results,
        "count": len(results),
    }


def save_insight(args: dict, ctx: ToolContext) -> dict:
    """Save an important insight or decision to long-term memory.

    Use this when the user makes an important decision, states a preference,
    or when you identify a key insight worth remembering for future sessions.
    """
    content = args.get("content", "").strip()
    if not content:
        return {"error": "content is required."}

    if len(content) < 10:
        return {"error": "Content too short. Provide meaningful content to save."}

    content_type = args.get("content_type", "insight")
    if content_type not in ("decision", "preference", "insight", "constraint"):
        return {
            "error": "Invalid content_type. Use: decision, preference, insight, constraint."
        }

    metadata = args.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    memory = save_memory(
        tenant_id=ctx.tenant_id,
        content=content,
        content_type=content_type,
        user_id=ctx.user_id,
        metadata=metadata,
    )

    if not memory:
        return {"error": "Failed to save memory."}

    return {
        "id": str(memory.id),
        "message": "Saved to long-term memory as '{}'.".format(content_type),
    }


# Tool definitions for registration
MEMORY_TOOLS = [
    ToolDefinition(
        name="search_memory",
        description=(
            "Search long-term memory for relevant past context from previous sessions. "
            "Use this at the start of conversations or when the user references past decisions. "
            "Returns previously saved decisions, preferences, insights, and constraints."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for in memory (e.g., 'ICP decisions', 'tone preferences').",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default 5, max 20).",
                    "default": 5,
                },
                "content_type": {
                    "type": "string",
                    "enum": ["decision", "preference", "insight", "constraint"],
                    "description": "Optional filter by memory type.",
                },
            },
            "required": ["query"],
        },
        handler=search_memory,
    ),
    ToolDefinition(
        name="save_insight",
        description=(
            "Save an important insight, decision, preference, or constraint to long-term memory. "
            "Use this when the user approves a strategy, states a preference, or makes a key decision "
            "that should be remembered in future conversations."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The insight or decision to save. Be specific and include context.",
                },
                "content_type": {
                    "type": "string",
                    "enum": ["decision", "preference", "insight", "constraint"],
                    "description": "Type of memory to save.",
                    "default": "insight",
                },
                "metadata": {
                    "type": "object",
                    "description": "Optional metadata (topic, tags, etc.).",
                },
            },
            "required": ["content"],
        },
        handler=save_insight,
    ),
]
