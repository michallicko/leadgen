"""Unit tests for mid-plan interruption handling (BL-1018).

Tests the interrupt classifier (keyword + Haiku fallback) and
the interrupt handlers (correction, stop, question, redirect).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from api.agents.interrupt_classifier import (
    InterruptClassification,
    _keyword_classify,
    classify_interrupt,
)
from api.agents.interrupt_handlers import (
    handle_correction,
    handle_question,
    handle_redirect,
    handle_stop,
    process_interrupt,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_state(**overrides) -> dict:
    """Build a minimal PlannerState-like dict for testing."""
    base = {
        "messages": [],
        "tool_context": {},
        "iteration": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cost_usd": "0",
        "model": "",
        "plan_id": "test-plan",
        "plan_config": {
            "id": "test-plan",
            "name": "Test Plan",
            "phases": [
                "research_company",
                "research_market",
                "build_strategy",
                "review_and_score",
            ],
        },
        "current_phase": "research_company",
        "phase_index": 0,
        "phase_results": {},
        "research_data": {},
        "user_corrections": [],
        "section_completeness": {},
        "is_interrupted": True,
        "interrupt_message": "",
        "interrupt_type": "",
        "findings": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Keyword classifier tests
# ---------------------------------------------------------------------------


class TestKeywordClassifier:
    """Tests for the keyword-based fast path classifier."""

    @pytest.mark.parametrize(
        "message,expected_type",
        [
            ("stop", "stop"),
            ("Stop everything", "stop"),
            ("wait a moment", "stop"),
            ("hold on", "stop"),
            ("pause please", "stop"),
            ("cancel this", "stop"),
            ("abort", "stop"),
        ],
    )
    def test_stop_signals(self, message: str, expected_type: str):
        result = _keyword_classify(message)
        assert result is not None
        assert result.type == expected_type
        assert result.confidence >= 0.8

    @pytest.mark.parametrize(
        "message,expected_type",
        [
            ("that's wrong, we sell to SMBs", "correction"),
            ("that's not right", "correction"),
            ("actually we pivoted to enterprise", "correction"),
            ("we don't do festivals anymore", "correction"),
            ("no, we focus on B2B", "correction"),
            ("incorrect — our market is DACH only", "correction"),
            ("not anymore, we stopped that product line", "correction"),
            ("we pivoted last year", "correction"),
        ],
    )
    def test_correction_signals(self, message: str, expected_type: str):
        result = _keyword_classify(message)
        assert result is not None
        assert result.type == expected_type
        assert result.confidence >= 0.8

    @pytest.mark.parametrize(
        "message,expected_type",
        [
            ("what did you find so far?", "question"),
            ("how far along are you?", "question"),
            ("why did you choose that approach?", "question"),
            ("show me the competitors", "question"),
            ("can you explain that?", "question"),
            ("did you check their website?", "question"),
            ("is this going well?", "question"),
        ],
    )
    def test_question_signals(self, message: str, expected_type: str):
        result = _keyword_classify(message)
        assert result is not None
        assert result.type == expected_type
        assert result.confidence >= 0.8

    @pytest.mark.parametrize(
        "message,expected_type",
        [
            ("focus on DACH market instead", "redirect"),
            ("switch to competitors analysis", "redirect"),
            ("let's do the strategy first", "redirect"),
            ("skip to review", "redirect"),
            ("move to build strategy", "redirect"),
            ("actually focus on enterprise segment", "redirect"),
        ],
    )
    def test_redirect_signals(self, message: str, expected_type: str):
        result = _keyword_classify(message)
        assert result is not None
        assert result.type == expected_type
        assert result.confidence >= 0.8

    def test_ambiguous_returns_none(self):
        """Messages without clear signals should return None."""
        result = _keyword_classify("I think we should consider something else")
        assert result is None

    def test_empty_message_defaults_to_correction(self):
        """Empty messages default to correction with low confidence."""
        result = _keyword_classify("")
        assert result is not None
        assert result.type == "correction"
        assert result.confidence < 0.8


# ---------------------------------------------------------------------------
# Full classifier tests (keyword + Haiku)
# ---------------------------------------------------------------------------


class TestClassifyInterrupt:
    """Tests for the two-stage classify_interrupt function."""

    def test_clear_stop_uses_keywords(self):
        """Clear stop signals should be classified by keywords, not Haiku."""
        result = classify_interrupt("stop", "research_company", {})
        assert result.type == "stop"
        assert result.confidence >= 0.8

    def test_clear_correction_uses_keywords(self):
        result = classify_interrupt("that's wrong", "research_company", {})
        assert result.type == "correction"
        assert result.confidence >= 0.8

    @patch("api.agents.interrupt_classifier._haiku_classify")
    def test_ambiguous_falls_through_to_haiku(self, mock_haiku):
        """Ambiguous messages should fall through to Haiku classification."""
        mock_haiku.return_value = InterruptClassification(
            type="redirect",
            confidence=0.75,
            extracted_info={"new_focus": "enterprise market"},
        )

        result = classify_interrupt(
            "I think we should consider the enterprise segment",
            "research_company",
            {},
        )

        mock_haiku.assert_called_once()
        assert result.type == "redirect"

    @patch("api.agents.interrupt_classifier._haiku_classify")
    def test_haiku_failure_defaults_to_correction(self, mock_haiku):
        """If Haiku fails, should default to correction."""
        mock_haiku.return_value = InterruptClassification(
            type="correction",
            confidence=0.5,
            extracted_info={"correction": "ambiguous message"},
        )

        result = classify_interrupt(
            "hmm interesting",
            "research_company",
            {},
        )

        assert result.type == "correction"


# ---------------------------------------------------------------------------
# Handler tests
# ---------------------------------------------------------------------------


class TestHandleCorrection:
    """Tests for the correction interrupt handler."""

    def test_adds_to_user_corrections(self):
        state = _make_state(
            interrupt_message="we don't do festivals",
            user_corrections=["previous correction"],
        )
        classification = {
            "type": "correction",
            "confidence": 0.9,
            "extracted_info": {"correction": "we don't do festivals"},
        }

        result = handle_correction(state, classification)

        assert len(result["user_corrections"]) == 2
        assert "we don't do festivals" in result["user_corrections"]
        assert "previous correction" in result["user_corrections"]

    def test_clears_interrupt_flags(self):
        state = _make_state(interrupt_message="that's wrong")
        classification = {
            "type": "correction",
            "confidence": 0.9,
            "extracted_info": {"correction": "that's wrong"},
        }

        result = handle_correction(state, classification)

        assert result["is_interrupted"] is False
        assert result["interrupt_message"] == ""

    def test_sets_interrupt_type_to_correction(self):
        state = _make_state(interrupt_message="wrong")
        classification = {
            "type": "correction",
            "confidence": 0.9,
            "extracted_info": {"correction": "wrong"},
        }

        result = handle_correction(state, classification)
        assert result["interrupt_type"] == "correction"


class TestHandleStop:
    """Tests for the stop interrupt handler."""

    def test_sets_stop_type_for_end_routing(self):
        state = _make_state(
            interrupt_message="stop",
            phase_results={
                "research_company": {"status": "complete", "data": {}},
            },
        )
        classification = {
            "type": "stop",
            "confidence": 0.9,
            "extracted_info": {"reason": "stop"},
        }

        result = handle_stop(state, classification)

        assert result["interrupt_type"] == "stop"
        assert result["is_interrupted"] is False

    def test_preserves_completed_phases(self):
        """Stop should not clear phase_results."""
        state = _make_state(
            interrupt_message="cancel",
            phase_results={
                "research_company": {"status": "complete", "data": {}},
                "research_market": {"status": "complete", "data": {}},
            },
        )
        classification = {
            "type": "stop",
            "confidence": 0.9,
            "extracted_info": {"reason": "cancel"},
        }

        result = handle_stop(state, classification)

        # phase_results should NOT be in the update (not overwritten)
        assert "phase_results" not in result


class TestHandleQuestion:
    """Tests for the question interrupt handler."""

    def test_clears_interrupt_flags_for_resume(self):
        state = _make_state(interrupt_message="what did you find?")
        classification = {
            "type": "question",
            "confidence": 0.85,
            "extracted_info": {"question": "what did you find?"},
        }

        result = handle_question(state, classification)

        assert result["is_interrupted"] is False
        assert result["interrupt_message"] == ""

    def test_sets_question_type(self):
        state = _make_state(interrupt_message="how far?")
        classification = {
            "type": "question",
            "confidence": 0.85,
            "extracted_info": {"question": "how far?"},
        }

        result = handle_question(state, classification)
        assert result["interrupt_type"] == "question"


class TestHandleRedirect:
    """Tests for the redirect interrupt handler."""

    def test_adds_redirect_to_corrections(self):
        state = _make_state(interrupt_message="focus on DACH market")
        classification = {
            "type": "redirect",
            "confidence": 0.85,
            "extracted_info": {"new_focus": "focus on DACH market"},
        }

        result = handle_redirect(state, classification)

        assert any("REDIRECT:" in c for c in result["user_corrections"])

    def test_clears_interrupt_flags(self):
        state = _make_state(interrupt_message="switch to strategy")
        classification = {
            "type": "redirect",
            "confidence": 0.85,
            "extracted_info": {"new_focus": "switch to strategy"},
        }

        result = handle_redirect(state, classification)

        assert result["is_interrupted"] is False
        assert result["interrupt_message"] == ""

    def test_jumps_to_matching_phase(self):
        """Redirect mentioning 'market' should jump to research_market phase."""
        state = _make_state(
            interrupt_message="focus on market analysis",
            current_phase="research_company",
            phase_index=0,
        )
        classification = {
            "type": "redirect",
            "confidence": 0.85,
            "extracted_info": {"new_focus": "focus on market analysis"},
        }

        result = handle_redirect(state, classification)

        # research_market is at index 1, so phase_index should be 0 (advance will +1)
        assert result.get("current_phase") == "research_market"

    def test_redirect_to_strategy_phase(self):
        """Redirect mentioning 'strategy' should jump to build_strategy."""
        state = _make_state(
            interrupt_message="skip to strategy building",
            current_phase="research_company",
            phase_index=0,
        )
        classification = {
            "type": "redirect",
            "confidence": 0.85,
            "extracted_info": {"new_focus": "skip to strategy building"},
        }

        result = handle_redirect(state, classification)

        assert result.get("current_phase") == "build_strategy"

    def test_redirect_with_haiku_phase_hint(self):
        """If Haiku provides a phase_hint, use it directly."""
        state = _make_state(
            interrupt_message="let's do scoring",
            current_phase="research_company",
            phase_index=0,
        )
        classification = {
            "type": "redirect",
            "confidence": 0.75,
            "extracted_info": {
                "new_focus": "let's do scoring",
                "phase_hint": "review_and_score",
            },
        }

        result = handle_redirect(state, classification)

        assert result.get("current_phase") == "review_and_score"

    def test_no_matching_phase_records_as_correction(self):
        """If no phase matches the redirect, record it as a correction."""
        state = _make_state(
            interrupt_message="focus on something random",
            current_phase="research_company",
            phase_index=0,
        )
        classification = {
            "type": "redirect",
            "confidence": 0.85,
            "extracted_info": {"new_focus": "focus on something random"},
        }

        result = handle_redirect(state, classification)

        # No phase_index change, but correction recorded
        assert any("REDIRECT:" in c for c in result["user_corrections"])
        assert "current_phase" not in result or result.get("current_phase") is None


# ---------------------------------------------------------------------------
# process_interrupt integration tests
# ---------------------------------------------------------------------------


class TestProcessInterrupt:
    """Tests for the process_interrupt dispatcher."""

    def test_dispatches_stop(self):
        state = _make_state(interrupt_message="stop")

        result = process_interrupt(state)

        assert result["interrupt_type"] == "stop"

    def test_dispatches_correction(self):
        state = _make_state(interrupt_message="that's wrong, we do B2B")

        result = process_interrupt(state)

        assert result["interrupt_type"] == "correction"
        assert any("that's wrong" in c for c in result["user_corrections"])

    def test_dispatches_question(self):
        state = _make_state(interrupt_message="what did you find so far?")

        result = process_interrupt(state)

        assert result["interrupt_type"] == "question"
        assert result["is_interrupted"] is False

    def test_dispatches_redirect(self):
        state = _make_state(interrupt_message="focus on DACH market instead")

        result = process_interrupt(state)

        assert result["interrupt_type"] == "redirect"

    def test_empty_message_defaults_to_correction(self):
        state = _make_state(interrupt_message="")

        result = process_interrupt(state)

        assert result["interrupt_type"] == "correction"
        assert result["is_interrupted"] is False

    @patch("api.agents.interrupt_classifier._haiku_classify")
    def test_ambiguous_message_uses_haiku(self, mock_haiku):
        """Ambiguous messages should trigger Haiku classification."""
        mock_haiku.return_value = InterruptClassification(
            type="redirect",
            confidence=0.75,
            extracted_info={"new_focus": "enterprise segment"},
        )

        state = _make_state(interrupt_message="I think we should consider enterprise")

        result = process_interrupt(state)

        mock_haiku.assert_called_once()
        assert result["interrupt_type"] == "redirect"
