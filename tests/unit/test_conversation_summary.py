"""Tests for conversation summarization service."""

from unittest.mock import patch


from api.services.memory.conversation_summary import (
    MESSAGE_THRESHOLD,
    RE_SUMMARIZE_GROWTH,
    SUMMARIZE_COUNT,
    _fallback_summarize,
    compact_conversation,
    format_summary_for_context,
    should_summarize,
    summarize_messages,
)


class TestShouldSummarize:
    def test_below_threshold_no_summary(self):
        assert should_summarize(10, False) is False

    def test_at_threshold_no_summary(self):
        assert should_summarize(MESSAGE_THRESHOLD, False) is False

    def test_above_threshold_triggers(self):
        assert should_summarize(MESSAGE_THRESHOLD + 1, False) is True

    def test_with_existing_summary_uses_re_summarize(self):
        assert should_summarize(RE_SUMMARIZE_GROWTH, True) is False
        assert should_summarize(RE_SUMMARIZE_GROWTH + 1, True) is True


class TestCompactConversation:
    def test_below_threshold_no_change(self):
        messages = [{"role": "user", "content": "hi"}] * 10
        result = compact_conversation(messages)
        assert result["summary"] is None
        assert result["messages"] == messages
        assert result["summarized_count"] == 0

    def test_above_threshold_summarizes(self):
        messages = [
            {"role": "user", "content": "Message {}".format(i)} for i in range(20)
        ]
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}):
            result = compact_conversation(messages)
            assert result["summary"] is not None
            assert result["summarized_count"] == SUMMARIZE_COUNT
            assert len(result["messages"]) == 20 - SUMMARIZE_COUNT


class TestFallbackSummarize:
    def test_extracts_user_messages(self):
        messages = [
            {"role": "user", "content": "I want to target SaaS companies"},
            {"role": "assistant", "content": "Sure, I can help with that"},
            {"role": "user", "content": "Focus on DACH region"},
        ]
        result = _fallback_summarize(messages, None)
        assert "SaaS" in result
        assert "DACH" in result

    def test_includes_existing_summary(self):
        messages = [{"role": "user", "content": "New topic"}]
        result = _fallback_summarize(messages, "Previous context about ICP")
        assert "Previous" in result

    def test_empty_messages(self):
        result = _fallback_summarize([], None)
        assert "No significant" in result


class TestFormatSummaryForContext:
    def test_wraps_summary(self):
        result = format_summary_for_context("User approved SaaS ICP.")
        assert "Conversation Summary" in result
        assert "User approved SaaS ICP." in result
        assert "End of Summary" in result


class TestSummarizeMessages:
    def test_returns_existing_for_empty_messages(self):
        result = summarize_messages([], "existing summary")
        assert result == "existing summary"

    def test_fallback_when_no_api_key(self):
        messages = [
            {"role": "user", "content": "Target SaaS in Germany"},
            {"role": "assistant", "content": "Great choice"},
        ]
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}):
            result = summarize_messages(messages)
            assert result is not None
            assert "SaaS" in result
