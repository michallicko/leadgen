"""Tests for the Copilot agent subgraph (Sprint 20).

Tests copilot construction, routing, tool access, and quick responses.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


from api.agents.intent import (
    DEFAULT_INTENT,
    VALID_INTENTS,
    classify_intent_fast,
)
from api.agents.subgraphs.copilot import (
    COPILOT_AGENT_PROMPT,
    MAX_COPILOT_ITERATIONS,
    _get_copilot_handler,
    _get_copilot_tool_defs,
    build_copilot_subgraph,
    copilot_should_continue,
)
from api.agents.state import AgentState
from api.tools.copilot_tools import (
    COPILOT_TOOL_DEFINITIONS,
    COPILOT_TOOL_NAMES,
)


def _make_state(**overrides) -> AgentState:
    """Create a minimal AgentState for testing."""
    base = {
        "messages": [],
        "tool_context": {},
        "iteration": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cost_usd": "0",
        "model": "claude-haiku-4-5-20251001",
        "intent": None,
        "active_agent": None,
        "research_results": None,
        "section_completeness": None,
        "pipeline_phase": None,
        "pipeline_phases_complete": None,
        "pipeline_context": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Copilot tool definition tests
# ---------------------------------------------------------------------------


class TestCopilotTools:
    def test_tool_names_match_definitions(self):
        """All defined tool names should have matching definitions."""
        defined_names = {t["name"] for t in COPILOT_TOOL_DEFINITIONS}
        assert defined_names == COPILOT_TOOL_NAMES

    def test_all_tools_have_required_fields(self):
        """Each tool definition must have name, description, input_schema, handler."""
        for tool_def in COPILOT_TOOL_DEFINITIONS:
            assert "name" in tool_def
            assert "description" in tool_def
            assert "input_schema" in tool_def
            assert "handler" in tool_def
            assert callable(tool_def["handler"])

    def test_get_copilot_tool_defs_returns_api_format(self):
        """Tool defs for API should not include handler."""
        defs = _get_copilot_tool_defs()
        assert len(defs) == len(COPILOT_TOOL_DEFINITIONS)
        for d in defs:
            assert "name" in d
            assert "description" in d
            assert "input_schema" in d
            assert "handler" not in d

    def test_get_copilot_handler_known_tool(self):
        handler = _get_copilot_handler("get_contact_info")
        assert handler is not None
        assert callable(handler)

    def test_get_copilot_handler_unknown_tool(self):
        handler = _get_copilot_handler("nonexistent_tool")
        assert handler is None

    def test_four_tools_available(self):
        """Copilot should have exactly 4 read-only tools."""
        assert len(COPILOT_TOOL_NAMES) == 4
        assert "get_contact_info" in COPILOT_TOOL_NAMES
        assert "get_company_info" in COPILOT_TOOL_NAMES
        assert "get_pipeline_status" in COPILOT_TOOL_NAMES
        assert "get_recent_activity" in COPILOT_TOOL_NAMES


# ---------------------------------------------------------------------------
# Copilot subgraph construction tests
# ---------------------------------------------------------------------------


class TestCopilotSubgraph:
    @patch("api.agents.subgraphs.copilot.get_stream_writer")
    def test_subgraph_compiles(self, mock_writer):
        """Copilot subgraph should compile without errors."""
        graph = build_copilot_subgraph()
        assert graph is not None

    def test_max_iterations_reasonable(self):
        """Copilot should have a lower iteration limit than specialist agents."""
        assert MAX_COPILOT_ITERATIONS <= 10

    def test_prompt_mentions_conciseness(self):
        """Copilot prompt should enforce brief responses."""
        assert (
            "100 words" in COPILOT_AGENT_PROMPT
            or "concise" in COPILOT_AGENT_PROMPT.lower()
        )


# ---------------------------------------------------------------------------
# Copilot routing tests
# ---------------------------------------------------------------------------


class TestCopilotRouting:
    def test_should_continue_no_messages(self):
        state = _make_state(messages=[])
        assert copilot_should_continue(state) == "end"

    def test_should_continue_max_iterations(self):
        mock_msg = MagicMock()
        mock_msg.tool_calls = [{"name": "test", "id": "1", "args": {}}]
        state = _make_state(
            messages=[mock_msg],
            iteration=MAX_COPILOT_ITERATIONS,
        )
        assert copilot_should_continue(state) == "end"

    def test_should_continue_with_tool_calls(self):
        from langchain_core.messages import AIMessage

        msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "get_contact_info", "id": "1", "args": {"query": "test"}}
            ],
        )
        state = _make_state(messages=[msg], iteration=1)
        assert copilot_should_continue(state) == "tools"

    def test_should_end_without_tool_calls(self):
        from langchain_core.messages import AIMessage

        msg = AIMessage(content="Here is your answer", tool_calls=[])
        state = _make_state(messages=[msg], iteration=1)
        assert copilot_should_continue(state) == "end"


# ---------------------------------------------------------------------------
# Intent classification tests (copilot as default)
# ---------------------------------------------------------------------------


class TestCopilotIntentClassification:
    def test_copilot_is_default_intent(self):
        assert DEFAULT_INTENT == "copilot"

    def test_copilot_in_valid_intents(self):
        assert "copilot" in VALID_INTENTS

    def test_enrichment_in_valid_intents(self):
        assert "enrichment" in VALID_INTENTS

    def test_outreach_in_valid_intents(self):
        assert "outreach" in VALID_INTENTS

    def test_short_message_classified_as_copilot(self):
        assert classify_intent_fast("hi") == "copilot"

    def test_greeting_classified_as_copilot(self):
        assert classify_intent_fast("hello") == "copilot"

    def test_thanks_classified_as_copilot(self):
        assert classify_intent_fast("thanks") == "copilot"

    def test_very_short_message_classified_as_copilot(self):
        assert classify_intent_fast("ok") == "copilot"

    def test_enrichment_keyword_detected(self):
        assert classify_intent_fast("run enrichment on these contacts") == "enrichment"

    def test_outreach_keyword_detected(self):
        assert classify_intent_fast("generate message for John") == "outreach"

    def test_strategy_keyword_still_works(self):
        assert (
            classify_intent_fast("write section on value proposition")
            == "strategy_edit"
        )

    def test_research_keyword_still_works(self):
        assert classify_intent_fast("research this company") == "research"

    def test_unknown_returns_none_for_llm(self):
        """Ambiguous messages should return None for LLM classification."""
        result = classify_intent_fast(
            "What's the best approach for targeting enterprise?"
        )
        assert result is None
