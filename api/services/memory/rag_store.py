"""RAG long-term memory store (BL-262).

Stores and retrieves key facts across chat sessions.  MVP uses
keyword-based retrieval with simple scoring.  Can be upgraded to
pgvector embeddings later.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from ...models import db

logger = logging.getLogger(__name__)

# Maximum tokens to inject from memory per agent turn
MAX_MEMORY_TOKENS = 1500

# Approximate tokens per character (conservative estimate)
CHARS_PER_TOKEN = 4

# Maximum number of facts to retrieve per query
MAX_FACTS_RETRIEVED = 10

# Stop-words to exclude from keyword extraction
_STOP_WORDS = frozenset(
    "a an the is are was were be been being have has had do does did "
    "will would shall should may might can could and or but if then else "
    "for to of in on at by with from as into about between through "
    "i me my we our you your he she it they them their this that these "
    "those what which who whom how when where why all each every some any "
    "no not very much more most also just only still already even".split()
)


class MemoryStore:
    """Keyword-based memory store backed by PostgreSQL.

    Stores facts as text chunks with extracted keywords for retrieval.
    Scoped by tenant_id for multi-tenant isolation.
    """

    def store_fact(
        self,
        tenant_id: str,
        text: str,
        chunk_type: str = "fact",
        playbook_id: Optional[str] = None,
        source_message_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Optional[str]:
        """Store a fact in long-term memory.

        Args:
            tenant_id: Tenant UUID.
            text: The fact text to store.
            chunk_type: One of 'fact', 'decision', 'preference', 'research'.
            playbook_id: Associated strategy document UUID.
            source_message_id: Chat message that produced this fact.
            session_id: Session identifier for grouping.

        Returns:
            The UUID of the stored fact, or None on error.
        """
        if not text or not text.strip():
            return None

        keywords = extract_keywords(text)

        try:
            import json as _json
            import uuid as _uuid
            from sqlalchemy import text as sa_text

            fact_id = str(_uuid.uuid4())
            kw_value = _json.dumps(keywords)

            db.session.execute(
                sa_text(
                    "INSERT INTO memory_facts "
                    "(id, tenant_id, playbook_id, source_message_id, "
                    "chunk_text, chunk_type, keywords, session_id) "
                    "VALUES (:id, :tid, :pid, :mid, :txt, :ctype, :kw, :sid)"
                ),
                {
                    "id": fact_id,
                    "tid": tenant_id,
                    "pid": playbook_id,
                    "mid": source_message_id,
                    "txt": text.strip(),
                    "ctype": chunk_type,
                    "kw": kw_value,
                    "sid": session_id,
                },
            )
            db.session.commit()
            return fact_id
        except Exception:
            logger.exception("Failed to store memory fact")
            db.session.rollback()
            return None

    def retrieve(
        self,
        tenant_id: str,
        query: str,
        max_tokens: int = MAX_MEMORY_TOKENS,
        max_facts: int = MAX_FACTS_RETRIEVED,
    ) -> list[dict]:
        """Retrieve relevant facts for a query.

        Uses keyword overlap scoring to rank stored facts by relevance.

        Args:
            tenant_id: Tenant UUID.
            query: The search query text.
            max_tokens: Maximum total tokens for returned facts.
            max_facts: Maximum number of facts to return.

        Returns:
            List of ``{"id": str, "text": str, "type": str, "score": float}``
            dicts ordered by relevance score (descending).
        """
        query_keywords = extract_keywords(query)
        if not query_keywords:
            return []

        try:
            from sqlalchemy import text as sa_text

            # Retrieve candidate facts for this tenant
            result = db.session.execute(
                sa_text(
                    "SELECT id, chunk_text, chunk_type, keywords "
                    "FROM memory_facts "
                    "WHERE tenant_id = :tid "
                    "ORDER BY created_at DESC "
                    "LIMIT 100"
                ),
                {"tid": tenant_id},
            )
            rows = result.fetchall()
        except Exception:
            logger.exception("Failed to retrieve memory facts")
            return []

        # Score each fact by keyword overlap
        scored = []
        query_kw_set = set(query_keywords)
        for row in rows:
            fact_id, text, chunk_type, kw_raw = row
            fact_keywords = _parse_keywords(kw_raw)
            if not fact_keywords:
                continue

            overlap = query_kw_set & set(fact_keywords)
            if not overlap:
                continue

            score = len(overlap) / max(len(query_kw_set), 1)
            scored.append(
                {
                    "id": str(fact_id),
                    "text": text,
                    "type": chunk_type,
                    "score": round(score, 3),
                }
            )

        # Sort by score descending
        scored.sort(key=lambda x: x["score"], reverse=True)

        # Apply token budget
        results = []
        total_chars = 0
        max_chars = max_tokens * CHARS_PER_TOKEN

        for fact in scored[:max_facts]:
            fact_chars = len(fact["text"])
            if total_chars + fact_chars > max_chars:
                break
            results.append(fact)
            total_chars += fact_chars

        return results

    def format_for_injection(self, facts: list[dict]) -> str:
        """Format retrieved facts as a text block for prompt injection.

        Args:
            facts: List of fact dicts from ``retrieve()``.

        Returns:
            Formatted string suitable for including in system prompt.
        """
        if not facts:
            return ""

        lines = ["[Long-term memory — relevant past context]"]
        for fact in facts:
            prefix = fact.get("type", "fact").capitalize()
            lines.append("- {}: {}".format(prefix, fact["text"]))
        return "\n".join(lines)

    def delete_for_tenant(self, tenant_id: str) -> int:
        """Delete all memory facts for a tenant.

        Returns:
            Number of deleted rows.
        """
        try:
            from sqlalchemy import text as sa_text

            result = db.session.execute(
                sa_text("DELETE FROM memory_facts WHERE tenant_id = :tid"),
                {"tid": tenant_id},
            )
            db.session.commit()
            return result.rowcount
        except Exception:
            logger.exception("Failed to delete memory facts")
            db.session.rollback()
            return 0


def extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from text.

    Removes stop-words, punctuation, and short tokens.

    Args:
        text: Input text.

    Returns:
        List of lowercase keyword strings.
    """
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    keywords = [w for w in words if w not in _STOP_WORDS and len(w) > 2]
    # Deduplicate while preserving order
    seen = set()
    result = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)
    return result


def _parse_keywords(kw_raw) -> list[str]:
    """Parse keywords from database storage format.

    Handles both PostgreSQL ARRAY (list) and SQLite TEXT (JSON string).
    """
    if isinstance(kw_raw, list):
        return kw_raw
    if isinstance(kw_raw, str):
        try:
            import json

            parsed = json.loads(kw_raw)
            if isinstance(parsed, list):
                return parsed
        except (ValueError, TypeError):
            pass
        # Try PostgreSQL array literal format: {a,b,c}
        if kw_raw.startswith("{") and kw_raw.endswith("}"):
            return [k.strip() for k in kw_raw[1:-1].split(",") if k.strip()]
    return []
