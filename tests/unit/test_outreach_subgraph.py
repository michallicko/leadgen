"""Tests for the Outreach Agent subgraph.

Tests subgraph construction, node routing, tool allowlisting,
and integration with the orchestrator intent classification.
"""

from __future__ import annotations


from langchain_core.messages import AIMessage, HumanMessage

from api.agents.subgraphs.outreach import (
    MAX_OUTREACH_ITERATIONS,
    OUTREACH_AGENT_PROMPT,
    OUTREACH_TOOL_NAMES,
    build_outreach_subgraph,
    outreach_should_continue,
)


# ---------------------------------------------------------------------------
# Subgraph construction
# ---------------------------------------------------------------------------


class TestBuildOutreachSubgraph:
    """Tests for build_outreach_subgraph."""

    def test_subgraph_compiles(self):
        """The outreach subgraph should compile without errors."""
        graph = build_outreach_subgraph()
        assert graph is not None

    def test_subgraph_has_expected_nodes(self):
        """The compiled graph should contain outreach_agent and outreach_tools nodes."""
        graph = build_outreach_subgraph()
        # LangGraph compiled graphs expose nodes via get_graph()
        node_names = set()
        for node in graph.get_graph().nodes:
            node_names.add(node)
        assert "outreach_agent" in node_names
        assert "outreach_tools" in node_names


# ---------------------------------------------------------------------------
# Routing logic
# ---------------------------------------------------------------------------


class TestOutreachShouldContinue:
    """Tests for outreach_should_continue conditional edge."""

    def test_routes_to_tools_on_tool_calls(self):
        """When last message has tool_calls, should route to tools."""
        state = {
            "messages": [
                AIMessage(
                    content="Let me generate that message.",
                    tool_calls=[
                        {
                            "name": "generate_message",
                            "args": {"contact_id": "abc"},
                            "id": "call_1",
                        }
                    ],
                )
            ],
            "iteration": 1,
        }
        assert outreach_should_continue(state) == "tools"

    def test_routes_to_end_without_tool_calls(self):
        """When last message has no tool_calls, should route to end."""
        state = {
            "messages": [AIMessage(content="Here is your message draft.")],
            "iteration": 1,
        }
        assert outreach_should_continue(state) == "end"

    def test_routes_to_end_on_empty_messages(self):
        """When messages list is empty, should route to end."""
        state = {"messages": [], "iteration": 0}
        assert outreach_should_continue(state) == "end"

    def test_routes_to_end_on_max_iterations(self):
        """When max iterations reached, should route to end even with tool calls."""
        state = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "generate_message",
                            "args": {"contact_id": "abc"},
                            "id": "call_1",
                        }
                    ],
                )
            ],
            "iteration": MAX_OUTREACH_ITERATIONS,
        }
        assert outreach_should_continue(state) == "end"

    def test_routes_to_end_on_human_message(self):
        """When last message is HumanMessage, should route to end."""
        state = {
            "messages": [HumanMessage(content="Write me a message")],
            "iteration": 0,
        }
        assert outreach_should_continue(state) == "end"


# ---------------------------------------------------------------------------
# Tool allowlisting
# ---------------------------------------------------------------------------


class TestOutreachToolNames:
    """Tests for the outreach tool name allowlist."""

    def test_expected_tools_in_allowlist(self):
        """All 5 message tools should be in the allowlist."""
        expected = {
            "generate_message",
            "list_messages",
            "update_message",
            "get_message_templates",
            "generate_variants",
        }
        assert OUTREACH_TOOL_NAMES == expected

    def test_strategy_tools_not_in_allowlist(self):
        """Strategy tools should NOT be in the outreach allowlist."""
        strategy_tools = {
            "update_strategy_section",
            "append_to_section",
            "set_extracted_field",
            "track_assumption",
        }
        for tool_name in strategy_tools:
            assert tool_name not in OUTREACH_TOOL_NAMES

    def test_research_tools_not_in_allowlist(self):
        """Research tools should NOT be in the outreach allowlist."""
        research_tools = {"web_search", "research_own_company", "count_contacts"}
        for tool_name in research_tools:
            assert tool_name not in OUTREACH_TOOL_NAMES


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


class TestOutreachPrompt:
    """Tests for the outreach agent system prompt."""

    def test_prompt_mentions_key_tools(self):
        """The system prompt should reference all key tools."""
        assert "generate_message" in OUTREACH_AGENT_PROMPT
        assert "generate_variants" in OUTREACH_AGENT_PROMPT
        assert "list_messages" in OUTREACH_AGENT_PROMPT
        assert "update_message" in OUTREACH_AGENT_PROMPT
        assert "get_message_templates" in OUTREACH_AGENT_PROMPT

    def test_prompt_is_concise(self):
        """The system prompt should be roughly ~200 tokens (under 1500 chars)."""
        assert len(OUTREACH_AGENT_PROMPT) < 1500

    def test_prompt_emphasizes_personalization(self):
        """The prompt should emphasize personalization."""
        lower = OUTREACH_AGENT_PROMPT.lower()
        assert "personalize" in lower or "personalized" in lower


# ---------------------------------------------------------------------------
# Intent classification routing (integration with orchestrator)
# ---------------------------------------------------------------------------


class TestOutreachIntentClassification:
    """Tests for outreach intent routing from the intent classifier."""

    def test_outreach_keywords_match(self):
        """Outreach keywords should route to outreach intent."""
        from api.agents.intent import classify_intent_fast

        assert classify_intent_fast("generate message for John") == "outreach"
        assert classify_intent_fast("write outreach for this contact") == "outreach"
        assert classify_intent_fast("write a message to the prospect") == "outreach"
        assert classify_intent_fast("linkedin message for Jane") == "outreach"
        assert classify_intent_fast("approve message for batch") == "outreach"

    def test_campaign_keywords_match(self):
        """Campaign keywords should route to campaign intent."""
        from api.agents.intent import classify_intent_fast

        assert classify_intent_fast("create campaign for batch-1") == "campaign"
        assert classify_intent_fast("launch campaign for tier 1") == "campaign"
        assert classify_intent_fast("campaign analytics for Q1") == "campaign"

    def test_strategy_keywords_dont_match_outreach(self):
        """Strategy keywords should NOT route to campaign."""
        from api.agents.intent import classify_intent_fast

        result = classify_intent_fast("write section on competitive positioning")
        assert result == "strategy_edit"
