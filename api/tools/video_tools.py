"""Video processing tool definitions for the AI agent (BL-268).

Provides the analyze_video tool that the agent can call to process
video files or URLs (YouTube/Vimeo) -- extracting transcripts,
keyframes, and generating combined summaries.
"""

from __future__ import annotations

import os

from ..services.multimodal.document_store import DocumentStore
from ..services.multimodal.video_processor import (
    check_ffmpeg,
    download_video_url,
    estimate_cost,
    get_video_metadata,
    process_video,
)
from ..services.tool_registry import ToolContext, ToolDefinition


def analyze_video(args: dict, ctx: ToolContext) -> dict:
    """Analyze a video file or URL.

    Handles both uploaded files (by file_id) and URLs (YouTube/Vimeo).
    Returns transcript, keyframes, and cost estimate.
    """
    file_id = args.get("file_id", "")
    url = args.get("url", "")
    query = args.get("query", "")
    max_duration = args.get("max_duration_minutes", 15)
    estimate_only = args.get("estimate_only", False)

    if not file_id and not url:
        return {"error": "Either file_id or url is required"}

    if not check_ffmpeg():
        return {"error": "ffmpeg is not installed on the server"}

    file_path = None
    filename = ""

    # Resolve file path
    if file_id:
        store = DocumentStore()
        info = store.get_upload_info(file_id, ctx.tenant_id)
        if not info:
            return {"error": "File not found: {}".format(file_id)}
        file_path = info.get("storage_path", "")
        filename = info.get("filename", "")
    elif url:
        # Download from URL
        file_path = download_video_url(url)
        if not file_path:
            return {"error": "Failed to download video from URL: {}".format(url)}
        filename = os.path.basename(file_path)

    if not file_path or not os.path.exists(file_path):
        return {"error": "Video file not accessible"}

    # Get metadata first
    metadata = get_video_metadata(file_path)
    if not metadata:
        return {"error": "Failed to read video metadata"}

    # Cost estimate
    cost = estimate_cost(metadata)

    if estimate_only:
        return {
            "filename": filename,
            "duration_minutes": cost.duration_minutes,
            "estimated_keyframes": cost.estimated_keyframes,
            "estimated_cost_usd": cost.total_cost_usd,
            "cost_breakdown": {
                "whisper_usd": cost.whisper_cost_usd,
                "vision_usd": cost.vision_cost_usd,
            },
            "has_audio": metadata.has_audio,
            "resolution": "{}x{}".format(metadata.width, metadata.height),
            "query": query,
        }

    # Full processing
    result = process_video(
        file_path,
        max_duration_minutes=max_duration,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
    )

    if result.error:
        return {"error": result.error, "filename": filename}

    response = {
        "filename": filename,
        "cached": result.cached,
        "duration_minutes": cost.duration_minutes,
        "estimated_cost_usd": cost.total_cost_usd,
        "has_audio": metadata.has_audio,
        "query": query,
    }

    # Transcript
    if result.transcript_text:
        # Truncate for token budget
        transcript = result.transcript_text
        if len(transcript) > 4000:
            transcript = transcript[:4000] + "\n\n[Transcript truncated]"
        response["transcript"] = transcript
        response["transcript_segments_count"] = len(result.transcript_segments)

    # Keyframes (paths only -- agent handles vision API calls)
    if result.keyframes:
        response["keyframes"] = [
            {
                "timestamp_seconds": kf.timestamp_seconds,
                "file_path": kf.file_path,
                "time_formatted": "{:02d}:{:02d}".format(
                    int(kf.timestamp_seconds // 60),
                    int(kf.timestamp_seconds % 60),
                ),
            }
            for kf in result.keyframes
        ]

    return response


VIDEO_TOOLS = [
    ToolDefinition(
        name="analyze_video",
        description=(
            "Analyze a video file or URL (YouTube, Vimeo). Extracts audio "
            "transcript (via Whisper), keyframes (via scene detection), and "
            "provides cost estimates. Use estimate_only=true first to check "
            "cost before full processing. Videos longer than 15 minutes are "
            "rejected. Supports uploaded files (by file_id) and URLs."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "UUID of an uploaded video file.",
                },
                "url": {
                    "type": "string",
                    "description": (
                        "Video URL (YouTube, Vimeo, etc.). "
                        "Either file_id or url is required."
                    ),
                },
                "query": {
                    "type": "string",
                    "description": (
                        "What to look for in the video (e.g., "
                        "'What product features are demonstrated?')."
                    ),
                },
                "max_duration_minutes": {
                    "type": "number",
                    "description": "Maximum allowed duration in minutes (default: 15).",
                },
                "estimate_only": {
                    "type": "boolean",
                    "description": (
                        "If true, only return cost estimate without processing. "
                        "Use this first to check cost before committing."
                    ),
                },
            },
        },
        handler=analyze_video,
    ),
]
