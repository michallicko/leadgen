"""Tests for memory tool handlers."""

import uuid
from unittest.mock import patch

import pytest

from api.services.tool_registry import ToolContext


class TestSearchMemoryTool:
    def test_empty_query_returns_error(self, app, db):
        from api.tools.memory_tools import search_memory

        ctx = ToolContext(tenant_id="test-tenant")
        result = search_memory({"query": ""}, ctx)
        assert "error" in result

    def test_invalid_content_type(self, app, db):
        from api.tools.memory_tools import search_memory

        ctx = ToolContext(tenant_id="test-tenant")
        result = search_memory({"query": "test", "content_type": "invalid"}, ctx)
        assert "error" in result

    def test_no_results(self, app, db, seed_tenant):
        from api.tools.memory_tools import search_memory

        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            ctx = ToolContext(tenant_id=seed_tenant)
            result = search_memory({"query": "nonexistent xyz123"}, ctx)
            assert result["results"] == []


class TestSaveInsightTool:
    def test_empty_content_returns_error(self, app, db):
        from api.tools.memory_tools import save_insight

        ctx = ToolContext(tenant_id="test-tenant")
        result = save_insight({"content": ""}, ctx)
        assert "error" in result

    def test_short_content_returns_error(self, app, db):
        from api.tools.memory_tools import save_insight

        ctx = ToolContext(tenant_id="test-tenant")
        result = save_insight({"content": "hi"}, ctx)
        assert "error" in result

    def test_invalid_content_type(self, app, db):
        from api.tools.memory_tools import save_insight

        ctx = ToolContext(tenant_id="test-tenant")
        result = save_insight(
            {"content": "some long content here", "content_type": "invalid"}, ctx
        )
        assert "error" in result

    def test_successful_save(self, app, db, seed_tenant):
        from api.tools.memory_tools import save_insight

        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            ctx = ToolContext(tenant_id=seed_tenant)
            result = save_insight(
                {
                    "content": "We decided to target B2B SaaS companies in DACH.",
                    "content_type": "decision",
                },
                ctx,
            )
            assert "id" in result
            assert "message" in result


class TestMultimodalTools:
    def test_analyze_document_no_file_id(self, app, db):
        from api.tools.multimodal_tools import analyze_document

        ctx = ToolContext(tenant_id="test-tenant")
        result = analyze_document({"file_id": ""}, ctx)
        assert "error" in result

    def test_analyze_document_invalid_detail(self, app, db):
        from api.tools.multimodal_tools import analyze_document

        ctx = ToolContext(tenant_id="test-tenant")
        result = analyze_document(
            {"file_id": "some-id", "detail_level": "invalid"}, ctx
        )
        assert "error" in result

    def test_analyze_image_no_file_id(self, app, db):
        from api.tools.multimodal_tools import analyze_image

        ctx = ToolContext(tenant_id="test-tenant")
        result = analyze_image({"file_id": ""}, ctx)
        assert "error" in result

    def test_extract_data_no_query(self, app, db):
        from api.tools.multimodal_tools import extract_data

        ctx = ToolContext(tenant_id="test-tenant")
        result = extract_data({"file_id": "some-id", "query": ""}, ctx)
        assert "error" in result


@pytest.fixture
def seed_tenant(db):
    """Create a test tenant and return its ID."""
    tenant_id = str(uuid.uuid4())
    from api.models import Tenant

    tenant = Tenant(id=tenant_id, name="Test Tenant", slug="test-mem-tools")
    db.session.add(tenant)
    db.session.flush()
    return tenant_id
