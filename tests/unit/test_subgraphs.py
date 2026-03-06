"""Unit tests for Sprint 12 multi-agent subgraphs.

Tests the intent classifier, strategy/research subgraph construction,
tool scoping, and orchestrator routing logic.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from api.agents.intent import (
    VALID_INTENTS,
    classify_intent_fast,
    classify_intent,
)
from api.agents.state import AgentState
from api.agents.subgraphs.strategy import (
    STRATEGY_TOOL_NAMES,
    STRATEGY_AGENT_PROMPT,
    build_strategy_subgraph,
    _get_strategy_tool_defs,
)
from api.agents.subgraphs.research import (
    RESEARCH_TOOL_NAMES,
    RESEARCH_AGENT_PROMPT,
    build_research_subgraph,
    _get_research_tool_defs,
)
from api.agents.orchestrator import (
    build_orchestrator_graph,
    route_to_agent,
)


# ---------------------------------------------------------------------------
# Intent classification tests
# ---------------------------------------------------------------------------


class TestIntentClassifyFast:
    """Test keyword-based fast classification."""

    def test_greetings_are_quick_answer(self):
        assert classify_intent_fast("hi") == "quick_answer"
        assert classify_intent_fast("hello") == "quick_answer"
        assert classify_intent_fast("thanks") == "quick_answer"
        assert classify_intent_fast("ok") == "quick_answer"

    def test_short_messages_are_quick_answer(self):
        assert classify_intent_fast("yes") == "quick_answer"
        assert classify_intent_fast("no") == "quick_answer"
        assert classify_intent_fast("sure") == "quick_answer"

    def test_strategy_keywords(self):
        assert (
            classify_intent_fast("write section executive summary") == "strategy_edit"
        )
        assert (
            classify_intent_fast("update section value proposition") == "strategy_edit"
        )
        assert (
            classify_intent_fast("generate strategy for my company") == "strategy_edit"
        )
        assert classify_intent_fast("set persona for CTOs") == "strategy_edit"
        assert classify_intent_fast("fill in the metrics section") == "strategy_edit"

    def test_research_keywords(self):
        assert (
            classify_intent_fast("search for AI trends in manufacturing") == "research"
        )
        assert classify_intent_fast("research our competitors") == "research"
        assert classify_intent_fast("how many contacts do we have?") == "research"
        assert classify_intent_fast("count companies in our CRM") == "research"
        assert classify_intent_fast("analyze enrichment data") == "research"

    def test_campaign_keywords(self):
        assert classify_intent_fast("generate message for the contacts") == "campaign"
        assert classify_intent_fast("create campaign for Q2") == "campaign"
        assert classify_intent_fast("write outreach email") == "campaign"

    def test_ambiguous_returns_none(self):
        result = classify_intent_fast("what do you think about our positioning?")
        assert result is None

    def test_empty_message(self):
        assert classify_intent_fast("") == "quick_answer"

    def test_all_valid_intents(self):
        """All possible intent values are in the VALID_INTENTS set."""
        assert "strategy_edit" in VALID_INTENTS
        assert "research" in VALID_INTENTS
        assert "quick_answer" in VALID_INTENTS
        assert "campaign" in VALID_INTENTS


class TestIntentClassifyLLM:
    """Test LLM-based classification (mocked)."""

    @patch("api.agents.intent.ChatAnthropic")
    def test_classify_uses_haiku(self, mock_chat):
        mock_response = MagicMock()
        mock_response.content = "research"
        mock_chat.return_value.invoke.return_value = mock_response

        intent, latency = classify_intent(
            "analyze our market competitors and find gaps"
        )
        # Fast path matches "competitor" keyword
        assert intent == "research"

    @patch("api.agents.intent.ChatAnthropic")
    def test_classify_invalid_response_defaults(self, mock_chat):
        mock_response = MagicMock()
        mock_response.content = "I think this is about strategy"
        mock_chat.return_value.invoke.return_value = mock_response

        # This message won't match fast path keywords
        intent, _ = classify_intent(
            "What's the best approach for our go-to-market in the European market?"
        )
        assert intent == "quick_answer"  # default

    @patch("api.agents.intent.ChatAnthropic")
    def test_classify_exception_defaults(self, mock_chat):
        mock_chat.return_value.invoke.side_effect = Exception("API error")

        intent, _ = classify_intent(
            "What's the best approach for our go-to-market in the European market?"
        )
        assert intent == "quick_answer"


# ---------------------------------------------------------------------------
# Strategy subgraph tests
# ---------------------------------------------------------------------------


class TestStrategySubgraph:
    """Test strategy agent subgraph construction and tool scoping."""

    def test_strategy_tool_names_count(self):
        """Strategy agent should have exactly 8 tools."""
        assert len(STRATEGY_TOOL_NAMES) == 8

    def test_strategy_tool_names_correct(self):
        """All expected strategy tools are in the set."""
        expected = {
            "update_strategy_section",
            "append_to_section",
            "set_extracted_field",
            "track_assumption",
            "check_readiness",
            "set_icp_tiers",
            "set_buyer_personas",
            "get_strategy_document",
        }
        assert STRATEGY_TOOL_NAMES == expected

    def test_strategy_tools_no_research(self):
        """Strategy tools should not include research tools."""
        research_tools = {"web_search", "research_own_company", "count_contacts"}
        assert not STRATEGY_TOOL_NAMES.intersection(research_tools)

    def test_strategy_prompt_concise(self):
        """Strategy agent prompt should be concise (~200 tokens)."""
        # Rough token estimate: ~4 chars per token
        estimated_tokens = len(STRATEGY_AGENT_PROMPT) / 4
        assert estimated_tokens < 400, "Strategy prompt too long: ~{} tokens".format(
            int(estimated_tokens)
        )

    def test_build_strategy_subgraph(self):
        """Strategy subgraph builds without errors."""
        graph = build_strategy_subgraph()
        assert graph is not None

    @patch("api.agents.subgraphs.strategy.get_tool")
    def test_get_strategy_tool_defs_filters(self, mock_get_tool):
        """_get_strategy_tool_defs only returns strategy tools."""
        mock_tool = MagicMock()
        mock_tool.name = "update_strategy_section"
        mock_tool.description = "Update a section"
        mock_tool.input_schema = {"type": "object", "properties": {}}

        def side_effect(name):
            if name in STRATEGY_TOOL_NAMES:
                t = MagicMock()
                t.name = name
                t.description = "Test tool"
                t.input_schema = {"type": "object", "properties": {}}
                return t
            return None

        mock_get_tool.side_effect = side_effect
        defs = _get_strategy_tool_defs()

        # Should only contain strategy tools
        tool_names = {d["name"] for d in defs}
        assert tool_names.issubset(STRATEGY_TOOL_NAMES)


# ---------------------------------------------------------------------------
# Research subgraph tests
# ---------------------------------------------------------------------------


class TestResearchSubgraph:
    """Test research agent subgraph construction and tool scoping."""

    def test_research_tool_names_count(self):
        """Research agent should have exactly 7 tools."""
        assert len(RESEARCH_TOOL_NAMES) == 7

    def test_research_tool_names_correct(self):
        """All expected research tools are in the set."""
        expected = {
            "web_search",
            "research_own_company",
            "count_contacts",
            "count_companies",
            "list_contacts",
            "filter_contacts",
            "analyze_enrichment_insights",
        }
        assert RESEARCH_TOOL_NAMES == expected

    def test_research_tools_no_strategy(self):
        """Research tools should not include strategy tools."""
        strategy_tools = {
            "update_strategy_section",
            "set_icp_tiers",
            "set_buyer_personas",
        }
        assert not RESEARCH_TOOL_NAMES.intersection(strategy_tools)

    def test_research_prompt_concise(self):
        """Research agent prompt should be concise."""
        estimated_tokens = len(RESEARCH_AGENT_PROMPT) / 4
        assert estimated_tokens < 300, "Research prompt too long: ~{} tokens".format(
            int(estimated_tokens)
        )

    def test_build_research_subgraph(self):
        """Research subgraph builds without errors."""
        graph = build_research_subgraph()
        assert graph is not None

    @patch("api.agents.subgraphs.research.get_tool")
    def test_get_research_tool_defs_filters(self, mock_get_tool):
        """_get_research_tool_defs only returns research tools."""

        def side_effect(name):
            if name in RESEARCH_TOOL_NAMES:
                t = MagicMock()
                t.name = name
                t.description = "Test tool"
                t.input_schema = {"type": "object", "properties": {}}
                return t
            return None

        mock_get_tool.side_effect = side_effect
        defs = _get_research_tool_defs()

        tool_names = {d["name"] for d in defs}
        assert tool_names.issubset(RESEARCH_TOOL_NAMES)


# ---------------------------------------------------------------------------
# Orchestrator routing tests
# ---------------------------------------------------------------------------


class TestOrchestratorRouting:
    """Test orchestrator intent-based routing."""

    def test_route_strategy_edit(self):
        state = {"intent": "strategy_edit"}
        assert route_to_agent(state) == "strategy_node"

    def test_route_research(self):
        state = {"intent": "research"}
        assert route_to_agent(state) == "research_node"

    def test_route_quick_answer(self):
        state = {"intent": "quick_answer"}
        assert route_to_agent(state) == "quick_response_node"

    def test_route_campaign(self):
        state = {"intent": "campaign"}
        assert route_to_agent(state) == "passthrough_node"

    def test_route_unknown_defaults_to_quick(self):
        state = {"intent": "unknown_intent"}
        assert route_to_agent(state) == "quick_response_node"

    def test_route_none_defaults_to_quick(self):
        state = {"intent": None}
        assert route_to_agent(state) == "quick_response_node"

    def test_route_missing_intent(self):
        state = {}
        assert route_to_agent(state) == "quick_response_node"


class TestOrchestratorGraph:
    """Test orchestrator graph construction."""

    def test_build_orchestrator_graph(self):
        """Orchestrator graph builds without errors."""
        graph = build_orchestrator_graph()
        assert graph is not None


# ---------------------------------------------------------------------------
# State schema tests
# ---------------------------------------------------------------------------


class TestAgentState:
    """Test the extended AgentState schema."""

    def test_state_has_intent_field(self):
        """AgentState should have intent field."""
        assert "intent" in AgentState.__annotations__

    def test_state_has_active_agent_field(self):
        """AgentState should have active_agent field."""
        assert "active_agent" in AgentState.__annotations__

    def test_state_has_research_results_field(self):
        """AgentState should have research_results field."""
        assert "research_results" in AgentState.__annotations__

    def test_state_has_section_completeness_field(self):
        """AgentState should have section_completeness field."""
        assert "section_completeness" in AgentState.__annotations__

    def test_state_preserves_existing_fields(self):
        """Existing state fields must still be present."""
        required = [
            "messages",
            "tool_context",
            "iteration",
            "total_input_tokens",
            "total_output_tokens",
            "total_cost_usd",
            "model",
        ]
        for field in required:
            assert field in AgentState.__annotations__, "Missing field: {}".format(
                field
            )


# ---------------------------------------------------------------------------
# Tool scope isolation tests
# ---------------------------------------------------------------------------


class TestToolIsolation:
    """Verify tool scopes don't overlap where they shouldn't."""

    def test_strategy_and_research_overlap_minimal(self):
        """Strategy and research tools should not overlap."""
        overlap = STRATEGY_TOOL_NAMES.intersection(RESEARCH_TOOL_NAMES)
        assert len(overlap) == 0, "Unexpected tool overlap: {}".format(overlap)
