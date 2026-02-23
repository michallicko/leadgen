"""Tests for the agent executor module."""

from unittest.mock import MagicMock

import pytest

from api.services.agent_executor import (
    MAX_TOOL_ITERATIONS,
    _execute_tool,
    _summarize_output,
    _truncate,
    execute_agent_turn,
)
from api.services.tool_registry import (
    ToolContext,
    ToolDefinition,
    clear_registry,
    register_tool,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Ensure a clean registry for each test."""
    clear_registry()
    yield
    clear_registry()


def _register_echo_tool():
    """Register a simple echo tool that returns its input."""
    register_tool(
        ToolDefinition(
            name="echo",
            description="Echoes input back",
            input_schema={"type": "object", "properties": {}},
            handler=lambda args, ctx: {"echoed": args},
        )
    )


def _register_failing_tool():
    """Register a tool that always raises an exception."""
    def fail_handler(args, ctx):
        raise ValueError("Tool exploded!")

    register_tool(
        ToolDefinition(
            name="fail_tool",
            description="Always fails",
            input_schema={"type": "object", "properties": {}},
            handler=fail_handler,
        )
    )


def _mock_client_response(content_blocks, stop_reason="end_turn", usage=None):
    """Create a mock response dict matching query_with_tools output."""
    return {
        "content": content_blocks,
        "model": "claude-haiku-4-5-20251001",
        "usage": usage or {"input_tokens": 100, "output_tokens": 50},
        "stop_reason": stop_reason,
    }


class TestTruncate:
    def test_short_string(self):
        assert _truncate("hello", 10) == "hello"

    def test_exact_length(self):
        assert _truncate("hello", 5) == "hello"

    def test_long_string(self):
        result = _truncate("hello world", 8)
        assert len(result) == 8
        assert result.endswith("...")


class TestSummarizeOutput:
    def test_none_output(self):
        assert _summarize_output("my_tool", None) == "Completed my_tool"

    def test_output_with_summary_key(self):
        output = {"summary": "Did the thing", "data": "..."}
        assert _summarize_output("my_tool", output) == "Did the thing"

    def test_output_without_summary(self):
        output = {"data": "something"}
        assert _summarize_output("my_tool", output) == "Completed my_tool"


class TestExecuteTool:
    def test_unknown_tool(self):
        ctx = ToolContext(tenant_id="t1")
        record = _execute_tool("nonexistent", {}, ctx)
        assert record.is_error is True
        assert "Unknown tool" in record.error_message
        assert record.duration_ms is not None

    def test_successful_execution(self):
        _register_echo_tool()
        ctx = ToolContext(tenant_id="t1")
        record = _execute_tool("echo", {"key": "value"}, ctx)
        assert record.is_error is False
        assert record.output == {"echoed": {"key": "value"}}
        assert record.duration_ms is not None
        assert record.duration_ms >= 0

    def test_failed_execution(self):
        _register_failing_tool()
        ctx = ToolContext(tenant_id="t1")
        record = _execute_tool("fail_tool", {}, ctx)
        assert record.is_error is True
        assert "Tool exploded!" in record.error_message
        assert record.duration_ms is not None


class TestExecuteAgentTurn:
    """Tests for the main agent loop generator."""

    def _make_client(self, responses):
        """Create a mock client that returns responses in sequence."""
        client = MagicMock()
        client.default_model = "claude-haiku-4-5-20251001"
        client.query_with_tools = MagicMock(side_effect=responses)
        client._estimate_cost = MagicMock(return_value=0.001)
        return client

    def _collect_events(self, generator):
        """Consume all events from the generator."""
        return list(generator)

    def test_text_only_response(self):
        """No tools called -- should yield chunk + done."""
        client = self._make_client([
            _mock_client_response(
                [{"type": "text", "text": "Hello there!"}],
                stop_reason="end_turn",
            )
        ])

        events = self._collect_events(
            execute_agent_turn(
                client=client,
                system_prompt="You are helpful.",
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                tool_context=ToolContext(tenant_id="t1"),
            )
        )

        assert len(events) == 2
        assert events[0].type == "chunk"
        assert events[0].data["text"] == "Hello there!"
        assert events[1].type == "done"
        assert events[1].data["tool_calls"] == []

    def test_single_tool_call(self):
        """One tool call then final text response."""
        _register_echo_tool()

        client = self._make_client([
            # First call: Claude wants to use echo tool
            _mock_client_response(
                [
                    {"type": "text", "text": "Let me check..."},
                    {
                        "type": "tool_use",
                        "id": "toolu_01",
                        "name": "echo",
                        "input": {"query": "test"},
                    },
                ],
                stop_reason="tool_use",
            ),
            # Second call: Claude responds with text after tool result
            _mock_client_response(
                [{"type": "text", "text": "Here's what I found: test"}],
                stop_reason="end_turn",
            ),
        ])

        events = self._collect_events(
            execute_agent_turn(
                client=client,
                system_prompt="You are helpful.",
                messages=[{"role": "user", "content": "Echo test"}],
                tools=[{"name": "echo", "description": "Echo", "input_schema": {}}],
                tool_context=ToolContext(tenant_id="t1"),
            )
        )

        types = [e.type for e in events]
        assert types == ["tool_start", "tool_result", "chunk", "done"]

        # Verify tool_start
        assert events[0].data["tool_name"] == "echo"
        assert events[0].data["tool_call_id"] == "toolu_01"

        # Verify tool_result
        assert events[1].data["status"] == "success"
        assert events[1].data["tool_call_id"] == "toolu_01"
        assert events[1].data["duration_ms"] is not None

        # Verify final text
        assert events[2].data["text"] == "Here's what I found: test"

        # Verify done event
        done_data = events[3].data
        assert len(done_data["tool_calls"]) == 1
        assert done_data["tool_calls"][0]["tool_name"] == "echo"
        assert done_data["tool_calls"][0]["status"] == "success"
        assert done_data["total_input_tokens"] == 200  # 100 * 2 calls
        assert done_data["total_output_tokens"] == 100  # 50 * 2 calls

    def test_multi_tool_chaining(self):
        """Multiple sequential tool calls before final text."""
        _register_echo_tool()

        register_tool(
            ToolDefinition(
                name="greet",
                description="Greets",
                input_schema={"type": "object", "properties": {}},
                handler=lambda args, ctx: {"greeting": "Hello!"},
            )
        )

        client = self._make_client([
            # First call: Claude calls echo
            _mock_client_response(
                [
                    {
                        "type": "tool_use",
                        "id": "toolu_01",
                        "name": "echo",
                        "input": {"msg": "hi"},
                    },
                ],
                stop_reason="tool_use",
            ),
            # Second call: Claude calls greet
            _mock_client_response(
                [
                    {
                        "type": "tool_use",
                        "id": "toolu_02",
                        "name": "greet",
                        "input": {},
                    },
                ],
                stop_reason="tool_use",
            ),
            # Third call: final text
            _mock_client_response(
                [{"type": "text", "text": "Done with tools."}],
                stop_reason="end_turn",
            ),
        ])

        events = self._collect_events(
            execute_agent_turn(
                client=client,
                system_prompt="test",
                messages=[{"role": "user", "content": "Do stuff"}],
                tools=[],
                tool_context=ToolContext(tenant_id="t1"),
            )
        )

        types = [e.type for e in events]
        assert types == [
            "tool_start", "tool_result",  # echo
            "tool_start", "tool_result",  # greet
            "chunk", "done",
        ]

        done = events[-1]
        assert len(done.data["tool_calls"]) == 2
        assert done.data["total_input_tokens"] == 300  # 3 API calls

    def test_parallel_tool_calls(self):
        """Claude sends multiple tool_use blocks in a single response."""
        _register_echo_tool()
        register_tool(
            ToolDefinition(
                name="greet",
                description="Greets",
                input_schema={"type": "object", "properties": {}},
                handler=lambda args, ctx: {"greeting": "Hi"},
            )
        )

        client = self._make_client([
            # Single response with two tool_use blocks
            _mock_client_response(
                [
                    {
                        "type": "tool_use",
                        "id": "toolu_01",
                        "name": "echo",
                        "input": {"msg": "a"},
                    },
                    {
                        "type": "tool_use",
                        "id": "toolu_02",
                        "name": "greet",
                        "input": {},
                    },
                ],
                stop_reason="tool_use",
            ),
            # Final text after both tools
            _mock_client_response(
                [{"type": "text", "text": "Both done."}],
                stop_reason="end_turn",
            ),
        ])

        events = self._collect_events(
            execute_agent_turn(
                client=client,
                system_prompt="test",
                messages=[{"role": "user", "content": "Do two things"}],
                tools=[],
                tool_context=ToolContext(tenant_id="t1"),
            )
        )

        types = [e.type for e in events]
        assert types == [
            "tool_start", "tool_result",  # echo
            "tool_start", "tool_result",  # greet
            "chunk", "done",
        ]

    def test_tool_failure_handling(self):
        """Failed tool should yield error status and continue loop."""
        _register_failing_tool()

        client = self._make_client([
            # Claude calls the failing tool
            _mock_client_response(
                [
                    {
                        "type": "tool_use",
                        "id": "toolu_01",
                        "name": "fail_tool",
                        "input": {},
                    },
                ],
                stop_reason="tool_use",
            ),
            # Claude handles the error gracefully
            _mock_client_response(
                [{"type": "text", "text": "Sorry, that tool failed."}],
                stop_reason="end_turn",
            ),
        ])

        events = self._collect_events(
            execute_agent_turn(
                client=client,
                system_prompt="test",
                messages=[{"role": "user", "content": "Break it"}],
                tools=[],
                tool_context=ToolContext(tenant_id="t1"),
            )
        )

        types = [e.type for e in events]
        assert types == ["tool_start", "tool_result", "chunk", "done"]

        # Verify tool_result has error status
        tool_result = events[1]
        assert tool_result.data["status"] == "error"
        assert "Tool exploded!" in tool_result.data["summary"]

        # Done event should also reflect the error
        done = events[-1]
        assert done.data["tool_calls"][0]["status"] == "error"

    def test_unknown_tool_handling(self):
        """Unknown tool should yield error and continue."""
        client = self._make_client([
            _mock_client_response(
                [
                    {
                        "type": "tool_use",
                        "id": "toolu_01",
                        "name": "nonexistent_tool",
                        "input": {},
                    },
                ],
                stop_reason="tool_use",
            ),
            _mock_client_response(
                [{"type": "text", "text": "That tool doesn't exist."}],
                stop_reason="end_turn",
            ),
        ])

        events = self._collect_events(
            execute_agent_turn(
                client=client,
                system_prompt="test",
                messages=[{"role": "user", "content": "Call unknown"}],
                tools=[],
                tool_context=ToolContext(tenant_id="t1"),
            )
        )

        tool_result = [e for e in events if e.type == "tool_result"][0]
        assert tool_result.data["status"] == "error"
        assert "Unknown tool" in tool_result.data["summary"]

    def test_iteration_cap(self):
        """Should stop after MAX_TOOL_ITERATIONS and yield warning."""
        _register_echo_tool()

        # Create responses that always request another tool call
        responses = []
        for i in range(MAX_TOOL_ITERATIONS):
            responses.append(
                _mock_client_response(
                    [
                        {
                            "type": "tool_use",
                            "id": "toolu_{:02d}".format(i),
                            "name": "echo",
                            "input": {"iteration": i},
                        },
                    ],
                    stop_reason="tool_use",
                )
            )

        client = self._make_client(responses)

        events = self._collect_events(
            execute_agent_turn(
                client=client,
                system_prompt="test",
                messages=[{"role": "user", "content": "Loop forever"}],
                tools=[],
                tool_context=ToolContext(tenant_id="t1"),
            )
        )

        # Should have tool_start + tool_result for each iteration,
        # then chunk (warning) + done
        done_event = events[-1]
        assert done_event.type == "done"
        assert len(done_event.data["tool_calls"]) == MAX_TOOL_ITERATIONS

        # Second to last should be the warning chunk
        warning = events[-2]
        assert warning.type == "chunk"
        assert "maximum number of actions" in warning.data["text"]

    def test_cost_tracking(self):
        """Verify total cost is summed across all API calls."""
        client = self._make_client([
            _mock_client_response(
                [{"type": "text", "text": "Done."}],
                stop_reason="end_turn",
                usage={"input_tokens": 500, "output_tokens": 200},
            )
        ])
        client._estimate_cost = MagicMock(return_value=0.0025)

        events = self._collect_events(
            execute_agent_turn(
                client=client,
                system_prompt="test",
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                tool_context=ToolContext(tenant_id="t1"),
            )
        )

        done = events[-1]
        assert done.data["total_input_tokens"] == 500
        assert done.data["total_output_tokens"] == 200
        assert done.data["total_cost_usd"] == "0.0025"

    def test_messages_mutated_correctly(self):
        """Verify that messages array is appended with assistant + tool_result."""
        _register_echo_tool()
        messages = [{"role": "user", "content": "Test"}]

        client = self._make_client([
            _mock_client_response(
                [
                    {"type": "text", "text": "Calling echo..."},
                    {
                        "type": "tool_use",
                        "id": "toolu_01",
                        "name": "echo",
                        "input": {"data": "test"},
                    },
                ],
                stop_reason="tool_use",
            ),
            _mock_client_response(
                [{"type": "text", "text": "All done."}],
                stop_reason="end_turn",
            ),
        ])

        # Consume all events
        list(
            execute_agent_turn(
                client=client,
                system_prompt="test",
                messages=messages,
                tools=[],
                tool_context=ToolContext(tenant_id="t1"),
            )
        )

        # Messages should have: original user, assistant (tool_use), user (tool_result)
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"
        # Tool result should be in the user message content
        tool_results = messages[2]["content"]
        assert len(tool_results) == 1
        assert tool_results[0]["type"] == "tool_result"
        assert tool_results[0]["tool_use_id"] == "toolu_01"

    def test_empty_text_response(self):
        """Response with no text content should still yield done."""
        client = self._make_client([
            _mock_client_response(
                [],  # Empty content blocks
                stop_reason="end_turn",
            )
        ])

        events = self._collect_events(
            execute_agent_turn(
                client=client,
                system_prompt="test",
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                tool_context=ToolContext(tenant_id="t1"),
            )
        )

        # Should just get done event (no chunk since no text)
        assert len(events) == 1
        assert events[0].type == "done"
