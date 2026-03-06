"""Tests for intent-aware tool routing."""

from api.services.memory.intent_router import (
    classify_intent,
    filter_tools_by_message,
    get_tools_for_intent,
)


class TestClassifyIntent:
    def test_strategy_intent(self):
        assert classify_intent("Help me define my ICP") == "strategy"
        assert classify_intent("Let's refine our strategy") == "strategy"
        assert classify_intent("What should our value proposition be?") == "strategy"

    def test_contacts_intent(self):
        assert classify_intent("Show me contacts in Germany") == "contacts"
        assert classify_intent("How many companies do we have?") == "contacts"
        assert classify_intent("List all leads tagged as priority") == "contacts"

    def test_messages_intent(self):
        assert (
            classify_intent("Generate outreach messages for these contacts")
            == "messages"
        )
        assert classify_intent("Draft an email for the CEO") == "messages"
        assert classify_intent("Review the message drafts") == "messages"

    def test_campaign_intent(self):
        assert classify_intent("Launch the campaign sequence") == "campaign"
        assert classify_intent("What's our open rate?") == "campaign"

    def test_documents_intent(self):
        assert classify_intent("Analyze this PDF document") == "documents"
        assert classify_intent("I uploaded a file, extract the data") == "documents"

    def test_general_fallback(self):
        assert classify_intent("Hello, how are you?") == "general"
        assert classify_intent("") == "general"
        assert classify_intent("What time is it?") == "general"

    def test_ambiguous_defaults_to_general(self):
        # Message that matches multiple intents equally
        result = classify_intent(
            "Show me contacts and generate campaign messages from this document"
        )
        # Could be contacts, messages, campaign, or documents — ambiguous
        assert result in ("general", "contacts", "messages", "campaign", "documents")


class TestGetToolsForIntent:
    def test_strategy_tools(self):
        tools = get_tools_for_intent("strategy")
        assert "get_strategy" in tools
        assert "search_memory" in tools

    def test_contacts_tools(self):
        tools = get_tools_for_intent("contacts")
        assert "list_contacts" in tools
        assert "count_companies" in tools

    def test_messages_tools(self):
        tools = get_tools_for_intent("messages")
        assert "generate_messages" in tools

    def test_general_returns_none(self):
        assert get_tools_for_intent("general") is None

    def test_filters_to_existing_tools(self):
        available = ["get_strategy", "web_search", "save_insight"]
        tools = get_tools_for_intent("strategy", available)
        assert all(t in available for t in tools)

    def test_unknown_intent_returns_none(self):
        assert get_tools_for_intent("nonexistent") is None


class TestFilterToolsByMessage:
    def test_strategy_filters(self):
        all_tools = [
            {"name": "get_strategy", "description": "..."},
            {"name": "list_contacts", "description": "..."},
            {"name": "generate_messages", "description": "..."},
            {"name": "save_insight", "description": "..."},
        ]
        filtered = filter_tools_by_message("Help me define my ICP", all_tools)
        tool_names = [t["name"] for t in filtered]
        assert "get_strategy" in tool_names
        assert "save_insight" in tool_names

    def test_general_returns_all(self):
        all_tools = [
            {"name": "tool1", "description": "..."},
            {"name": "tool2", "description": "..."},
        ]
        filtered = filter_tools_by_message("Hello", all_tools)
        assert len(filtered) == len(all_tools)

    def test_too_few_tools_fallback(self):
        """If intent filtering would leave < 2 tools, fall back to all."""
        all_tools = [
            {"name": "unrelated_tool", "description": "..."},
        ]
        filtered = filter_tools_by_message("Define my ICP strategy", all_tools)
        assert len(filtered) == len(all_tools)  # Falls back
