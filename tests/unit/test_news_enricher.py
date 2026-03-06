"""Unit tests for News & PR enrichment."""

import json
from unittest.mock import MagicMock, patch

from sqlalchemy import text as sa_text


TENANT_ID = "t0000000-0000-0000-0000-000000000001"
COMPANY_ID = "c0000000-0000-0000-0000-000000000001"


def _make_news_response():
    """Sample Perplexity response for news enrichment."""
    return {
        "media_mentions": [
            {
                "headline": "Acme Corp Raises $50M Series C",
                "source": "TechCrunch",
                "date": "2026-01-15",
                "summary": "Enterprise automation company closes Series C round led by Sequoia.",
                "sentiment": "positive",
                "url": "https://techcrunch.com/acme-series-c",
            },
            {
                "headline": "Acme Corp Expands to APAC Market",
                "source": "Bloomberg",
                "date": "2026-02-20",
                "summary": "Acme opens Singapore office as part of Asia-Pacific expansion.",
                "sentiment": "positive",
                "url": None,
            },
        ],
        "press_releases": [
            {
                "headline": "Acme Corp Launches AI-Powered Workflow Engine",
                "date": "2026-03-01",
                "summary": "New product uses LLMs to automate enterprise document processing.",
                "url": "https://acme.com/press/ai-workflow",
            },
        ],
        "sentiment_score": 0.75,
        "thought_leadership": "CEO published 3 articles on AI adoption in Forbes. CTO spoke at AWS re:Invent 2025.",
        "news_summary": "Acme Corp has strong positive media presence driven by recent funding and product launches. The company is actively expanding into APAC and investing in AI capabilities.",
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


class TestEnrichNews:
    """Tests for enrich_news() with mocked Perplexity."""

    @patch("api.services.news_enricher.log_llm_usage", None)
    @patch("api.services.news_enricher.PerplexityClient")
    def test_successful_enrichment(self, MockClient, app, db):
        """Successful news enrichment writes to DB and returns cost."""
        _seed_company(db)

        mock_response = MagicMock()
        mock_response.content = json.dumps(_make_news_response())
        mock_response.input_tokens = 400
        mock_response.output_tokens = 500
        mock_response.cost_usd = 0.0009
        MockClient.return_value.query.return_value = mock_response

        with app.app_context():
            app.config["PERPLEXITY_API_KEY"] = "test-key"
            from api.services.news_enricher import enrich_news

            result = enrich_news(COMPANY_ID, TENANT_ID)

        assert "enrichment_cost_usd" in result
        assert result["enrichment_cost_usd"] == 0.0009
        assert "error" not in result

        # Verify DB write
        row = db.session.execute(
            sa_text("SELECT * FROM company_news WHERE company_id = :id"),
            {"id": COMPANY_ID},
        ).fetchone()
        assert row is not None

    @patch("api.services.news_enricher.log_llm_usage", None)
    @patch("api.services.news_enricher.PerplexityClient")
    def test_company_not_found(self, MockClient, app, db):
        """Returns error when company doesn't exist."""
        with app.app_context():
            app.config["PERPLEXITY_API_KEY"] = "test-key"
            from api.services.news_enricher import enrich_news

            result = enrich_news("nonexistent-id", TENANT_ID)

        assert result["enrichment_cost_usd"] == 0
        assert result["error"] == "company_not_found"
        MockClient.return_value.query.assert_not_called()

    @patch("api.services.news_enricher.log_llm_usage", None)
    @patch("api.services.news_enricher.PerplexityClient")
    def test_api_error_handled(self, MockClient, app, db):
        """API errors return gracefully without crashing."""
        _seed_company(db)

        MockClient.return_value.query.side_effect = Exception("rate limited")

        with app.app_context():
            app.config["PERPLEXITY_API_KEY"] = "test-key"
            from api.services.news_enricher import enrich_news

            result = enrich_news(COMPANY_ID, TENANT_ID)

        assert result["enrichment_cost_usd"] == 0
        assert "api_error" in result["error"]

    @patch("api.services.news_enricher.log_llm_usage", None)
    @patch("api.services.news_enricher.PerplexityClient")
    def test_no_news_found(self, MockClient, app, db):
        """Empty response is stored correctly."""
        _seed_company(db)

        empty = {
            "media_mentions": [],
            "press_releases": [],
            "sentiment_score": None,
            "thought_leadership": None,
            "news_summary": None,
        }
        mock_response = MagicMock()
        mock_response.content = json.dumps(empty)
        mock_response.input_tokens = 200
        mock_response.output_tokens = 50
        mock_response.cost_usd = 0.0003
        MockClient.return_value.query.return_value = mock_response

        with app.app_context():
            app.config["PERPLEXITY_API_KEY"] = "test-key"
            from api.services.news_enricher import enrich_news

            result = enrich_news(COMPANY_ID, TENANT_ID)

        assert "error" not in result

        row = db.session.execute(
            sa_text("SELECT news_summary FROM company_news WHERE company_id = :id"),
            {"id": COMPANY_ID},
        ).fetchone()
        assert row is not None
        assert row[0] is None

    @patch("api.services.news_enricher.log_llm_usage", None)
    @patch("api.services.news_enricher.PerplexityClient")
    def test_sentiment_score_clamped(self, MockClient, app, db):
        """Sentiment score is clamped to [-1, 1] range."""
        _seed_company(db)

        data = _make_news_response()
        data["sentiment_score"] = 5.0  # Out of range
        mock_response = MagicMock()
        mock_response.content = json.dumps(data)
        mock_response.input_tokens = 400
        mock_response.output_tokens = 500
        mock_response.cost_usd = 0.0009
        MockClient.return_value.query.return_value = mock_response

        with app.app_context():
            app.config["PERPLEXITY_API_KEY"] = "test-key"
            from api.services.news_enricher import enrich_news

            result = enrich_news(COMPANY_ID, TENANT_ID)

        assert "error" not in result

        row = db.session.execute(
            sa_text("SELECT sentiment_score FROM company_news WHERE company_id = :id"),
            {"id": COMPANY_ID},
        ).fetchone()
        assert row is not None
        assert float(row[0]) == 1.0  # Clamped to max

    @patch("api.services.news_enricher.log_llm_usage", None)
    @patch("api.services.news_enricher.PerplexityClient")
    def test_upsert_overwrites_existing(self, MockClient, app, db):
        """Second enrichment updates existing row."""
        _seed_company(db)

        def make_response(summary):
            data = _make_news_response()
            data["news_summary"] = summary
            mock = MagicMock()
            mock.content = json.dumps(data)
            mock.input_tokens = 400
            mock.output_tokens = 500
            mock.cost_usd = 0.0009
            return mock

        with app.app_context():
            app.config["PERPLEXITY_API_KEY"] = "test-key"
            from api.services.news_enricher import enrich_news

            MockClient.return_value.query.return_value = make_response("First summary")
            enrich_news(COMPANY_ID, TENANT_ID)

            MockClient.return_value.query.return_value = make_response(
                "Updated summary"
            )
            enrich_news(COMPANY_ID, TENANT_ID)

        row = db.session.execute(
            sa_text("SELECT news_summary FROM company_news WHERE company_id = :id"),
            {"id": COMPANY_ID},
        ).fetchone()
        assert row[0] == "Updated summary"

    @patch("api.services.news_enricher.log_llm_usage", None)
    @patch("api.services.news_enricher.PerplexityClient")
    def test_parse_error_handled(self, MockClient, app, db):
        """Unparseable response returns error."""
        _seed_company(db)

        mock_response = MagicMock()
        mock_response.content = "Sorry, I can't find any news about this company."
        mock_response.input_tokens = 100
        mock_response.output_tokens = 20
        mock_response.cost_usd = 0.0001
        MockClient.return_value.query.return_value = mock_response

        with app.app_context():
            app.config["PERPLEXITY_API_KEY"] = "test-key"
            from api.services.news_enricher import enrich_news

            result = enrich_news(COMPANY_ID, TENANT_ID)

        assert result["error"] == "parse_error"


class TestHelpers:
    """Tests for helper functions."""

    def test_safe_float_valid(self):
        from api.services.news_enricher import _safe_float

        assert _safe_float(0.5) == 0.5
        assert _safe_float("0.75") == 0.75
        assert _safe_float(-0.3) == -0.3

    def test_safe_float_clamped(self):
        from api.services.news_enricher import _safe_float

        assert _safe_float(5.0) == 1.0
        assert _safe_float(-3.0) == -1.0

    def test_safe_float_invalid(self):
        from api.services.news_enricher import _safe_float

        assert _safe_float(None) is None
        assert _safe_float("not a number") is None

    def test_safe_json_list(self):
        from api.services.news_enricher import _safe_json_list

        assert _safe_json_list(None) == "[]"
        assert _safe_json_list([]) == "[]"
        items = [{"headline": "test"}]
        assert json.loads(_safe_json_list(items)) == items
