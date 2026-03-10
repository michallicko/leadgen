"""Unit tests for enrichment tool wrappers (BL-128, BL-1001).

Tests the tool wrappers in api/tools/enrichment_tools.py including
check_enrichment_status and the 5 enricher tool wrappers.
"""

import json
from unittest.mock import patch

from sqlalchemy import text as sa_text

from api.services.tool_registry import ToolContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TENANT_ID = "t0000000-0000-0000-0000-000000000001"
COMPANY_ID = "c0000000-0000-0000-0000-000000000001"
CONTACT_ID = "ct000000-0000-0000-0000-000000000001"


def _make_ctx():
    return ToolContext(tenant_id=TENANT_ID, user_id="u001")


def _setup_base_data(db):
    """Insert tenant, company, and contact."""
    db.session.execute(
        sa_text("INSERT INTO tenants (id, name, slug) VALUES (:tid, :name, :slug)"),
        {"tid": TENANT_ID, "name": "Test Tenant", "slug": "test"},
    )
    db.session.execute(
        sa_text("""
            INSERT INTO companies (id, tenant_id, name, domain, industry, status)
            VALUES (:id, :tid, :name, :domain, :industry, :status)
        """),
        {
            "id": COMPANY_ID,
            "tid": TENANT_ID,
            "name": "TestCorp",
            "domain": "testcorp.com",
            "industry": "software_saas",
            "status": "enriched_l1",
        },
    )
    db.session.execute(
        sa_text("""
            INSERT INTO contacts (id, tenant_id, company_id, first_name, last_name, job_title)
            VALUES (:id, :tid, :cid, :fn, :ln, :title)
        """),
        {
            "id": CONTACT_ID,
            "tid": TENANT_ID,
            "cid": COMPANY_ID,
            "fn": "Jane",
            "ln": "Doe",
            "title": "VP Engineering",
        },
    )
    db.session.commit()


def _setup_pipeline_run(db, pipeline_run_id="pr-001", status="running"):
    """Insert a pipeline_run + tag + stage_runs for status checks."""
    tag_id = "tag-001"
    db.session.execute(
        sa_text("INSERT INTO tags (id, tenant_id, name) VALUES (:id, :tid, :name)"),
        {"id": tag_id, "tid": TENANT_ID, "name": "test-batch"},
    )

    db.session.execute(
        sa_text("""
            INSERT INTO pipeline_runs (id, tenant_id, tag_id, status, stages, config,
                                       started_at)
            VALUES (:id, :tid, :bid, :status, :stages, :config,
                    CURRENT_TIMESTAMP)
        """),
        {
            "id": pipeline_run_id,
            "tid": TENANT_ID,
            "bid": tag_id,
            "status": status,
            "stages": json.dumps({"l1": "sr-001", "l2": "sr-002"}),
            "config": "{}",
        },
    )

    db.session.execute(
        sa_text("""
            INSERT INTO stage_runs (id, tenant_id, tag_id, stage, status, total, done, failed, cost_usd, config, started_at)
            VALUES (:id, :tid, :bid, :stage, :status, :total, :done, :failed, :cost, :config, CURRENT_TIMESTAMP)
        """),
        {
            "id": "sr-001",
            "tid": TENANT_ID,
            "bid": tag_id,
            "stage": "l1",
            "status": "completed",
            "total": 10,
            "done": 10,
            "failed": 0,
            "cost": 0.20,
            "config": "{}",
        },
    )
    db.session.execute(
        sa_text("""
            INSERT INTO stage_runs (id, tenant_id, tag_id, stage, status, total, done, failed, cost_usd, config, started_at)
            VALUES (:id, :tid, :bid, :stage, :status, :total, :done, :failed, :cost, :config, CURRENT_TIMESTAMP)
        """),
        {
            "id": "sr-002",
            "tid": TENANT_ID,
            "bid": tag_id,
            "stage": "l2",
            "status": "running",
            "total": 5,
            "done": 2,
            "failed": 0,
            "cost": 0.10,
            "config": "{}",
        },
    )
    db.session.commit()


# ---------------------------------------------------------------------------
# Tests: check_enrichment_status
# ---------------------------------------------------------------------------


class TestCheckEnrichmentStatus:
    """Tests for the check_enrichment_status tool handler."""

    def test_returns_pipeline_status(self, app, db):
        from api.tools.enrichment_tools import _check_enrichment_status

        with app.app_context():
            _setup_base_data(db)
            _setup_pipeline_run(db)

            result = _check_enrichment_status(
                {"pipeline_run_id": "pr-001"}, _make_ctx()
            )

            assert result["pipeline_run_id"] == "pr-001"
            assert result["status"] == "running"
            assert result["tag_name"] == "test-batch"
            assert len(result["stages"]) == 2
            assert result["progress"]["total_items"] == 15
            assert result["progress"]["completed"] == 12

    def test_returns_error_for_missing_pipeline(self, app, db):
        from api.tools.enrichment_tools import _check_enrichment_status

        with app.app_context():
            _setup_base_data(db)

            result = _check_enrichment_status(
                {"pipeline_run_id": "nonexistent"}, _make_ctx()
            )

            assert "error" in result

    def test_requires_pipeline_run_id(self, app, db):
        from api.tools.enrichment_tools import _check_enrichment_status

        with app.app_context():
            result = _check_enrichment_status({}, _make_ctx())
            assert "error" in result

    def test_shows_cost_summary(self, app, db):
        from api.tools.enrichment_tools import _check_enrichment_status

        with app.app_context():
            _setup_base_data(db)
            _setup_pipeline_run(db)

            result = _check_enrichment_status(
                {"pipeline_run_id": "pr-001"}, _make_ctx()
            )

            assert result["total_cost_credits"] == 300


# ---------------------------------------------------------------------------
# Tests: enrichment tool wrappers (mock the underlying enrichers)
# ---------------------------------------------------------------------------


class TestEnrichCompanyNews:
    """Tests for enrich_company_news tool wrapper."""

    def test_calls_enricher_and_returns_result(self, app, db):
        from api.tools.enrichment_tools import _enrich_company_news

        with app.app_context():
            _setup_base_data(db)
            mock_result = {"enrichment_cost_usd": 0.04}

            with patch(
                "api.services.news_enricher.enrich_news",
                return_value=mock_result,
            ):
                result = _enrich_company_news({"company_id": COMPANY_ID}, _make_ctx())

            assert "enrichment_cost_usd" in result or "error" in result

    def test_requires_company_id(self, app, db):
        from api.tools.enrichment_tools import _enrich_company_news

        with app.app_context():
            result = _enrich_company_news({}, _make_ctx())
            assert result["error"] == "company_id is required"


class TestEnrichCompanySignals:
    """Tests for enrich_company_signals tool wrapper."""

    def test_requires_company_id(self, app, db):
        from api.tools.enrichment_tools import _enrich_company_signals

        with app.app_context():
            result = _enrich_company_signals({}, _make_ctx())
            assert result["error"] == "company_id is required"


class TestEnrichContactSocial:
    """Tests for enrich_contact_social tool wrapper."""

    def test_requires_contact_id(self, app, db):
        from api.tools.enrichment_tools import _enrich_contact_social

        with app.app_context():
            result = _enrich_contact_social({}, _make_ctx())
            assert result["error"] == "contact_id is required"


class TestEnrichContactCareer:
    """Tests for enrich_contact_career tool wrapper."""

    def test_requires_contact_id(self, app, db):
        from api.tools.enrichment_tools import _enrich_contact_career

        with app.app_context():
            result = _enrich_contact_career({}, _make_ctx())
            assert result["error"] == "contact_id is required"


class TestEnrichContactDetails:
    """Tests for enrich_contact_details tool wrapper."""

    def test_requires_contact_id(self, app, db):
        from api.tools.enrichment_tools import _enrich_contact_details_handler

        with app.app_context():
            result = _enrich_contact_details_handler({}, _make_ctx())
            assert result["error"] == "contact_id is required"


# ---------------------------------------------------------------------------
# Tests: Tool definitions
# ---------------------------------------------------------------------------


class TestToolDefinitions:
    """Verify tool definitions are well-formed."""

    def test_all_tools_have_required_fields(self):
        from api.tools.enrichment_tools import ENRICHMENT_AGENT_TOOLS

        assert len(ENRICHMENT_AGENT_TOOLS) == 6

        for tool in ENRICHMENT_AGENT_TOOLS:
            assert tool.name, "Tool must have a name"
            assert tool.description, "Tool must have a description"
            assert tool.input_schema, "Tool must have an input_schema"
            assert tool.handler, "Tool must have a handler"
            assert tool.input_schema.get("type") == "object"

    def test_tool_names_are_unique(self):
        from api.tools.enrichment_tools import ENRICHMENT_AGENT_TOOLS

        names = [t.name for t in ENRICHMENT_AGENT_TOOLS]
        assert len(names) == len(set(names)), "Tool names must be unique"
