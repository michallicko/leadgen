"""Unit tests for api/agents/prompts.py — layered prompt assembly."""

from api.agents.prompts import (
    PHASE_TOOL_MAP,
    SUMMARIZATION_THRESHOLD,
    build_capabilities_layer,
    build_context_layer,
    build_identity_layer,
    build_layered_system_prompt,
    build_layered_system_prompt_string,
    filter_tools_for_phase,
    prepare_conversation_messages,
)


# ---------------------------------------------------------------------------
# Layer 0: Identity
# ---------------------------------------------------------------------------


class TestIdentityLayer:
    def test_contains_company_name(self):
        result = build_identity_layer("Acme Corp")
        assert "Acme Corp" in result

    def test_contains_critical_rules(self):
        result = build_identity_layer("TestCo")
        assert "CRITICAL RULES" in result
        assert "NEVER use negative" in result

    def test_contains_tone_rules(self):
        result = build_identity_layer("TestCo")
        assert "TONE RULES" in result

    def test_contains_response_length(self):
        result = build_identity_layer("TestCo")
        assert "150 words" in result

    def test_contains_response_style(self):
        result = build_identity_layer("TestCo")
        assert "fractional CMO" in result


# ---------------------------------------------------------------------------
# Layer 1: Capabilities (phase-filtered tools)
# ---------------------------------------------------------------------------


class TestFilterToolsForPhase:
    SAMPLE_TOOLS = [
        {"name": "web_search", "description": "Search web", "input_schema": {}},
        {"name": "get_strategy_document", "description": "Get doc", "input_schema": {}},
        {"name": "get_contacts", "description": "Get contacts", "input_schema": {}},
        {"name": "unknown_tool", "description": "Unknown", "input_schema": {}},
    ]

    def test_strategy_phase_filters(self):
        result = filter_tools_for_phase(self.SAMPLE_TOOLS, "strategy")
        names = {t["name"] for t in result}
        assert "web_search" in names
        assert "get_strategy_document" in names
        assert "get_contacts" not in names
        assert "unknown_tool" not in names

    def test_contacts_phase_filters(self):
        result = filter_tools_for_phase(self.SAMPLE_TOOLS, "contacts")
        names = {t["name"] for t in result}
        assert "get_contacts" in names
        assert "web_search" in names

    def test_unknown_phase_returns_all(self):
        result = filter_tools_for_phase(self.SAMPLE_TOOLS, "unknown_phase")
        assert len(result) == len(self.SAMPLE_TOOLS)

    def test_all_phases_have_mappings(self):
        for phase in ("strategy", "contacts", "messages", "campaign"):
            assert phase in PHASE_TOOL_MAP


class TestCapabilitiesLayer:
    def test_contains_phase(self):
        tools = [{"name": "web_search", "description": "S", "input_schema": {}}]
        result = build_capabilities_layer(tools, "strategy")
        assert "strategy" in result

    def test_contains_tool_names(self):
        tools = [
            {"name": "web_search", "description": "S", "input_schema": {}},
            {"name": "get_doc", "description": "D", "input_schema": {}},
        ]
        result = build_capabilities_layer(tools, "strategy")
        assert "web_search" in result
        assert "get_doc" in result

    def test_contains_sections(self):
        result = build_capabilities_layer([], "strategy")
        assert "Executive Summary" in result


# ---------------------------------------------------------------------------
# Layer 2: Context
# ---------------------------------------------------------------------------


class TestContextLayer:
    def test_includes_objective(self):
        result = build_context_layer(
            document_content="",
            objective="Enter DACH market",
            enrichment_parts=None,
            phase="strategy",
            phase_instructions="",
            page_context=None,
            language=None,
        )
        assert "Enter DACH market" in result

    def test_includes_document_content(self):
        result = build_context_layer(
            document_content="## Executive Summary\nOur plan...",
            objective=None,
            enrichment_parts=None,
            phase="strategy",
            phase_instructions="",
            page_context=None,
            language=None,
        )
        assert "Our plan..." in result

    def test_empty_document_message(self):
        result = build_context_layer(
            document_content="",
            objective=None,
            enrichment_parts=None,
            phase="strategy",
            phase_instructions="",
            page_context=None,
            language=None,
        )
        assert "currently empty" in result

    def test_includes_enrichment(self):
        enrichment = ["COMPANY PROFILE:", "  Name: Acme Corp"]
        result = build_context_layer(
            document_content="",
            objective=None,
            enrichment_parts=enrichment,
            phase="strategy",
            phase_instructions="",
            page_context=None,
            language=None,
        )
        assert "Acme Corp" in result

    def test_includes_phase_instructions(self):
        result = build_context_layer(
            document_content="",
            objective=None,
            enrichment_parts=None,
            phase="strategy",
            phase_instructions="Do strategy things.",
            page_context=None,
            language=None,
        )
        assert "Do strategy things." in result


# ---------------------------------------------------------------------------
# Layer 3: Conversation summarization
# ---------------------------------------------------------------------------


class TestConversationSummarization:
    def test_below_threshold_no_change(self):
        messages = [{"role": "user", "content": f"msg {i}"} for i in range(10)]
        result = prepare_conversation_messages(messages)
        assert len(result) == 10

    def test_at_threshold_no_change(self):
        messages = [
            {"role": "user", "content": f"msg {i}"}
            for i in range(SUMMARIZATION_THRESHOLD)
        ]
        result = prepare_conversation_messages(messages)
        assert len(result) == SUMMARIZATION_THRESHOLD

    def test_above_threshold_summarizes(self):
        messages = [{"role": "user", "content": f"msg {i}"} for i in range(20)]
        result = prepare_conversation_messages(messages, client=None)
        # Should have: 1 summary + (20 - 10) = 11 messages
        assert len(result) == 11
        assert "summary" in result[0]["content"].lower()

    def test_summary_message_is_user_role(self):
        messages = [{"role": "user", "content": f"msg {i}"} for i in range(20)]
        result = prepare_conversation_messages(messages, client=None)
        assert result[0]["role"] == "user"

    def test_summary_preserves_recent_messages(self):
        messages = [{"role": "user", "content": f"msg {i}"} for i in range(20)]
        result = prepare_conversation_messages(messages, client=None)
        # Last message should be the 20th original message
        assert result[-1]["content"] == "msg 19"


# ---------------------------------------------------------------------------
# Full assembly
# ---------------------------------------------------------------------------


class TestLayeredSystemPrompt:
    def test_returns_three_content_blocks(self):
        result = build_layered_system_prompt(
            company_name="TestCo",
            tools=[],
            phase="strategy",
            document_content="",
        )
        assert len(result) == 3
        assert all(b["type"] == "text" for b in result)

    def test_first_two_blocks_have_cache_control(self):
        result = build_layered_system_prompt(
            company_name="TestCo",
            tools=[],
            phase="strategy",
            document_content="",
        )
        assert "cache_control" in result[0]
        assert result[0]["cache_control"] == {"type": "ephemeral"}
        assert "cache_control" in result[1]
        assert result[1]["cache_control"] == {"type": "ephemeral"}

    def test_third_block_no_cache_control(self):
        result = build_layered_system_prompt(
            company_name="TestCo",
            tools=[],
            phase="strategy",
            document_content="",
        )
        assert "cache_control" not in result[2]

    def test_string_version_concatenates(self):
        result = build_layered_system_prompt_string(
            company_name="TestCo",
            tools=[],
            phase="strategy",
            document_content="doc content",
        )
        assert isinstance(result, str)
        assert "TestCo" in result
        assert "doc content" in result
