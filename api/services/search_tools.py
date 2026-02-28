"""Web search tool handler for AI chat tool-use.

Provides internet search capability via the Perplexity sonar API.
The tool wraps the existing PerplexityClient with:
- 10-second timeout
- Graceful error handling (never exposes raw API errors)
- Cost logging via LlmUsageLog
- Citation extraction from search results

Rate limiting is handled by the agent executor (3 calls/turn for web_search).
Registered with the AGENT tool registry at app startup.
"""

from __future__ import annotations

import logging
import os
import time

import requests

from ..models import db
from .llm_logger import log_llm_usage
from .perplexity_client import PerplexityClient
from .tool_registry import ToolContext, ToolDefinition

logger = logging.getLogger(__name__)

# Search-specific configuration
SEARCH_TIMEOUT = 10  # seconds
SEARCH_MODEL = "sonar"
MAX_QUERY_LENGTH = 500


def _get_perplexity_client():
    """Create a PerplexityClient configured for agent search.

    Returns None if the API key is not configured.
    """
    api_key = os.environ.get("PERPLEXITY_API_KEY", "")
    if not api_key:
        return None
    return PerplexityClient(
        api_key=api_key,
        default_model=SEARCH_MODEL,
        timeout=SEARCH_TIMEOUT,
        max_retries=0,  # No retries for interactive search (stay within timeout)
    )


def web_search(args: dict, ctx: ToolContext) -> dict:
    """Search the internet via Perplexity sonar API.

    Args:
        args: {"query": "search query string"}
        ctx: ToolContext with tenant_id for cost logging.

    Returns:
        {"answer": "...", "citations": ["url1", ...]}
        or {"error": "..."} on failure.
    """
    query = args.get("query", "").strip()
    if not query:
        return {"error": "Query is required."}

    if len(query) > MAX_QUERY_LENGTH:
        return {
            "error": "Query too long (max {} characters). Please shorten your search.".format(
                MAX_QUERY_LENGTH
            )
        }

    client = _get_perplexity_client()
    if client is None:
        return {
            "error": "Web search is not configured. Ask your administrator to set up the Perplexity API key."
        }

    start_ms = int(time.monotonic() * 1000)

    try:
        result = client.query(
            system_prompt=(
                "You are a research assistant. Provide concise, factual answers "
                "based on current web search results. Include specific data points, "
                "names, and dates when available. If the information is uncertain, "
                "say so."
            ),
            user_prompt=query,
            model=SEARCH_MODEL,
            max_tokens=800,
            temperature=0.1,
        )

        elapsed_ms = int(time.monotonic() * 1000) - start_ms

        # Log cost
        log_llm_usage(
            tenant_id=ctx.tenant_id,
            operation="agent_web_search",
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            provider="perplexity",
            user_id=ctx.user_id,
            duration_ms=elapsed_ms,
            metadata={"query_length": len(query)},
        )
        db.session.commit()

        # Extract citations from the response content
        # Perplexity includes inline citations like [1], [2] etc.
        # The actual URLs come from the API response
        citations = []
        if hasattr(result, "citations") and result.citations:
            citations = result.citations

        return {
            "answer": result.content,
            "citations": citations,
            "summary": "Search completed ({} tokens)".format(
                result.input_tokens + result.output_tokens
            ),
        }

    except requests.Timeout:
        elapsed_ms = int(time.monotonic() * 1000) - start_ms
        logger.warning(
            "Perplexity search timed out after %dms for query: %.100s",
            elapsed_ms,
            query,
        )
        return {"error": "Search timed out. Try a more specific query."}

    except requests.HTTPError as exc:
        elapsed_ms = int(time.monotonic() * 1000) - start_ms
        status = getattr(exc.response, "status_code", 0) if exc.response else 0
        logger.warning(
            "Perplexity API error %s after %dms for query: %.100s",
            status,
            elapsed_ms,
            query,
        )
        return {"error": "Search temporarily unavailable."}

    except Exception as exc:
        logger.exception("Unexpected error in web_search: %s", exc)
        return {"error": "Search temporarily unavailable."}


# ---------------------------------------------------------------------------
# Tool definition for registry
# ---------------------------------------------------------------------------

SEARCH_TOOLS = [
    ToolDefinition(
        name="web_search",
        description=(
            "Search the internet for current information about markets, "
            "companies, competitors, industry trends, or prospects. "
            "Returns a concise answer with source citations. "
            "Use this when you need up-to-date information that isn't "
            "in the CRM data. Max 3 searches per conversation turn."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "The search query. Be specific for better results. "
                        "Example: 'latest AI adoption trends in European manufacturing 2026' "
                        "rather than just 'AI trends'. Max 500 characters."
                    ),
                },
            },
            "required": ["query"],
        },
        handler=web_search,
    ),
]
