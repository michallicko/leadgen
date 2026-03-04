"""Tests for company research tool (BL-241).

Tests cover:
- Returns cached enrichment when company is already enriched
- Runs research pipeline when no enrichment exists
- force=True bypasses cache and re-runs research
- Missing company returns error
- Missing domain returns error
- Research pipeline failure returns error with details
- Tool definition is registered correctly
"""

from unittest.mock import patch

import pytest

from api.services.company_research_tool import (
    COMPANY_RESEARCH_TOOLS,
    ENRICHED_STATUSES,
    research_own_company,
)
from api.services.tool_registry import ToolContext, clear_registry, register_tool


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _register_tools():
    """Register company research tools for each test."""
    clear_registry()
    for tool in COMPANY_RESEARCH_TOOLS:
        try:
            register_tool(tool)
        except ValueError:
            pass
    yield
    clear_registry()


@pytest.fixture
def ctx(seed_tenant):
    """ToolContext for the seed tenant."""
    return ToolContext(tenant_id=str(seed_tenant.id), user_id="user-123")


@pytest.fixture
def fake_company_row():
    """Fake DB row for a company with is_self=True."""
    return (
        "company-uuid-123",  # id
        "example.com",  # domain
        "Example Corp",  # name
        "new",  # status (not enriched)
    )


@pytest.fixture
def fake_enriched_company_row():
    """Fake DB row for an already-enriched company."""
    return (
        "company-uuid-123",
        "example.com",
        "Example Corp",
        "enriched_l2",
    )


FAKE_ENRICHMENT_DATA = {
    "company": {
        "name": "Example Corp",
        "domain": "example.com",
        "industry": "Software",
        "industry_category": "SaaS",
        "summary": "A software company.",
        "company_size": "50-100",
        "revenue_range": "$1M-$5M",
        "hq_country": "US",
        "hq_city": "New York",
    },
    "company_overview": "Example Corp makes SaaS tools.",
    "ai_opportunities": "Automate lead scoring.",
    "pain_hypothesis": "Manual data entry wastes time.",
    "quick_wins": "Integrate with CRM",
    "pitch_framing": "Save 10 hours per week.",
    "competitors": "Competitor A, Competitor B",
}


# ---------------------------------------------------------------------------
# Tests: company lookup failures
# ---------------------------------------------------------------------------


class TestCompanyLookup:
    def test_no_company_returns_error(self, ctx):
        """When no is_self company exists, return a helpful error."""
        with patch(
            "api.services.company_research_tool.db"
        ) as mock_db:
            mock_db.session.execute.return_value.fetchone.return_value = None

            result = research_own_company({}, ctx)

        assert "error" in result
        assert "onboarding" in result["error"].lower() or "company" in result["error"].lower()

    def test_missing_domain_returns_error(self, ctx):
        """When company has no domain, return a helpful error."""
        row_no_domain = ("company-uuid-123", None, "Example Corp", "new")
        with patch(
            "api.services.company_research_tool.db"
        ) as mock_db:
            mock_db.session.execute.return_value.fetchone.return_value = row_no_domain

            result = research_own_company({}, ctx)

        assert "error" in result
        assert "domain" in result["error"].lower()


# ---------------------------------------------------------------------------
# Tests: cached enrichment
# ---------------------------------------------------------------------------


class TestCachedEnrichment:
    def test_returns_cached_when_enriched(self, ctx, fake_enriched_company_row):
        """When status is enriched_l2 and data exists, return cached results."""
        with patch(
            "api.services.company_research_tool.db"
        ) as mock_db, patch(
            "api.services.company_research_tool._load_existing_enrichment",
            return_value=FAKE_ENRICHMENT_DATA.copy(),
        ):
            mock_db.session.execute.return_value.fetchone.return_value = (
                fake_enriched_company_row
            )

            result = research_own_company({}, ctx)

        assert result.get("cached") is True
        assert "summary" in result
        assert "cached" in result["summary"].lower() or "previously" in result["summary"].lower()
        assert result.get("company") == FAKE_ENRICHMENT_DATA["company"]

    def test_force_bypasses_cache(self, ctx, fake_enriched_company_row):
        """force=True runs research even when already enriched."""
        fake_research_result = {
            "success": True,
            "company_name": "Example Corp",
            "enrichment_cost_usd": 0.12,
            "steps_completed": ["website_fetch", "web_search", "ai_synthesis", "database_save"],
        }

        with patch(
            "api.services.company_research_tool.db"
        ) as mock_db, patch(
            "api.services.company_research_tool._load_existing_enrichment",
            return_value=FAKE_ENRICHMENT_DATA.copy(),
        ), patch(
            "api.services.research_service.ResearchService"
        ) as MockService:
            mock_db.session.execute.return_value.fetchone.return_value = (
                fake_enriched_company_row
            )
            MockService.return_value.research_company.return_value = fake_research_result

            result = research_own_company({"force": True}, ctx)

        assert result.get("cached") is False
        MockService.return_value.research_company.assert_called_once()

    def test_all_enriched_statuses_use_cache(self, ctx):
        """All statuses in ENRICHED_STATUSES return cached data."""
        for status in ENRICHED_STATUSES:
            row = ("company-uuid-123", "example.com", "Example Corp", status)
            with patch(
                "api.services.company_research_tool.db"
            ) as mock_db, patch(
                "api.services.company_research_tool._load_existing_enrichment",
                return_value=FAKE_ENRICHMENT_DATA.copy(),
            ):
                mock_db.session.execute.return_value.fetchone.return_value = row
                result = research_own_company({}, ctx)

            assert result.get("cached") is True, f"Status {status!r} should return cached"


# ---------------------------------------------------------------------------
# Tests: research pipeline execution
# ---------------------------------------------------------------------------


class TestResearchPipeline:
    def test_runs_pipeline_for_unenriched_company(self, ctx, fake_company_row):
        """When company has no enrichment, run the research pipeline."""
        fake_research_result = {
            "success": True,
            "company_name": "Example Corp",
            "enrichment_cost_usd": 0.15,
            "steps_completed": ["website_fetch", "web_search", "ai_synthesis", "database_save"],
        }

        with patch(
            "api.services.company_research_tool.db"
        ) as mock_db, patch(
            "api.services.company_research_tool._load_existing_enrichment",
            return_value=FAKE_ENRICHMENT_DATA.copy(),
        ), patch(
            "api.services.research_service.ResearchService"
        ) as MockService:
            mock_db.session.execute.return_value.fetchone.return_value = fake_company_row
            MockService.return_value.research_company.return_value = fake_research_result

            result = research_own_company({}, ctx)

        assert result.get("cached") is False
        assert "steps_completed" in result
        assert result["cost_usd"] == 0.15
        # Verify on_progress=None was passed (no callback)
        _, kwargs = MockService.return_value.research_company.call_args
        assert kwargs.get("on_progress") is None

    def test_pipeline_failure_returns_error(self, ctx, fake_company_row):
        """When research pipeline fails, return error dict."""
        fake_failure_result = {
            "success": False,
            "error": "Perplexity API returned 429",
            "steps_completed": ["website_fetch"],
        }

        with patch(
            "api.services.company_research_tool.db"
        ) as mock_db, patch(
            "api.services.research_service.ResearchService"
        ) as MockService:
            mock_db.session.execute.return_value.fetchone.return_value = fake_company_row
            MockService.return_value.research_company.return_value = fake_failure_result

            result = research_own_company({}, ctx)

        assert "error" in result
        assert "429" in result["error"]
        assert result["domain"] == "example.com"

    def test_pipeline_exception_returns_error(self, ctx, fake_company_row):
        """When research service raises an exception, return error dict."""
        with patch(
            "api.services.company_research_tool.db"
        ) as mock_db, patch(
            "api.services.research_service.ResearchService"
        ) as MockService:
            mock_db.session.execute.return_value.fetchone.return_value = fake_company_row
            MockService.return_value.research_company.side_effect = RuntimeError(
                "Network unreachable"
            )

            result = research_own_company({}, ctx)

        assert "error" in result
        assert "Network unreachable" in result["error"]


# ---------------------------------------------------------------------------
# Tests: tool definition
# ---------------------------------------------------------------------------


class TestToolDefinition:
    def test_tool_list_has_one_item(self):
        assert len(COMPANY_RESEARCH_TOOLS) == 1

    def test_tool_name(self):
        tool = COMPANY_RESEARCH_TOOLS[0]
        assert tool.name == "research_own_company"

    def test_tool_handler(self):
        tool = COMPANY_RESEARCH_TOOLS[0]
        assert tool.handler is research_own_company

    def test_tool_has_force_param(self):
        tool = COMPANY_RESEARCH_TOOLS[0]
        props = tool.input_schema.get("properties", {})
        assert "force" in props
        assert props["force"]["type"] == "boolean"

    def test_force_not_required(self):
        tool = COMPANY_RESEARCH_TOOLS[0]
        required = tool.input_schema.get("required", [])
        assert "force" not in required
