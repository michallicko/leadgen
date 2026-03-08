"""Two-layer quality scoring for GTM strategies.

Layer 1: Automatic completeness tracking (cheap, runs on every save).
Layer 2: AI quality scoring via Anthropic Opus (expensive, on-demand).
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ---- Expected sections for a GTM strategy (match strategy-template.ts) ----

DEFAULT_EXPECTED_SECTIONS = [
    "Executive Summary",
    "Ideal Customer Profile (ICP)",
    "Value Proposition",
    "Competitive Landscape",
    "Channel Strategy",
    "Messaging Framework",
    "Sales Process",
    "Metrics & KPIs",
    "Action Plan",
]

# Minimum characters of body content to consider a section "filled"
_MIN_SECTION_LENGTH = 50


# ---- Data classes ----


@dataclass
class SectionScore:
    section_name: str
    completeness: float  # 0-1 (0=empty, 1=filled)
    quality_score: float | None = None  # 1-5 (None if not yet scored)
    quality_reasoning: str = ""
    improvement_suggestions: list[str] = field(default_factory=list)
    scored_at: str | None = None  # ISO timestamp


@dataclass
class StrategyScore:
    completeness_ratio: float  # N/M sections filled
    sections_filled: int
    sections_total: int
    section_scores: list[SectionScore] = field(default_factory=list)
    overall_quality: float | None = None  # Weighted average of quality scores
    overall_assessment: str = ""


# ---- Layer 1: Completeness ----


def _parse_sections(content: str) -> dict[str, str]:
    """Parse markdown into {heading: body} for H2 sections."""
    parts = re.split(r"^##\s+(.+)$", content, flags=re.MULTILINE)
    # parts alternates: [preamble, heading1, content1, heading2, content2, ...]
    sections: dict[str, str] = {}
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        sections[heading] = body
    return sections


def _fuzzy_match(expected: str, found: str) -> bool:
    """Check if expected section name fuzzy-matches a found heading."""
    e = expected.lower()
    f = found.lower()
    return e in f or f in e


def calculate_completeness(
    content: str,
    expected_sections: list[str] | None = None,
) -> dict:
    """
    Layer 1: Automatic completeness tracking.

    Parse the strategy markdown, identify sections (H2 headings),
    check which have substantive content (>50 chars below the heading).

    Returns: {
        "ratio": 0.6,
        "filled": 3,
        "total": 5,
        "sections": {"Executive Summary": true, "ICP": false, ...}
    }
    """
    if not expected_sections:
        expected_sections = list(DEFAULT_EXPECTED_SECTIONS)

    if not content or not content.strip():
        return {
            "ratio": 0.0,
            "filled": 0,
            "total": len(expected_sections),
            "sections": {s: False for s in expected_sections},
        }

    found_sections = _parse_sections(content)

    filled = 0
    section_status: dict[str, bool] = {}

    for expected in expected_sections:
        matched = False
        for found_heading, found_body in found_sections.items():
            if (
                _fuzzy_match(expected, found_heading)
                and len(found_body) > _MIN_SECTION_LENGTH
            ):
                matched = True
                break
        section_status[expected] = matched
        if matched:
            filled += 1

    total = len(expected_sections)
    return {
        "ratio": filled / total if total > 0 else 0.0,
        "filled": filled,
        "total": total,
        "sections": section_status,
    }


# ---- Layer 2: AI Quality Scoring ----

_SCORING_SYSTEM_PROMPT = """\
You are a GTM strategy quality evaluator. Score each section of the strategy \
document on a 1-5 scale for quality, specificity, and actionability.

Scoring rubric:
1 - Empty or placeholder text only
2 - Vague, generic content with no specifics
3 - Reasonable but lacks depth or company-specific detail
4 - Good quality with specific, actionable content
5 - Excellent — specific, data-informed, actionable, well-structured

For each section, provide:
- score (integer 1-5)
- reasoning (1-2 sentences)
- suggestions (list of 1-3 concrete improvements)

Also provide an overall_assessment (2-3 sentences) summarizing the strategy's \
strengths and key gaps.

Respond ONLY with valid JSON matching this schema:
{
  "sections": [
    {
      "section_name": "Section Name",
      "score": 4,
      "reasoning": "...",
      "suggestions": ["..."]
    }
  ],
  "overall_assessment": "..."
}
"""


def _build_scoring_user_prompt(content: str, goal: str = "") -> str:
    """Build the user prompt for the scoring LLM call."""
    parts = ["Score the following GTM strategy document:\n"]
    if goal:
        parts.append(f"Business objective: {goal}\n")
    parts.append(f"---\n{content}\n---")
    return "\n".join(parts)


async def score_strategy_quality(
    content: str,
    goal: str = "",
) -> StrategyScore:
    """
    Layer 2: AI quality scoring using Anthropic.

    Calls the Anthropic API with the strategy content.
    Returns per-section quality scores and overall assessment.
    """
    from ..services.anthropic_client import AnthropicClient

    completeness = calculate_completeness(content)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set, returning completeness only")
        return StrategyScore(
            completeness_ratio=completeness["ratio"],
            sections_filled=completeness["filled"],
            sections_total=completeness["total"],
            section_scores=[
                SectionScore(
                    section_name=name,
                    completeness=1.0 if is_filled else 0.0,
                )
                for name, is_filled in completeness["sections"].items()
            ],
            overall_assessment="AI scoring unavailable (no API key configured).",
        )

    client = AnthropicClient(
        api_key=api_key, default_model="claude-sonnet-4-5-20241022"
    )
    user_prompt = _build_scoring_user_prompt(content, goal)

    try:
        response = client.query(
            system_prompt=_SCORING_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model="claude-sonnet-4-5-20241022",
            max_tokens=2000,
        )

        # Parse JSON from response
        raw = response.content.strip()
        # Handle markdown code fences
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        result = json.loads(raw)
    except Exception:
        logger.exception("AI scoring failed")
        return StrategyScore(
            completeness_ratio=completeness["ratio"],
            sections_filled=completeness["filled"],
            sections_total=completeness["total"],
            section_scores=[
                SectionScore(
                    section_name=name,
                    completeness=1.0 if is_filled else 0.0,
                )
                for name, is_filled in completeness["sections"].items()
            ],
            overall_assessment="AI scoring failed. Showing completeness only.",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    scored_sections = result.get("sections", [])

    # Merge AI scores with completeness data
    section_scores: list[SectionScore] = []
    ai_score_map = {s["section_name"]: s for s in scored_sections}

    for name, is_filled in completeness["sections"].items():
        ai = ai_score_map.get(name)
        # Try fuzzy match if exact match fails
        if not ai:
            for ai_name, ai_data in ai_score_map.items():
                if _fuzzy_match(name, ai_name):
                    ai = ai_data
                    break

        section_scores.append(
            SectionScore(
                section_name=name,
                completeness=1.0 if is_filled else 0.0,
                quality_score=ai["score"] if ai else None,
                quality_reasoning=ai.get("reasoning", "") if ai else "",
                improvement_suggestions=ai.get("suggestions", []) if ai else [],
                scored_at=now_iso if ai else None,
            )
        )

    # Calculate overall quality as average of scored sections
    scored_values = [
        s.quality_score for s in section_scores if s.quality_score is not None
    ]
    overall_quality = sum(scored_values) / len(scored_values) if scored_values else None

    return StrategyScore(
        completeness_ratio=completeness["ratio"],
        sections_filled=completeness["filled"],
        sections_total=completeness["total"],
        section_scores=section_scores,
        overall_quality=overall_quality,
        overall_assessment=result.get("overall_assessment", ""),
    )


def strategy_score_to_dict(score: StrategyScore) -> dict:
    """Convert a StrategyScore to a JSON-serializable dict."""
    return asdict(score)
