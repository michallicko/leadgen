"""Unit tests for api/agents/graph.py — graph execution and SSE generation."""

from api.agents.graph import _build_tool_calls_summary
from api.agents.nodes import route_node, should_continue, after_tools
from api.agents.state import AgentState, create_initial_state


# ---------------------------------------------------------------------------
# Node: route
# ---------------------------------------------------------------------------


class TestRouteNode:
    def test_first_iteration_strategy_uses_sonnet(self):
        state = create_initial_state(
            messages=[],
            system_prompt="",
            tools=[],
            tool_context={},
            phase="strategy",
        )
        result = route_node(state)
        assert result["model"] == "claude-sonnet-4-5-20241022"

    def test_first_iteration_contacts_uses_haiku(self):
        state = create_initial_state(
            messages=[],
            system_prompt="",
            tools=[],
            tool_context={},
            phase="contacts",
        )
        result = route_node(state)
        assert result["model"] == "claude-haiku-4-5-20251001"

    def test_subsequent_iteration_uses_haiku(self):
        state = create_initial_state(
            messages=[],
            system_prompt="",
            tools=[],
            tool_context={},
            phase="strategy",
        )
        state["iteration_count"] = 3
        result = route_node(state)
        assert result["model"] == "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# Conditional edges
# ---------------------------------------------------------------------------


class TestShouldContinue:
    def test_no_tool_calls_returns_end(self):
        state: AgentState = {
            "stop_reason": "end_turn",
            "content_blocks": [{"type": "text", "text": "Hello"}],
            "iteration_count": 1,
        }
        assert should_continue(state) == "end"

    def test_tool_use_returns_execute_tools(self):
        state: AgentState = {
            "stop_reason": "tool_use",
            "content_blocks": [
                {"type": "text", "text": "Let me search"},
                {"type": "tool_use", "id": "tc-1", "name": "web_search", "input": {}},
            ],
            "iteration_count": 1,
        }
        assert should_continue(state) == "execute_tools"

    def test_max_iterations_returns_end(self):
        state: AgentState = {
            "stop_reason": "tool_use",
            "content_blocks": [
                {"type": "tool_use", "id": "tc-1", "name": "web_search", "input": {}},
            ],
            "iteration_count": 25,
        }
        assert should_continue(state) == "end"


class TestAfterTools:
    def test_no_halt_continues(self):
        state: AgentState = {
            "should_halt": False,
            "iteration_count": 2,
        }
        assert after_tools(state) == "call_model"

    def test_halt_stops(self):
        state: AgentState = {
            "should_halt": True,
            "iteration_count": 2,
        }
        assert after_tools(state) == "halt"

    def test_max_iterations_stops(self):
        state: AgentState = {
            "should_halt": False,
            "iteration_count": 25,
        }
        assert after_tools(state) == "end"


# ---------------------------------------------------------------------------
# Tool calls summary
# ---------------------------------------------------------------------------


class TestBuildToolCallsSummary:
    def test_empty(self):
        state: AgentState = {"tool_calls": []}
        result = _build_tool_calls_summary(state)
        assert result == []

    def test_with_calls(self):
        state: AgentState = {
            "tool_calls": [
                {
                    "tool_name": "web_search",
                    "tool_call_id": "tc-1",
                    "input_args": {"q": "test"},
                    "output": {"results": []},
                    "is_error": False,
                    "error_message": None,
                    "duration_ms": 100,
                },
                {
                    "tool_name": "get_doc",
                    "tool_call_id": "tc-2",
                    "input_args": {},
                    "output": None,
                    "is_error": True,
                    "error_message": "Not found",
                    "duration_ms": 5,
                },
            ],
        }
        result = _build_tool_calls_summary(state)
        assert len(result) == 2
        assert result[0]["status"] == "success"
        assert result[1]["status"] == "error"
        assert result[1]["error_message"] == "Not found"
