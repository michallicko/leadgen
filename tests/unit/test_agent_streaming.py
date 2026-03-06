"""Unit tests for api/agents/streaming.py — AG-UI event generation."""

import json


from api.agents.streaming import (
    AGUIEvent,
    legacy_chunk,
    legacy_done,
    legacy_tool_result,
    legacy_tool_start,
    run_finished,
    run_started,
    state_delta,
    text_message_content,
    text_message_end,
    text_message_start,
    tool_call_args,
    tool_call_end,
    tool_call_start,
)


class TestAGUIEvent:
    def test_to_sse_format(self):
        event = AGUIEvent(type="TEST", data={"key": "value"})
        sse = event.to_sse()
        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")

        payload = json.loads(sse[6:-2])
        assert payload["type"] == "TEST"
        assert payload["key"] == "value"


class TestRunEvents:
    def test_run_started(self):
        event = run_started("run-1", "thread-1")
        assert event.type == "RUN_STARTED"
        assert event.data["run_id"] == "run-1"
        assert event.data["thread_id"] == "thread-1"

    def test_run_finished(self):
        event = run_finished(
            run_id="run-1",
            tool_calls=[{"tool_name": "search", "status": "success"}],
            model="claude-haiku-4-5-20251001",
            total_input_tokens=100,
            total_output_tokens=50,
            total_cost_usd="0.001",
        )
        assert event.type == "RUN_FINISHED"
        assert event.data["run_id"] == "run-1"
        assert event.data["total_input_tokens"] == 100
        assert len(event.data["tool_calls"]) == 1


class TestTextMessageEvents:
    def test_start(self):
        event = text_message_start("msg-1")
        assert event.type == "TEXT_MESSAGE_START"
        assert event.data["message_id"] == "msg-1"
        assert event.data["role"] == "assistant"

    def test_content(self):
        event = text_message_content("msg-1", "Hello world")
        assert event.type == "TEXT_MESSAGE_CONTENT"
        assert event.data["delta"] == "Hello world"

    def test_end(self):
        event = text_message_end("msg-1")
        assert event.type == "TEXT_MESSAGE_END"
        assert event.data["message_id"] == "msg-1"


class TestToolCallEvents:
    def test_start(self):
        event = tool_call_start("tc-1", "web_search")
        assert event.type == "TOOL_CALL_START"
        assert event.data["tool_name"] == "web_search"
        assert event.data["tool_call_type"] == "function"

    def test_args(self):
        event = tool_call_args("tc-1", '{"query": "test"}')
        assert event.type == "TOOL_CALL_ARGS"
        assert event.data["delta"] == '{"query": "test"}'

    def test_end(self):
        event = tool_call_end("tc-1", "web_search", "success", "Found 5 results", 250)
        assert event.type == "TOOL_CALL_END"
        assert event.data["status"] == "success"
        assert event.data["duration_ms"] == 250


class TestStateDelta:
    def test_single_operation(self):
        event = state_delta(
            [
                {"op": "replace", "path": "/document_changed", "value": True},
            ]
        )
        assert event.type == "STATE_DELTA"
        assert len(event.data["delta"]) == 1
        assert event.data["delta"][0]["path"] == "/document_changed"

    def test_multiple_operations(self):
        event = state_delta(
            [
                {"op": "replace", "path": "/document_changed", "value": True},
                {"op": "replace", "path": "/changes_summary", "value": "Updated ICP"},
            ]
        )
        assert len(event.data["delta"]) == 2


class TestLegacyEvents:
    def test_legacy_chunk(self):
        sse = legacy_chunk("Hello")
        payload = json.loads(sse[6:-2])
        assert payload["type"] == "chunk"
        assert payload["text"] == "Hello"

    def test_legacy_tool_start(self):
        sse = legacy_tool_start("web_search", "tc-1", {"query": "test"})
        payload = json.loads(sse[6:-2])
        assert payload["type"] == "tool_start"
        assert payload["tool_name"] == "web_search"

    def test_legacy_tool_result(self):
        sse = legacy_tool_result("tc-1", "web_search", "success", "Done", "{}", 100)
        payload = json.loads(sse[6:-2])
        assert payload["type"] == "tool_result"
        assert payload["status"] == "success"

    def test_legacy_done(self):
        sse = legacy_done(
            message_id="msg-1",
            tool_calls=[],
            model="claude-haiku-4-5-20251001",
            total_input_tokens=100,
            total_output_tokens=50,
            total_cost_usd="0.001",
        )
        payload = json.loads(sse[6:-2])
        assert payload["type"] == "done"
        assert payload["message_id"] == "msg-1"

    def test_legacy_done_with_document_changed(self):
        sse = legacy_done(
            message_id="msg-1",
            tool_calls=[],
            model="claude-haiku-4-5-20251001",
            total_input_tokens=0,
            total_output_tokens=0,
            total_cost_usd="0",
            document_changed=True,
            changes_summary="Updated Executive Summary",
        )
        payload = json.loads(sse[6:-2])
        assert payload["document_changed"] is True
        assert payload["changes_summary"] == "Updated Executive Summary"
