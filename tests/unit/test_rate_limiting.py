"""Tests for agent executor rate limiting.

Tests cover:
- Tool calls within limits succeed
- Tool calls exceeding per-tool limit are rejected with error
- Different tools have independent counters
- Custom rate limits (e.g. web_search) from TOOL_RATE_LIMITS are respected
"""

import pytest

from api.services.agent_executor import (
    DEFAULT_TOOL_RATE_LIMIT,
    TOOL_RATE_LIMITS,
    execute_agent_turn,
)
from api.services.tool_registry import (
    ToolContext,
    ToolDefinition,
    clear_registry,
    register_tool,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_registry()
    yield
    clear_registry()


def _make_echo_tool(name="echo_tool"):
    """Register a simple tool that returns its input."""
    tool = ToolDefinition(
        name=name,
        description="Echo tool for testing",
        input_schema={"type": "object", "properties": {}},
        handler=lambda args, ctx: {"echo": args},
    )
    register_tool(tool)
    return tool


class FakeClient:
    """Fake AnthropicClient that returns pre-scripted responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.default_model = "test-model"
        self.call_index = 0

    def query_with_tools(self, **kwargs):
        resp = self.responses[self.call_index]
        self.call_index += 1
        return resp

    @staticmethod
    def _estimate_cost(model, input_tokens, output_tokens):
        return 0.0


def _tool_use_response(tool_calls):
    """Build a response dict with tool_use blocks."""
    content = []
    for name, input_args, call_id in tool_calls:
        content.append({
            "type": "tool_use",
            "id": call_id,
            "name": name,
            "input": input_args,
        })
    return {
        "content": content,
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def _text_response(text):
    """Build a final text response."""
    return {
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


class TestRateLimiting:
    def test_default_limit_allows_calls(self, app):
        """Tool calls within the default limit succeed."""
        _make_echo_tool("my_tool")

        # Make 5 calls (default limit) then a final text response
        tool_calls = [
            ("my_tool", {"n": i}, "call_{}".format(i))
            for i in range(DEFAULT_TOOL_RATE_LIMIT)
        ]
        responses = [
            _tool_use_response([tc]) for tc in tool_calls
        ] + [_text_response("done")]

        client = FakeClient(responses)
        ctx = ToolContext(tenant_id="t1")

        events = list(execute_agent_turn(
            client=client,
            system_prompt="test",
            messages=[],
            tools=[],
            tool_context=ctx,
            app=app,
        ))

        # All 5 should succeed
        results = [e for e in events if e.type == "tool_result"]
        assert len(results) == DEFAULT_TOOL_RATE_LIMIT
        for r in results:
            assert r.data["status"] == "success"

    def test_exceeding_default_limit_returns_error(self, app):
        """The 6th call to a tool with default limit is rejected."""
        _make_echo_tool("my_tool")

        # Make 6 calls (one over limit)
        tool_calls = [
            ("my_tool", {"n": i}, "call_{}".format(i))
            for i in range(DEFAULT_TOOL_RATE_LIMIT + 1)
        ]
        responses = [
            _tool_use_response([tc]) for tc in tool_calls
        ] + [_text_response("done")]

        client = FakeClient(responses)
        ctx = ToolContext(tenant_id="t1")

        events = list(execute_agent_turn(
            client=client,
            system_prompt="test",
            messages=[],
            tools=[],
            tool_context=ctx,
            app=app,
        ))

        results = [e for e in events if e.type == "tool_result"]
        assert len(results) == DEFAULT_TOOL_RATE_LIMIT + 1

        # First 5 succeed, 6th is error
        for r in results[:DEFAULT_TOOL_RATE_LIMIT]:
            assert r.data["status"] == "success"
        assert results[DEFAULT_TOOL_RATE_LIMIT].data["status"] == "error"
        assert "Rate limit" in results[DEFAULT_TOOL_RATE_LIMIT].data["summary"]

    def test_web_search_custom_limit(self, app):
        """web_search has a custom rate limit from TOOL_RATE_LIMITS."""
        _make_echo_tool("web_search")

        ws_limit = TOOL_RATE_LIMITS["web_search"]
        num_calls = ws_limit + 1
        tool_calls = [
            ("web_search", {"q": "test"}, "ws_{}".format(i))
            for i in range(num_calls)
        ]
        responses = [
            _tool_use_response([tc]) for tc in tool_calls
        ] + [_text_response("done")]

        client = FakeClient(responses)
        ctx = ToolContext(tenant_id="t1")

        events = list(execute_agent_turn(
            client=client,
            system_prompt="test",
            messages=[],
            tools=[],
            tool_context=ctx,
            app=app,
        ))

        results = [e for e in events if e.type == "tool_result"]
        assert len(results) == num_calls

        for r in results[:ws_limit]:
            assert r.data["status"] == "success"
        assert results[ws_limit].data["status"] == "error"
        assert "Rate limit" in results[ws_limit].data["summary"]

    def test_independent_counters(self, app):
        """Different tools have independent rate counters."""
        _make_echo_tool("tool_a")
        _make_echo_tool("tool_b")

        # 5 calls to tool_a + 5 calls to tool_b = 10 total, all within limits
        tool_calls = (
            [("tool_a", {}, "a_{}".format(i)) for i in range(5)]
            + [("tool_b", {}, "b_{}".format(i)) for i in range(5)]
        )
        responses = [
            _tool_use_response([tc]) for tc in tool_calls
        ] + [_text_response("done")]

        client = FakeClient(responses)
        ctx = ToolContext(tenant_id="t1")

        events = list(execute_agent_turn(
            client=client,
            system_prompt="test",
            messages=[],
            tools=[],
            tool_context=ctx,
            app=app,
        ))

        results = [e for e in events if e.type == "tool_result"]
        assert len(results) == 10
        for r in results:
            assert r.data["status"] == "success"
