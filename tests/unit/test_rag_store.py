"""Tests for RAG long-term memory store (BL-262)."""

import json

import pytest

from api.services.memory.rag_store import (
    MAX_MEMORY_TOKENS,
    MemoryStore,
    extract_keywords,
    _parse_keywords,
)


class TestExtractKeywords:
    def test_removes_stop_words(self):
        kws = extract_keywords("the quick brown fox is very fast")
        assert "the" not in kws
        assert "very" not in kws
        assert "quick" in kws
        assert "brown" in kws
        assert "fox" in kws
        assert "fast" in kws

    def test_removes_short_words(self):
        kws = extract_keywords("AI is a big tool")
        # "AI" and "is" and "a" are 2 chars or less / stop words
        assert "big" in kws
        assert "tool" in kws

    def test_deduplicates(self):
        kws = extract_keywords("target target target companies")
        assert kws.count("target") == 1

    def test_lowercase(self):
        kws = extract_keywords("Enterprise SaaS Companies")
        assert all(kw == kw.lower() for kw in kws)

    def test_empty_input(self):
        assert extract_keywords("") == []
        assert extract_keywords("   ") == []


class TestParseKeywords:
    def test_list_input(self):
        assert _parse_keywords(["a", "b"]) == ["a", "b"]

    def test_json_string(self):
        assert _parse_keywords('["foo", "bar"]') == ["foo", "bar"]

    def test_pg_array_literal(self):
        assert _parse_keywords("{foo,bar,baz}") == ["foo", "bar", "baz"]

    def test_none(self):
        assert _parse_keywords(None) == []

    def test_invalid_string(self):
        assert _parse_keywords("not json") == []


class TestMemoryStore:
    @pytest.fixture
    def store(self):
        return MemoryStore()

    @pytest.fixture
    def tenant_id(self):
        return "11111111-1111-1111-1111-111111111111"

    def test_store_and_retrieve(self, app, db, store, tenant_id):
        """Store a fact and retrieve it by keyword."""
        # Create tenant first
        from sqlalchemy import text as sa_text

        with app.app_context():
            db.session.execute(
                sa_text(
                    "INSERT INTO tenants (id, name, slug) "
                    "VALUES (:id, 'test', 'test')"
                ),
                {"id": tenant_id},
            )
            db.session.commit()

            # We need the memory_facts table — create it manually for SQLite
            db.session.execute(
                sa_text(
                    "CREATE TABLE IF NOT EXISTS memory_facts ("
                    "id VARCHAR(36) PRIMARY KEY, "
                    "tenant_id VARCHAR(36) NOT NULL, "
                    "playbook_id VARCHAR(36), "
                    "source_message_id VARCHAR(36), "
                    "chunk_text TEXT NOT NULL, "
                    "chunk_type VARCHAR(20) NOT NULL DEFAULT 'fact', "
                    "keywords TEXT DEFAULT '[]', "
                    "session_id VARCHAR(36), "
                    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                    ")"
                )
            )
            db.session.commit()

            fact_id = store.store_fact(
                tenant_id=tenant_id,
                text="We target enterprise SaaS companies with 500+ employees",
                chunk_type="decision",
            )
            assert fact_id is not None

            results = store.retrieve(tenant_id, "enterprise SaaS targeting")
            assert len(results) >= 1
            assert "enterprise" in results[0]["text"].lower()

    def test_tenant_isolation(self, app, db, store, tenant_id):
        """Tenant A's facts should not be visible to tenant B."""
        tenant_b = "22222222-2222-2222-2222-222222222222"

        with app.app_context():
            from sqlalchemy import text as sa_text

            for tid, name in [(tenant_id, "A"), (tenant_b, "B")]:
                db.session.execute(
                    sa_text(
                        "INSERT INTO tenants (id, name, slug) "
                        "VALUES (:id, :name, :slug)"
                    ),
                    {"id": tid, "name": name, "slug": name.lower()},
                )

            db.session.execute(
                sa_text(
                    "CREATE TABLE IF NOT EXISTS memory_facts ("
                    "id VARCHAR(36) PRIMARY KEY, "
                    "tenant_id VARCHAR(36) NOT NULL, "
                    "playbook_id VARCHAR(36), "
                    "source_message_id VARCHAR(36), "
                    "chunk_text TEXT NOT NULL, "
                    "chunk_type VARCHAR(20) NOT NULL DEFAULT 'fact', "
                    "keywords TEXT DEFAULT '[]', "
                    "session_id VARCHAR(36), "
                    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                    ")"
                )
            )
            db.session.commit()

            store.store_fact(
                tenant_id=tenant_id,
                text="Tenant A targets fintech companies",
                chunk_type="fact",
            )

            # Tenant B should find nothing
            results = store.retrieve(tenant_b, "fintech companies")
            assert len(results) == 0

    def test_format_for_injection(self, store):
        """Formatted output should include fact type prefixes."""
        facts = [
            {"text": "We target enterprise SaaS", "type": "decision", "score": 0.9},
            {"text": "User prefers consultative tone", "type": "preference", "score": 0.8},
        ]
        output = store.format_for_injection(facts)
        assert "Decision:" in output
        assert "Preference:" in output
        assert "enterprise SaaS" in output

    def test_format_empty(self, store):
        assert store.format_for_injection([]) == ""

    def test_store_empty_text_returns_none(self, store):
        assert store.store_fact("tid", "") is None
        assert store.store_fact("tid", "   ") is None
