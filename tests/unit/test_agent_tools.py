"""Unit tests for api/agents/tools.py — tool adapter and phase filtering."""

from api.agents.tools import (
    DEFAULT_TOOL_RATE_LIMIT,
    TOOL_RATE_LIMITS,
    execute_tool_call,
    summarize_tool_output,
    truncate_output,
)


class TestTruncateOutput:
    def test_short_string_unchanged(self):
        assert truncate_output("hello", 100) == "hello"

    def test_exact_limit_unchanged(self):
        text = "a" * 100
        assert truncate_output(text, 100) == text

    def test_over_limit_truncated(self):
        text = "a" * 200
        result = truncate_output(text, 100)
        assert len(result) == 100
        assert result.endswith("...")

    def test_default_limit(self):
        text = "a" * 3000
        result = truncate_output(text)
        assert len(result) == 2048


class TestSummarizeToolOutput:
    def test_none_output(self):
        result = summarize_tool_output("web_search", None)
        assert "web_search" in result

    def test_empty_dict(self):
        result = summarize_tool_output("web_search", {})
        assert "web_search" in result

    def test_with_summary_key(self):
        output = {"summary": "Found 5 results", "data": [1, 2, 3]}
        result = summarize_tool_output("web_search", output)
        assert result == "Found 5 results"

    def test_without_summary_key(self):
        output = {"data": [1, 2, 3]}
        result = summarize_tool_output("web_search", output)
        assert "web_search" in result


class TestExecuteToolCall:
    def test_unknown_tool(self):
        result = execute_tool_call(
            "nonexistent_tool",
            {},
            {"tenant_id": "t1"},
        )
        assert result["is_error"] is True
        assert "Unknown tool" in result["error_message"]
        assert result["duration_ms"] >= 0

    def test_unknown_tool_no_app(self):
        result = execute_tool_call(
            "also_nonexistent",
            {"arg": "val"},
            {"tenant_id": "t1"},
            app=None,
        )
        assert result["is_error"] is True


class TestRateLimits:
    def test_web_search_has_limit(self):
        assert "web_search" in TOOL_RATE_LIMITS
        assert TOOL_RATE_LIMITS["web_search"] == 5

    def test_default_limit(self):
        assert DEFAULT_TOOL_RATE_LIMIT == 15
