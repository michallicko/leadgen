"""Unit tests for AnthropicClient.stream_query() streaming support."""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests as req

from api.services.anthropic_client import AnthropicClient, MODEL_PRICING


def _sse_lines(*events):
    """Build a list of SSE byte-lines from (event_type, data_dict) tuples.

    Each event becomes:
        b'event: <type>'
        b'data: <json>'
        b''   (blank separator)
    """
    lines = []
    for event_type, data in events:
        lines.append("event: {}".format(event_type).encode())
        lines.append("data: {}".format(json.dumps(data)).encode())
        lines.append(b"")
    return lines


def _make_stream_response(status_code, sse_lines_list):
    """Create a mock response with iter_lines() returning SSE bytes."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = status_code == 200
    resp.iter_lines.return_value = iter(sse_lines_list)
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = req.HTTPError(
            "Error {}".format(status_code), response=resp,
        )
    # Context manager support for `with requests.post(...) as resp`
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestStreamQueryYieldsTextChunks:
    """stream_query() should yield text strings from content_block_delta events."""

    def test_yields_text_chunks(self):
        client = AnthropicClient(api_key="test-key")

        sse = _sse_lines(
            ("content_block_delta", {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "Hello"},
            }),
            ("content_block_delta", {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": " world"},
            }),
            ("message_stop", {"type": "message_stop"}),
        )

        mock_resp = _make_stream_response(200, sse)

        with patch("api.services.anthropic_client.requests.post", return_value=mock_resp):
            chunks = list(client.stream_query(
                messages=[{"role": "user", "content": "Say hello"}],
                system_prompt="You are helpful.",
            ))

        assert chunks == ["Hello", " world"]

    def test_yields_many_chunks(self):
        """Verify streaming works with many sequential chunks."""
        client = AnthropicClient(api_key="test-key")

        events = []
        for i in range(20):
            events.append(("content_block_delta", {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "chunk{} ".format(i)},
            }))
        events.append(("message_stop", {"type": "message_stop"}))

        mock_resp = _make_stream_response(200, _sse_lines(*events))

        with patch("api.services.anthropic_client.requests.post", return_value=mock_resp):
            chunks = list(client.stream_query(
                messages=[{"role": "user", "content": "Go"}],
                system_prompt="sys",
            ))

        assert len(chunks) == 20
        assert chunks[0] == "chunk0 "
        assert chunks[19] == "chunk19 "


class TestStreamQueryHandlesErrors:
    """stream_query() should raise on non-200 responses."""

    def test_raises_on_400(self):
        client = AnthropicClient(api_key="test-key")

        mock_resp = _make_stream_response(400, [])

        with patch("api.services.anthropic_client.requests.post", return_value=mock_resp):
            with pytest.raises(req.HTTPError):
                # Must consume the generator to trigger the error
                list(client.stream_query(
                    messages=[{"role": "user", "content": "bad"}],
                    system_prompt="sys",
                ))

    def test_raises_on_401(self):
        client = AnthropicClient(api_key="bad-key")

        mock_resp = _make_stream_response(401, [])

        with patch("api.services.anthropic_client.requests.post", return_value=mock_resp):
            with pytest.raises(req.HTTPError):
                list(client.stream_query(
                    messages=[{"role": "user", "content": "hi"}],
                    system_prompt="sys",
                ))

    def test_raises_on_500(self):
        client = AnthropicClient(api_key="test-key")

        mock_resp = _make_stream_response(500, [])

        with patch("api.services.anthropic_client.requests.post", return_value=mock_resp):
            with pytest.raises(req.HTTPError):
                list(client.stream_query(
                    messages=[{"role": "user", "content": "hi"}],
                    system_prompt="sys",
                ))


class TestStreamQuerySkipsNonTextEvents:
    """stream_query() should only yield text from text_delta events."""

    def test_skips_ping_and_message_start(self):
        client = AnthropicClient(api_key="test-key")

        sse = _sse_lines(
            ("message_start", {
                "type": "message_start",
                "message": {"id": "msg_123", "model": "claude-opus-4-6"},
            }),
            ("content_block_start", {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            }),
            ("ping", {"type": "ping"}),
            ("content_block_delta", {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "Only this"},
            }),
            ("content_block_stop", {
                "type": "content_block_stop",
                "index": 0,
            }),
            ("message_delta", {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": {"output_tokens": 10},
            }),
            ("message_stop", {"type": "message_stop"}),
        )

        mock_resp = _make_stream_response(200, sse)

        with patch("api.services.anthropic_client.requests.post", return_value=mock_resp):
            chunks = list(client.stream_query(
                messages=[{"role": "user", "content": "test"}],
                system_prompt="sys",
            ))

        assert chunks == ["Only this"]

    def test_skips_input_json_delta(self):
        """Tool-use deltas should not be yielded as text."""
        client = AnthropicClient(api_key="test-key")

        sse = _sse_lines(
            ("content_block_delta", {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "input_json_delta", "partial_json": '{"key":'},
            }),
            ("content_block_delta", {
                "type": "content_block_delta",
                "index": 1,
                "delta": {"type": "text_delta", "text": "Real text"},
            }),
            ("message_stop", {"type": "message_stop"}),
        )

        mock_resp = _make_stream_response(200, sse)

        with patch("api.services.anthropic_client.requests.post", return_value=mock_resp):
            chunks = list(client.stream_query(
                messages=[{"role": "user", "content": "tool test"}],
                system_prompt="sys",
            ))

        assert chunks == ["Real text"]

    def test_handles_malformed_data_lines(self):
        """Malformed JSON in data lines should be skipped, not crash."""
        client = AnthropicClient(api_key="test-key")

        lines = [
            b"event: content_block_delta",
            b"data: {this is not valid json}",
            b"",
            b"event: content_block_delta",
            b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"OK"}}',
            b"",
            b"event: message_stop",
            b'data: {"type":"message_stop"}',
            b"",
        ]

        mock_resp = _make_stream_response(200, lines)

        with patch("api.services.anthropic_client.requests.post", return_value=mock_resp):
            chunks = list(client.stream_query(
                messages=[{"role": "user", "content": "test"}],
                system_prompt="sys",
            ))

        assert chunks == ["OK"]


class TestStreamQueryPayload:
    """Verify the request payload sent by stream_query()."""

    def test_sends_stream_true(self):
        client = AnthropicClient(api_key="test-key")

        sse = _sse_lines(("message_stop", {"type": "message_stop"}))
        mock_resp = _make_stream_response(200, sse)

        with patch("api.services.anthropic_client.requests.post", return_value=mock_resp) as mock_post:
            list(client.stream_query(
                messages=[{"role": "user", "content": "hi"}],
                system_prompt="sys",
            ))

            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["json"]["stream"] is True
            assert call_kwargs["stream"] is True

    def test_sends_correct_headers(self):
        client = AnthropicClient(api_key="my-api-key")

        sse = _sse_lines(("message_stop", {"type": "message_stop"}))
        mock_resp = _make_stream_response(200, sse)

        with patch("api.services.anthropic_client.requests.post", return_value=mock_resp) as mock_post:
            list(client.stream_query(
                messages=[{"role": "user", "content": "hi"}],
                system_prompt="sys",
            ))

            headers = mock_post.call_args[1]["headers"]
            assert headers["x-api-key"] == "my-api-key"
            assert "anthropic-version" in headers
            assert headers["Content-Type"] == "application/json"

    def test_sends_messages_and_system(self):
        client = AnthropicClient(api_key="test-key")

        sse = _sse_lines(("message_stop", {"type": "message_stop"}))
        mock_resp = _make_stream_response(200, sse)

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "What's up?"},
        ]

        with patch("api.services.anthropic_client.requests.post", return_value=mock_resp) as mock_post:
            list(client.stream_query(
                messages=messages,
                system_prompt="Be concise",
            ))

            payload = mock_post.call_args[1]["json"]
            assert payload["system"] == "Be concise"
            assert payload["messages"] == messages

    def test_default_max_tokens(self):
        client = AnthropicClient(api_key="test-key")

        sse = _sse_lines(("message_stop", {"type": "message_stop"}))
        mock_resp = _make_stream_response(200, sse)

        with patch("api.services.anthropic_client.requests.post", return_value=mock_resp) as mock_post:
            list(client.stream_query(
                messages=[{"role": "user", "content": "hi"}],
                system_prompt="sys",
            ))

            payload = mock_post.call_args[1]["json"]
            assert payload["max_tokens"] == 4096

    def test_custom_max_tokens(self):
        client = AnthropicClient(api_key="test-key")

        sse = _sse_lines(("message_stop", {"type": "message_stop"}))
        mock_resp = _make_stream_response(200, sse)

        with patch("api.services.anthropic_client.requests.post", return_value=mock_resp) as mock_post:
            list(client.stream_query(
                messages=[{"role": "user", "content": "hi"}],
                system_prompt="sys",
                max_tokens=8192,
            ))

            payload = mock_post.call_args[1]["json"]
            assert payload["max_tokens"] == 8192


class TestOpus46Pricing:
    """Verify Opus 4.6 is in the pricing table."""

    def test_opus_46_in_model_pricing(self):
        assert "claude-opus-4-6" in MODEL_PRICING

    def test_opus_46_pricing_values(self):
        pricing = MODEL_PRICING["claude-opus-4-6"]
        assert pricing["input_per_m"] == 15.0
        assert pricing["output_per_m"] == 75.0

    def test_cost_estimate_opus_46(self):
        """Opus 4.6: $15/1M input + $75/1M output."""
        # 1000 input * 15/1M + 500 output * 75/1M = 0.015 + 0.0375 = 0.0525
        cost = AnthropicClient._estimate_cost("claude-opus-4-6", 1000, 500)
        assert abs(cost - 0.0525) < 0.0001
