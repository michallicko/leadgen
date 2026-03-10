"""Unit tests for the enrichment agent subgraph (BL-1001).

Tests the enrichment subgraph at api/agents/subgraphs/enrichment.py including
graph construction, routing logic, tool filtering, and iteration limits.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


# ---------------------------------------------------------------------------
# Tests: graph construction
# ---------------------------------------------------------------------------


class TestBuildEnrichmentSubgraph:
    """Verify the enrichment subgraph compiles correctly."""

    def test_builds_without_error(self):
        from api.agents.subgraphs.enrichment import build_enrichment_subgraph

        graph = build_enrichment_subgraph()
        assert graph is not None

    def test_has_expected_nodes(self):
        from api.agents.subgraphs.enrichment import build_enrichment_subgraph

        graph = build_enrichment_subgraph()
        graph_def = graph.get_graph()
        node_ids = list(graph_def.nodes)
        assert "enrichment_agent" in node_ids
        assert "enrichment_tools" in node_ids


# ---------------------------------------------------------------------------
# Tests: routing / should_continue
# ---------------------------------------------------------------------------


class TestEnrichmentShouldContinue:
    """Test the conditional edge routing logic."""

    def test_returns_tools_when_tool_calls_present(self):
        from api.agents.subgraphs.enrichment import enrichment_should_continue

        ai_msg = AIMessage(
            content="",
            tool_calls=[{"name": "enrich_company_news", "id": "tc1", "args": {}}],
        )
        state = {"messages": [ai_msg], "iteration": 0}
        assert enrichment_should_continue(state) == "tools"

    def test_returns_end_when_no_tool_calls(self):
        from api.agents.subgraphs.enrichment import enrichment_should_continue

        ai_msg = AIMessage(content="Done enriching.")
        state = {"messages": [ai_msg], "iteration": 0}
        assert enrichment_should_continue(state) == "end"

    def test_returns_end_when_max_iterations(self):
        from api.agents.subgraphs.enrichment import (
            MAX_ENRICHMENT_ITERATIONS,
            enrichment_should_continue,
        )

        ai_msg = AIMessage(
            content="",
            tool_calls=[{"name": "enrich_company_news", "id": "tc1", "args": {}}],
        )
        state = {"messages": [ai_msg], "iteration": MAX_ENRICHMENT_ITERATIONS}
        assert enrichment_should_continue(state) == "end"

    def test_returns_end_when_empty_messages(self):
        from api.agents.subgraphs.enrichment import enrichment_should_continue

        state = {"messages": [], "iteration": 0}
        assert enrichment_should_continue(state) == "end"


# ---------------------------------------------------------------------------
# Tests: tool filtering in enrichment_tools_node
# ---------------------------------------------------------------------------


class TestEnrichmentToolsNode:
    """Test the enrichment tools executor node."""

    def test_rejects_non_enrichment_tools(self):
        from api.agents.subgraphs.enrichment import enrichment_tools_node

        ai_msg = AIMessage(
            content="",
            tool_calls=[{"name": "web_search", "id": "tc1", "args": {"query": "test"}}],
        )
        state = {
            "messages": [ai_msg],
            "tool_context": {"tenant_id": "t001"},
        }

        with patch("api.agents.subgraphs.enrichment.get_stream_writer") as mock_writer:
            mock_writer.return_value = MagicMock()
            result = enrichment_tools_node(state)

        assert len(result["messages"]) == 1
        assert "not available" in result["messages"][0].content

    def test_returns_empty_when_no_tool_calls(self):
        from api.agents.subgraphs.enrichment import enrichment_tools_node

        ai_msg = AIMessage(content="No tools needed.")
        state = {
            "messages": [ai_msg],
            "tool_context": {"tenant_id": "t001"},
        }

        with patch("api.agents.subgraphs.enrichment.get_stream_writer") as mock_writer:
            mock_writer.return_value = MagicMock()
            result = enrichment_tools_node(state)

        assert result["messages"] == []

    def test_executes_valid_enrichment_tool(self):
        from api.agents.subgraphs.enrichment import enrichment_tools_node

        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "enrich_company_news",
                    "id": "tc1",
                    "args": {"company_id": "c001"},
                }
            ],
        )
        state = {
            "messages": [ai_msg],
            "tool_context": {"tenant_id": "t001", "user_id": "u001"},
        }

        mock_tool = MagicMock()
        mock_tool.handler.return_value = {"enrichment_cost_usd": 0.04}

        with (
            patch("api.agents.subgraphs.enrichment.get_stream_writer") as mock_writer,
            patch("api.agents.subgraphs.enrichment.get_tool", return_value=mock_tool),
        ):
            mock_writer.return_value = MagicMock()
            result = enrichment_tools_node(state)

        assert len(result["messages"]) == 1
        assert "enrichment_cost_usd" in result["messages"][0].content

    def test_handles_tool_execution_error(self):
        from api.agents.subgraphs.enrichment import enrichment_tools_node

        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "enrich_company_news",
                    "id": "tc1",
                    "args": {"company_id": "c001"},
                }
            ],
        )
        state = {
            "messages": [ai_msg],
            "tool_context": {"tenant_id": "t001", "user_id": "u001"},
        }

        mock_tool = MagicMock()
        mock_tool.handler.side_effect = RuntimeError("API timeout")

        with (
            patch("api.agents.subgraphs.enrichment.get_stream_writer") as mock_writer,
            patch("api.agents.subgraphs.enrichment.get_tool", return_value=mock_tool),
        ):
            mock_writer.return_value = MagicMock()
            result = enrichment_tools_node(state)

        assert len(result["messages"]) == 1
        assert "API timeout" in result["messages"][0].content


# ---------------------------------------------------------------------------
# Tests: enrichment_agent_node
# ---------------------------------------------------------------------------


class TestEnrichmentAgentNode:
    """Test the enrichment agent LLM node."""

    def test_adds_system_prompt_if_missing(self):
        from api.agents.subgraphs.enrichment import enrichment_agent_node

        mock_response = AIMessage(content="I'll enrich that company.")
        mock_response.usage_metadata = {"input_tokens": 100, "output_tokens": 50}

        with (
            patch("api.agents.subgraphs.enrichment.ChatAnthropic") as MockModel,
            patch("api.agents.subgraphs.enrichment.get_stream_writer") as mock_writer,
            patch(
                "api.agents.subgraphs.enrichment._get_enrichment_tool_defs",
                return_value=[],
            ),
        ):
            mock_writer.return_value = MagicMock()
            mock_instance = MagicMock()
            mock_instance.invoke.return_value = mock_response
            MockModel.return_value = mock_instance

            state = {
                "messages": [HumanMessage(content="Enrich company X")],
                "iteration": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost_usd": "0",
                "model": "claude-haiku-4-5-20251001",
            }

            enrichment_agent_node(state)

        # Verify system prompt was prepended
        call_args = mock_instance.invoke.call_args[0][0]
        assert isinstance(call_args[0], SystemMessage)
        assert "enrichment coordinator" in call_args[0].content

    def test_tracks_token_usage(self):
        from api.agents.subgraphs.enrichment import enrichment_agent_node

        mock_response = AIMessage(content="Done.")
        mock_response.usage_metadata = {"input_tokens": 200, "output_tokens": 100}

        with (
            patch("api.agents.subgraphs.enrichment.ChatAnthropic") as MockModel,
            patch("api.agents.subgraphs.enrichment.get_stream_writer") as mock_writer,
            patch(
                "api.agents.subgraphs.enrichment._get_enrichment_tool_defs",
                return_value=[],
            ),
        ):
            mock_writer.return_value = MagicMock()
            mock_instance = MagicMock()
            mock_instance.invoke.return_value = mock_response
            MockModel.return_value = mock_instance

            state = {
                "messages": [HumanMessage(content="test")],
                "iteration": 5,
                "total_input_tokens": 500,
                "total_output_tokens": 200,
                "total_cost_usd": "0.001",
                "model": "claude-haiku-4-5-20251001",
            }

            result = enrichment_agent_node(state)

        assert result["total_input_tokens"] == 700
        assert result["total_output_tokens"] == 300
        assert result["iteration"] == 6
        assert result["active_agent"] == "enrichment"


# ---------------------------------------------------------------------------
# Tests: tool name constants
# ---------------------------------------------------------------------------


class TestEnrichmentToolNames:
    """Verify the enrichment tool name set is correct."""

    def test_contains_all_expected_tools(self):
        from api.agents.subgraphs.enrichment import ENRICHMENT_TOOL_NAMES

        expected = {
            "enrich_company_news",
            "enrich_company_signals",
            "enrich_contact_social",
            "enrich_contact_career",
            "enrich_contact_details",
            "check_enrichment_status",
            "estimate_enrichment_cost",
            "start_enrichment",
        }
        assert expected == set(ENRICHMENT_TOOL_NAMES)

    def test_is_frozenset(self):
        from api.agents.subgraphs.enrichment import ENRICHMENT_TOOL_NAMES

        assert isinstance(ENRICHMENT_TOOL_NAMES, frozenset)
