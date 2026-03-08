"""Unit tests for the message router (BL-1010).

Tests keyword routing, Haiku classification (mocked), escalation
detection, and edge cases.
"""

from unittest.mock import MagicMock, patch

from api.agents.router import (
    RouteDecision,
    _keyword_route,
    _haiku_classify,
    handle_escalation,
    route_message,
)


# ---------------------------------------------------------------
# Keyword routing
# ---------------------------------------------------------------


class TestKeywordRoute:
    def test_greeting_routes_to_chat(self):
        for greeting in ["hi", "hello", "hey", "thanks", "ok"]:
            decision = _keyword_route(greeting, "playbook")
            assert decision is not None
            assert decision.target == "chat"
            assert decision.reason == "greeting"

    def test_data_lookup_routes_to_chat(self):
        queries = [
            "how many contacts do I have",
            "show me the companies",
            "list all batches",
            "count enriched contacts",
            "what's in my pipeline",
        ]
        for q in queries:
            decision = _keyword_route(q, "playbook")
            assert decision is not None
            assert decision.target == "chat"
            assert decision.reason == "data_lookup_keyword"

    def test_planning_commands_route_to_planner(self):
        commands = [
            "build a strategy for SaaS",
            "create an ICP tier",
            "generate messaging framework",
            "write executive summary",
            "analyze my competitors",
            "research this market",
            "draft the value proposition",
        ]
        for cmd in commands:
            decision = _keyword_route(cmd, "playbook")
            assert decision is not None, "Should route: {}".format(cmd)
            assert decision.target == "planner", "Expected planner for: {}".format(cmd)
            assert decision.reason == "planning_keyword"

    def test_domain_input_routes_to_planner(self):
        decision = _keyword_route("unitedarts.cz", "playbook")
        assert decision is not None
        assert decision.target == "planner"
        assert decision.reason == "domain_input"

    def test_domain_with_subdomain(self):
        decision = _keyword_route("app.example.com", "playbook")
        assert decision is not None
        assert decision.target == "planner"
        assert decision.reason == "domain_input"

    def test_help_request_routes_to_chat(self):
        queries = [
            "help me understand this",
            "how do i use the pipeline",
            "what can you do",
        ]
        for q in queries:
            decision = _keyword_route(q, "playbook")
            assert decision is not None
            assert decision.target == "chat"
            assert decision.reason == "help_request"

    def test_short_question_routes_to_chat(self):
        decision = _keyword_route("what is ICP?", "playbook")
        assert decision is not None
        assert decision.target == "chat"
        assert decision.reason == "short_question"

    def test_short_message_routes_to_chat(self):
        decision = _keyword_route("ok", "playbook")
        assert decision is not None
        assert decision.target == "chat"

    def test_very_short_message_routes_to_chat(self):
        decision = _keyword_route("hi", "playbook")
        assert decision is not None
        assert decision.target == "chat"

    def test_ambiguous_message_returns_none(self):
        # A message that doesn't match any keyword pattern
        decision = _keyword_route(
            "I think we should focus on enterprise customers", "playbook"
        )
        assert decision is None

    def test_sentence_with_dot_not_domain(self):
        # Sentences with dots should not be treated as domains
        decision = _keyword_route(
            "I think this is good. What do you think?", "playbook"
        )
        # Should not be domain_input (too many words)
        if decision is not None:
            assert decision.reason != "domain_input"

    def test_url_not_treated_as_domain(self):
        # URLs starting with http should not match domain pattern
        decision = _keyword_route("http://example.com", "playbook")
        if decision is not None:
            assert decision.reason != "domain_input"


# ---------------------------------------------------------------
# Haiku classification (mocked)
# ---------------------------------------------------------------


class TestHaikuClassify:
    @patch("api.agents.router.ChatAnthropic")
    def test_haiku_returns_planner(self, mock_chat_cls):
        mock_response = MagicMock()
        mock_response.content = "PLANNER"
        mock_instance = MagicMock()
        mock_instance.invoke.return_value = mock_response
        mock_chat_cls.return_value = mock_instance

        decision = _haiku_classify(
            "Let's rethink our approach to mid-market",
            "playbook",
            {"company_name": "Acme"},
            {"has_strategy": True},
        )
        assert decision.target == "planner"
        assert decision.reason == "haiku_classification"

    @patch("api.agents.router.ChatAnthropic")
    def test_haiku_returns_chat(self, mock_chat_cls):
        mock_response = MagicMock()
        mock_response.content = "CHAT"
        mock_instance = MagicMock()
        mock_instance.invoke.return_value = mock_response
        mock_chat_cls.return_value = mock_instance

        decision = _haiku_classify(
            "What does the pipeline look like?",
            "playbook",
            {"company_name": "Acme"},
            {"has_strategy": True},
        )
        assert decision.target == "chat"
        assert decision.reason == "haiku_classification"

    @patch("api.agents.router.ChatAnthropic")
    def test_haiku_defaults_to_chat_on_error(self, mock_chat_cls):
        mock_instance = MagicMock()
        mock_instance.invoke.side_effect = Exception("API error")
        mock_chat_cls.return_value = mock_instance

        decision = _haiku_classify(
            "Something ambiguous",
            "playbook",
            {},
            {},
        )
        assert decision.target == "chat"
        assert decision.reason == "haiku_fallback"

    @patch("api.agents.router.ChatAnthropic")
    def test_haiku_defaults_to_chat_on_garbled_response(self, mock_chat_cls):
        mock_response = MagicMock()
        mock_response.content = "I'm not sure what to classify this as"
        mock_instance = MagicMock()
        mock_instance.invoke.return_value = mock_response
        mock_chat_cls.return_value = mock_instance

        decision = _haiku_classify(
            "Something ambiguous",
            "playbook",
            {},
            {},
        )
        # Should default to chat since response doesn't cleanly parse as PLANNER
        assert decision.target == "chat"


# ---------------------------------------------------------------
# Escalation detection
# ---------------------------------------------------------------


class TestEscalation:
    def test_detects_escalation_signals(self):
        escalation_messages = [
            "that's wrong, I need something different",
            "not helpful at all",
            "try again with more detail",
            "do better please",
            "that's not what i asked for",
            "no, i meant something else",
        ]
        for msg in escalation_messages:
            decision = handle_escalation(msg, "thread-123")
            assert decision.target == "planner", "Should escalate: {}".format(msg)
            assert decision.reason == "escalation"

    def test_no_escalation_for_normal_messages(self):
        normal_messages = [
            "thanks, that looks good",
            "perfect, let's move on",
            "great work",
        ]
        for msg in normal_messages:
            decision = handle_escalation(msg, "thread-123")
            assert decision.target == "chat"
            assert decision.reason == "no_escalation"


# ---------------------------------------------------------------
# Full route_message integration
# ---------------------------------------------------------------


class TestRouteMessage:
    @patch("api.agents.router._haiku_classify")
    def test_keyword_match_skips_haiku(self, mock_haiku):
        decision = route_message(
            message="hello",
            page_context="playbook",
            thread_id="t-1",
            tenant_context={},
            state={},
        )
        assert decision.target == "chat"
        assert decision.reason == "greeting"
        mock_haiku.assert_not_called()

    @patch("api.agents.router._haiku_classify")
    def test_ambiguous_message_calls_haiku(self, mock_haiku):
        mock_haiku.return_value = RouteDecision(
            target="planner", reason="haiku_classification"
        )
        decision = route_message(
            message="I think we should pivot to enterprise customers and rethink everything",
            page_context="playbook",
            thread_id="t-1",
            tenant_context={},
            state={},
        )
        assert decision.target == "planner"
        mock_haiku.assert_called_once()

    @patch("api.agents.router.get_active_plan", create=True)
    def test_active_planner_always_wins(self, mock_get_plan):
        """When planner_bridge is available and plan is active, route to planner_interrupt."""
        mock_get_plan.return_value = {"plan_id": "p-123"}

        # Patch the import inside route_message
        with patch.dict(
            "sys.modules",
            {"api.agents.planner_bridge": MagicMock(get_active_plan=mock_get_plan)},
        ):
            decision = route_message(
                message="hello",  # Would normally go to chat
                page_context="playbook",
                thread_id="t-1",
                tenant_context={},
                state={},
            )
            assert decision.target == "planner_interrupt"
            assert decision.plan_id == "p-123"

    def test_planner_bridge_import_failure_graceful(self):
        """When planner_bridge is not available, routing continues normally."""
        # The default behavior — planner_bridge ImportError is caught
        decision = route_message(
            message="hello",
            page_context="playbook",
            thread_id="t-1",
            tenant_context={},
            state={},
        )
        # Should fall through to keyword routing (greeting)
        assert decision.target == "chat"


# ---------------------------------------------------------------
# RouteDecision dataclass
# ---------------------------------------------------------------


class TestRouteDecision:
    def test_default_plan_id_is_none(self):
        d = RouteDecision(target="chat", reason="test")
        assert d.plan_id is None

    def test_plan_id_set(self):
        d = RouteDecision(target="planner", reason="test", plan_id="p-1")
        assert d.plan_id == "p-1"
