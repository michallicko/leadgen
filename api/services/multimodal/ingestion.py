"""File upload ingestion: validation, storage, and processing dispatch.

Handles file uploads from the API, validates size/type, stores to disk (dev)
or S3 (production), and dispatches to the appropriate extractor.
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from ...models import ExtractedContent, FileUpload, db

logger = logging.getLogger(__name__)

# Size and type constraints
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_URL_RESPONSE_SIZE = 10 * 1024 * 1024  # 10 MB
URL_FETCH_TIMEOUT = 10  # seconds

ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "image",
    "image/png": "image",
    "image/webp": "image",
    "image/gif": "image",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "word",
    "text/html": "html",
}

# Extension to MIME type fallback (when Content-Type is generic)
EXTENSION_MAP = {
    ".pdf": "application/pdf",
    ".jpg": "application/pdf",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".html": "text/html",
    ".htm": "text/html",
}


def get_upload_dir() -> Path:
    """Return the upload directory, creating it if needed."""
    upload_dir = Path(os.environ.get("UPLOAD_DIR", "uploads"))
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def validate_upload(filename: str, size_bytes: int, mime_type: str) -> Optional[str]:
    """Validate file upload parameters.

    Returns an error message string if invalid, None if valid.
    """
    if size_bytes > MAX_FILE_SIZE:
        return "File too large. Maximum size is 50MB."

    if size_bytes == 0:
        return "File is empty."

    # Try MIME type first, then fall back to extension
    if mime_type not in ALLOWED_MIME_TYPES:
        ext = Path(filename).suffix.lower()
        resolved_mime = EXTENSION_MAP.get(ext)
        if resolved_mime is None:
            supported = "PDF, DOCX, JPEG, PNG, WebP, GIF, HTML"
            return "Unsupported file type. Supported formats: {}".format(supported)

    return None


def resolve_mime_type(filename: str, declared_mime: str) -> str:
    """Resolve the effective MIME type from declared type or extension."""
    if declared_mime in ALLOWED_MIME_TYPES:
        return declared_mime
    ext = Path(filename).suffix.lower()
    return EXTENSION_MAP.get(ext, declared_mime)


def store_file(file_data: bytes, filename: str, tenant_id: str) -> str:
    """Store uploaded file to local disk. Returns the storage path.

    In production, this would upload to S3 instead.
    """
    safe_name = "{}_{}".format(uuid.uuid4().hex[:12], _sanitize_filename(filename))
    tenant_dir = get_upload_dir() / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)

    file_path = tenant_dir / safe_name
    file_path.write_bytes(file_data)

    return str(file_path)


def _sanitize_filename(filename: str) -> str:
    """Remove path separators and dangerous characters from filename."""
    # Keep only the basename and replace dangerous chars
    name = Path(filename).name
    # Replace any non-alphanumeric (except . - _) with underscore
    safe = "".join(c if c.isalnum() or c in ".-_" else "_" for c in name)
    return safe[:200]  # Truncate to reasonable length


def create_file_record(
    tenant_id: str,
    user_id: str,
    original_filename: str,
    mime_type: str,
    size_bytes: int,
    storage_path: str,
) -> FileUpload:
    """Create a FileUpload database record."""
    file_record = FileUpload(
        tenant_id=tenant_id,
        user_id=user_id,
        filename=_sanitize_filename(original_filename),
        original_filename=original_filename,
        mime_type=mime_type,
        size_bytes=size_bytes,
        storage_path=storage_path,
        processing_status="pending",
    )
    db.session.add(file_record)
    db.session.flush()
    return file_record


def process_file(file_id: str) -> None:
    """Process an uploaded file: extract content and generate summary.

    This is the main dispatch function that routes to the appropriate
    extractor based on MIME type.
    """
    from .extractors import extract_content
    from .summarizer import summarize_content

    file_record = db.session.get(FileUpload, file_id)
    if not file_record:
        logger.error("File record not found: %s", file_id)
        return

    try:
        file_record.processing_status = "processing"
        db.session.commit()

        # Extract content based on MIME type
        file_type = ALLOWED_MIME_TYPES.get(file_record.mime_type, "unknown")
        storage_path = file_record.storage_path

        extracted = extract_content(storage_path, file_type, file_record.mime_type)

        if not extracted:
            file_record.processing_status = "failed"
            file_record.error_message = "No content could be extracted from file."
            db.session.commit()
            return

        # Store full text
        full_text = extracted.get("text", "")
        token_count = _estimate_tokens(full_text)

        content_record = ExtractedContent(
            file_id=file_id,
            content_type="full_text",
            content_text=full_text,
            page_range=extracted.get("page_range"),
            token_count=token_count,
        )
        db.session.add(content_record)

        # Generate and store summary
        if full_text and token_count > 100:
            summary = summarize_content(full_text, file_record.original_filename)
            if summary:
                summary_record = ExtractedContent(
                    file_id=file_id,
                    content_type="summary",
                    content_text=None,
                    content_summary=summary,
                    token_count=_estimate_tokens(summary),
                )
                db.session.add(summary_record)

        file_record.processing_status = "completed"
        db.session.commit()

    except Exception:
        logger.exception("Failed to process file %s", file_id)
        db.session.rollback()
        file_record.processing_status = "failed"
        file_record.error_message = "Processing failed unexpectedly."
        db.session.commit()


def _estimate_tokens(text: str) -> int:
    """Rough token count estimate (~4 chars per token for English)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def fetch_url_content(url: str) -> dict:
    """Fetch content from a URL for processing.

    Returns:
        {"data": bytes, "mime_type": str, "filename": str}
        or {"error": str} on failure.
    """
    import requests

    try:
        resp = requests.get(
            url,
            timeout=URL_FETCH_TIMEOUT,
            headers={"User-Agent": "LeadgenBot/1.0"},
            stream=True,
        )
        resp.raise_for_status()

        # Check size
        content_length = resp.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_URL_RESPONSE_SIZE:
            return {"error": "URL content too large (max 10MB)."}

        data = resp.content
        if len(data) > MAX_URL_RESPONSE_SIZE:
            return {"error": "URL content too large (max 10MB)."}

        mime_type = resp.headers.get("Content-Type", "text/html").split(";")[0].strip()
        # Extract filename from URL
        from urllib.parse import urlparse

        path = urlparse(url).path
        filename = Path(path).name or "page.html"

        return {"data": data, "mime_type": mime_type, "filename": filename}

    except requests.Timeout:
        return {"error": "URL fetch timed out ({}s limit).".format(URL_FETCH_TIMEOUT)}
    except requests.RequestException as exc:
        return {"error": "Failed to fetch URL: {}".format(str(exc)[:200])}
