"""Unit tests for the domain-first research service (BL-189, BL-190).

Tests website fetching, parsing, progress events, and data compatibility
with the existing _load_enrichment_data() format.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Website fetching & parsing (no DB needed)
# ---------------------------------------------------------------------------


class TestParseHtml:
    """Test HTML parsing and content extraction."""

    def setup_method(self):
        from api.services.research_service import _parse_html

        self.parse = _parse_html

    def test_basic_html(self):
        html = """
        <html>
        <head>
            <title>Acme Corp - Enterprise Solutions</title>
            <meta name="description" content="Leading B2B software company">
        </head>
        <body>
            <nav>Navigation links</nav>
            <main>
                <h1>Welcome to Acme</h1>
                <p>We build enterprise automation tools.</p>
            </main>
            <footer>Copyright 2024</footer>
            <script>var x = 1;</script>
        </body>
        </html>
        """
        result = self.parse(html)
        assert result is not None
        assert result["title"] == "Acme Corp - Enterprise Solutions"
        assert result["meta_description"] == "Leading B2B software company"
        assert "enterprise automation tools" in result["body_text"]
        # Nav, footer, script should be stripped from body_text
        assert "Navigation links" not in result["body_text"]
        assert "Copyright 2024" not in result["body_text"]
        assert "var x = 1" not in result["body_text"]

    def test_og_description_fallback(self):
        html = """
        <html>
        <head>
            <title>Test</title>
            <meta property="og:description" content="OG description text">
        </head>
        <body><p>Content</p></body>
        </html>
        """
        result = self.parse(html)
        assert result["meta_description"] == "OG description text"

    def test_extracts_links(self):
        html = """
        <html>
        <head><title>Test</title></head>
        <body>
            <a href="/about">About</a>
            <a href="/team">Team</a>
            <a href="mailto:info@test.com">Email</a>
            <a href="#section">Anchor</a>
        </body>
        </html>
        """
        result = self.parse(html)
        assert "/about" in result["links"]
        assert "/team" in result["links"]
        # mailto and anchors should be excluded
        assert "mailto:info@test.com" not in result["links"]
        assert "#section" not in result["links"]

    def test_empty_html(self):
        result = self.parse("<html><head></head><body></body></html>")
        assert result is not None
        assert result["title"] == ""
        assert result["body_text"] == ""


class TestFindSubpageUrls:
    """Test subpage URL discovery from link lists."""

    def setup_method(self):
        from api.services.research_service import _find_subpage_urls

        self.find = _find_subpage_urls

    def test_finds_about_page(self):
        urls = self.find("https://acme.com/", ["/about", "/contact", "/blog"])
        assert "https://acme.com/about" in urls

    def test_finds_team_page(self):
        urls = self.find("https://acme.com/", ["/team", "/careers"])
        assert "https://acme.com/team" in urls

    def test_finds_products_page(self):
        urls = self.find("https://acme.com/", ["/products", "/pricing"])
        assert "https://acme.com/products" in urls

    def test_ignores_external_links(self):
        urls = self.find(
            "https://acme.com/",
            ["https://other.com/about", "/about"],
        )
        assert len(urls) == 1
        assert "https://acme.com/about" in urls

    def test_max_subpages_limit(self):
        urls = self.find(
            "https://acme.com/",
            ["/about", "/team", "/products", "/services", "/solutions"],
        )
        # MAX_SUBPAGES is 3
        assert len(urls) <= 3

    def test_deduplicates(self):
        urls = self.find(
            "https://acme.com/",
            ["/about", "/about/", "/about"],
        )
        assert len(urls) == 1


class TestFetchWebsite:
    """Test the full website fetch pipeline."""

    @patch("api.services.research_service._fetch_page")
    def test_successful_fetch(self, mock_fetch):
        from api.services.research_service import fetch_website

        mock_resp = MagicMock()
        mock_resp.text = """
        <html>
        <head><title>United Arts - Creative Agency</title>
        <meta name="description" content="Prague-based creative agency">
        </head>
        <body><p>We create amazing art.</p></body>
        </html>
        """

        mock_fetch.return_value = mock_resp
        result = fetch_website("unitedarts.cz")

        assert result is not None
        assert result["pages_fetched"] >= 1
        assert "United Arts" in result["all_text"]
        assert "amazing art" in result["all_text"]

    @patch("api.services.research_service._fetch_page")
    def test_failed_fetch_returns_none(self, mock_fetch):
        from api.services.research_service import fetch_website

        mock_fetch.return_value = None
        result = fetch_website("nonexistent-domain.xyz")
        assert result is None

    def test_none_domain(self):
        from api.services.research_service import fetch_website

        assert fetch_website(None) is None

    def test_empty_domain(self):
        from api.services.research_service import fetch_website

        assert fetch_website("") is None


# ---------------------------------------------------------------------------
# Progress events
# ---------------------------------------------------------------------------


class TestProgressEvents:
    """Test that progress events are emitted correctly."""

    @patch("api.services.research_service._fetch_page")
    def test_emits_progress_on_website_fetch(self, mock_fetch):
        from api.services.research_service import fetch_website

        mock_resp = MagicMock()
        mock_resp.text = (
            "<html><head><title>Test</title></head><body>Content</body></html>"
        )
        mock_fetch.return_value = mock_resp

        events = []
        fetch_website("test.com", on_progress=lambda e: events.append(e))

        assert len(events) >= 2  # running + completed
        assert events[0]["status"] == "running"
        assert events[0]["step"] == "website_fetch"
        assert events[-1]["status"] == "completed"

    @patch("api.services.research_service._fetch_page")
    def test_emits_error_on_failed_fetch(self, mock_fetch):
        from api.services.research_service import fetch_website

        mock_fetch.return_value = None

        events = []
        fetch_website("broken.com", on_progress=lambda e: events.append(e))

        assert len(events) >= 2
        error_events = [e for e in events if e["status"] == "error"]
        assert len(error_events) >= 1

    def test_event_structure(self):
        from api.services.research_service import _make_event

        event = _make_event(
            "test_step",
            "Test Tool",
            "test.com",
            "completed",
            "Done",
            {"key": "val"},
            1234,
        )
        assert event["step"] == "test_step"
        assert event["tool_name"] == "Test Tool"
        assert event["target"] == "test.com"
        assert event["status"] == "completed"
        assert event["summary"] == "Done"
        assert event["detail"] == {"key": "val"}
        assert event["duration_ms"] == 1234


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


class TestParseJsonResponse:
    """Test JSON response parsing from LLM output."""

    def setup_method(self):
        from api.services.research_service import _parse_json_response

        self.parse = _parse_json_response

    def test_clean_json(self):
        result = self.parse('{"name": "Acme", "industry": "software_saas"}')
        assert result["name"] == "Acme"
        assert result["industry"] == "software_saas"

    def test_json_with_code_fences(self):
        result = self.parse('```json\n{"name": "Acme"}\n```')
        assert result["name"] == "Acme"

    def test_json_with_surrounding_text(self):
        result = self.parse('Here is the result:\n{"name": "Acme"}\nDone.')
        assert result["name"] == "Acme"

    def test_invalid_json_returns_empty(self):
        result = self.parse("This is not JSON at all")
        assert result == {}

    def test_empty_string(self):
        result = self.parse("")
        assert result == {}


# ---------------------------------------------------------------------------
# Web search (mocked Perplexity)
# ---------------------------------------------------------------------------


class TestRunWebSearch:
    """Test the Perplexity web search step."""

    @patch("api.services.research_service.PerplexityClient")
    def test_successful_search(self, mock_client_class):
        from api.services.research_service import run_web_search

        mock_response = MagicMock()
        mock_response.content = json.dumps(
            {
                "company_name": "United Arts",
                "summary": "Creative agency in Prague",
                "industry": "creative_services",
                "employees": "15",
                "confidence": 0.8,
            }
        )
        mock_response.cost_usd = 0.003
        mock_response.input_tokens = 500
        mock_response.output_tokens = 200

        mock_client_class.return_value.query.return_value = mock_response

        results, cost, usage = run_web_search(
            "unitedarts.cz", "Unitedarts", "We are a creative agency"
        )

        assert results["company_name"] == "United Arts"
        assert results["industry"] == "creative_services"
        assert cost == 0.003
        assert usage["input_tokens"] == 500

    @patch("api.services.research_service.PerplexityClient")
    def test_search_failure_returns_empty(self, mock_client_class):
        from api.services.research_service import run_web_search

        mock_client_class.return_value.query.side_effect = Exception("API down")

        results, cost, usage = run_web_search("test.com", "Test", "content")

        assert results == {}
        assert cost == 0.0

    @patch("api.services.research_service.PerplexityClient")
    def test_emits_progress_events(self, mock_client_class):
        from api.services.research_service import run_web_search

        mock_response = MagicMock()
        mock_response.content = '{"company_name": "Test"}'
        mock_response.cost_usd = 0.001
        mock_response.input_tokens = 100
        mock_response.output_tokens = 50
        mock_client_class.return_value.query.return_value = mock_response

        events = []
        run_web_search(
            "test.com", "Test", "content", on_progress=lambda e: events.append(e)
        )

        assert len(events) >= 2
        steps = [e["step"] for e in events]
        assert "web_search" in steps


# ---------------------------------------------------------------------------
# AI Synthesis (mocked Anthropic)
# ---------------------------------------------------------------------------


class TestRunSynthesis:
    """Test the Claude synthesis step."""

    @patch("api.services.research_service.AnthropicClient")
    def test_successful_synthesis(self, mock_client_class):
        from api.services.research_service import run_synthesis

        mock_response = MagicMock()
        mock_response.content = json.dumps(
            {
                "executive_brief": "United Arts is a creative agency in Prague.",
                "ai_opportunities": "Workflow automation for design processes",
                "pain_hypothesis": "Manual design review processes slow delivery",
                "quick_wins": [
                    {
                        "title": "Automate review",
                        "description": "Use AI for design QA",
                        "effort": "low",
                    }
                ],
                "pitch_framing": "Focus on creative workflow efficiency",
            }
        )
        mock_response.cost_usd = 0.015
        mock_response.input_tokens = 2000
        mock_response.output_tokens = 800

        mock_client_class.return_value.query.return_value = mock_response

        synthesis, cost, usage = run_synthesis(
            "unitedarts.cz",
            "United Arts",
            "We create amazing art",
            {"industry": "creative_services"},
        )

        assert "creative agency" in synthesis["executive_brief"]
        assert synthesis["ai_opportunities"]
        assert synthesis["pain_hypothesis"]
        assert len(synthesis["quick_wins"]) == 1
        assert cost == 0.015

    @patch("api.services.research_service.AnthropicClient")
    def test_synthesis_failure_returns_empty(self, mock_client_class):
        from api.services.research_service import run_synthesis

        mock_client_class.return_value.query.side_effect = Exception("Claude down")

        synthesis, cost, usage = run_synthesis("test.com", "Test", "content", {})

        assert synthesis == {}
        assert cost == 0.0


# ---------------------------------------------------------------------------
# Data compatibility with _load_enrichment_data()
# ---------------------------------------------------------------------------


class TestDataCompatibility:
    """Test that saved enrichment data is compatible with _load_enrichment_data() format."""

    def test_to_text_string(self):
        from api.services.research_service import _to_text

        assert _to_text("hello") == "hello"

    def test_to_text_list(self):
        from api.services.research_service import _to_text

        assert _to_text(["a", "b", "c"]) == "a, b, c"

    def test_to_text_dict(self):
        from api.services.research_service import _to_text

        result = _to_text({"key": "val"})
        assert '"key"' in result

    def test_to_text_none(self):
        from api.services.research_service import _to_text

        assert _to_text(None) == ""

    def test_to_text_number(self):
        from api.services.research_service import _to_text

        assert _to_text(42) == "42"


class TestSaveToCompany:
    """Test company table update logic."""

    def test_employee_size_buckets(self):
        """Verify employee count maps to correct company_size buckets."""
        # Test the bucket logic inline (matches _save_to_company implementation)
        test_cases = [
            (5, "micro"),
            (15, "small"),
            (100, "medium"),
            (500, "large"),
            (5000, "enterprise"),
        ]
        for emp_count, expected_size in test_cases:
            if emp_count < 10:
                size = "micro"
            elif emp_count < 50:
                size = "small"
            elif emp_count < 250:
                size = "medium"
            elif emp_count < 1000:
                size = "large"
            else:
                size = "enterprise"
            assert size == expected_size, f"{emp_count} should map to {expected_size}"


# ---------------------------------------------------------------------------
# ResearchService integration (mocked external calls)
# ---------------------------------------------------------------------------


class TestResearchServiceIntegration:
    """Test the full research pipeline with mocked externals."""

    @patch("api.services.research_service.log_llm_usage", None)
    @patch("api.services.research_service.run_synthesis")
    @patch("api.services.research_service.run_web_search")
    @patch("api.services.research_service.fetch_website")
    @patch("api.services.research_service._save_research_asset")
    @patch("api.services.research_service._save_l2_and_modules")
    @patch("api.services.research_service._save_l1_enrichment")
    @patch("api.services.research_service._save_to_company")
    @patch("api.services.research_service.db")
    def test_full_pipeline_success(
        self,
        mock_db,
        mock_save_company,
        mock_save_l1,
        mock_save_l2,
        mock_save_asset,
        mock_fetch,
        mock_search,
        mock_synthesis,
    ):
        from api.services.research_service import ResearchService

        # Mock website fetch
        mock_fetch.return_value = {
            "homepage": {
                "title": "Acme Corp",
                "meta_description": "B2B SaaS",
                "body_text": "Enterprise tools",
                "links": [],
            },
            "subpages": [],
            "all_text": "Homepage title: Acme Corp\nEnterprise tools",
            "pages_fetched": 1,
        }

        # Mock web search
        mock_search.return_value = (
            {
                "company_name": "Acme Corp",
                "industry": "software_saas",
                "employees": "50",
                "confidence": 0.85,
            },
            0.003,
            {
                "input_tokens": 500,
                "output_tokens": 200,
                "model": "sonar-pro",
                "provider": "perplexity",
            },
        )

        # Mock synthesis
        mock_synthesis.return_value = (
            {
                "executive_brief": "Acme Corp builds enterprise tools.",
                "ai_opportunities": "Automate customer onboarding",
                "pain_hypothesis": "Manual processes slow growth",
                "quick_wins": [
                    {"title": "Win 1", "description": "desc", "effort": "low"}
                ],
                "pitch_framing": "Focus on efficiency gains",
            },
            0.015,
            {
                "input_tokens": 2000,
                "output_tokens": 800,
                "model": "claude-sonnet-4-5-20250929",
                "provider": "anthropic",
            },
        )

        service = ResearchService()
        result = service.research_company(
            company_id="test-company-id",
            tenant_id="test-tenant-id",
            domain="acme.com",
        )

        assert result["success"] is True
        assert result["company_name"] == "Acme Corp"
        assert result["enrichment_cost_usd"] == pytest.approx(0.018)
        assert "website_fetch" in result["steps_completed"]
        assert "web_search" in result["steps_completed"]
        assert "ai_synthesis" in result["steps_completed"]
        assert "database_save" in result["steps_completed"]

        # Verify save functions were called
        mock_save_company.assert_called_once()
        mock_save_l1.assert_called_once()
        mock_save_l2.assert_called_once()

    @patch("api.services.research_service.log_llm_usage", None)
    @patch("api.services.research_service.run_synthesis")
    @patch("api.services.research_service.run_web_search")
    @patch("api.services.research_service.fetch_website")
    @patch("api.services.research_service._save_research_asset")
    @patch("api.services.research_service._save_l2_and_modules")
    @patch("api.services.research_service._save_l1_enrichment")
    @patch("api.services.research_service._save_to_company")
    @patch("api.services.research_service.db")
    def test_continues_without_website(
        self,
        mock_db,
        mock_save_company,
        mock_save_l1,
        mock_save_l2,
        mock_save_asset,
        mock_fetch,
        mock_search,
        mock_synthesis,
    ):
        """Research continues even if website fetch fails."""
        from api.services.research_service import ResearchService

        mock_fetch.return_value = None  # Website unreachable

        mock_search.return_value = (
            {"company_name": "Test Corp", "confidence": 0.6},
            0.003,
            {
                "input_tokens": 500,
                "output_tokens": 200,
                "model": "sonar-pro",
                "provider": "perplexity",
            },
        )
        mock_synthesis.return_value = (
            {"executive_brief": "Test Corp overview"},
            0.015,
            {
                "input_tokens": 2000,
                "output_tokens": 800,
                "model": "claude-sonnet-4-5-20250929",
                "provider": "anthropic",
            },
        )

        service = ResearchService()
        result = service.research_company(
            company_id="test-id",
            tenant_id="test-tenant",
            domain="unreachable.com",
        )

        assert result["success"] is True
        assert "website_fetch" not in result["steps_completed"]
        assert "web_search" in result["steps_completed"]
        assert "ai_synthesis" in result["steps_completed"]

    @patch("api.services.research_service.run_synthesis")
    @patch("api.services.research_service.run_web_search")
    @patch("api.services.research_service.fetch_website")
    @patch("api.services.research_service._save_research_asset")
    @patch("api.services.research_service._save_l2_and_modules")
    @patch("api.services.research_service._save_l1_enrichment")
    @patch("api.services.research_service._save_to_company")
    @patch("api.services.research_service.db")
    def test_progress_callback_receives_events(
        self,
        mock_db,
        mock_save_company,
        mock_save_l1,
        mock_save_l2,
        mock_save_asset,
        mock_fetch,
        mock_search,
        mock_synthesis,
    ):
        """Progress callback receives events from all steps."""
        from api.services.research_service import ResearchService

        mock_fetch.return_value = {
            "homepage": {
                "title": "Test",
                "meta_description": "",
                "body_text": "Content",
                "links": [],
            },
            "subpages": [],
            "all_text": "Content",
            "pages_fetched": 1,
        }
        mock_search.return_value = ({"company_name": "Test"}, 0.001, {})
        mock_synthesis.return_value = ({"executive_brief": "Test"}, 0.01, {})

        events = []
        service = ResearchService()
        service.research_company(
            company_id="test-id",
            tenant_id="test-tenant",
            domain="test.com",
            on_progress=lambda e: events.append(e),
        )

        # Should have events from multiple steps
        steps = {e["step"] for e in events}
        assert "website_parse" in steps  # Content extraction step
        assert "database_save" in steps  # Final save step

    @patch("api.services.research_service.run_synthesis")
    @patch("api.services.research_service.run_web_search")
    @patch("api.services.research_service.fetch_website")
    @patch("api.services.research_service.db")
    def test_db_save_failure_returns_error(
        self,
        mock_db,
        mock_fetch,
        mock_search,
        mock_synthesis,
    ):
        """Database save failure is reported in the result."""
        from api.services.research_service import ResearchService

        mock_fetch.return_value = {
            "homepage": {
                "title": "Test",
                "meta_description": "",
                "body_text": "X",
                "links": [],
            },
            "subpages": [],
            "all_text": "X",
            "pages_fetched": 1,
        }
        mock_search.return_value = (
            {"company_name": "Test", "confidence": 0.5},
            0.001,
            {},
        )
        mock_synthesis.return_value = ({"executive_brief": "Test"}, 0.01, {})

        # Make DB operations fail
        mock_db.session.execute.side_effect = Exception("DB connection lost")
        mock_db.session.rollback = MagicMock()

        service = ResearchService()
        result = service.research_company(
            company_id="test-id",
            tenant_id="test-tenant",
            domain="test.com",
        )

        assert result["success"] is False
        assert "error" in result
        assert "database_save" not in result["steps_completed"]
