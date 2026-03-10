"""Tests for the agent testing framework (BL-270)."""

import json
import tempfile
from pathlib import Path

import pytest

from api.agents.testing.fixtures import (
    ConversationTurn,
    ExpectedResponse,
    ExpectedToolCall,
    GoldenConversation,
    load_fixtures,
)
from api.agents.testing.framework import (
    compute_quality_scores,
    evaluate_turn,
    run_conversation,
    run_test_suite,
)


# ---------------------------------------------------------------------------
# Fixtures (pytest)
# ---------------------------------------------------------------------------


@pytest.fixture
def simple_golden():
    """A simple golden conversation for testing."""
    return GoldenConversation(
        name="test-conversation",
        description="A test fixture",
        model="claude-haiku-4-5-20251001",
        system_prompt="You are a test agent.",
        turns=[
            ConversationTurn(
                user_message="Hello",
                expected_tool_calls=[],
                expected_response=ExpectedResponse(
                    contains=["hello"],
                    not_contains=["error"],
                    min_length=5,
                ),
                assertion_level="semantic",
            ),
        ],
    )


@pytest.fixture
def tool_call_golden():
    """Golden conversation with expected tool calls."""
    return GoldenConversation(
        name="tool-test",
        description="Tests tool call matching",
        model="claude-haiku-4-5-20251001",
        system_prompt="You are a test agent with tools.",
        turns=[
            ConversationTurn(
                user_message="Research Acme",
                expected_tool_calls=[
                    ExpectedToolCall(
                        name="research_own_company",
                        args_contains={"query": "Acme"},
                    ),
                ],
                expected_response=ExpectedResponse(contains=["research"]),
                assertion_level="semantic",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# ExpectedToolCall tests
# ---------------------------------------------------------------------------


class TestExpectedToolCall:
    def test_matches_strict_exact(self):
        tc = ExpectedToolCall(name="web_search", args_contains={"query": "test"})
        assert tc.matches("web_search", {"query": "test"}, "strict")

    def test_matches_strict_no_match_name(self):
        tc = ExpectedToolCall(name="web_search")
        assert not tc.matches("other_tool", {}, "strict")

    def test_matches_strict_no_match_args(self):
        tc = ExpectedToolCall(name="web_search", args_contains={"query": "test"})
        assert not tc.matches("web_search", {"query": "other"}, "strict")

    def test_matches_semantic_case_insensitive(self):
        tc = ExpectedToolCall(name="web_search", args_contains={"query": "acme"})
        assert tc.matches("web_search", {"query": "Search for ACME Corp"}, "semantic")

    def test_matches_structural_name_only(self):
        tc = ExpectedToolCall(name="web_search", args_contains={"query": "specific"})
        # Structural only checks name, ignores args
        assert tc.matches("web_search", {"query": "totally different"}, "structural")

    def test_matches_with_args_exact(self):
        tc = ExpectedToolCall(
            name="update",
            args_exact={"section": "icp", "content": "test"},
        )
        assert tc.matches("update", {"section": "icp", "content": "test"}, "strict")
        assert not tc.matches(
            "update", {"section": "icp", "content": "other"}, "strict"
        )


# ---------------------------------------------------------------------------
# ExpectedResponse tests
# ---------------------------------------------------------------------------


class TestExpectedResponse:
    def test_matches_contains_strict(self):
        resp = ExpectedResponse(contains=["hello", "world"])
        passed, failures = resp.matches("hello world test", "strict")
        assert passed
        assert failures == []

    def test_matches_contains_strict_fail(self):
        resp = ExpectedResponse(contains=["hello", "missing"])
        passed, failures = resp.matches("hello world", "strict")
        assert not passed
        assert len(failures) == 1

    def test_matches_contains_semantic_case_insensitive(self):
        resp = ExpectedResponse(contains=["Hello"])
        passed, failures = resp.matches("HELLO WORLD", "semantic")
        assert passed

    def test_matches_not_contains(self):
        resp = ExpectedResponse(not_contains=["error", "fail"])
        passed, failures = resp.matches("something with an error", "semantic")
        assert not passed

    def test_matches_markdown_format(self):
        resp = ExpectedResponse(format="markdown")
        passed, _ = resp.matches("# Header\n- bullet", "semantic")
        assert passed

        passed, failures = resp.matches("plain text only", "semantic")
        assert not passed

    def test_matches_length_constraints(self):
        resp = ExpectedResponse(min_length=10, max_length=50)
        passed, _ = resp.matches("short", "strict")
        assert not passed

        passed, _ = resp.matches("this is a normal response", "strict")
        assert passed

        passed, _ = resp.matches("x" * 100, "strict")
        assert not passed


# ---------------------------------------------------------------------------
# GoldenConversation parsing tests
# ---------------------------------------------------------------------------


class TestGoldenConversation:
    def test_from_dict(self):
        data = {
            "name": "test",
            "description": "A test",
            "model": "claude-haiku-4-5-20251001",
            "system_prompt": "You are a bot.",
            "tags": ["smoke"],
            "turns": [
                {
                    "user_message": "Hi",
                    "expected_tool_calls": [
                        {"name": "greet", "args_contains": {"name": "user"}}
                    ],
                    "expected_response": {
                        "contains": ["hello"],
                        "format": "markdown",
                    },
                    "assertion_level": "semantic",
                }
            ],
        }
        conv = GoldenConversation.from_dict(data)
        assert conv.name == "test"
        assert len(conv.turns) == 1
        assert conv.turns[0].expected_tool_calls[0].name == "greet"
        assert conv.turns[0].assertion_level == "semantic"
        assert conv.tags == ["smoke"]

    def test_from_file(self):
        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "agent_conversations"
        research_file = fixtures_dir / "research_flow.json"
        if research_file.exists():
            conv = GoldenConversation.from_file(research_file)
            assert conv.name == "research-flow"
            assert len(conv.turns) == 2

    def test_from_dict_defaults(self):
        data = {"name": "minimal", "turns": [{"user_message": "test"}]}
        conv = GoldenConversation.from_dict(data)
        assert conv.model == "claude-haiku-4-5-20251001"
        assert conv.turns[0].assertion_level == "structural"


# ---------------------------------------------------------------------------
# Fixture loading tests
# ---------------------------------------------------------------------------


class TestLoadFixtures:
    def test_load_from_project_dir(self):
        fixtures = load_fixtures()
        # Should find the research_flow.json and error_handling.json
        assert len(fixtures) >= 2
        names = [f.name for f in fixtures]
        assert "research-flow" in names

    def test_load_with_tag_filter(self):
        fixtures = load_fixtures(tags=["smoke"])
        assert all(any(t in f.tags for t in ["smoke"]) for f in fixtures)

    def test_load_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fixtures = load_fixtures(directory=tmpdir)
            assert fixtures == []

    def test_load_nonexistent_dir(self):
        fixtures = load_fixtures(directory="/nonexistent/path")
        assert fixtures == []


# ---------------------------------------------------------------------------
# Quality scoring tests
# ---------------------------------------------------------------------------


class TestQualityScoring:
    def test_relevance_all_keywords_found(self):
        scores = compute_quality_scores(
            "This is about acme corp strategy", ["acme", "strategy"]
        )
        assert scores["relevance"] == 1.0

    def test_relevance_partial_keywords(self):
        scores = compute_quality_scores("This is about acme corp", ["acme", "strategy"])
        assert scores["relevance"] == 0.5

    def test_relevance_no_keywords(self):
        scores = compute_quality_scores("some text", None)
        assert scores["relevance"] == 1.0

    def test_completeness_empty(self):
        scores = compute_quality_scores("")
        assert scores["completeness"] == 0.0

    def test_completeness_short(self):
        scores = compute_quality_scores("hi there")
        assert scores["completeness"] == 0.3

    def test_completeness_medium(self):
        scores = compute_quality_scores("a " * 10)
        assert scores["completeness"] == 0.6

    def test_completeness_full(self):
        scores = compute_quality_scores("word " * 25)
        assert scores["completeness"] == 1.0

    def test_conciseness_short(self):
        scores = compute_quality_scores("word " * 50)
        assert scores["conciseness"] == 1.0

    def test_conciseness_long(self):
        scores = compute_quality_scores("word " * 500)
        assert scores["conciseness"] == 0.4


# ---------------------------------------------------------------------------
# Turn evaluation tests
# ---------------------------------------------------------------------------


class TestEvaluateTurn:
    def test_passing_turn(self):
        turn = ConversationTurn(
            user_message="Hello",
            expected_tool_calls=[],
            expected_response=ExpectedResponse(contains=["hello"]),
            assertion_level="semantic",
        )
        result = evaluate_turn(
            turn=turn,
            turn_index=0,
            actual_response_text="Hello there! How can I help?",
            actual_tool_calls=[],
        )
        assert result.passed

    def test_failing_turn_missing_keyword(self):
        turn = ConversationTurn(
            user_message="Research",
            expected_tool_calls=[],
            expected_response=ExpectedResponse(contains=["research", "analysis"]),
            assertion_level="strict",
        )
        result = evaluate_turn(
            turn=turn,
            turn_index=0,
            actual_response_text="Here is the research data",
            actual_tool_calls=[],
        )
        assert not result.passed
        assert len(result.response_failures) > 0

    def test_tool_call_matching_strict(self):
        turn = ConversationTurn(
            user_message="Search",
            expected_tool_calls=[
                ExpectedToolCall(name="web_search", args_contains={"query": "test"}),
            ],
            assertion_level="strict",
        )
        result = evaluate_turn(
            turn=turn,
            turn_index=0,
            actual_response_text="Searching...",
            actual_tool_calls=[
                {"name": "web_search", "args": {"query": "test"}},
            ],
        )
        assert result.tool_call_results[0].matched

    def test_tool_call_matching_semantic(self):
        turn = ConversationTurn(
            user_message="Search",
            expected_tool_calls=[
                ExpectedToolCall(name="web_search", args_contains={"query": "test"}),
            ],
            assertion_level="semantic",
        )
        result = evaluate_turn(
            turn=turn,
            turn_index=0,
            actual_response_text="Searching...",
            actual_tool_calls=[
                {"name": "web_search", "args": {"query": "test query"}},
            ],
        )
        assert result.tool_call_results[0].matched

    def test_tool_call_not_matching(self):
        turn = ConversationTurn(
            user_message="Search",
            expected_tool_calls=[
                ExpectedToolCall(name="web_search"),
            ],
            assertion_level="strict",
        )
        result = evaluate_turn(
            turn=turn,
            turn_index=0,
            actual_response_text="Searching...",
            actual_tool_calls=[
                {"name": "other_tool", "args": {}},
            ],
        )
        assert not result.tool_call_results[0].matched


# ---------------------------------------------------------------------------
# Conversation runner tests
# ---------------------------------------------------------------------------


class TestRunConversation:
    def test_run_passing_conversation(self, simple_golden):
        def mock_agent(system_prompt, user_message, model):
            return ("Hello! I can help you with that.", [])

        result = run_conversation(simple_golden, mock_agent)
        assert result.passed
        assert result.pass_rate == 1.0

    def test_run_failing_conversation(self, simple_golden):
        def mock_agent(system_prompt, user_message, model):
            return ("Error occurred", [])

        result = run_conversation(simple_golden, mock_agent)
        assert not result.passed

    def test_run_with_agent_exception(self, simple_golden):
        def mock_agent(system_prompt, user_message, model):
            raise RuntimeError("Agent crashed")

        result = run_conversation(simple_golden, mock_agent)
        assert not result.passed
        assert result.error is not None

    def test_run_with_tool_calls(self, tool_call_golden):
        def mock_agent(system_prompt, user_message, model):
            return (
                "I researched Acme Corp.",
                [{"name": "research_own_company", "args": {"query": "Acme Corp"}}],
            )

        result = run_conversation(tool_call_golden, mock_agent)
        assert result.passed


# ---------------------------------------------------------------------------
# Test suite runner
# ---------------------------------------------------------------------------


class TestRunTestSuite:
    def test_full_suite(self, simple_golden, tool_call_golden):
        def mock_agent(system_prompt, user_message, model):
            if "Hello" in user_message:
                return ("Hello! How can I help?", [])
            return (
                "I researched the company.",
                [{"name": "research_own_company", "args": {"query": "Acme Corp"}}],
            )

        report = run_test_suite([simple_golden, tool_call_golden], mock_agent)
        assert report.total_conversations == 2
        assert report.passed_conversations == 2
        assert report.total_turns == 2
        assert report.passed_turns == 2

    def test_regression_detection(self, simple_golden):
        def mock_agent(system_prompt, user_message, model):
            return ("Error occurred", [])

        previous = {"test-conversation": {"passed": True}}
        report = run_test_suite([simple_golden], mock_agent, previous)
        assert len(report.regressions) == 1
        assert "REGRESSION" in report.regressions[0]

    def test_report_serialization(self, simple_golden):
        def mock_agent(system_prompt, user_message, model):
            return ("Hello there!", [])

        report = run_test_suite([simple_golden], mock_agent)
        data = report.to_dict()
        assert "summary" in data
        assert "conversations" in data
        assert data["summary"]["total_conversations"] == 1

        json_str = report.to_json()
        parsed = json.loads(json_str)
        assert parsed["summary"]["total_conversations"] == 1
