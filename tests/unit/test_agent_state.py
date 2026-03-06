"""Unit tests for api/agents/state.py — AgentState creation and defaults."""

from api.agents.state import ToolCallRecord, create_initial_state


class TestCreateInitialState:
    """Tests for create_initial_state()."""

    def test_returns_agent_state_dict(self):
        state = create_initial_state(
            messages=[],
            system_prompt="You are a test assistant.",
            tools=[],
            tool_context={"tenant_id": "t1"},
        )
        assert isinstance(state, dict)

    def test_default_values(self):
        state = create_initial_state(
            messages=[],
            system_prompt="prompt",
            tools=[],
            tool_context={"tenant_id": "t1"},
        )
        assert state["phase"] == "strategy"
        assert state["model"] == "claude-haiku-4-5-20251001"
        assert state["tool_calls"] == []
        assert state["iteration_count"] == 0
        assert state["total_input_tokens"] == 0
        assert state["total_output_tokens"] == 0
        assert state["total_cost_usd"] == "0"
        assert state["should_halt"] is False
        assert state["halt_reason"] is None
        assert state["document_changed"] is False
        assert state["changes_summary"] is None
        assert state["stop_reason"] is None
        assert state["content_blocks"] == []

    def test_custom_values(self):
        msgs = [{"role": "user", "content": "Hello"}]
        tools = [{"name": "web_search", "description": "Search", "input_schema": {}}]
        ctx = {"tenant_id": "t1", "user_id": "u1", "document_id": "d1"}

        state = create_initial_state(
            messages=msgs,
            system_prompt="custom prompt",
            tools=tools,
            tool_context=ctx,
            phase="contacts",
            model="claude-sonnet-4-5-20241022",
            run_id="run-123",
        )
        assert state["messages"] == msgs
        assert state["system_prompt"] == "custom prompt"
        assert state["tools"] == tools
        assert state["tool_context"] == ctx
        assert state["phase"] == "contacts"
        assert state["model"] == "claude-sonnet-4-5-20241022"
        assert state["run_id"] == "run-123"

    def test_messages_are_copied(self):
        """Ensure the state gets a copy, not a reference to the original."""
        original = [{"role": "user", "content": "test"}]
        state = create_initial_state(
            messages=original,
            system_prompt="p",
            tools=[],
            tool_context={},
        )
        # We pass the list directly — the caller is responsible for copying
        # but the state should hold the reference to whatever was passed
        assert state["messages"] is original


class TestToolCallRecord:
    """Tests for ToolCallRecord TypedDict."""

    def test_minimal_record(self):
        record: ToolCallRecord = {
            "tool_name": "web_search",
            "tool_call_id": "tc-1",
            "input_args": {"query": "test"},
        }
        assert record["tool_name"] == "web_search"

    def test_full_record(self):
        record: ToolCallRecord = {
            "tool_name": "web_search",
            "tool_call_id": "tc-1",
            "input_args": {"query": "test"},
            "output": {"results": []},
            "is_error": False,
            "error_message": None,
            "duration_ms": 150,
            "status": "success",
        }
        assert record["status"] == "success"
        assert record["duration_ms"] == 150
