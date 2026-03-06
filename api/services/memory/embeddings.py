"""RAG long-term memory with pgvector similarity search.

Generates embeddings via OpenAI or Anthropic API and stores them in PostgreSQL
with pgvector for cross-session knowledge retrieval.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from sqlalchemy import text

from ...models import MemoryEmbedding, db

logger = logging.getLogger(__name__)

# Embedding configuration
EMBEDDING_MODEL = "text-embedding-3-small"  # OpenAI
EMBEDDING_DIMENSIONS = 1536
DEFAULT_TOP_K = 5
MAX_CONTENT_LENGTH = 8000  # chars


def generate_embedding(content: str) -> Optional[list[float]]:
    """Generate an embedding vector for the given content.

    Uses OpenAI embeddings API (text-embedding-3-small, 1536 dims).
    Returns None if the API key is not configured.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        logger.debug("OPENAI_API_KEY not set, skipping embedding generation")
        return None

    try:
        import requests

        response = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": "Bearer {}".format(api_key),
                "Content-Type": "application/json",
            },
            json={
                "model": EMBEDDING_MODEL,
                "input": content[: EMBEDDING_DIMENSIONS * 4],  # ~6K chars
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]

    except Exception:
        logger.exception("Embedding generation failed")
        return None


def save_memory(
    tenant_id: str,
    content: str,
    content_type: str = "decision",
    user_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    source_message_id: Optional[str] = None,
) -> Optional[MemoryEmbedding]:
    """Save a memory entry with its embedding.

    Args:
        tenant_id: Tenant UUID for isolation.
        content: The text content to remember.
        content_type: One of 'decision', 'preference', 'insight', 'constraint'.
        user_id: Optional user who created this memory.
        metadata: Optional metadata dict (topic, tags, etc.).
        source_message_id: Optional chat message that triggered this save.

    Returns:
        The created MemoryEmbedding record, or None on failure.
    """
    if not content or len(content.strip()) < 10:
        return None

    content = content[:MAX_CONTENT_LENGTH]

    # Generate embedding
    embedding = generate_embedding(content)
    embedding_json = json.dumps(embedding) if embedding else None

    memory = MemoryEmbedding(
        tenant_id=tenant_id,
        user_id=user_id,
        content=content,
        content_type=content_type,
        embedding=embedding_json,
        metadata_=metadata or {},
        source_message_id=source_message_id,
    )
    db.session.add(memory)
    db.session.flush()
    return memory


def search_memories(
    tenant_id: str,
    query: str,
    top_k: int = DEFAULT_TOP_K,
    content_type: Optional[str] = None,
) -> list[dict]:
    """Search for relevant memories using vector similarity.

    Falls back to keyword search if pgvector is not available
    or embeddings are not configured.

    Args:
        tenant_id: Tenant UUID for isolation.
        query: The search query text.
        top_k: Number of results to return.
        content_type: Optional filter by content type.

    Returns:
        List of {"content": str, "score": float, "metadata": dict, "id": str}.
    """
    # Try vector search first
    query_embedding = generate_embedding(query)
    if query_embedding:
        results = _vector_search(tenant_id, query_embedding, top_k, content_type)
        if results is not None:
            return results

    # Fall back to keyword search
    return _keyword_search(tenant_id, query, top_k, content_type)


def _vector_search(
    tenant_id: str,
    query_embedding: list[float],
    top_k: int,
    content_type: Optional[str],
) -> Optional[list[dict]]:
    """Perform pgvector cosine similarity search.

    Returns None if pgvector is not available (triggers keyword fallback).
    """
    try:
        embedding_str = "[{}]".format(",".join(str(x) for x in query_embedding))

        type_filter = ""
        params = {
            "tenant_id": tenant_id,
            "embedding": embedding_str,
            "top_k": top_k,
        }
        if content_type:
            type_filter = "AND content_type = :content_type"
            params["content_type"] = content_type

        sql = text(
            """
            SELECT id, content, content_type, metadata,
                   1 - (embedding <=> :embedding::vector) AS score
            FROM memory_embeddings
            WHERE tenant_id = :tenant_id
              AND embedding IS NOT NULL
              {type_filter}
            ORDER BY embedding <=> :embedding::vector
            LIMIT :top_k
        """.format(type_filter=type_filter)
        )

        rows = db.session.execute(sql, params).fetchall()
        return [
            {
                "id": str(row.id),
                "content": row.content,
                "content_type": row.content_type,
                "metadata": row.metadata or {},
                "score": round(float(row.score), 4) if row.score else 0.0,
            }
            for row in rows
        ]

    except Exception:
        # pgvector not available or query failed
        logger.debug("Vector search failed, falling back to keyword search")
        return None


def _keyword_search(
    tenant_id: str,
    query: str,
    top_k: int,
    content_type: Optional[str],
) -> list[dict]:
    """Fall back keyword search using ILIKE.

    Used when pgvector is not available or embeddings are not generated.
    """
    filters = [MemoryEmbedding.tenant_id == tenant_id]
    if content_type:
        filters.append(MemoryEmbedding.content_type == content_type)

    # Simple keyword matching
    keywords = query.lower().split()
    if keywords:
        # Match any keyword in content
        for kw in keywords[:5]:  # Limit to 5 keywords
            filters.append(MemoryEmbedding.content.ilike("%{}%".format(kw)))

    results = (
        MemoryEmbedding.query.filter(*filters)
        .order_by(MemoryEmbedding.created_at.desc())
        .limit(top_k)
        .all()
    )

    return [
        {
            "id": str(m.id),
            "content": m.content,
            "content_type": m.content_type,
            "metadata": m.metadata_ or {},
            "score": 0.5,  # Fixed score for keyword results
        }
        for m in results
    ]


def get_recent_memories(
    tenant_id: str,
    limit: int = 10,
    content_type: Optional[str] = None,
) -> list[dict]:
    """Get the most recent memories for a tenant (no search)."""
    query = MemoryEmbedding.query.filter_by(tenant_id=tenant_id)
    if content_type:
        query = query.filter_by(content_type=content_type)

    results = query.order_by(MemoryEmbedding.created_at.desc()).limit(limit).all()
    return [m.to_dict() for m in results]
