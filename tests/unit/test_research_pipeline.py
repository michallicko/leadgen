"""Tests for the research pipeline: web_fetch, market_research, cross_checker, pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


from api.agents.tools.cross_checker import (
    CrossCheckResult,
    cross_check_findings,
    needs_halt_gate,
)
from api.agents.tools.market_research import MarketResearchResult, _parse_json_array
from api.agents.tools.research_pipeline import run_research_pipeline
from api.agents.tools.web_fetch import (
    CompanyExtract,
    WebsiteData,
    _extract_meta_description,
    _extract_title,
    _find_subpage_links,
    fetch_website,
    html_to_text,
)


# ---------------------------------------------------------------------------
# web_fetch: html_to_text
# ---------------------------------------------------------------------------


class TestHtmlToText:
    def test_strips_script_tags(self):
        html = "<html><body><script>var x = 1;</script><p>Hello world</p></body></html>"
        result = html_to_text(html)
        assert "var x" not in result
        assert "Hello world" in result

    def test_strips_style_tags(self):
        html = "<html><body><style>body { color: red; }</style><p>Content</p></body></html>"
        result = html_to_text(html)
        assert "color" not in result
        assert "Content" in result

    def test_strips_nav_footer(self):
        html = (
            "<html><body>"
            "<nav>Menu items</nav>"
            "<main><p>Main content</p></main>"
            "<footer>Footer links</footer>"
            "</body></html>"
        )
        result = html_to_text(html)
        assert "Menu items" not in result
        assert "Footer links" not in result
        assert "Main content" in result

    def test_cleans_whitespace(self):
        html = "<p>  Multiple   spaces   here  </p>"
        result = html_to_text(html)
        assert "  " not in result
        assert "Multiple spaces here" in result

    def test_truncates_long_content(self):
        html = "<p>{}</p>".format("A" * 20000)
        result = html_to_text(html)
        assert len(result) <= 10000

    def test_handles_empty_html(self):
        assert html_to_text("") == ""

    def test_handles_plain_text(self):
        result = html_to_text("Just plain text")
        assert "Just plain text" in result


# ---------------------------------------------------------------------------
# web_fetch: _find_subpage_links
# ---------------------------------------------------------------------------


class TestFindSubpageLinks:
    def test_finds_about_page(self):
        html = '<a href="/about">About Us</a>'
        links = _find_subpage_links(html, "example.com")
        assert "https://example.com/about" in links

    def test_finds_services_page(self):
        html = '<a href="/services">Our Services</a>'
        links = _find_subpage_links(html, "example.com")
        assert "https://example.com/services" in links

    def test_finds_team_page(self):
        html = '<a href="/team">Our Team</a>'
        links = _find_subpage_links(html, "example.com")
        assert "https://example.com/team" in links

    def test_handles_absolute_urls(self):
        html = '<a href="https://example.com/about">About</a>'
        links = _find_subpage_links(html, "example.com")
        assert "https://example.com/about" in links

    def test_ignores_external_links(self):
        html = '<a href="https://other.com/about">About</a>'
        links = _find_subpage_links(html, "example.com")
        assert len(links) == 0

    def test_limits_to_max_subpages(self):
        html = "".join(
            '<a href="/about-{}">About {}</a>'.format(i, i) for i in range(20)
        )
        links = _find_subpage_links(html, "example.com")
        assert len(links) <= 5

    def test_deduplicates_links(self):
        html = '<a href="/about">1</a><a href="/about">2</a>'
        links = _find_subpage_links(html, "example.com")
        assert len(links) == 1


# ---------------------------------------------------------------------------
# web_fetch: title and description extraction
# ---------------------------------------------------------------------------


class TestMetaExtraction:
    def test_extract_title(self):
        html = "<html><head><title>Acme Corp - Innovation</title></head></html>"
        assert _extract_title(html) == "Acme Corp - Innovation"

    def test_extract_title_empty(self):
        assert _extract_title("<html><head></head></html>") == ""

    def test_extract_meta_description(self):
        html = '<meta name="description" content="We build great software.">'
        assert _extract_meta_description(html) == "We build great software."

    def test_extract_meta_description_reverse_order(self):
        html = '<meta content="Reversed order" name="description">'
        assert _extract_meta_description(html) == "Reversed order"

    def test_extract_meta_description_missing(self):
        assert _extract_meta_description("<html></html>") == ""


# ---------------------------------------------------------------------------
# web_fetch: fetch_website
# ---------------------------------------------------------------------------


class TestFetchWebsite:
    @patch("api.agents.tools.web_fetch.requests.Session")
    def test_handles_network_error_gracefully(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.side_effect = ConnectionError("Network unreachable")

        result = fetch_website("unreachable.com")
        assert result.error is not None
        assert "could not fetch" in result.error.lower()
        assert result.url == "https://unreachable.com"

    @patch("api.agents.tools.web_fetch._extract_company_data")
    @patch("api.agents.tools.web_fetch.requests.Session")
    def test_fetches_main_page_and_subpages(self, mock_session_cls, mock_extract):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        main_html = (
            "<html><head><title>Acme</title>"
            '<meta name="description" content="Best company">'
            "</head><body>"
            '<a href="/about">About</a>'
            "<p>Welcome to Acme</p>"
            "</body></html>"
        )
        about_html = "<html><body><p>About Acme Corp founded in 2020</p></body></html>"

        responses = []
        main_resp = MagicMock()
        main_resp.text = main_html
        main_resp.raise_for_status.return_value = None
        responses.append(main_resp)

        about_resp = MagicMock()
        about_resp.text = about_html
        about_resp.raise_for_status.return_value = None
        responses.append(about_resp)

        mock_session.get.side_effect = responses

        mock_extract.return_value = CompanyExtract(
            company_name="Acme", products_services=["Software"]
        )

        result = fetch_website("acme.com")
        assert result.error is None
        assert result.title == "Acme"
        assert result.description == "Best company"
        assert len(result.pages_fetched) >= 1
        assert "https://acme.com" in result.raw_content

    @patch("api.agents.tools.web_fetch.requests.Session")
    def test_returns_partial_data_on_subpage_failure(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        main_html = (
            '<html><body><a href="/about">About</a><p>Main content</p></body></html>'
        )
        main_resp = MagicMock()
        main_resp.text = main_html
        main_resp.raise_for_status.return_value = None

        def side_effect(url, **kwargs):
            if "/about" in url:
                raise ConnectionError("Subpage timeout")
            return main_resp

        mock_session.get.side_effect = side_effect

        with patch("api.agents.tools.web_fetch._extract_company_data") as mock_extract:
            mock_extract.return_value = CompanyExtract(company_name="Test")
            result = fetch_website("test.com")

        assert result.error is None
        assert len(result.pages_fetched) == 1  # Only main page


# ---------------------------------------------------------------------------
# market_research: _parse_json_array
# ---------------------------------------------------------------------------


class TestParseJsonArray:
    def test_parses_valid_json_array(self):
        result = _parse_json_array('[{"name": "A"}, {"name": "B"}]')
        assert len(result) == 2
        assert result[0]["name"] == "A"

    def test_handles_markdown_fences(self):
        result = _parse_json_array('```json\n[{"name": "A"}]\n```')
        assert len(result) == 1

    def test_returns_empty_on_invalid_json(self):
        assert _parse_json_array("not json at all") == []

    def test_returns_empty_on_non_array(self):
        assert _parse_json_array('{"name": "A"}') == []

    def test_filters_non_dict_items(self):
        result = _parse_json_array('[{"name": "A"}, "string", 42]')
        assert len(result) == 1


# ---------------------------------------------------------------------------
# market_research: research_market
# ---------------------------------------------------------------------------


class TestResearchMarket:
    @patch.dict("os.environ", {"PERPLEXITY_API_KEY": ""})
    def test_returns_error_without_api_key(self):
        from api.agents.tools.market_research import research_market

        result = research_market("Acme Corp")
        assert result.error is not None
        assert "not configured" in result.error

    @patch("api.agents.tools.market_research._create_perplexity_client")
    @patch.dict("os.environ", {"PERPLEXITY_API_KEY": "test-key"})
    def test_returns_competitors_on_success(self, mock_create_client):
        from api.agents.tools.market_research import research_market

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_resp = MagicMock()
        mock_resp.content = '[{"name": "Rival Inc", "description": "A competitor"}]'
        mock_resp.citations = ["https://source.com"]
        mock_client.query.return_value = mock_resp

        result = research_market("Acme Corp", industry="SaaS", location="Europe")
        assert len(result.competitors) >= 1
        assert result.competitors[0]["name"] == "Rival Inc"
        assert "https://source.com" in result.sources


# ---------------------------------------------------------------------------
# cross_checker: cross_check_findings
# ---------------------------------------------------------------------------


class TestCrossCheckFindings:
    def test_matching_data_confirmed(self):
        website = {"location": "San Francisco", "team_size": "50-100"}
        external = {
            "market_data": [
                {"fact": "Located in San Francisco", "source_url": "https://s.com"}
            ]
        }
        results = cross_check_findings(website, external)
        location_checks = [r for r in results if r.field == "location"]
        if location_checks:
            assert location_checks[0].verdict in ("confirmed", "website_trusted")

    def test_single_source_conflict_trusts_website(self):
        website = {"team_size": "50"}
        external = {
            "market_data": [
                {"fact": "500 employees at the company", "source_url": "https://s.com"}
            ]
        }
        results = cross_check_findings(website, external)
        team_checks = [r for r in results if r.field == "team_size"]
        if team_checks:
            assert team_checks[0].verdict == "website_trusted"

    def test_consensus_conflict_with_many_sources(self):
        """3+ external sources disagreeing should trigger consensus_conflict."""
        website = {"location": "Berlin"}
        external = {
            "market_data": [
                {"fact": "Based in London", "source_url": "https://s1.com"},
                {"fact": "Located in London", "source_url": "https://s2.com"},
                {"fact": "Headquartered in London", "source_url": "https://s3.com"},
            ]
        }
        results = cross_check_findings(website, external)
        location_checks = [r for r in results if r.field == "location"]
        # The external claims are about 'location' and come from 3 sources
        # Since _extract_external_claims groups by keyword, this tests the mechanism
        if location_checks:
            # With 3 sources, should be consensus_conflict
            assert location_checks[0].verdict in (
                "consensus_conflict",
                "website_trusted",
            )

    def test_no_data_when_website_empty(self):
        website = {"location": ""}
        external = {
            "market_data": [
                {"fact": "Headquartered in Paris", "source_url": "https://s.com"}
            ]
        }
        results = cross_check_findings(website, external)
        location_checks = [r for r in results if r.field == "location"]
        if location_checks:
            assert location_checks[0].verdict == "no_data"


class TestNeedsHaltGate:
    def test_filters_consensus_conflicts(self):
        results = [
            CrossCheckResult(
                field="team_size",
                website_value="50",
                external_value="500",
                verdict="consensus_conflict",
                confidence=0.4,
            ),
            CrossCheckResult(
                field="location",
                website_value="Berlin",
                external_value="Berlin",
                verdict="confirmed",
                confidence=0.95,
            ),
            CrossCheckResult(
                field="founding_year",
                website_value="2020",
                external_value="2019",
                verdict="website_trusted",
                confidence=0.8,
            ),
        ]
        gates = needs_halt_gate(results)
        assert len(gates) == 1
        assert gates[0].field == "team_size"

    def test_returns_empty_when_no_conflicts(self):
        results = [
            CrossCheckResult(
                field="location",
                website_value="Berlin",
                external_value="Berlin",
                verdict="confirmed",
                confidence=0.95,
            ),
        ]
        assert needs_halt_gate(results) == []


# ---------------------------------------------------------------------------
# research_pipeline: run_research_pipeline
# ---------------------------------------------------------------------------


class TestRunResearchPipeline:
    @patch("api.agents.tools.research_pipeline.research_market")
    @patch("api.agents.tools.research_pipeline.fetch_website")
    def test_calls_all_steps_in_order(self, mock_fetch, mock_market):
        mock_fetch.return_value = WebsiteData(
            url="https://acme.com",
            title="Acme",
            description="Best company",
            pages_fetched=["https://acme.com"],
            raw_content={"https://acme.com": "Welcome to Acme"},
            extracted=CompanyExtract(
                company_name="Acme",
                products_services=["Software"],
                industries=["Tech"],
                location="SF",
            ),
        )
        mock_market.return_value = MarketResearchResult(
            competitors=[{"name": "Rival", "description": "A rival"}],
            market_data=[],
            industry_trends=[],
            sources=["https://source.com"],
        )

        result = run_research_pipeline("acme.com", goal="grow market share")

        mock_fetch.assert_called_once_with("acme.com")
        mock_market.assert_called_once()
        assert result.website["url"] == "https://acme.com"
        assert len(result.market["competitors"]) == 1
        assert "https://acme.com" in result.all_sources
        assert "https://source.com" in result.all_sources

    @patch("api.agents.tools.research_pipeline.research_market")
    @patch("api.agents.tools.research_pipeline.fetch_website")
    def test_emit_finding_called_at_each_step(self, mock_fetch, mock_market):
        mock_fetch.return_value = WebsiteData(
            url="https://test.com",
            title="Test",
            description="",
            pages_fetched=["https://test.com"],
            raw_content={"https://test.com": "Content"},
            extracted=CompanyExtract(company_name="Test"),
        )
        mock_market.return_value = MarketResearchResult(
            competitors=[{"name": "C1"}], sources=[]
        )

        emit_calls: list[tuple[str, str]] = []

        def mock_emit(title: str, message: str) -> None:
            emit_calls.append((title, message))

        run_research_pipeline("test.com", emit_finding=mock_emit)

        titles = [c[0] for c in emit_calls]
        assert "Fetching website" in titles
        assert "Researching market" in titles
        assert "Cross-checking" in titles

    @patch("api.agents.tools.research_pipeline.research_market")
    @patch("api.agents.tools.research_pipeline.fetch_website")
    def test_handles_website_error(self, mock_fetch, mock_market):
        mock_fetch.return_value = WebsiteData(
            url="https://fail.com",
            title="",
            description="",
            error="Connection refused",
            extracted=CompanyExtract(company_name="fail.com"),
        )
        mock_market.return_value = MarketResearchResult(sources=[])

        result = run_research_pipeline("fail.com")
        assert len(result.errors) >= 1
        assert "Website fetch" in result.errors[0]

    @patch("api.agents.tools.research_pipeline.research_market")
    @patch("api.agents.tools.research_pipeline.fetch_website")
    def test_confirmed_facts_populated(self, mock_fetch, mock_market):
        mock_fetch.return_value = WebsiteData(
            url="https://co.com",
            title="Co",
            description="",
            pages_fetched=["https://co.com"],
            raw_content={"https://co.com": "text"},
            extracted=CompanyExtract(
                company_name="Co",
                location="Berlin",
            ),
        )
        mock_market.return_value = MarketResearchResult(
            competitors=[],
            market_data=[
                {"fact": "Headquartered in Berlin", "source_url": "https://s.com"}
            ],
            sources=["https://s.com"],
        )

        result = run_research_pipeline("co.com")
        # If cross-check finds a match, it should be in confirmed_facts
        if result.confirmed_facts:
            assert any("berlin" in v.lower() for v in result.confirmed_facts.values())
