"""Unit tests for shared Anthropic API client."""

import json
from unittest.mock import MagicMock, patch

import pytest

from api.services.anthropic_client import AnthropicClient, AnthropicResponse


class TestModelSelection:
    """Test model selection and configuration."""

    def test_default_model_is_haiku(self):
        client = AnthropicClient(api_key="test-key")
        assert client.default_model == "claude-haiku-4-5-20251001"

    def test_custom_default_model(self):
        client = AnthropicClient(api_key="test-key", default_model="claude-sonnet-4-5-20241022")
        assert client.default_model == "claude-sonnet-4-5-20241022"

    def test_query_uses_specified_model(self):
        client = AnthropicClient(api_key="test-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": "result"}],
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("api.services.anthropic_client.requests.post", return_value=mock_resp) as mock_post:
            client.query(
                system_prompt="system",
                user_prompt="user",
                model="claude-sonnet-4-5-20241022",
            )
            payload = mock_post.call_args[1]["json"]
            assert payload["model"] == "claude-sonnet-4-5-20241022"

    def test_query_uses_default_model_when_none_specified(self):
        client = AnthropicClient(api_key="test-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": "result"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("api.services.anthropic_client.requests.post", return_value=mock_resp) as mock_post:
            client.query(system_prompt="s", user_prompt="u")
            payload = mock_post.call_args[1]["json"]
            assert payload["model"] == "claude-haiku-4-5-20251001"


class TestRetryLogic:
    """Test retry behavior on transient errors."""

    def test_retry_on_529(self):
        """529 Overloaded should be retried."""
        import requests as req

        client = AnthropicClient(api_key="test-key", max_retries=2, retry_delay=0.01)

        fail_resp = MagicMock()
        fail_resp.status_code = 529
        fail_resp.raise_for_status.side_effect = req.HTTPError("Overloaded")

        success_resp = MagicMock()
        success_resp.status_code = 200
        success_resp.json.return_value = {
            "content": [{"type": "text", "text": "ok"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        success_resp.raise_for_status = MagicMock()

        with patch("api.services.anthropic_client.requests.post",
                    side_effect=[fail_resp, success_resp]) as mock_post:
            result = client.query(system_prompt="s", user_prompt="u")
            assert result.content == "ok"
            assert mock_post.call_count == 2

    def test_retry_on_500(self):
        """500 Server Error should be retried."""
        import requests as req

        client = AnthropicClient(api_key="test-key", max_retries=2, retry_delay=0.01)

        fail_resp = MagicMock()
        fail_resp.status_code = 500
        fail_resp.raise_for_status.side_effect = req.HTTPError("Server Error")

        success_resp = MagicMock()
        success_resp.status_code = 200
        success_resp.json.return_value = {
            "content": [{"type": "text", "text": "recovered"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        success_resp.raise_for_status = MagicMock()

        with patch("api.services.anthropic_client.requests.post",
                    side_effect=[fail_resp, success_resp]):
            result = client.query(system_prompt="s", user_prompt="u")
            assert result.content == "recovered"

    def test_no_retry_on_400(self):
        """400 Bad Request should NOT be retried."""
        import requests as req

        client = AnthropicClient(api_key="test-key", max_retries=3, retry_delay=0.01)

        fail_resp = MagicMock()
        fail_resp.status_code = 400
        fail_resp.raise_for_status.side_effect = req.HTTPError("Bad Request")

        with patch("api.services.anthropic_client.requests.post",
                    return_value=fail_resp) as mock_post:
            with pytest.raises(req.HTTPError):
                client.query(system_prompt="s", user_prompt="u")
            assert mock_post.call_count == 1


class TestCostTracking:
    """Test token usage and cost tracking."""

    def test_response_has_token_counts(self):
        client = AnthropicClient(api_key="test-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": "data"}],
            "usage": {"input_tokens": 500, "output_tokens": 200},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("api.services.anthropic_client.requests.post", return_value=mock_resp):
            result = client.query(system_prompt="s", user_prompt="u")
            assert result.input_tokens == 500
            assert result.output_tokens == 200

    def test_cost_estimate_haiku(self):
        """Haiku: $0.80/1M input + $4/1M output."""
        client = AnthropicClient(api_key="test-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": "data"}],
            "usage": {"input_tokens": 1000, "output_tokens": 500},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("api.services.anthropic_client.requests.post", return_value=mock_resp):
            result = client.query(system_prompt="s", user_prompt="u")
            assert result.cost_usd > 0
            # 1000 * 0.80/1M + 500 * 4.0/1M = 0.0008 + 0.002 = 0.0028
            assert abs(result.cost_usd - 0.0028) < 0.0001

    def test_response_has_model_used(self):
        client = AnthropicClient(api_key="test-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": "data"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("api.services.anthropic_client.requests.post", return_value=mock_resp):
            result = client.query(system_prompt="s", user_prompt="u",
                                  model="claude-sonnet-4-5-20241022")
            assert result.model == "claude-sonnet-4-5-20241022"


class TestAnthropicHeaders:
    """Test Anthropic-specific API headers."""

    def test_anthropic_version_header(self):
        client = AnthropicClient(api_key="test-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": "ok"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("api.services.anthropic_client.requests.post", return_value=mock_resp) as mock_post:
            client.query(system_prompt="s", user_prompt="u")
            headers = mock_post.call_args[1]["headers"]
            assert "anthropic-version" in headers
            assert headers["x-api-key"] == "test-key"

    def test_system_prompt_in_top_level_field(self):
        """Anthropic API uses top-level 'system' field, not in messages."""
        client = AnthropicClient(api_key="test-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": "ok"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("api.services.anthropic_client.requests.post", return_value=mock_resp) as mock_post:
            client.query(system_prompt="Be helpful", user_prompt="Hi")
            payload = mock_post.call_args[1]["json"]
            assert payload["system"] == "Be helpful"
            # Messages should only have user message
            assert len(payload["messages"]) == 1
            assert payload["messages"][0]["role"] == "user"
