"""Unit tests for Strategic Signals enrichment."""

import json
from unittest.mock import MagicMock, patch

from sqlalchemy import text as sa_text


TENANT_ID = "t0000000-0000-0000-0000-000000000001"
COMPANY_ID = "c0000000-0000-0000-0000-000000000001"


def _make_signals_response():
    """Sample Perplexity response for signals enrichment."""
    return {
        "digital_initiatives": "Migrating ERP to cloud, launched internal AI chatbot",
        "leadership_changes": "New CTO hired from Google in Q1 2026",
        "hiring_signals": "Actively hiring — 45 open roles, 60% growth YoY",
        "ai_hiring": "3 ML engineer and 2 data scientist positions open",
        "tech_partnerships": "Announced partnership with Databricks for data platform",
        "competitor_ai_moves": "Main competitor launched AI copilot product in Feb 2026",
        "ai_adoption_level": "piloting",
        "news_confidence": "high",
        "growth_indicators": "Series C ($50M) closed in Jan 2026, expanding to APAC",
        "job_posting_count": 45,
        "hiring_departments": ["Engineering", "Sales", "Product"],
        "workflow_ai_evidence": "Using GitHub Copilot and internal LLM-based ticket routing",
        "regulatory_pressure": "GDPR compliance driving data platform modernization",
        "employee_sentiment": "4.2/5 Glassdoor, positive culture mentions",
        "tech_stack_categories": "cloud-native, AWS, Kubernetes, Python, React",
        "digital_maturity_score": "3-established",
        "it_spend_indicators": "IT budget growing ~20% YoY per job postings",
    }


def _seed_company(db):
    """Insert a test company."""
    db.session.execute(
        sa_text("""
            INSERT INTO companies (id, tenant_id, name, domain, industry, hq_country)
            VALUES (:id, :tid, :name, :domain, :industry, :country)
        """),
        {
            "id": COMPANY_ID,
            "tid": TENANT_ID,
            "name": "Acme Corp",
            "domain": "acme.com",
            "industry": "software_saas",
            "country": "US",
        },
    )
    db.session.commit()


class TestEnrichSignals:
    """Tests for enrich_signals() with mocked Perplexity."""

    @patch("api.services.signals_enricher.log_llm_usage", None)
    @patch("api.services.signals_enricher.PerplexityClient")
    def test_successful_enrichment(self, MockClient, app, db):
        """Successful signals enrichment writes to DB and returns cost."""
        _seed_company(db)

        mock_response = MagicMock()
        mock_response.content = json.dumps(_make_signals_response())
        mock_response.input_tokens = 500
        mock_response.output_tokens = 400
        mock_response.cost_usd = 0.0009
        MockClient.return_value.query.return_value = mock_response

        with app.app_context():
            app.config["PERPLEXITY_API_KEY"] = "test-key"
            from api.services.signals_enricher import enrich_signals

            result = enrich_signals(COMPANY_ID, TENANT_ID)

        assert "enrichment_cost_usd" in result
        assert result["enrichment_cost_usd"] == 0.0009
        assert "error" not in result

        # Verify DB write
        row = db.session.execute(
            sa_text("SELECT * FROM company_enrichment_signals WHERE company_id = :id"),
            {"id": COMPANY_ID},
        ).fetchone()
        assert row is not None

    @patch("api.services.signals_enricher.log_llm_usage", None)
    @patch("api.services.signals_enricher.PerplexityClient")
    def test_company_not_found(self, MockClient, app, db):
        """Returns error when company doesn't exist."""
        with app.app_context():
            app.config["PERPLEXITY_API_KEY"] = "test-key"
            from api.services.signals_enricher import enrich_signals

            result = enrich_signals("nonexistent-id", TENANT_ID)

        assert result["enrichment_cost_usd"] == 0
        assert result["error"] == "company_not_found"
        MockClient.return_value.query.assert_not_called()

    @patch("api.services.signals_enricher.log_llm_usage", None)
    @patch("api.services.signals_enricher.PerplexityClient")
    def test_api_error_handled(self, MockClient, app, db):
        """API errors return gracefully without crashing."""
        _seed_company(db)

        MockClient.return_value.query.side_effect = Exception("API timeout")

        with app.app_context():
            app.config["PERPLEXITY_API_KEY"] = "test-key"
            from api.services.signals_enricher import enrich_signals

            result = enrich_signals(COMPANY_ID, TENANT_ID)

        assert result["enrichment_cost_usd"] == 0
        assert "api_error" in result["error"]

    @patch("api.services.signals_enricher.log_llm_usage", None)
    @patch("api.services.signals_enricher.PerplexityClient")
    def test_parse_error_handled(self, MockClient, app, db):
        """Unparseable response returns error."""
        _seed_company(db)

        mock_response = MagicMock()
        mock_response.content = "This is not JSON at all"
        mock_response.input_tokens = 100
        mock_response.output_tokens = 50
        mock_response.cost_usd = 0.0001
        MockClient.return_value.query.return_value = mock_response

        with app.app_context():
            app.config["PERPLEXITY_API_KEY"] = "test-key"
            from api.services.signals_enricher import enrich_signals

            result = enrich_signals(COMPANY_ID, TENANT_ID)

        assert result["enrichment_cost_usd"] == 0
        assert result["error"] == "parse_error"

    @patch("api.services.signals_enricher.log_llm_usage", None)
    @patch("api.services.signals_enricher.PerplexityClient")
    def test_markdown_fenced_json(self, MockClient, app, db):
        """JSON wrapped in markdown fences is parsed correctly."""
        _seed_company(db)

        fenced = "```json\n" + json.dumps(_make_signals_response()) + "\n```"
        mock_response = MagicMock()
        mock_response.content = fenced
        mock_response.input_tokens = 500
        mock_response.output_tokens = 400
        mock_response.cost_usd = 0.0009
        MockClient.return_value.query.return_value = mock_response

        with app.app_context():
            app.config["PERPLEXITY_API_KEY"] = "test-key"
            from api.services.signals_enricher import enrich_signals

            result = enrich_signals(COMPANY_ID, TENANT_ID)

        assert "error" not in result
        assert result["enrichment_cost_usd"] == 0.0009

    @patch("api.services.signals_enricher.log_llm_usage", None)
    @patch("api.services.signals_enricher.PerplexityClient")
    def test_null_fields_handled(self, MockClient, app, db):
        """Response with null fields is stored without crash."""
        _seed_company(db)

        sparse = {
            "digital_initiatives": None,
            "leadership_changes": None,
            "ai_adoption_level": "none",
            "news_confidence": "low",
        }
        mock_response = MagicMock()
        mock_response.content = json.dumps(sparse)
        mock_response.input_tokens = 200
        mock_response.output_tokens = 100
        mock_response.cost_usd = 0.0003
        MockClient.return_value.query.return_value = mock_response

        with app.app_context():
            app.config["PERPLEXITY_API_KEY"] = "test-key"
            from api.services.signals_enricher import enrich_signals

            result = enrich_signals(COMPANY_ID, TENANT_ID)

        assert "error" not in result

        row = db.session.execute(
            sa_text(
                "SELECT ai_adoption_level FROM company_enrichment_signals WHERE company_id = :id"
            ),
            {"id": COMPANY_ID},
        ).fetchone()
        assert row is not None
        assert row[0] == "none"

    @patch("api.services.signals_enricher.log_llm_usage", None)
    @patch("api.services.signals_enricher.PerplexityClient")
    def test_upsert_overwrites_existing(self, MockClient, app, db):
        """Second enrichment updates existing row."""
        _seed_company(db)

        def make_response(level):
            data = _make_signals_response()
            data["ai_adoption_level"] = level
            mock = MagicMock()
            mock.content = json.dumps(data)
            mock.input_tokens = 500
            mock.output_tokens = 400
            mock.cost_usd = 0.0009
            return mock

        with app.app_context():
            app.config["PERPLEXITY_API_KEY"] = "test-key"
            from api.services.signals_enricher import enrich_signals

            MockClient.return_value.query.return_value = make_response("exploring")
            enrich_signals(COMPANY_ID, TENANT_ID)

            MockClient.return_value.query.return_value = make_response("scaling")
            enrich_signals(COMPANY_ID, TENANT_ID)

        row = db.session.execute(
            sa_text(
                "SELECT ai_adoption_level FROM company_enrichment_signals WHERE company_id = :id"
            ),
            {"id": COMPANY_ID},
        ).fetchone()
        assert row[0] == "scaling"


class TestHelpers:
    """Tests for helper functions."""

    def test_safe_int_valid(self):
        from api.services.signals_enricher import _safe_int

        assert _safe_int(42) == 42
        assert _safe_int("15") == 15

    def test_safe_int_invalid(self):
        from api.services.signals_enricher import _safe_int

        assert _safe_int(None) is None
        assert _safe_int("not a number") is None
        assert _safe_int([]) is None

    def test_safe_json_list(self):
        from api.services.signals_enricher import _safe_json

        assert _safe_json(None) == "[]"
        assert _safe_json(["a", "b"]) == '["a", "b"]'
        assert _safe_json("raw string") == "raw string"

    def test_parse_json_plain(self):
        from api.services.signals_enricher import _parse_json

        assert _parse_json('{"key": "value"}') == {"key": "value"}

    def test_parse_json_fenced(self):
        from api.services.signals_enricher import _parse_json

        fenced = '```json\n{"key": "value"}\n```'
        assert _parse_json(fenced) == {"key": "value"}

    def test_parse_json_none(self):
        from api.services.signals_enricher import _parse_json

        assert _parse_json(None) is None
        assert _parse_json("not json") is None
