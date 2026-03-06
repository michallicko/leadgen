"""Multimodal tool definitions for the AI agent (BL-265, BL-266).

Provides tools that the agent can call to analyze uploaded documents,
images, and web pages.  Registered with the global tool registry at
app startup.
"""

from __future__ import annotations

from ..services.multimodal.document_store import DocumentStore
from ..services.multimodal.html_processor import fetch_and_extract
from ..services.tool_registry import ToolContext, ToolDefinition


def analyze_document(args: dict, ctx: ToolContext) -> dict:
    """Analyze an uploaded document by file_id with a query.

    Retrieves cached summary or extracted text, returns relevant content.
    """
    file_id = args.get("file_id", "")
    query = args.get("query", "")

    if not file_id:
        return {"error": "file_id is required"}

    store = DocumentStore()

    info = store.get_upload_info(file_id, ctx.tenant_id)
    if not info:
        return {"error": "File not found: {}".format(file_id)}

    # Try summary first (L1), fall back to full text (L2)
    summary = store.get_file_summary(file_id, ctx.tenant_id)
    if summary:
        return {
            "filename": info["filename"],
            "summary": summary,
            "query": query,
            "detail_level": "summary",
        }

    full_text = store.get_extracted_text(file_id, ctx.tenant_id)
    if full_text:
        # Truncate to avoid token overflow
        if len(full_text) > 8000:
            full_text = full_text[:8000] + "\n\n[Content truncated]"
        return {
            "filename": info["filename"],
            "content": full_text,
            "query": query,
            "detail_level": "full_text",
        }

    return {
        "filename": info["filename"],
        "status": info["status"],
        "error": "Content not yet extracted. Status: {}".format(info["status"]),
    }


def analyze_image(args: dict, ctx: ToolContext) -> dict:
    """Analyze an uploaded image by file_id with a query.

    Returns image metadata and instructions for vision processing.
    """
    file_id = args.get("file_id", "")
    query = args.get("query", "")

    if not file_id:
        return {"error": "file_id is required"}

    store = DocumentStore()
    info = store.get_upload_info(file_id, ctx.tenant_id)
    if not info:
        return {"error": "File not found: {}".format(file_id)}

    # Check for cached description
    summary = store.get_file_summary(file_id, ctx.tenant_id)
    if summary:
        return {
            "filename": info["filename"],
            "description": summary,
            "query": query,
        }

    return {
        "filename": info["filename"],
        "status": info["status"],
        "mime_type": info["mime_type"],
        "needs_vision_processing": True,
        "query": query,
    }


def fetch_and_analyze_url(args: dict, ctx: ToolContext) -> dict:
    """Fetch a URL and extract main content for analysis.

    Handles SSRF protection and content caching.
    """
    url = args.get("url", "")
    query = args.get("query", "")

    if not url:
        return {"error": "url is required"}

    result = fetch_and_extract(url)

    if result.error:
        return {"error": result.error, "url": url}

    content = result.content
    # Truncate long content
    if len(content) > 6000:
        content = content[:6000] + "\n\n[Content truncated]"

    return {
        "url": url,
        "title": result.title,
        "content": content,
        "word_count": result.word_count,
        "cached": result.cached,
        "query": query,
    }


MULTIMODAL_TOOLS = [
    ToolDefinition(
        name="analyze_document",
        description=(
            "Analyze an uploaded document (PDF, Word). Returns the document "
            "summary or full extracted text. Use this to answer questions "
            "about uploaded files."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "UUID of the uploaded file to analyze.",
                },
                "query": {
                    "type": "string",
                    "description": (
                        "What to look for in the document. Be specific "
                        "(e.g., 'What is their revenue?' not just 'analyze')."
                    ),
                },
            },
            "required": ["file_id", "query"],
        },
        handler=analyze_document,
    ),
    ToolDefinition(
        name="analyze_image",
        description=(
            "Analyze an uploaded image (PNG, JPEG, WebP). Returns the image "
            "description or flags it for vision processing. Use this for "
            "screenshots, org charts, product photos."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "UUID of the uploaded image to analyze.",
                },
                "query": {
                    "type": "string",
                    "description": (
                        "What to look for in the image (e.g., "
                        "'Who is the decision maker in this org chart?')."
                    ),
                },
            },
            "required": ["file_id", "query"],
        },
        handler=analyze_image,
    ),
    ToolDefinition(
        name="fetch_and_analyze_url",
        description=(
            "Fetch a web page and extract its main content for analysis. "
            "Use this to analyze competitor websites, landing pages, blog "
            "posts, or any public URL. Automatically removes navigation, "
            "ads, and other boilerplate."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch and analyze.",
                },
                "query": {
                    "type": "string",
                    "description": (
                        "What to look for on the page (e.g., "
                        "'What is their pricing model?')."
                    ),
                },
            },
            "required": ["url", "query"],
        },
        handler=fetch_and_analyze_url,
    ),
]
