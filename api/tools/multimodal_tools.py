"""Multimodal tool definitions for the AI agent.

Provides tools for document analysis, data extraction, and image analysis.
Registered with the AGENT tool registry at app startup.
"""

from __future__ import annotations

import logging

from ..models import FileUpload
from ..services.multimodal.context_manager import get_file_context
from ..services.tool_registry import ToolContext, ToolDefinition

logger = logging.getLogger(__name__)


def analyze_document(args: dict, ctx: ToolContext) -> dict:
    """Retrieve and analyze content from an uploaded document.

    Returns the document summary (L1) or full text (L2) based on detail level.
    """
    file_id = args.get("file_id", "")
    detail = args.get("detail_level", "l1")

    if not file_id:
        return {"error": "file_id is required."}

    if detail not in ("l0", "l1", "l2"):
        return {"error": "detail_level must be 'l0', 'l1', or 'l2'."}

    # Verify tenant access
    file_record = FileUpload.query.filter_by(
        id=file_id, tenant_id=ctx.tenant_id
    ).first()
    if not file_record:
        return {"error": "File not found."}

    result = get_file_context(file_id, detail)
    if not result:
        return {"error": "No content available for this file."}

    return {
        "filename": file_record.original_filename,
        "content": result["content"],
        "detail_level": result["level"],
        "tokens_used": result["tokens"],
    }


def extract_data(args: dict, ctx: ToolContext) -> dict:
    """Extract specific data points from an uploaded document.

    Searches the document content for the requested information.
    """
    file_id = args.get("file_id", "")
    query = args.get("query", "")

    if not file_id:
        return {"error": "file_id is required."}
    if not query:
        return {"error": "query is required."}

    # Verify tenant access
    file_record = FileUpload.query.filter_by(
        id=file_id, tenant_id=ctx.tenant_id
    ).first()
    if not file_record:
        return {"error": "File not found."}

    # Get full text for searching
    result = get_file_context(file_id, "l2", max_tokens=4000)
    if not result or not result.get("content"):
        return {"error": "No content available to search."}

    return {
        "filename": file_record.original_filename,
        "content": result["content"],
        "query": query,
        "note": "Search the content above for: {}".format(query),
    }


def analyze_image(args: dict, ctx: ToolContext) -> dict:
    """Analyze an uploaded image and describe its content.

    Returns the extracted/described content from the image.
    """
    file_id = args.get("file_id", "")

    if not file_id:
        return {"error": "file_id is required."}

    file_record = FileUpload.query.filter_by(
        id=file_id, tenant_id=ctx.tenant_id
    ).first()
    if not file_record:
        return {"error": "File not found."}

    if not file_record.mime_type.startswith("image/"):
        return {"error": "This file is not an image."}

    result = get_file_context(file_id, "l2")
    if not result or not result.get("content"):
        return {"error": "No analysis available for this image."}

    return {
        "filename": file_record.original_filename,
        "analysis": result["content"],
        "tokens_used": result["tokens"],
    }


# Tool definitions for registration
MULTIMODAL_TOOLS = [
    ToolDefinition(
        name="analyze_document",
        description=(
            "Retrieve and analyze content from an uploaded document (PDF, Word, HTML). "
            "Returns a summary by default, or full text at 'l2' detail level. "
            "Use this to understand uploaded documents before answering questions about them."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "The UUID of the uploaded file to analyze.",
                },
                "detail_level": {
                    "type": "string",
                    "enum": ["l0", "l1", "l2"],
                    "description": (
                        "Level of detail: 'l0' for brief mention, "
                        "'l1' for summary (default), 'l2' for full text."
                    ),
                    "default": "l1",
                },
            },
            "required": ["file_id"],
        },
        handler=analyze_document,
    ),
    ToolDefinition(
        name="extract_data",
        description=(
            "Extract specific data points from an uploaded document. "
            "Provide the file ID and a query describing what data to find. "
            "Returns the relevant document content for you to search through."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "The UUID of the uploaded file.",
                },
                "query": {
                    "type": "string",
                    "description": "What data to look for in the document.",
                },
            },
            "required": ["file_id", "query"],
        },
        handler=extract_data,
    ),
    ToolDefinition(
        name="analyze_image",
        description=(
            "Analyze an uploaded image (screenshot, chart, photo). "
            "Returns a description of the image content including any "
            "text, data from charts/tables, or visual elements."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "The UUID of the uploaded image file.",
                },
            },
            "required": ["file_id"],
        },
        handler=analyze_image,
    ),
]
