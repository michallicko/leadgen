"""Tests for auto-save detection of important decisions."""

from api.services.memory.auto_save import (
    detect_saveable_content,
    should_auto_save,
)


class TestDetectSaveableContent:
    def test_decision_detected(self):
        result = detect_saveable_content(
            "I want to focus on SaaS companies in the DACH region.",
            role="user",
        )
        assert result is not None
        assert result["content_type"] == "decision"

    def test_preference_detected(self):
        result = detect_saveable_content(
            "I prefer a professional tone in all outreach messages.",
            role="user",
        )
        assert result is not None
        assert result["content_type"] == "preference"

    def test_constraint_detected(self):
        result = detect_saveable_content(
            "Budget is limited to 5000 EUR per month for campaigns.",
            role="user",
        )
        assert result is not None
        assert result["content_type"] == "constraint"

    def test_approval_detected(self):
        result = detect_saveable_content(
            "Yes, that's exactly what I need. Let's go with this strategy.",
            role="user",
        )
        assert result is not None
        assert result["content_type"] == "decision"

    def test_rejection_detected(self):
        result = detect_saveable_content(
            "No, don't contact companies under 50 employees.",
            role="user",
        )
        assert result is not None

    def test_assistant_messages_ignored(self):
        result = detect_saveable_content(
            "I recommend focusing on SaaS companies.",
            role="assistant",
        )
        assert result is None

    def test_short_messages_ignored(self):
        result = detect_saveable_content("ok", role="user")
        assert result is None

    def test_empty_messages_ignored(self):
        result = detect_saveable_content("", role="user")
        assert result is None

    def test_filler_not_detected(self):
        result = detect_saveable_content(
            "Thanks for the information about that topic.",
            role="user",
        )
        assert result is None

    def test_lets_go_with(self):
        result = detect_saveable_content(
            "Let's go with the professional tone for our emails.",
            role="user",
        )
        assert result is not None
        assert result["content_type"] == "decision"

    def test_exclude_constraint(self):
        result = detect_saveable_content(
            "Don't contact companies that have less than 10 employees, exclude them.",
            role="user",
        )
        assert result is not None
        assert result["content_type"] == "constraint"


class TestShouldAutoSave:
    def test_decision_keywords(self):
        assert should_auto_save("I decide to focus on B2B SaaS") is True

    def test_preference_keywords(self):
        assert should_auto_save("I prefer a casual tone for outreach") is True

    def test_constraint_keywords(self):
        assert should_auto_save("Budget must not exceed 10000 per month") is True

    def test_filler_ignored(self):
        assert should_auto_save("Can you show me the list?") is False

    def test_short_message_ignored(self):
        assert should_auto_save("yes") is False

    def test_assistant_ignored(self):
        assert should_auto_save("I decide to do this", role="assistant") is False
