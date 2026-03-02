"""Tests for enrichment trigger tools (BL-146).

Tests cover:
- estimate_enrichment_cost returns cost breakdown for a valid tag
- estimate_enrichment_cost lists tags when tag_name is empty
- estimate_enrichment_cost returns error for unknown tag
- start_enrichment requires confirmed=true
- start_enrichment returns error for unknown tag
"""

import uuid

import pytest

from api.models import db
from api.services.enrichment_trigger_tools import (
    ENRICHMENT_TRIGGER_TOOLS,
    estimate_enrichment_cost,
    start_enrichment,
)
from api.services.tool_registry import ToolContext


@pytest.fixture
def ctx(seed_tenant):
    """Create a ToolContext with the seeded tenant."""
    return ToolContext(tenant_id=seed_tenant)


@pytest.fixture
def tag_with_companies(seed_tenant):
    """Create a tag with some companies for testing."""
    from sqlalchemy import text

    tag_id = str(uuid.uuid4())
    db.session.execute(
        text("INSERT INTO tags (id, tenant_id, name) VALUES (:id, :t, :n)"),
        {"id": tag_id, "t": str(seed_tenant), "n": "test-batch"},
    )

    # Create a few companies in this tag
    for i in range(3):
        company_id = str(uuid.uuid4())
        db.session.execute(
            text("""
                INSERT INTO companies (id, tenant_id, tag_id, name, domain, status)
                VALUES (:id, :t, :b, :n, :d, 'new')
            """),
            {
                "id": company_id,
                "t": str(seed_tenant),
                "b": tag_id,
                "n": "Company {}".format(i),
                "d": "company{}.com".format(i),
            },
        )
    db.session.commit()
    return tag_id


class TestEstimateEnrichmentCost:
    """Tests for estimate_enrichment_cost tool."""

    def test_lists_tags_when_no_tag_name(self, app, ctx, tag_with_companies):
        """When tag_name is empty, should list available tags."""
        result = estimate_enrichment_cost({}, ctx)
        assert "available_tags" in result
        assert any(t["name"] == "test-batch" for t in result["available_tags"])

    def test_returns_error_for_unknown_tag(self, app, ctx, tag_with_companies):
        """Unknown tag should return error with available tags."""
        result = estimate_enrichment_cost({"tag_name": "nonexistent"}, ctx)
        assert "error" in result
        assert "nonexistent" in result["error"]
        assert "available_tags" in result

    def test_returns_cost_breakdown(self, app, ctx, tag_with_companies):
        """Valid tag should return per-stage cost breakdown."""
        result = estimate_enrichment_cost({"tag_name": "test-batch"}, ctx)
        assert "error" not in result
        assert "stages" in result
        assert "total_cost_usd" in result
        assert "total_cost_credits" in result
        assert "total_eligible" in result
        assert "summary" in result

        # Check stage structure
        for stage in result["stages"]:
            assert "stage" in stage
            assert "eligible_count" in stage
            assert "cost_per_item_usd" in stage
            assert "total_cost_credits" in stage

    def test_custom_stages(self, app, ctx, tag_with_companies):
        """Should accept custom stage list."""
        result = estimate_enrichment_cost(
            {"tag_name": "test-batch", "stages": ["l1"]}, ctx
        )
        assert "error" not in result
        assert len(result["stages"]) == 1
        assert result["stages"][0]["stage"] == "l1"


class TestStartEnrichment:
    """Tests for start_enrichment tool."""

    def test_requires_confirmation(self, app, ctx, tag_with_companies):
        """Should reject if confirmed is not true."""
        result = start_enrichment(
            {"tag_name": "test-batch", "confirmed": False}, ctx
        )
        assert "error" in result
        assert "confirmation" in result["error"].lower()

    def test_requires_tag_name(self, app, ctx):
        """Should reject if tag_name is missing."""
        result = start_enrichment({"confirmed": True}, ctx)
        assert "error" in result
        assert "tag_name" in result["error"]

    def test_returns_error_for_unknown_tag(self, app, ctx):
        """Unknown tag should return error."""
        result = start_enrichment(
            {"tag_name": "nonexistent", "confirmed": True}, ctx
        )
        assert "error" in result
        assert "nonexistent" in result["error"]


class TestToolRegistration:
    """Test that tools are properly defined for registry."""

    def test_tools_have_correct_names(self):
        """Tools should have expected names."""
        names = {t.name for t in ENRICHMENT_TRIGGER_TOOLS}
        assert "estimate_enrichment_cost" in names
        assert "start_enrichment" in names

    def test_tools_have_schemas(self):
        """Each tool should have a valid input schema."""
        for tool in ENRICHMENT_TRIGGER_TOOLS:
            assert tool.input_schema is not None
            assert tool.input_schema.get("type") == "object"
            assert "properties" in tool.input_schema
