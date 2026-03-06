"""Tests for conversation summarization (BL-263)."""

import pytest

from api.services.memory.conversation_manager import (
    RECENT_WINDOW,
    apply_floating_window,
    build_summarization_request,
    extract_facts_for_memory,
    needs_summarization,
)


def _make_messages(count, role_alternating=True):
    """Generate a list of test messages."""
    msgs = []
    for i in range(count):
        role = "user" if (i % 2 == 0 or not role_alternating) else "assistant"
        msgs.append({"role": role, "content": "Message {}".format(i + 1)})
    return msgs


class TestNeedsSummarization:
    def test_below_window_does_not_need_summary(self):
        msgs = _make_messages(5)
        assert needs_summarization(msgs) is False

    def test_at_window_does_not_need_summary(self):
        msgs = _make_messages(RECENT_WINDOW)
        assert needs_summarization(msgs) is False

    def test_above_window_needs_summary(self):
        msgs = _make_messages(RECENT_WINDOW + 5)
        assert needs_summarization(msgs) is True

    def test_excludes_summary_messages(self):
        msgs = _make_messages(8)
        summary = {
            "role": "system",
            "content": "Summary",
            "extra": {"type": "conversation_summary"},
        }
        msgs.insert(0, summary)
        # 8 real messages + 1 summary = should not need summarization
        assert needs_summarization(msgs) is False


class TestBuildSummarizationRequest:
    def test_returns_none_below_window(self):
        msgs = _make_messages(5)
        assert build_summarization_request(msgs) is None

    def test_returns_prompt_above_window(self):
        msgs = _make_messages(15)
        prompt = build_summarization_request(msgs)
        assert prompt is not None
        assert "Key decisions" in prompt
        assert "Message 1" in prompt

    def test_does_not_include_recent_in_prompt(self):
        msgs = _make_messages(15)
        prompt = build_summarization_request(msgs, window=10)
        # Last 10 messages should NOT be in the summarization prompt
        assert "Message 15" not in prompt
        # But earlier messages should be
        assert "Message 1" in prompt


class TestApplyFloatingWindow:
    def test_short_conversation_unchanged(self):
        msgs = _make_messages(5)
        result = apply_floating_window(msgs)
        assert len(result) == 5
        assert result == msgs

    def test_long_conversation_with_summary(self):
        msgs = _make_messages(20)
        result = apply_floating_window(msgs, summary_text="Test summary")
        # Should be: 1 summary + 10 recent
        assert len(result) == RECENT_WINDOW + 1
        assert "summary" in result[0]["content"].lower()
        assert result[-1]["content"] == "Message 20"

    def test_long_conversation_without_summary(self):
        msgs = _make_messages(20)
        result = apply_floating_window(msgs, summary_text=None)
        # Falls back to just recent window
        assert len(result) == RECENT_WINDOW
        assert result[-1]["content"] == "Message 20"

    def test_excludes_existing_summaries(self):
        msgs = _make_messages(8)
        summary = {
            "role": "system",
            "content": "Old summary",
            "extra": {"type": "conversation_summary"},
        }
        msgs.insert(0, summary)
        result = apply_floating_window(msgs)
        # Old summary should be excluded, only real messages
        assert len(result) == 8
        for m in result:
            assert m.get("extra", {}).get("type") != "conversation_summary"


class TestExtractFactsForMemory:
    def test_extracts_decision(self):
        user = "Let's focus on enterprise SaaS."
        assistant = "Great, we've decided to target enterprise SaaS companies."
        facts = extract_facts_for_memory(user, assistant)
        assert len(facts) >= 1
        assert any(f["type"] == "decision" for f in facts)

    def test_extracts_preference(self):
        user = "I prefer a consultative tone in our outreach."
        assistant = "Understood, I'll use a consultative tone."
        facts = extract_facts_for_memory(user, assistant)
        assert any(f["type"] == "preference" for f in facts)

    def test_no_facts_from_greeting(self):
        user = "Hello!"
        assistant = "Hi there! How can I help you today?"
        facts = extract_facts_for_memory(user, assistant)
        assert len(facts) == 0

    def test_returns_list(self):
        facts = extract_facts_for_memory("test", "test response")
        assert isinstance(facts, list)
