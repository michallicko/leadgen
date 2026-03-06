"""Tests for the pipeline orchestrator (Sprint 20).

Tests phase tracking, sequential handoff, routing, and pipeline state.
"""

from __future__ import annotations

from unittest.mock import patch


from api.agents.pipeline import (
    PHASE_ORDER,
    PHASES,
    _build_pipeline_context,
    _detect_phase,
    build_pipeline_graph,
    get_pipeline_status,
    pipeline_route,
)
from api.agents.state import AgentState


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
# Phase detection tests
# ---------------------------------------------------------------------------


class TestPhaseDetection:
    def test_explicit_phase_takes_priority(self):
        state = _make_state(pipeline_phase="messages")
        assert _detect_phase(state) == "messages"

    def test_infer_from_page_context_strategy(self):
        state = _make_state(tool_context={"page_context": "strategy"})
        assert _detect_phase(state) == "strategy"

    def test_infer_from_page_context_playbook(self):
        state = _make_state(tool_context={"page_context": "playbook"})
        assert _detect_phase(state) == "strategy"

    def test_infer_from_page_context_contacts(self):
        state = _make_state(tool_context={"page_context": "contacts"})
        assert _detect_phase(state) == "contacts"

    def test_infer_from_page_context_companies(self):
        state = _make_state(tool_context={"page_context": "companies"})
        assert _detect_phase(state) == "contacts"

    def test_infer_from_page_context_messages(self):
        state = _make_state(tool_context={"page_context": "messages"})
        assert _detect_phase(state) == "messages"

    def test_infer_from_page_context_outreach(self):
        state = _make_state(tool_context={"page_context": "outreach"})
        assert _detect_phase(state) == "messages"

    def test_infer_from_page_context_campaign(self):
        state = _make_state(tool_context={"page_context": "campaign"})
        assert _detect_phase(state) == "campaign"

    def test_default_to_strategy(self):
        state = _make_state()
        assert _detect_phase(state) == "strategy"

    def test_invalid_explicit_phase_falls_through(self):
        state = _make_state(pipeline_phase="invalid_phase")
        assert _detect_phase(state) == "strategy"


# ---------------------------------------------------------------------------
# Pipeline context tests
# ---------------------------------------------------------------------------


class TestPipelineContext:
    def test_empty_state_returns_empty_context(self):
        state = _make_state()
        ctx = _build_pipeline_context(state)
        assert ctx.get("phases_complete") == []

    def test_includes_research_results(self):
        state = _make_state(research_results={"key": "value"})
        ctx = _build_pipeline_context(state)
        assert ctx["research_results"] == {"key": "value"}

    def test_includes_section_completeness(self):
        state = _make_state(
            section_completeness={"executive_summary": True, "icp": False}
        )
        ctx = _build_pipeline_context(state)
        assert ctx["section_completeness"]["executive_summary"] is True

    def test_includes_phases_complete(self):
        state = _make_state(pipeline_phases_complete=["strategy", "contacts"])
        ctx = _build_pipeline_context(state)
        assert ctx["phases_complete"] == ["strategy", "contacts"]

    def test_merges_existing_pipeline_context(self):
        state = _make_state(
            pipeline_context={"custom_key": "custom_value"},
            research_results={"data": "research"},
        )
        ctx = _build_pipeline_context(state)
        assert ctx["custom_key"] == "custom_value"
        assert ctx["research_results"] == {"data": "research"}


# ---------------------------------------------------------------------------
# Pipeline routing tests
# ---------------------------------------------------------------------------


class TestPipelineRoute:
    def test_strategy_edit_routes_to_strategy(self):
        state = _make_state(intent="strategy_edit", pipeline_phase="strategy")
        assert pipeline_route(state) == "pipeline_strategy_node"

    def test_research_routes_to_research(self):
        state = _make_state(intent="research", pipeline_phase="strategy")
        assert pipeline_route(state) == "research_node"

    def test_enrichment_routes_to_enrichment(self):
        state = _make_state(intent="enrichment", pipeline_phase="contacts")
        assert pipeline_route(state) == "pipeline_enrichment_node"

    def test_outreach_routes_to_outreach(self):
        state = _make_state(intent="outreach", pipeline_phase="messages")
        assert pipeline_route(state) == "pipeline_outreach_node"

    def test_copilot_routes_to_copilot(self):
        state = _make_state(intent="copilot")
        assert pipeline_route(state) == "copilot_node"

    def test_unknown_intent_defaults_to_copilot(self):
        state = _make_state(intent="unknown_intent")
        assert pipeline_route(state) == "copilot_node"

    def test_none_intent_defaults_to_copilot(self):
        state = _make_state(intent=None)
        assert pipeline_route(state) == "copilot_node"


# ---------------------------------------------------------------------------
# Pipeline status tests
# ---------------------------------------------------------------------------


class TestPipelineStatus:
    def test_initial_status(self):
        state = _make_state()
        status = get_pipeline_status(state)
        assert status["current_phase"] == "strategy"
        assert status["phase_order"] == PHASE_ORDER
        assert not status["phases"]["strategy"]["complete"]
        assert status["phases"]["strategy"]["current"]

    def test_with_completed_phases(self):
        state = _make_state(
            pipeline_phase="messages",
            pipeline_phases_complete=["strategy", "contacts"],
        )
        status = get_pipeline_status(state)
        assert status["current_phase"] == "messages"
        assert status["phases"]["strategy"]["complete"]
        assert status["phases"]["contacts"]["complete"]
        assert not status["phases"]["messages"]["complete"]
        assert status["phases"]["messages"]["current"]

    def test_all_phases_present(self):
        state = _make_state()
        status = get_pipeline_status(state)
        for phase_name in PHASE_ORDER:
            assert phase_name in status["phases"]

    def test_phase_labels_and_descriptions(self):
        state = _make_state()
        status = get_pipeline_status(state)
        for name, info in PHASES.items():
            assert status["phases"][name]["label"] == info["label"]
            assert status["phases"][name]["description"] == info["description"]


# ---------------------------------------------------------------------------
# Pipeline graph construction tests
# ---------------------------------------------------------------------------


class TestPipelineGraph:
    @patch("api.agents.pipeline.classify_intent")
    @patch("api.agents.pipeline.get_stream_writer")
    def test_graph_compiles(self, mock_writer, mock_classify):
        """Pipeline graph should compile without errors."""
        graph = build_pipeline_graph()
        assert graph is not None

    def test_phase_order_is_correct(self):
        assert PHASE_ORDER == ["strategy", "contacts", "messages", "campaign"]

    def test_all_phases_have_definitions(self):
        for phase in PHASE_ORDER:
            assert phase in PHASES
            assert "label" in PHASES[phase]
            assert "primary_intents" in PHASES[phase]
            assert "description" in PHASES[phase]
