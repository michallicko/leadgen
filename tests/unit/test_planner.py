"""Unit tests for the deterministic planner (BL-1009).

Tests the planner state machine: initialization, phase execution order,
interrupt handling, phase advancement, state persistence, and SSE events.
"""

import pytest

from api.agents.planner import (
    PHASE_HANDLERS,
    advance_phase_node,
    advance_router,
    build_planner_graph,
    check_interrupt_node,
    classify_interrupt,
    execute_phase_node,
    initialize_node,
    interrupt_router,
    phase_router,
)
from api.agents.planner_bridge import (
    clear_active_plan,
    execute_planner_turn,
    get_active_plan,
    list_active_plans,
    save_active_plan,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_plan_config():
    """A minimal plan config for testing."""
    return {
        "id": "plan-test-001",
        "name": "Test GTM Strategy",
        "phases": [
            "research_company",
            "research_market",
            "build_strategy",
            "review_and_score",
        ],
        "research_requirements": {
            "primary_source": "website",
            "cross_check_policy": "verify",
        },
        "scoring_rubric": {
            "sections": ["ICP", "Value Proposition", "Channel Strategy"],
        },
        "persona": "strategist",
        "system_prompt_template": "You are a GTM strategist.",
        "tools": ["web_research", "update_section"],
        "discovery_questions": [],
    }


@pytest.fixture()
def base_state(sample_plan_config):
    """A base PlannerState dict for testing node functions."""
    return {
        "messages": [],
        "tool_context": {"tenant_id": "test-tenant"},
        "iteration": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cost_usd": "0",
        "model": "",
        "plan_id": sample_plan_config["id"],
        "plan_config": sample_plan_config,
        "current_phase": "research_company",
        "phase_index": 0,
        "phase_results": {},
        "research_data": {},
        "user_corrections": [],
        "section_completeness": {},
        "is_interrupted": False,
        "interrupt_message": "",
        "interrupt_type": "",
        "findings": [],
    }


class MockWriter:
    """Captures SSEEvent objects emitted by nodes."""

    def __init__(self):
        self.events = []

    def __call__(self, event):
        self.events.append(event)


# ---------------------------------------------------------------------------
# classify_interrupt tests
# ---------------------------------------------------------------------------


class TestClassifyInterrupt:
    def test_stop_keywords(self):
        assert classify_interrupt("stop") == "stop"
        assert classify_interrupt("Please wait") == "stop"
        assert classify_interrupt("Hold on a second") == "stop"
        assert classify_interrupt("That's wrong") == "stop"
        assert classify_interrupt("cancel this") == "stop"
        assert classify_interrupt("abort the plan") == "stop"

    def test_redirect_keywords(self):
        assert classify_interrupt("Actually, focus on contacts") == "redirect"
        assert classify_interrupt("Instead do market research") == "redirect"
        assert classify_interrupt("Switch to a different approach") == "redirect"
        assert classify_interrupt("Skip this phase") == "redirect"

    def test_question_keywords(self):
        assert classify_interrupt("What is the ICP?") == "question"
        assert classify_interrupt("How many competitors?") == "question"
        assert classify_interrupt("show me the results") == "question"

    def test_correction_default(self):
        assert classify_interrupt("The revenue is 50M not 30M") == "correction"
        assert classify_interrupt("Add fintech to industries") == "correction"
        assert classify_interrupt("more detail on pricing") == "correction"

    def test_empty_message(self):
        assert classify_interrupt("") == "correction"


# ---------------------------------------------------------------------------
# Node function tests
# ---------------------------------------------------------------------------


class TestInitializeNode:
    def test_sets_first_phase(self, base_state, monkeypatch):
        monkeypatch.setattr(
            "api.agents.planner.get_stream_writer", lambda: MockWriter()
        )
        result = initialize_node(base_state)
        assert result["current_phase"] == "research_company"
        assert result["phase_index"] == 0
        assert result["is_interrupted"] is False

    def test_empty_phases(self, base_state, monkeypatch):
        monkeypatch.setattr(
            "api.agents.planner.get_stream_writer", lambda: MockWriter()
        )
        base_state["plan_config"]["phases"] = []
        result = initialize_node(base_state)
        assert result["current_phase"] == ""
        assert result["phase_index"] == 0


class TestExecutePhaseNode:
    def test_known_phase(self, base_state, monkeypatch):
        writer = MockWriter()
        monkeypatch.setattr("api.agents.planner.get_stream_writer", lambda: writer)
        base_state["current_phase"] = "research_company"
        result = execute_phase_node(base_state)

        assert "research_data" in result
        assert result["research_data"]["company"]["status"] == "stub_complete"
        # Should emit phase_start + 2 findings
        phase_starts = [e for e in writer.events if e.type == "phase_start"]
        findings = [e for e in writer.events if e.type == "research_finding"]
        assert len(phase_starts) == 1
        assert len(findings) == 2

    def test_unknown_phase_skipped(self, base_state, monkeypatch):
        writer = MockWriter()
        monkeypatch.setattr("api.agents.planner.get_stream_writer", lambda: writer)
        base_state["current_phase"] = "nonexistent_phase"
        result = execute_phase_node(base_state)

        assert result["phase_results"]["nonexistent_phase"]["status"] == "skipped"

    def test_empty_phase(self, base_state, monkeypatch):
        writer = MockWriter()
        monkeypatch.setattr("api.agents.planner.get_stream_writer", lambda: writer)
        base_state["current_phase"] = ""
        result = execute_phase_node(base_state)
        assert result == {}


class TestCheckInterruptNode:
    def test_not_interrupted(self, base_state):
        base_state["is_interrupted"] = False
        result = check_interrupt_node(base_state)
        assert result["is_interrupted"] is False

    def test_correction_interrupt(self, base_state):
        base_state["is_interrupted"] = True
        base_state["interrupt_message"] = "Revenue is 50M not 30M"
        result = check_interrupt_node(base_state)
        assert result["interrupt_type"] == "correction"
        assert result["is_interrupted"] is False
        assert "Revenue is 50M not 30M" in result["user_corrections"]

    def test_stop_interrupt(self, base_state):
        base_state["is_interrupted"] = True
        base_state["interrupt_message"] = "stop"
        result = check_interrupt_node(base_state)
        assert result["interrupt_type"] == "stop"

    def test_question_interrupt(self, base_state):
        base_state["is_interrupted"] = True
        base_state["interrupt_message"] = "What is the market size?"
        result = check_interrupt_node(base_state)
        assert result["interrupt_type"] == "question"
        assert result["is_interrupted"] is False

    def test_redirect_interrupt(self, base_state):
        base_state["is_interrupted"] = True
        base_state["interrupt_message"] = "Actually focus on competitors"
        result = check_interrupt_node(base_state)
        assert result["interrupt_type"] == "redirect"
        assert result["is_interrupted"] is False


class TestAdvancePhaseNode:
    def test_advance_to_next(self, base_state):
        base_state["phase_index"] = 0
        result = advance_phase_node(base_state)
        assert result["phase_index"] == 1
        assert result["current_phase"] == "research_market"

    def test_advance_to_last(self, base_state):
        base_state["phase_index"] = 2
        result = advance_phase_node(base_state)
        assert result["phase_index"] == 3
        assert result["current_phase"] == "review_and_score"

    def test_advance_past_end(self, base_state):
        base_state["phase_index"] = 3
        result = advance_phase_node(base_state)
        assert result["phase_index"] == 4
        assert result["current_phase"] == ""


# ---------------------------------------------------------------------------
# Router tests
# ---------------------------------------------------------------------------


class TestPhaseRouter:
    def test_no_interrupt(self, base_state):
        base_state["is_interrupted"] = False
        assert phase_router(base_state) == "advance_phase"

    def test_interrupted(self, base_state):
        base_state["is_interrupted"] = True
        assert phase_router(base_state) == "check_interrupt"


class TestInterruptRouter:
    def test_stop_ends(self, base_state):
        base_state["interrupt_type"] = "stop"
        assert interrupt_router(base_state) == "__end__"

    def test_correction_resumes(self, base_state):
        base_state["interrupt_type"] = "correction"
        assert interrupt_router(base_state) == "execute_phase"

    def test_question_resumes(self, base_state):
        base_state["interrupt_type"] = "question"
        assert interrupt_router(base_state) == "execute_phase"

    def test_redirect_resumes(self, base_state):
        base_state["interrupt_type"] = "redirect"
        assert interrupt_router(base_state) == "execute_phase"


class TestAdvanceRouter:
    def test_has_next_phase(self, base_state):
        base_state["current_phase"] = "research_market"
        assert advance_router(base_state) == "execute_phase"

    def test_no_more_phases(self, base_state):
        base_state["current_phase"] = ""
        assert advance_router(base_state) == "__end__"


# ---------------------------------------------------------------------------
# Plan state persistence tests
# ---------------------------------------------------------------------------


class TestPlanStatePersistence:
    def test_save_and_get(self):
        state = {"plan_id": "p1", "current_phase": "research"}
        save_active_plan("thread-1", state)
        assert get_active_plan("thread-1") == state

    def test_get_nonexistent(self):
        assert get_active_plan("nonexistent") is None

    def test_clear(self):
        save_active_plan("thread-2", {"plan_id": "p2"})
        clear_active_plan("thread-2")
        assert get_active_plan("thread-2") is None

    def test_clear_nonexistent(self):
        # Should not raise
        clear_active_plan("nonexistent")

    def test_list_active(self):
        # Clear any previous state
        for tid in list(list_active_plans().keys()):
            clear_active_plan(tid)

        save_active_plan("t1", {"plan_id": "p1"})
        save_active_plan("t2", {"plan_id": "p2"})
        active = list_active_plans()
        assert active == {"t1": "p1", "t2": "p2"}

        # Cleanup
        clear_active_plan("t1")
        clear_active_plan("t2")


# ---------------------------------------------------------------------------
# Phase handler registry
# ---------------------------------------------------------------------------


class TestPhaseHandlerRegistry:
    def test_all_standard_phases_have_handlers(self):
        expected = {
            "research_company",
            "research_market",
            "build_strategy",
            "review_and_score",
        }
        assert set(PHASE_HANDLERS.keys()) == expected

    def test_handlers_are_callable(self):
        for name, handler in PHASE_HANDLERS.items():
            assert callable(handler), f"Handler for '{name}' is not callable"


# ---------------------------------------------------------------------------
# End-to-end graph execution tests
# ---------------------------------------------------------------------------


class TestPlannerGraphE2E:
    def test_full_plan_execution(self, sample_plan_config):
        """Run the planner through all 4 phases and verify completion."""
        events = list(
            execute_planner_turn(
                message="Build a GTM strategy",
                plan_config=sample_plan_config,
                tool_context={"tenant_id": "test"},
            )
        )

        # Should have a done event at the end
        done_events = [e for e in events if e.type == "done"]
        assert len(done_events) == 1

        done = done_events[0]
        assert done.data["plan_id"] == "plan-test-001"
        completed = done.data["phases_completed"]
        assert "research_company" in completed
        assert "research_market" in completed
        assert "build_strategy" in completed
        assert "review_and_score" in completed

    def test_phase_start_events_emitted(self, sample_plan_config):
        """Verify phase_start events are emitted for each phase."""
        events = list(
            execute_planner_turn(
                message="Build strategy",
                plan_config=sample_plan_config,
                tool_context={"tenant_id": "test"},
            )
        )

        phase_starts = [e for e in events if e.type == "phase_start"]
        # 1 for initialize + 4 for each phase
        assert len(phase_starts) >= 5

    def test_research_finding_events(self, sample_plan_config):
        """Verify research_finding events are emitted during execution."""
        events = list(
            execute_planner_turn(
                message="Build strategy",
                plan_config=sample_plan_config,
                tool_context={"tenant_id": "test"},
            )
        )

        findings = [e for e in events if e.type == "research_finding"]
        # Each of 4 phases emits at least 2 findings
        assert len(findings) >= 8

    def test_empty_phases_plan(self):
        """Plan with no phases should complete immediately."""
        plan = {"id": "empty", "name": "Empty", "phases": []}
        events = list(
            execute_planner_turn(
                message="Start",
                plan_config=plan,
                tool_context={"tenant_id": "test"},
            )
        )

        done_events = [e for e in events if e.type == "done"]
        assert len(done_events) == 1
        assert done_events[0].data["phases_completed"] == []

    def test_single_phase_plan(self):
        """Plan with one phase should execute it and complete."""
        plan = {"id": "single", "name": "Single", "phases": ["research_company"]}
        events = list(
            execute_planner_turn(
                message="Research",
                plan_config=plan,
                tool_context={"tenant_id": "test"},
            )
        )

        done_events = [e for e in events if e.type == "done"]
        assert len(done_events) == 1
        assert "research_company" in done_events[0].data["phases_completed"]

    def test_unknown_phase_skipped(self):
        """Phases without handlers should be skipped gracefully."""
        plan = {
            "id": "with-unknown",
            "name": "Unknown Phase",
            "phases": ["research_company", "future_phase", "review_and_score"],
        }
        events = list(
            execute_planner_turn(
                message="Build",
                plan_config=plan,
                tool_context={"tenant_id": "test"},
            )
        )

        done_events = [e for e in events if e.type == "done"]
        assert len(done_events) == 1
        completed = done_events[0].data["phases_completed"]
        # research_company and review_and_score should complete
        assert "research_company" in completed
        assert "review_and_score" in completed
        # future_phase was skipped, not completed
        assert "future_phase" not in completed

    def test_plan_with_system_prompt(self, sample_plan_config):
        """Planner accepts an optional system prompt."""
        events = list(
            execute_planner_turn(
                message="Build",
                plan_config=sample_plan_config,
                tool_context={"tenant_id": "test"},
                system_prompt="You are a GTM strategist.",
            )
        )

        done_events = [e for e in events if e.type == "done"]
        assert len(done_events) == 1


# ---------------------------------------------------------------------------
# Build graph compilation test
# ---------------------------------------------------------------------------


class TestBuildPlannerGraph:
    def test_compiles(self, sample_plan_config):
        graph = build_planner_graph(sample_plan_config)
        assert graph is not None
