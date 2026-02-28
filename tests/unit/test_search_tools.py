"""Tests for web search tool handler (SEARCH feature).

Tests cover:
- Successful search with answer and citations
- Missing API key returns helpful error
- Empty/long query validation
- Timeout handling (graceful error)
- HTTP error handling (graceful error)
- Cost logging via LlmUsageLog
- Tool definition registered correctly
"""

import os
from unittest.mock import MagicMock, patch

import pytest
import requests

from api.services.search_tools import (
    SEARCH_TOOLS,
    MAX_QUERY_LENGTH,
    web_search,
)
from api.services.tool_registry import ToolContext, clear_registry, register_tool


@pytest.fixture(autouse=True)
def _register_search_tools():
    """Register search tools for each test."""
    clear_registry()
    for tool in SEARCH_TOOLS:
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


class FakePerplexityResponse:
    """Fake response from PerplexityClient.query()."""

    def __init__(
        self,
        content="Search result text.",
        model="sonar",
        input_tokens=50,
        output_tokens=100,
        cost_usd=0.00015,
    ):
        self.content = content
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cost_usd = cost_usd


class TestWebSearch:
    def test_empty_query_returns_error(self, db, seed_tenant, ctx):
        result = web_search({"query": ""}, ctx)
        assert "error" in result
        assert "required" in result["error"].lower()

    def test_long_query_returns_error(self, db, seed_tenant, ctx):
        result = web_search({"query": "x" * (MAX_QUERY_LENGTH + 1)}, ctx)
        assert "error" in result
        assert "too long" in result["error"].lower()

    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": ""})
    def test_missing_api_key_returns_error(self, db, seed_tenant, ctx):
        result = web_search({"query": "test search"}, ctx)
        assert "error" in result
        assert "not configured" in result["error"].lower()

    @patch("api.services.search_tools._get_perplexity_client")
    def test_successful_search(self, mock_get_client, db, seed_tenant, ctx):
        mock_client = MagicMock()
        mock_client.query.return_value = FakePerplexityResponse(
            content="AI adoption is growing in European manufacturing.",
            model="sonar",
            input_tokens=50,
            output_tokens=100,
        )
        mock_get_client.return_value = mock_client

        result = web_search({"query": "AI adoption in manufacturing"}, ctx)

        assert "error" not in result
        assert result["answer"] == "AI adoption is growing in European manufacturing."
        assert isinstance(result["citations"], list)
        assert "summary" in result

    @patch("api.services.search_tools._get_perplexity_client")
    def test_timeout_returns_graceful_error(self, mock_get_client, db, seed_tenant, ctx):
        mock_client = MagicMock()
        mock_client.query.side_effect = requests.Timeout("Connection timed out")
        mock_get_client.return_value = mock_client

        result = web_search({"query": "slow search"}, ctx)

        assert "error" in result
        assert "timed out" in result["error"].lower()

    @patch("api.services.search_tools._get_perplexity_client")
    def test_http_error_returns_graceful_error(self, mock_get_client, db, seed_tenant, ctx):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 429
        exc = requests.HTTPError(response=mock_response)
        mock_client.query.side_effect = exc
        mock_get_client.return_value = mock_client

        result = web_search({"query": "rate limited"}, ctx)

        assert "error" in result
        assert "unavailable" in result["error"].lower()

    @patch("api.services.search_tools._get_perplexity_client")
    def test_unexpected_error_returns_graceful_error(self, mock_get_client, db, seed_tenant, ctx):
        mock_client = MagicMock()
        mock_client.query.side_effect = RuntimeError("Something unexpected")
        mock_get_client.return_value = mock_client

        result = web_search({"query": "broken search"}, ctx)

        assert "error" in result
        assert "unavailable" in result["error"].lower()

    @patch("api.services.search_tools._get_perplexity_client")
    def test_cost_logged_on_success(self, mock_get_client, db, seed_tenant, ctx):
        mock_client = MagicMock()
        mock_client.query.return_value = FakePerplexityResponse(
            content="Result",
            model="sonar",
            input_tokens=50,
            output_tokens=100,
        )
        mock_get_client.return_value = mock_client

        web_search({"query": "logged search"}, ctx)

        # Check LlmUsageLog was created
        from api.models import LlmUsageLog
        logs = LlmUsageLog.query.filter_by(
            tenant_id=str(seed_tenant.id),
            operation="agent_web_search",
        ).all()
        assert len(logs) == 1
        assert logs[0].provider == "perplexity"
        assert logs[0].model == "sonar"
        assert logs[0].input_tokens == 50
        assert logs[0].output_tokens == 100

    @patch("api.services.search_tools._get_perplexity_client")
    def test_no_cost_logged_on_error(self, mock_get_client, db, seed_tenant, ctx):
        mock_client = MagicMock()
        mock_client.query.side_effect = requests.Timeout("timeout")
        mock_get_client.return_value = mock_client

        web_search({"query": "timeout search"}, ctx)

        from api.models import LlmUsageLog
        logs = LlmUsageLog.query.filter_by(
            tenant_id=str(seed_tenant.id),
            operation="agent_web_search",
        ).all()
        assert len(logs) == 0


class TestSearchToolDefinitions:
    def test_tool_registered(self):
        from api.services.tool_registry import get_tool
        assert get_tool("web_search") is not None

    def test_tool_count(self):
        assert len(SEARCH_TOOLS) == 1

    def test_tool_schema_valid(self):
        tool = SEARCH_TOOLS[0]
        assert tool.input_schema["type"] == "object"
        assert "query" in tool.input_schema["properties"]
        assert "query" in tool.input_schema["required"]
