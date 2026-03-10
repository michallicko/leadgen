"""Version service for strategy document snapshots (BL-1014).

Provides create, list, get, restore, and auto-snapshot operations for
Google Docs-style version browsing on strategy documents.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..models import StrategyDocument, StrategyVersion, db

logger = logging.getLogger(__name__)


def create_version(
    document_id: str,
    content: str,
    author_type: str,
    description: str,
    metadata: dict | None = None,
) -> dict:
    """Create a new version snapshot. Auto-increments version_number."""
    # Get the latest version number for this document
    latest = (
        StrategyVersion.query.filter_by(document_id=document_id)
        .order_by(StrategyVersion.version.desc())
        .first()
    )
    next_version = (latest.version + 1) if latest else 1

    edit_source = "ai_tool" if author_type == "ai" else "manual"

    doc = StrategyDocument.query.get(document_id)
    if not doc:
        raise ValueError("Document not found: {}".format(document_id))

    snap = StrategyVersion(
        document_id=document_id,
        tenant_id=doc.tenant_id,
        version=next_version,
        content=content,
        extracted_data=doc.extracted_data,
        edit_source=edit_source,
        description=description,
        metadata_=metadata or {},
    )
    db.session.add(snap)
    db.session.commit()
    return snap.to_dict()


def list_versions(document_id: str, limit: int = 50) -> list[dict]:
    """List versions for a document, newest first."""
    versions = (
        StrategyVersion.query.filter_by(document_id=document_id)
        .order_by(StrategyVersion.version.desc())
        .limit(limit)
        .all()
    )
    return [v.to_dict() for v in versions]


def get_version(version_id: str) -> dict | None:
    """Get a specific version with full content."""
    snap = StrategyVersion.query.get(version_id)
    if not snap:
        return None
    result = snap.to_dict()
    result["content"] = snap.content or ""
    result["extracted_data"] = (
        snap.extracted_data if isinstance(snap.extracted_data, dict) else {}
    )
    return result


def restore_version(document_id: str, version_id: str) -> dict:
    """Restore a version: creates a new snapshot of current state, then restores old content."""
    doc = StrategyDocument.query.get(document_id)
    if not doc:
        raise ValueError("Document not found: {}".format(document_id))

    snap = StrategyVersion.query.get(version_id)
    if not snap or snap.document_id != document_id:
        raise ValueError("Version not found or does not belong to this document")

    # Save current state as a snapshot before restoring
    create_version(
        document_id=document_id,
        content=doc.content or "",
        author_type="user",
        description="Auto-save before restoring version {}".format(snap.version),
        metadata={"trigger": "before_restore", "restored_from": version_id},
    )

    # Restore the document content from the snapshot
    doc.content = snap.content
    if snap.extracted_data:
        doc.extracted_data = snap.extracted_data
    doc.version += 1
    db.session.commit()

    return {
        "success": True,
        "restored_version": snap.version,
        "current_version": doc.version,
    }


def auto_snapshot_if_needed(
    document_id: str,
    trigger: str,
    description: str | None = None,
) -> dict | None:
    """Create auto-snapshot based on trigger type.

    Triggers:
    - 'ai_section_complete': After AI finishes writing a section
    - 'ai_plan_complete': After AI finishes a full plan execution
    - 'before_overwrite': Before AI overwrites existing content

    Debounce: don't create if last version is < 30 seconds old with same content.
    """
    doc = StrategyDocument.query.get(document_id)
    if not doc:
        return None

    # Debounce: check if last version is recent with same content
    latest = (
        StrategyVersion.query.filter_by(document_id=document_id)
        .order_by(StrategyVersion.created_at.desc())
        .first()
    )
    if latest and latest.created_at:
        # Handle both timezone-aware and naive datetimes
        now = datetime.now(timezone.utc)
        created = latest.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age = (now - created).total_seconds()
        if age < 30 and latest.content == doc.content:
            logger.debug(
                "Debounced auto-snapshot for doc %s (%.1fs old, same content)",
                document_id,
                age,
            )
            return None

    desc = description or "Auto-snapshot: {}".format(trigger.replace("_", " "))
    return create_version(
        document_id=document_id,
        content=doc.content or "",
        author_type="ai" if trigger.startswith("ai_") else "user",
        description=desc,
        metadata={"trigger": trigger},
    )
