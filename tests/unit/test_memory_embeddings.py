"""Tests for RAG long-term memory embeddings service."""

from unittest.mock import patch

import pytest


class TestGenerateEmbedding:
    def test_no_api_key_returns_none(self):
        from api.services.memory.embeddings import generate_embedding

        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            result = generate_embedding("test content")
            assert result is None


class TestSaveMemory:
    def test_empty_content_returns_none(self, app, db):
        from api.services.memory.embeddings import save_memory

        result = save_memory(tenant_id="test-tenant", content="")
        assert result is None

    def test_short_content_returns_none(self, app, db):
        from api.services.memory.embeddings import save_memory

        result = save_memory(tenant_id="test-tenant", content="hi")
        assert result is None

    def test_saves_memory_without_embedding(self, app, db, seed_tenant):
        from api.services.memory.embeddings import save_memory

        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            result = save_memory(
                tenant_id=seed_tenant,
                content="We decided to focus on SaaS companies in DACH region.",
                content_type="decision",
                metadata={"topic": "ICP"},
            )
            assert result is not None
            assert result.content_type == "decision"
            assert (
                result.content
                == "We decided to focus on SaaS companies in DACH region."
            )


class TestKeywordSearch:
    def test_keyword_search_finds_match(self, app, db, seed_tenant):
        from api.services.memory.embeddings import save_memory, _keyword_search

        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            save_memory(
                tenant_id=seed_tenant,
                content="Target SaaS companies with 50-200 employees in Germany.",
                content_type="decision",
            )
            db.session.commit()

            results = _keyword_search(
                tenant_id=seed_tenant,
                query="SaaS Germany",
                top_k=5,
                content_type=None,
            )
            assert len(results) > 0
            assert "SaaS" in results[0]["content"]

    def test_keyword_search_with_type_filter(self, app, db, seed_tenant):
        from api.services.memory.embeddings import save_memory, _keyword_search

        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            save_memory(
                tenant_id=seed_tenant,
                content="Always use professional tone in outreach.",
                content_type="preference",
            )
            save_memory(
                tenant_id=seed_tenant,
                content="Budget is 5000 EUR per month.",
                content_type="constraint",
            )
            db.session.commit()

            results = _keyword_search(
                tenant_id=seed_tenant,
                query="tone",
                top_k=5,
                content_type="preference",
            )
            assert len(results) == 1
            assert "tone" in results[0]["content"]

    def test_keyword_search_empty_results(self, app, db, seed_tenant):
        from api.services.memory.embeddings import _keyword_search

        results = _keyword_search(
            tenant_id=seed_tenant,
            query="nonexistent content xyz123",
            top_k=5,
            content_type=None,
        )
        assert len(results) == 0


class TestSearchMemories:
    def test_falls_back_to_keyword_without_api_key(self, app, db, seed_tenant):
        from api.services.memory.embeddings import save_memory, search_memories

        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            save_memory(
                tenant_id=seed_tenant,
                content="Our ICP is mid-market B2B SaaS in Europe.",
                content_type="decision",
            )
            db.session.commit()

            results = search_memories(
                tenant_id=seed_tenant,
                query="ICP SaaS",
            )
            assert len(results) > 0


# Fixture for creating a test tenant
@pytest.fixture
def seed_tenant(db):
    """Create a test tenant and return its ID."""
    import uuid
    from api.models import Tenant

    tenant_id = str(uuid.uuid4())
    tenant = Tenant(
        id=tenant_id,
        name="Test Tenant",
        slug="test-tenant",
    )
    db.session.add(tenant)
    db.session.flush()
    return tenant_id
