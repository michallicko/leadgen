"""Unit tests for shared Perplexity API client."""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from api.services.perplexity_client import PerplexityClient, PerplexityResponse


class TestModelSelection:
    """Test model selection and configuration."""

    def test_default_model_is_sonar(self):
        client = PerplexityClient(api_key="test-key")
        assert client.default_model == "sonar"

    def test_custom_default_model(self):
        client = PerplexityClient(api_key="test-key", default_model="sonar-pro")
        assert client.default_model == "sonar-pro"

    def test_query_uses_specified_model(self):
        client = PerplexityClient(api_key="test-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "test response"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("api.services.perplexity_client.requests.post", return_value=mock_resp) as mock_post:
            client.query(
                system_prompt="system",
                user_prompt="user",
                model="sonar-pro",
            )
            payload = mock_post.call_args[1]["json"]
            assert payload["model"] == "sonar-pro"

    def test_query_uses_default_model_when_none_specified(self):
        client = PerplexityClient(api_key="test-key", default_model="sonar")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "test"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("api.services.perplexity_client.requests.post", return_value=mock_resp) as mock_post:
            client.query(system_prompt="s", user_prompt="u")
            payload = mock_post.call_args[1]["json"]
            assert payload["model"] == "sonar"


class TestRetryLogic:
    """Test retry behavior on transient errors."""

    def test_retry_on_429(self):
        """429 Too Many Requests should be retried."""
        import requests as req

        client = PerplexityClient(api_key="test-key", max_retries=2, retry_delay=0.01)

        fail_resp = MagicMock()
        fail_resp.status_code = 429
        fail_resp.raise_for_status.side_effect = req.HTTPError("Too Many Requests")

        success_resp = MagicMock()
        success_resp.status_code = 200
        success_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        success_resp.raise_for_status = MagicMock()

        with patch("api.services.perplexity_client.requests.post",
                    side_effect=[fail_resp, success_resp]) as mock_post:
            result = client.query(system_prompt="s", user_prompt="u")
            assert result.content == "ok"
            assert mock_post.call_count == 2

    def test_retry_on_500(self):
        """500 Server Error should be retried."""
        import requests as req

        client = PerplexityClient(api_key="test-key", max_retries=2, retry_delay=0.01)

        fail_resp = MagicMock()
        fail_resp.status_code = 500
        fail_resp.raise_for_status.side_effect = req.HTTPError("Server Error")

        success_resp = MagicMock()
        success_resp.status_code = 200
        success_resp.json.return_value = {
            "choices": [{"message": {"content": "recovered"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        success_resp.raise_for_status = MagicMock()

        with patch("api.services.perplexity_client.requests.post",
                    side_effect=[fail_resp, success_resp]):
            result = client.query(system_prompt="s", user_prompt="u")
            assert result.content == "recovered"

    def test_no_retry_on_400(self):
        """400 Bad Request should NOT be retried."""
        import requests as req

        client = PerplexityClient(api_key="test-key", max_retries=3, retry_delay=0.01)

        fail_resp = MagicMock()
        fail_resp.status_code = 400
        fail_resp.raise_for_status.side_effect = req.HTTPError("Bad Request")

        with patch("api.services.perplexity_client.requests.post",
                    return_value=fail_resp) as mock_post:
            with pytest.raises(req.HTTPError):
                client.query(system_prompt="s", user_prompt="u")
            assert mock_post.call_count == 1  # No retries

    def test_retries_exhausted_raises(self):
        """After max retries, should raise the error."""
        import requests as req

        client = PerplexityClient(api_key="test-key", max_retries=2, retry_delay=0.01)

        fail_resp = MagicMock()
        fail_resp.status_code = 429
        fail_resp.raise_for_status.side_effect = req.HTTPError("Rate limited")

        with patch("api.services.perplexity_client.requests.post",
                    return_value=fail_resp) as mock_post:
            with pytest.raises(req.HTTPError):
                client.query(system_prompt="s", user_prompt="u")
            assert mock_post.call_count == 3  # 1 initial + 2 retries


class TestCostTracking:
    """Test token usage and cost tracking in response."""

    def test_response_has_token_counts(self):
        client = PerplexityClient(api_key="test-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "data"}}],
            "usage": {"prompt_tokens": 350, "completion_tokens": 200},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("api.services.perplexity_client.requests.post", return_value=mock_resp):
            result = client.query(system_prompt="s", user_prompt="u")
            assert result.input_tokens == 350
            assert result.output_tokens == 200

    def test_response_has_model_used(self):
        client = PerplexityClient(api_key="test-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "data"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("api.services.perplexity_client.requests.post", return_value=mock_resp):
            result = client.query(system_prompt="s", user_prompt="u", model="sonar-pro")
            assert result.model == "sonar-pro"

    def test_cost_estimate_sonar(self):
        """Sonar model: $1/1M input + $1/1M output tokens."""
        client = PerplexityClient(api_key="test-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "data"}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 500},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("api.services.perplexity_client.requests.post", return_value=mock_resp):
            result = client.query(system_prompt="s", user_prompt="u", model="sonar")
            assert result.cost_usd > 0
            # 1500 tokens at $1/1M = $0.0015
            assert abs(result.cost_usd - 0.0015) < 0.0001


class TestTimeoutHandling:
    """Test timeout configuration."""

    def test_default_timeout(self):
        client = PerplexityClient(api_key="test-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("api.services.perplexity_client.requests.post", return_value=mock_resp) as mock_post:
            client.query(system_prompt="s", user_prompt="u")
            assert mock_post.call_args[1]["timeout"] == 60

    def test_custom_timeout(self):
        client = PerplexityClient(api_key="test-key", timeout=120)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("api.services.perplexity_client.requests.post", return_value=mock_resp) as mock_post:
            client.query(system_prompt="s", user_prompt="u")
            assert mock_post.call_args[1]["timeout"] == 120


class TestQueryParameters:
    """Test that query parameters are properly forwarded."""

    def test_max_tokens_forwarded(self):
        client = PerplexityClient(api_key="test-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("api.services.perplexity_client.requests.post", return_value=mock_resp) as mock_post:
            client.query(system_prompt="s", user_prompt="u", max_tokens=800)
            payload = mock_post.call_args[1]["json"]
            assert payload["max_tokens"] == 800

    def test_temperature_forwarded(self):
        client = PerplexityClient(api_key="test-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("api.services.perplexity_client.requests.post", return_value=mock_resp) as mock_post:
            client.query(system_prompt="s", user_prompt="u", temperature=0.5)
            payload = mock_post.call_args[1]["json"]
            assert payload["temperature"] == 0.5

    def test_search_recency_filter_forwarded(self):
        client = PerplexityClient(api_key="test-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("api.services.perplexity_client.requests.post", return_value=mock_resp) as mock_post:
            client.query(system_prompt="s", user_prompt="u", search_recency_filter="week")
            payload = mock_post.call_args[1]["json"]
            assert payload["search_recency_filter"] == "week"
