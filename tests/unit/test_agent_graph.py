"""Unit tests for the LangGraph strategy agent (Sprint 11).

Tests the graph construction, prompt layering, AG-UI events,
and state management without requiring actual LLM calls.
"""

import json
from unittest.mock import MagicMock


from api.agents.events import (
    RUN_FINISHED,
    RUN_STARTED,
    TEXT_MESSAGE_CONTENT,
    TOOL_CALL_END,
    TOOL_CALL_START,
    run_finished,
    run_started,
    sse_to_agui,
    text_message_content,
    tool_call_end,
    tool_call_start,
)
from api.agents.graph import (
    SSEEvent,
    build_strategy_graph,
    build_system_messages,
    should_continue,
)
from api.agents.prompts.context import (
    STRATEGY_SECTIONS,
    _compute_section_status,
    build_context_block,
)
from api.agents.prompts.identity import (
    build_identity_blocks,
)


# ---------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------


class TestGraphConstruction:
    def test_graph_compiles(self):
        graph = build_strategy_graph()
        assert graph is not None

    def test_graph_has_agent_and_tools_nodes(self):
        """The compiled graph should have agent and tools nodes."""
        graph = build_strategy_graph()
        # CompiledStateGraph exposes nodes
        node_names = set(graph.nodes.keys())
        assert "agent" in node_names
        assert "tools" in node_names


# ---------------------------------------------------------------
# Routing logic
# ---------------------------------------------------------------


class TestShouldContinue:
    def test_empty_messages_returns_end(self):
        state = {"messages": [], "iteration": 0}
        assert should_continue(state) == "end"

    def test_no_tool_calls_returns_end(self):
        from langchain_core.messages import AIMessage

        msg = AIMessage(content="Hello")
        state = {"messages": [msg], "iteration": 0}
        assert should_continue(state) == "end"

    def test_with_tool_calls_returns_tools(self):
        from langchain_core.messages import AIMessage

        msg = AIMessage(
            content="",
            tool_calls=[{"name": "test_tool", "args": {}, "id": "tc_1"}],
        )
        state = {"messages": [msg], "iteration": 0}
        assert should_continue(state) == "tools"

    def test_max_iterations_returns_end(self):
        from langchain_core.messages import AIMessage

        msg = AIMessage(
            content="",
            tool_calls=[{"name": "test_tool", "args": {}, "id": "tc_1"}],
        )
        state = {"messages": [msg], "iteration": 25}
        assert should_continue(state) == "end"


# ---------------------------------------------------------------
# Prompt layering
# ---------------------------------------------------------------


class TestPromptLayering:
    def test_identity_blocks_have_cache_control(self):
        blocks = build_identity_blocks("TestCorp")
        assert len(blocks) == 2
        for block in blocks:
            assert block["type"] == "text"
            assert "cache_control" in block
            assert block["cache_control"]["type"] == "ephemeral"

    def test_identity_blocks_contain_company_name(self):
        blocks = build_identity_blocks("AcmeCorp")
        combined = " ".join(b["text"] for b in blocks)
        assert "AcmeCorp" in combined

    def test_identity_blocks_above_min_token_threshold(self):
        """Identity blocks should be >1024 tokens for caching."""
        blocks = build_identity_blocks("TestCorp")
        total_chars = sum(len(b["text"]) for b in blocks)
        # Rough estimate: 1 token ~= 4 chars, need > 1024 tokens
        assert total_chars > 4000

    def test_context_block_no_cache_control(self):
        doc = MagicMock()
        doc.content = ""
        doc.objective = "Test objective"
        doc.extracted_data = {}
        block = build_context_block(doc)
        assert block["type"] == "text"
        assert "cache_control" not in block

    def test_context_block_includes_objective(self):
        doc = MagicMock()
        doc.content = ""
        doc.objective = "Grow revenue 50%"
        doc.extracted_data = {}
        block = build_context_block(doc)
        assert "Grow revenue 50%" in block["text"]

    def test_build_system_messages_returns_system_message(self):
        from langchain_core.messages import SystemMessage

        doc = MagicMock()
        doc.content = ""
        doc.objective = "Test"
        doc.extracted_data = {}
        doc.phase = "strategy"

        msgs = build_system_messages(company_name="TestCorp", document=doc)
        assert len(msgs) == 1
        assert isinstance(msgs[0], SystemMessage)


# ---------------------------------------------------------------
# Section completeness
# ---------------------------------------------------------------


class TestSectionStatus:
    def test_empty_content(self):
        status = _compute_section_status("")
        assert len(status) == len(STRATEGY_SECTIONS)
        for line in status:
            assert "[EMPTY" in line

    def test_partial_section(self):
        content = (
            "## Executive Summary\n"
            + " ".join(["word"] * 30)
            + "\n\n## Value Proposition & Messaging\n"
        )
        status = _compute_section_status(content)
        exec_line = [s for s in status if "Executive Summary" in s][0]
        assert "[PARTIAL" in exec_line

    def test_complete_section(self):
        content = "## Executive Summary\n" + " ".join(["word"] * 100) + "\n"
        status = _compute_section_status(content)
        exec_line = [s for s in status if "Executive Summary" in s][0]
        assert "[COMPLETE" in exec_line


# ---------------------------------------------------------------
# AG-UI events
# ---------------------------------------------------------------


class TestAGUIEvents:
    def test_run_started_event(self):
        ev = run_started("thread-1", "run-1")
        assert ev.type == RUN_STARTED
        assert ev.data["threadId"] == "thread-1"
        assert ev.data["runId"] == "run-1"

    def test_run_finished_event(self):
        ev = run_finished("thread-1", "run-1")
        assert ev.type == RUN_FINISHED

    def test_text_message_content_event(self):
        ev = text_message_content("msg-1", "Hello world")
        assert ev.type == TEXT_MESSAGE_CONTENT
        assert ev.data["delta"] == "Hello world"

    def test_tool_call_start_event(self):
        ev = tool_call_start("tc-1", "web_search", {"query": "test"})
        assert ev.type == TOOL_CALL_START
        assert ev.data["toolCallName"] == "web_search"

    def test_tool_call_end_event(self):
        ev = tool_call_end("tc-1", "web_search", "success", "Found results", "", 150)
        assert ev.type == TOOL_CALL_END
        assert ev.data["status"] == "success"
        assert ev.data["durationMs"] == 150

    def test_to_sse_format(self):
        ev = run_started("t1", "r1")
        sse = ev.to_sse()
        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")
        payload = json.loads(sse[6:-2])
        assert payload["type"] == RUN_STARTED

    def test_sse_to_agui_chunk(self):
        events = sse_to_agui("chunk", {"text": "hello"}, "r1")
        assert len(events) == 1
        assert events[0].type == TEXT_MESSAGE_CONTENT
        assert events[0].data["delta"] == "hello"

    def test_sse_to_agui_tool_start(self):
        events = sse_to_agui(
            "tool_start",
            {"tool_call_id": "tc1", "tool_name": "test"},
            "r1",
        )
        assert events[0].type == TOOL_CALL_START

    def test_sse_to_agui_tool_result(self):
        events = sse_to_agui(
            "tool_result",
            {
                "tool_call_id": "tc1",
                "tool_name": "test",
                "status": "success",
                "summary": "OK",
            },
            "r1",
        )
        assert events[0].type == TOOL_CALL_END

    def test_sse_to_agui_done(self):
        events = sse_to_agui("done", {"tool_calls": [], "model": "haiku"}, "r1")
        assert events[0].type == RUN_FINISHED

    def test_sse_to_agui_section_update(self):
        from api.agents.events import STATE_DELTA

        events = sse_to_agui(
            "section_update",
            {
                "section": "Executive Summary",
                "content": "Test",
                "action": "update",
            },
            "r1",
        )
        assert events[0].type == STATE_DELTA


# ---------------------------------------------------------------
# SSEEvent dataclass
# ---------------------------------------------------------------


class TestSSEEvent:
    def test_sse_event_creation(self):
        ev = SSEEvent(type="chunk", data={"text": "hi"})
        assert ev.type == "chunk"
        assert ev.data["text"] == "hi"
