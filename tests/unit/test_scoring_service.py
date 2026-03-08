"""Tests for the two-layer quality scoring service (BL-1016)."""

import asyncio
import json
from unittest.mock import MagicMock, patch

from api.services.scoring_service import (
    DEFAULT_EXPECTED_SECTIONS,
    SectionScore,
    StrategyScore,
    calculate_completeness,
    score_strategy_quality,
    strategy_score_to_dict,
)


# ---------------------------------------------------------------------------
# Layer 1: calculate_completeness
# ---------------------------------------------------------------------------


class TestCalculateCompleteness:
    """Tests for the automatic completeness tracking (Layer 1)."""

    def test_full_strategy_returns_ratio_1(self):
        """All sections filled => ratio 1.0."""
        content = """# GTM Strategy

## Executive Summary

This is a comprehensive executive summary that describes our go-to-market approach in detail with specifics.

## Ideal Customer Profile (ICP)

Our target customers are mid-market SaaS companies with 50-500 employees in North America and Europe.

## Value Proposition

We deliver unique value through our AI-powered platform that reduces manual work by 80% for sales teams.

## Competitive Landscape

Key competitors include Competitor A, Competitor B. Our differentiation is deeper AI integration.

## Channel Strategy

Primary channels are LinkedIn outbound, content marketing, and partner referrals for enterprise deals.

## Messaging Framework

Core messaging pillars: efficiency, intelligence, scalability. Position as the AI sales copilot.

## Sales Process

Product-led growth with sales-assist. Free trial to paid conversion, with enterprise sales motion for larger deals.

## Metrics & KPIs

Track MQL to SQL conversion (target 25%), CAC payback under 12 months, NRR above 120%.

## Action Plan

Month 1: Launch outbound. Month 2: Content engine. Month 3: Partner program. Review metrics weekly.
"""
        result = calculate_completeness(content)
        assert result["ratio"] == 1.0
        assert result["filled"] == 9
        assert result["total"] == 9
        assert all(v is True for v in result["sections"].values())

    def test_partial_strategy_returns_correct_ratio(self):
        """Only some sections filled => correct partial ratio."""
        content = """# GTM Strategy

## Executive Summary

This is a comprehensive executive summary that describes our go-to-market approach in detail with specifics.

## Ideal Customer Profile (ICP)

Our target customers are mid-market SaaS companies with 50-500 employees in North America and Europe.

## Value Proposition

Short.

## Competitive Landscape

## Channel Strategy

Primary channels are LinkedIn outbound, content marketing, and partner referrals for enterprise deals.

## Messaging Framework

## Sales Process

## Metrics & KPIs

## Action Plan
"""
        result = calculate_completeness(content)
        # Executive Summary, ICP, Channel Strategy are filled (>50 chars)
        # Value Proposition is too short (<50 chars)
        # Others are empty
        assert result["filled"] == 3
        assert result["total"] == 9
        assert abs(result["ratio"] - 3 / 9) < 0.01

    def test_empty_content_returns_ratio_0(self):
        """Empty content => ratio 0.0."""
        result = calculate_completeness("")
        assert result["ratio"] == 0.0
        assert result["filled"] == 0
        assert result["total"] == 9
        assert all(v is False for v in result["sections"].values())

    def test_none_content_returns_ratio_0(self):
        """None/whitespace content => ratio 0.0."""
        result = calculate_completeness("   ")
        assert result["ratio"] == 0.0
        assert result["filled"] == 0

    def test_fuzzy_section_matching(self):
        """Section headings with slight variations still match."""
        content = """# Strategy

## ICP

Our target customers are mid-market SaaS companies with 50-500 employees in North America and Europe.

## Executive Summary

This is a comprehensive executive summary that describes our go-to-market approach in detail with specifics.
"""
        result = calculate_completeness(content)
        # "ICP" should fuzzy-match "Ideal Customer Profile (ICP)"
        assert result["sections"]["Ideal Customer Profile (ICP)"] is True
        assert result["sections"]["Executive Summary"] is True
        assert result["filled"] == 2

    def test_custom_expected_sections(self):
        """Custom section list works correctly."""
        content = """# Strategy

## Company Profile

Detailed company profile with lots of information about who we are and what we do here at Acme Corp.

## Market Analysis

Comprehensive market analysis showing TAM, SAM, SOM breakdowns and competitive positioning.
"""
        result = calculate_completeness(
            content,
            expected_sections=["Company Profile", "Market Analysis", "ICP Definition"],
        )
        assert result["total"] == 3
        assert result["filled"] == 2
        assert result["sections"]["Company Profile"] is True
        assert result["sections"]["Market Analysis"] is True
        assert result["sections"]["ICP Definition"] is False

    def test_section_below_threshold_not_counted(self):
        """Sections with content <50 chars are not considered filled."""
        content = """# Strategy

## Executive Summary

Too short.

## Value Proposition

Also too short.
"""
        result = calculate_completeness(content)
        assert result["sections"]["Executive Summary"] is False
        assert result["sections"]["Value Proposition"] is False
        assert result["filled"] == 0

    def test_default_sections_match_template(self):
        """Default expected sections list covers the strategy template."""
        assert len(DEFAULT_EXPECTED_SECTIONS) == 9
        assert "Executive Summary" in DEFAULT_EXPECTED_SECTIONS
        assert "Action Plan" in DEFAULT_EXPECTED_SECTIONS


# ---------------------------------------------------------------------------
# Layer 2: score_strategy_quality (mocked LLM)
# ---------------------------------------------------------------------------


class TestScoreStrategyQuality:
    """Tests for AI quality scoring (Layer 2) with mocked Anthropic."""

    def test_returns_valid_score_with_mocked_opus(self):
        """Mocked Opus returns valid StrategyScore."""
        mock_response = MagicMock()
        mock_response.content = json.dumps(
            {
                "sections": [
                    {
                        "section_name": "Executive Summary",
                        "score": 4,
                        "reasoning": "Well-structured and specific.",
                        "suggestions": ["Add market size data."],
                    },
                    {
                        "section_name": "Ideal Customer Profile (ICP)",
                        "score": 3,
                        "reasoning": "Good start but needs more firmographic detail.",
                        "suggestions": ["Add revenue range.", "Specify tech stack."],
                    },
                ],
                "overall_assessment": "Solid foundation with room for improvement in ICP specifics.",
            }
        )

        content = """# Strategy

## Executive Summary

This is a comprehensive executive summary that describes our go-to-market approach in detail with specifics.

## Ideal Customer Profile (ICP)

Our target customers are mid-market SaaS companies with 50-500 employees in North America.
"""

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch(
                "api.services.anthropic_client.AnthropicClient"
            ) as mock_client_cls:
                mock_client = MagicMock()
                mock_client.query.return_value = mock_response
                mock_client_cls.return_value = mock_client

                score = asyncio.get_event_loop().run_until_complete(
                    score_strategy_quality(content, goal="Enter European market")
                )

        assert isinstance(score, StrategyScore)
        assert score.sections_total == 9
        assert score.overall_quality is not None
        assert score.overall_quality == 3.5  # (4 + 3) / 2
        assert (
            score.overall_assessment
            == "Solid foundation with room for improvement in ICP specifics."
        )
        assert len(score.section_scores) == 9

        # Check scored sections
        exec_summary = next(
            s for s in score.section_scores if s.section_name == "Executive Summary"
        )
        assert exec_summary.quality_score == 4
        assert exec_summary.quality_reasoning == "Well-structured and specific."
        assert len(exec_summary.improvement_suggestions) == 1

    def test_no_api_key_returns_completeness_only(self):
        """Without API key, returns completeness data without quality scores."""
        content = """# Strategy

## Executive Summary

This is a comprehensive executive summary that describes our go-to-market approach in detail with specifics.
"""

        with patch.dict("os.environ", {}, clear=True):
            # Ensure ANTHROPIC_API_KEY is not set
            import os

            os.environ.pop("ANTHROPIC_API_KEY", None)

            score = asyncio.get_event_loop().run_until_complete(
                score_strategy_quality(content)
            )

        assert isinstance(score, StrategyScore)
        assert score.overall_quality is None
        assert "unavailable" in score.overall_assessment.lower()
        assert score.sections_filled == 1

    def test_llm_failure_returns_graceful_fallback(self):
        """LLM failure returns completeness with error message."""
        content = """# Strategy

## Executive Summary

This is a comprehensive executive summary that describes our go-to-market approach in detail with specifics.
"""

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch(
                "api.services.anthropic_client.AnthropicClient"
            ) as mock_client_cls:
                mock_client = MagicMock()
                mock_client.query.side_effect = RuntimeError("API timeout")
                mock_client_cls.return_value = mock_client

                score = asyncio.get_event_loop().run_until_complete(
                    score_strategy_quality(content)
                )

        assert isinstance(score, StrategyScore)
        assert score.overall_quality is None
        assert "failed" in score.overall_assessment.lower()


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestStrategyScoreToDict:
    """Tests for serialization."""

    def test_serializes_to_dict(self):
        score = StrategyScore(
            completeness_ratio=0.5,
            sections_filled=2,
            sections_total=4,
            section_scores=[
                SectionScore(
                    section_name="Test",
                    completeness=1.0,
                    quality_score=4.0,
                    quality_reasoning="Good",
                    improvement_suggestions=["Add more"],
                    scored_at="2026-03-08T00:00:00Z",
                ),
            ],
            overall_quality=4.0,
            overall_assessment="Good overall.",
        )
        result = strategy_score_to_dict(score)
        assert isinstance(result, dict)
        assert result["completeness_ratio"] == 0.5
        assert result["sections_filled"] == 2
        assert len(result["section_scores"]) == 1
        assert result["section_scores"][0]["quality_score"] == 4.0
        assert result["overall_quality"] == 4.0
