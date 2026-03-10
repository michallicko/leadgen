"""Unit tests for the Opus Specialist module (api/agents/specialist.py)."""

import json
from unittest.mock import MagicMock, patch

from api.agents.specialist import (
    SpecialistContext,
    SpecialistResult,
    _build_specialist_system_prompt,
    _build_specialist_user_message,
    invoke_specialist,
    invoke_specialist_scoring,
    parse_specialist_response,
)


def _make_context(**overrides):
    """Create a SpecialistContext with sensible defaults."""
    defaults = {
        "task": "Write the ICP section",
        "rubric": {
            "specificity": "Score 5 if ICP includes firmographics and psychographics"
        },
        "research": {"perplexity": "Company X sells widgets to SMBs in DACH region."},
        "user_context": ["We target companies with 50-200 employees"],
        "existing_sections": {"Executive Summary": "We help SMBs grow faster."},
        "constraints": "Facts only. Every claim must trace to research.",
        "persona": "You are a senior GTM strategist.",
    }
    defaults.update(overrides)
    return SpecialistContext(**defaults)


# ---------------------------------------------------------------------------
# System prompt assembly
# ---------------------------------------------------------------------------


class TestBuildSpecialistSystemPrompt:
    def test_includes_persona(self):
        ctx = _make_context(persona="You are a B2B marketing expert.")
        prompt = _build_specialist_system_prompt(ctx)
        assert "You are a B2B marketing expert." in prompt

    def test_includes_task(self):
        ctx = _make_context(task="Write the Competitive Positioning section")
        prompt = _build_specialist_system_prompt(ctx)
        assert "Write the Competitive Positioning section" in prompt

    def test_includes_rubric(self):
        ctx = _make_context(
            rubric={"depth": "Score 5 if analysis covers 3+ competitors"}
        )
        prompt = _build_specialist_system_prompt(ctx)
        assert "3+ competitors" in prompt

    def test_includes_constraints(self):
        ctx = _make_context(constraints="No speculation. Cite sources.")
        prompt = _build_specialist_system_prompt(ctx)
        assert "No speculation. Cite sources." in prompt

    def test_includes_output_format_instructions(self):
        ctx = _make_context()
        prompt = _build_specialist_system_prompt(ctx)
        assert "### Content" in prompt
        assert "### Self-Score" in prompt
        assert "### Improvement Suggestions" in prompt
        assert "### Sources Used" in prompt


# ---------------------------------------------------------------------------
# User message assembly
# ---------------------------------------------------------------------------


class TestBuildSpecialistUserMessage:
    def test_includes_research(self):
        ctx = _make_context(research={"web_search": "Company X has 500 employees"})
        msg = _build_specialist_user_message(ctx)
        assert "Company X has 500 employees" in msg
        assert "Source: web_search" in msg

    def test_includes_research_dict_values(self):
        ctx = _make_context(research={"api": {"employees": 500, "revenue": "10M"}})
        msg = _build_specialist_user_message(ctx)
        assert '"employees": 500' in msg

    def test_includes_user_context(self):
        ctx = _make_context(user_context=["Focus on enterprise segment", "Ignore SMBs"])
        msg = _build_specialist_user_message(ctx)
        assert "- Focus on enterprise segment" in msg
        assert "- Ignore SMBs" in msg

    def test_includes_existing_sections(self):
        ctx = _make_context(existing_sections={"ICP": "Mid-market SaaS companies."})
        msg = _build_specialist_user_message(ctx)
        assert "### ICP" in msg
        assert "Mid-market SaaS companies." in msg
        assert "do NOT repeat" in msg

    def test_truncates_long_existing_sections(self):
        long_content = "A" * 600
        ctx = _make_context(existing_sections={"Summary": long_content})
        msg = _build_specialist_user_message(ctx)
        assert "..." in msg
        # Should be truncated to 500 + "..."
        assert "A" * 500 in msg
        assert "A" * 501 not in msg

    def test_empty_research(self):
        ctx = _make_context(research={})
        msg = _build_specialist_user_message(ctx)
        assert "Research Findings" not in msg

    def test_empty_user_context(self):
        ctx = _make_context(user_context=[])
        msg = _build_specialist_user_message(ctx)
        assert "User Context" not in msg

    def test_empty_existing_sections(self):
        ctx = _make_context(existing_sections={})
        msg = _build_specialist_user_message(ctx)
        assert "Already Written" not in msg


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

WELL_FORMATTED_RESPONSE = """### Content
The ideal customer profile targets mid-market SaaS companies with 50-200 employees
in the DACH region. These companies typically have annual revenue of EUR 5-50M.

### Self-Score
Score: 4
Reasoning: The ICP is specific with firmographics but could include more psychographic detail.

### Improvement Suggestions
- Add buyer pain points and motivations
- Include technology stack preferences
- Specify decision-making process

### Sources Used
- perplexity research on Company X
- user input on employee count
"""


class TestParseSpecialistResponse:
    def test_extracts_content(self):
        result = parse_specialist_response(WELL_FORMATTED_RESPONSE)
        assert "ideal customer profile" in result.content
        assert "DACH region" in result.content

    def test_extracts_score(self):
        result = parse_specialist_response(WELL_FORMATTED_RESPONSE)
        assert result.score == 4.0

    def test_extracts_score_reasoning(self):
        result = parse_specialist_response(WELL_FORMATTED_RESPONSE)
        assert "firmographics" in result.score_reasoning

    def test_extracts_suggestions(self):
        result = parse_specialist_response(WELL_FORMATTED_RESPONSE)
        assert len(result.improvement_suggestions) == 3
        assert "buyer pain points" in result.improvement_suggestions[0]

    def test_extracts_sources(self):
        result = parse_specialist_response(WELL_FORMATTED_RESPONSE)
        assert len(result.sources_used) == 2
        assert "perplexity" in result.sources_used[0]

    def test_handles_decimal_score(self):
        response = "### Content\nSome text\n\n### Self-Score\nScore: 3.5\nReasoning: OK"
        result = parse_specialist_response(response)
        assert result.score == 3.5

    def test_handles_missing_content_header(self):
        """If no ### Content header, treat everything before Self-Score as content."""
        response = (
            "Here is my analysis of the market.\n\n"
            "### Self-Score\nScore: 3\nReasoning: Good enough"
        )
        result = parse_specialist_response(response)
        assert "analysis of the market" in result.content
        assert result.score == 3.0

    def test_handles_completely_unformatted(self):
        """If Opus ignores format entirely, return entire text as content."""
        response = "Just a raw block of text with no headers at all."
        result = parse_specialist_response(response)
        assert result.content == response
        assert result.score == 0.0
        assert result.improvement_suggestions == []
        assert result.sources_used == []

    def test_handles_empty_response(self):
        result = parse_specialist_response("")
        assert result.content == ""
        assert result.score == 0.0

    def test_handles_asterisk_bullets(self):
        response = (
            "### Content\nText\n\n"
            "### Improvement Suggestions\n* Item one\n* Item two\n\n"
            "### Sources Used\n* Source A"
        )
        result = parse_specialist_response(response)
        assert len(result.improvement_suggestions) == 2
        assert len(result.sources_used) == 1


# ---------------------------------------------------------------------------
# Dataclass basics
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_specialist_context_fields(self):
        ctx = _make_context()
        assert ctx.task == "Write the ICP section"
        assert isinstance(ctx.rubric, dict)
        assert isinstance(ctx.research, dict)
        assert isinstance(ctx.user_context, list)

    def test_specialist_result_defaults(self):
        result = SpecialistResult(
            content="hello",
            score=4.0,
            score_reasoning="good",
            improvement_suggestions=[],
            sources_used=[],
        )
        assert result.tokens_used == {}
        assert result.cost_usd == 0.0


# ---------------------------------------------------------------------------
# invoke_specialist (mocked API)
# ---------------------------------------------------------------------------


class TestInvokeSpecialist:
    def test_non_streaming_returns_valid_result(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = WELL_FORMATTED_RESPONSE
        mock_response.input_tokens = 1000
        mock_response.output_tokens = 500
        mock_response.cost_usd = 0.06
        mock_client.query.return_value = mock_response

        ctx = _make_context()
        result = invoke_specialist(ctx, client=mock_client)

        assert isinstance(result, SpecialistResult)
        assert "ideal customer profile" in result.content
        assert result.score == 4.0
        assert result.tokens_used == {"input": 1000, "output": 500}
        assert result.cost_usd == 0.06
        mock_client.query.assert_called_once()

    def test_streaming_calls_callback(self):
        mock_client = MagicMock()
        chunks = [
            "### Content\n",
            "Hello world\n",
            "### Self-Score\n",
            "Score: 5\n",
            "Reasoning: Great",
        ]
        mock_client.stream_query.return_value = iter(chunks)
        mock_client.last_stream_usage = {"input_tokens": 800, "output_tokens": 200}

        callback_chunks = []
        ctx = _make_context()
        result = invoke_specialist(
            ctx, stream_callback=lambda c: callback_chunks.append(c), client=mock_client
        )

        assert callback_chunks == chunks
        assert isinstance(result, SpecialistResult)
        assert result.tokens_used["input"] == 800
        assert result.tokens_used["output"] == 200
        mock_client.stream_query.assert_called_once()

    def test_creates_client_when_not_provided(self):
        with patch("api.agents.specialist.AnthropicClient") as MockClient:
            mock_instance = MagicMock()
            mock_response = MagicMock()
            mock_response.content = (
                "### Content\nTest\n### Self-Score\nScore: 3\nReasoning: OK"
            )
            mock_response.input_tokens = 100
            mock_response.output_tokens = 50
            mock_response.cost_usd = 0.01
            mock_instance.query.return_value = mock_response
            MockClient.return_value = mock_instance

            ctx = _make_context()
            result = invoke_specialist(ctx)

            MockClient.assert_called_once_with(default_model="claude-opus-4-6")
            assert result.content == "Test"


# ---------------------------------------------------------------------------
# invoke_specialist_scoring (mocked API)
# ---------------------------------------------------------------------------


class TestInvokeSpecialistScoring:
    def test_returns_parsed_json(self):
        mock_client = MagicMock()
        scoring_output = {
            "sections": {
                "ICP": {"score": 4, "reasoning": "Good specificity"},
                "Value Prop": {"score": 3, "reasoning": "Too generic"},
            },
            "overall_score": 3.5,
            "overall_assessment": "Solid foundation but needs refinement.",
            "top_improvements": ["Add more data points to ICP"],
        }
        mock_response = MagicMock()
        mock_response.content = json.dumps(scoring_output)
        mock_response.input_tokens = 2000
        mock_response.output_tokens = 300
        mock_response.cost_usd = 0.05
        mock_client.query.return_value = mock_response

        result = invoke_specialist_scoring(
            sections={"ICP": "Mid-market SaaS", "Value Prop": "We help you grow"},
            rubric={"specificity": "Score 5 if detailed"},
            goal="Expand into DACH",
            client=mock_client,
        )

        assert result["overall_score"] == 3.5
        assert "ICP" in result["sections"]
        assert result["sections"]["ICP"]["score"] == 4

    def test_handles_non_json_response(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "I cannot produce valid JSON right now."
        mock_response.input_tokens = 500
        mock_response.output_tokens = 50
        mock_response.cost_usd = 0.01
        mock_client.query.return_value = mock_response

        result = invoke_specialist_scoring(
            sections={"ICP": "Some text"},
            rubric={},
            client=mock_client,
        )

        assert result["overall_score"] == 0
        assert "cannot produce" in result["overall_assessment"]

    def test_includes_goal_in_prompt(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"sections": {}, "overall_score": 4, "overall_assessment": "OK", "top_improvements": []}'
        mock_response.input_tokens = 100
        mock_response.output_tokens = 50
        mock_response.cost_usd = 0.01
        mock_client.query.return_value = mock_response

        invoke_specialist_scoring(
            sections={"ICP": "Text"},
            rubric={},
            goal="Enter US market",
            client=mock_client,
        )

        # Check the user_prompt passed to query includes the goal
        call_kwargs = mock_client.query.call_args
        assert "Enter US market" in call_kwargs.kwargs.get(
            "user_prompt", call_kwargs.args[1] if len(call_kwargs.args) > 1 else ""
        )
