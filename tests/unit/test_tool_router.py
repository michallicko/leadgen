"""Tests for intent-aware tool routing (BL-264)."""

import pytest

from api.services.tool_registry import (
    ToolDefinition,
    clear_registry,
    register_tool,
)
from api.services.tool_router import (
    PHASE_TOOLS,
    UNIVERSAL_TOOLS,
    get_tools_for_context,
)


def _dummy_handler(args, ctx):
    return {}


@pytest.fixture(autouse=True)
def _register_sample_tools(app):
    """Register a set of sample tools for testing."""
    clear_registry()
    # Register a representative set of tools
    tool_names = set()
    for tools in PHASE_TOOLS.values():
        tool_names.update(tools)
    tool_names.update(UNIVERSAL_TOOLS)

    with app.app_context():
        for name in tool_names:
            register_tool(
                ToolDefinition(
                    name=name,
                    description="Test tool: {}".format(name),
                    input_schema={"type": "object", "properties": {}},
                    handler=_dummy_handler,
                )
            )
    yield
    clear_registry()


class TestGetToolsForContext:
    """Tests for get_tools_for_context()."""

    def test_strategy_phase_returns_strategy_tools(self, app):
        with app.app_context():
            tools = get_tools_for_context("strategy")
            names = {t["name"] for t in tools}

        for tool in PHASE_TOOLS["strategy"]:
            assert tool in names, "Missing strategy tool: {}".format(tool)

    def test_strategy_phase_excludes_campaign_tools(self, app):
        with app.app_context():
            tools = get_tools_for_context("strategy")
            names = {t["name"] for t in tools}

        # Campaign-only tools should not appear
        campaign_only = set(PHASE_TOOLS.get("campaign", [])) - set(
            PHASE_TOOLS["strategy"]
        ) - set(UNIVERSAL_TOOLS)
        for tool in campaign_only:
            assert tool not in names, "Unexpected campaign tool: {}".format(tool)

    def test_contacts_phase_returns_contacts_tools(self, app):
        with app.app_context():
            tools = get_tools_for_context("contacts")
            names = {t["name"] for t in tools}

        for tool in PHASE_TOOLS["contacts"]:
            assert tool in names

    def test_universal_tools_always_present(self, app):
        for phase in ["strategy", "contacts", "messages", "campaign"]:
            with app.app_context():
                tools = get_tools_for_context(phase)
                names = {t["name"] for t in tools}

            for tool in UNIVERSAL_TOOLS:
                assert tool in names, (
                    "Universal tool '{}' missing in phase '{}'".format(tool, phase)
                )

    def test_unknown_phase_returns_universal_only(self, app):
        with app.app_context():
            tools = get_tools_for_context("nonexistent_phase")
            names = {t["name"] for t in tools}

        # Should have universal tools
        for tool in UNIVERSAL_TOOLS:
            assert tool in names

        # Should not have phase-specific tools (beyond overlap with universal)
        total_expected = set(UNIVERSAL_TOOLS)
        assert names == total_expected

    def test_page_context_adds_extra_tools(self, app):
        with app.app_context():
            # Strategy phase + contacts page context
            tools = get_tools_for_context("strategy", page_context="contacts")
            names = {t["name"] for t in tools}

        # Should include strategy tools AND contacts page tools
        assert "update_strategy_section" in names  # from strategy phase
        assert "filter_contacts_by_icp" in names  # from contacts page context

    def test_returns_list_of_dicts(self, app):
        with app.app_context():
            tools = get_tools_for_context("strategy")

        assert isinstance(tools, list)
        for t in tools:
            assert isinstance(t, dict)
            assert "name" in t
            assert "description" in t
            assert "input_schema" in t
