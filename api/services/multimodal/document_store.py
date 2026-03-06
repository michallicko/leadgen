"""Document store for multimodal file processing (BL-265).

Orchestrates upload metadata storage, content extraction, and
summary caching in PostgreSQL.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from ...models import db

logger = logging.getLogger(__name__)

# Default upload directory for local development
DEFAULT_UPLOAD_DIR = "/tmp/leadgen-uploads"

# Maximum upload size: 50 MB
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Approximate tokens per character
CHARS_PER_TOKEN = 4


class DocumentStore:
    """Manages file upload metadata and extracted content in PG."""

    def __init__(self, upload_dir: Optional[str] = None):
        self.upload_dir = upload_dir or os.environ.get("UPLOAD_DIR", DEFAULT_UPLOAD_DIR)
        os.makedirs(self.upload_dir, exist_ok=True)

    def save_upload(
        self,
        tenant_id: str,
        filename: str,
        mime_type: str,
        size_bytes: int,
        storage_path: str,
        created_by: Optional[str] = None,
    ) -> Optional[str]:
        """Record a file upload in the database.

        Args:
            tenant_id: Tenant UUID.
            filename: Original filename.
            mime_type: MIME type string.
            size_bytes: File size in bytes.
            storage_path: Path where file is stored.
            created_by: User UUID who uploaded.

        Returns:
            The file upload UUID, or None on error.

        Raises:
            ValueError: If file exceeds MAX_UPLOAD_BYTES.
        """
        if size_bytes > MAX_UPLOAD_BYTES:
            raise ValueError(
                "File size {} bytes exceeds maximum allowed {} bytes".format(
                    size_bytes, MAX_UPLOAD_BYTES
                )
            )
        try:
            from sqlalchemy import text as sa_text

            result = db.session.execute(
                sa_text(
                    "INSERT INTO file_uploads "
                    "(tenant_id, filename, mime_type, size_bytes, "
                    "storage_path, status, created_by) "
                    "VALUES (:tid, :fn, :mt, :sz, :sp, 'pending', :cb) "
                    "RETURNING id"
                ),
                {
                    "tid": tenant_id,
                    "fn": filename,
                    "mt": mime_type,
                    "sz": size_bytes,
                    "sp": storage_path,
                    "cb": created_by,
                },
            )
            db.session.commit()
            row = result.fetchone()
            return str(row[0]) if row else None
        except Exception:
            logger.exception("Failed to save upload metadata")
            db.session.rollback()
            return None

    def update_status(
        self, file_id: str, status: str, tenant_id: str, page_count: int = None
    ) -> bool:
        """Update the processing status of a file upload.

        Args:
            file_id: File upload UUID.
            status: New status (pending, processing, done, failed).
            tenant_id: Tenant UUID (for isolation).
            page_count: Number of pages (for PDFs).

        Returns:
            True if updated.
        """
        try:
            from sqlalchemy import text as sa_text

            params = {"fid": file_id, "st": status, "tid": tenant_id}
            set_clause = "status = :st"
            if page_count is not None:
                set_clause += ", page_count = :pc"
                params["pc"] = page_count

            db.session.execute(
                sa_text(
                    "UPDATE file_uploads SET {} WHERE id = :fid AND tenant_id = :tid".format(
                        set_clause
                    )
                ),
                params,
            )
            db.session.commit()
            return True
        except Exception:
            logger.exception("Failed to update file status")
            db.session.rollback()
            return False

    def save_extracted_content(
        self,
        file_id: str,
        content_type: str,
        content_text: str,
        content_summary: Optional[str] = None,
        page_number: Optional[int] = None,
        model_used: Optional[str] = None,
    ) -> Optional[str]:
        """Store extracted content from a file.

        Args:
            file_id: File upload UUID.
            content_type: Type of content (text, summary, table, image_desc).
            content_text: The extracted text content.
            content_summary: LLM-generated summary (optional).
            page_number: Page number for PDFs.
            model_used: Model used for summarization.

        Returns:
            Extracted content UUID, or None on error.
        """
        token_count = len(content_text) // CHARS_PER_TOKEN

        try:
            from sqlalchemy import text as sa_text

            result = db.session.execute(
                sa_text(
                    "INSERT INTO extracted_content "
                    "(file_id, content_type, content_text, content_summary, "
                    "page_number, token_count, model_used) "
                    "VALUES (:fid, :ct, :txt, :sum, :pn, :tc, :mu) "
                    "RETURNING id"
                ),
                {
                    "fid": file_id,
                    "ct": content_type,
                    "txt": content_text,
                    "sum": content_summary,
                    "pn": page_number,
                    "tc": token_count,
                    "mu": model_used,
                },
            )
            db.session.commit()
            row = result.fetchone()
            return str(row[0]) if row else None
        except Exception:
            logger.exception("Failed to save extracted content")
            db.session.rollback()
            return None

    def get_file_summary(self, file_id: str, tenant_id: str) -> Optional[str]:
        """Get the cached summary for a file.

        Args:
            file_id: File upload UUID.
            tenant_id: Tenant UUID (for isolation).

        Returns:
            Summary text, or None if not available.
        """
        try:
            from sqlalchemy import text as sa_text

            result = db.session.execute(
                sa_text(
                    "SELECT ec.content_summary FROM extracted_content ec "
                    "JOIN file_uploads fu ON fu.id = ec.file_id "
                    "WHERE ec.file_id = :fid AND fu.tenant_id = :tid "
                    "AND ec.content_type = 'summary' "
                    "ORDER BY ec.created_at DESC LIMIT 1"
                ),
                {"fid": file_id, "tid": tenant_id},
            )
            row = result.fetchone()
            return row[0] if row else None
        except Exception:
            logger.exception("Failed to get file summary")
            return None

    def get_extracted_text(self, file_id: str, tenant_id: str) -> Optional[str]:
        """Get the full extracted text for a file.

        Args:
            file_id: File upload UUID.
            tenant_id: Tenant UUID (for isolation).

        Returns:
            Concatenated extracted text, or None.
        """
        try:
            from sqlalchemy import text as sa_text

            result = db.session.execute(
                sa_text(
                    "SELECT ec.content_text FROM extracted_content ec "
                    "JOIN file_uploads fu ON fu.id = ec.file_id "
                    "WHERE ec.file_id = :fid AND fu.tenant_id = :tid "
                    "AND ec.content_type = 'text' "
                    "ORDER BY ec.page_number ASC NULLS LAST"
                ),
                {"fid": file_id, "tid": tenant_id},
            )
            rows = result.fetchall()
            if not rows:
                return None
            return "\n\n".join(row[0] for row in rows if row[0])
        except Exception:
            logger.exception("Failed to get extracted text")
            return None

    def get_upload_info(self, file_id: str, tenant_id: str) -> Optional[dict]:
        """Get upload metadata for a file.

        Args:
            file_id: File upload UUID.
            tenant_id: Tenant UUID (for isolation).

        Returns:
            Dict with file metadata, or None.
        """
        try:
            from sqlalchemy import text as sa_text

            result = db.session.execute(
                sa_text(
                    "SELECT id, tenant_id, filename, mime_type, size_bytes, "
                    "storage_path, status, page_count, created_at "
                    "FROM file_uploads WHERE id = :fid AND tenant_id = :tid"
                ),
                {"fid": file_id, "tid": tenant_id},
            )
            row = result.fetchone()
            if not row:
                return None
            return {
                "id": str(row[0]),
                "tenant_id": str(row[1]),
                "filename": row[2],
                "mime_type": row[3],
                "size_bytes": row[4],
                "storage_path": row[5],
                "status": row[6],
                "page_count": row[7],
                "created_at": str(row[8]) if row[8] else None,
            }
        except Exception:
            logger.exception("Failed to get upload info")
            return None
