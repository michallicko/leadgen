"""Tests for the tool registry module."""

import pytest

from api.services.tool_registry import (
    ToolContext,
    ToolDefinition,
    clear_registry,
    get_tool,
    get_tools_for_api,
    register_tool,
    unregister_tool,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Ensure a clean registry for each test."""
    clear_registry()
    yield
    clear_registry()


def _make_tool(name="test_tool", description="A test tool"):
    """Helper to create a simple ToolDefinition."""
    return ToolDefinition(
        name=name,
        description=description,
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
        handler=lambda args, ctx: {"result": "ok"},
    )


class TestRegisterTool:
    def test_register_and_lookup(self):
        tool = _make_tool()
        register_tool(tool)
        assert get_tool("test_tool") is tool

    def test_register_duplicate_raises(self):
        register_tool(_make_tool())
        with pytest.raises(ValueError, match="already registered"):
            register_tool(_make_tool())

    def test_unregister(self):
        register_tool(_make_tool())
        unregister_tool("test_tool")
        assert get_tool("test_tool") is None

    def test_unregister_nonexistent_is_noop(self):
        unregister_tool("nonexistent")  # Should not raise

    def test_get_tool_not_found(self):
        assert get_tool("nonexistent") is None


class TestGetToolsForAPI:
    def test_empty_registry(self):
        assert get_tools_for_api() == []

    def test_single_tool(self):
        register_tool(_make_tool("get_data", "Get some data"))
        tools = get_tools_for_api()
        assert len(tools) == 1
        assert tools[0]["name"] == "get_data"
        assert tools[0]["description"] == "Get some data"
        assert "type" in tools[0]["input_schema"]

    def test_multiple_tools(self):
        register_tool(_make_tool("tool_a", "Tool A"))
        register_tool(_make_tool("tool_b", "Tool B"))
        tools = get_tools_for_api()
        assert len(tools) == 2
        names = {t["name"] for t in tools}
        assert names == {"tool_a", "tool_b"}

    def test_api_format_matches_claude_spec(self):
        """Verify output matches Claude API tools format."""
        register_tool(_make_tool())
        tools = get_tools_for_api()
        tool = tools[0]
        # Must have exactly these keys
        assert set(tool.keys()) == {"name", "description", "input_schema"}
        # input_schema must be a valid JSON Schema object
        assert tool["input_schema"]["type"] == "object"
        assert "properties" in tool["input_schema"]


class TestToolContext:
    def test_context_creation(self):
        ctx = ToolContext(
            tenant_id="tenant-123",
            user_id="user-456",
            document_id="doc-789",
        )
        assert ctx.tenant_id == "tenant-123"
        assert ctx.user_id == "user-456"
        assert ctx.document_id == "doc-789"

    def test_context_optional_fields(self):
        ctx = ToolContext(tenant_id="tenant-123")
        assert ctx.user_id is None
        assert ctx.document_id is None


class TestToolHandler:
    def test_handler_receives_args_and_context(self):
        """Verify handlers get the correct arguments."""
        received = {}

        def handler(args, ctx):
            received["args"] = args
            received["ctx"] = ctx
            return {"status": "done"}

        tool = ToolDefinition(
            name="test_handler",
            description="Tests handler",
            input_schema={"type": "object", "properties": {}},
            handler=handler,
        )
        register_tool(tool)

        ctx = ToolContext(tenant_id="t1", user_id="u1")
        result = tool.handler({"key": "value"}, ctx)

        assert result == {"status": "done"}
        assert received["args"] == {"key": "value"}
        assert received["ctx"].tenant_id == "t1"
