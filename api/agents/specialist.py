"""Opus Specialist — called as a tool by the deterministic planner.

Receives structured context, returns high-quality output with self-scoring.
Stateless per invocation — all context provided by the caller.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from ..services.anthropic_client import AnthropicClient

logger = logging.getLogger(__name__)

SPECIALIST_MODEL = "claude-opus-4-6"
SPECIALIST_MAX_TOKENS = 8192
SPECIALIST_TEMPERATURE = 0.3


@dataclass
class SpecialistContext:
    """Structured context assembled by the planner (code, not LLM)."""

    task: str  # What to produce (e.g., "Write Market Analysis section")
    rubric: dict  # Scoring criteria from plan config
    research: dict  # Raw research findings
    user_context: list[str]  # Filtered relevant user messages/corrections
    existing_sections: dict[str, str]  # Already-written sections (prevent repetition)
    constraints: str  # e.g., "Facts only. Every claim must trace to research."
    persona: str  # From plan config


@dataclass
class SpecialistResult:
    """Output from the specialist."""

    content: str  # The generated content (markdown)
    score: float  # Self-evaluated quality score (1-5)
    score_reasoning: str  # Why this score
    improvement_suggestions: list[str]  # What could be better
    sources_used: list[str]  # Which research sources were referenced
    tokens_used: dict = field(default_factory=dict)  # {input: N, output: N}
    cost_usd: float = 0.0


def invoke_specialist(
    context: SpecialistContext,
    stream_callback: Optional[callable] = None,
    client: Optional[AnthropicClient] = None,
) -> SpecialistResult:
    """Call Opus to perform high-quality synthesis/writing/scoring.

    Args:
        context: Structured context with everything Opus needs.
        stream_callback: Optional callback for streaming chunks (for typewriter effect).
        client: Optional AnthropicClient instance (created if not provided).

    Returns:
        SpecialistResult with content, score, and metadata.
    """
    if client is None:
        client = AnthropicClient(default_model=SPECIALIST_MODEL)

    system = _build_specialist_system_prompt(context)
    user_message = _build_specialist_user_message(context)

    messages = [{"role": "user", "content": user_message}]

    if stream_callback:
        # Stream for typewriter effect
        accumulated = ""
        for chunk in client.stream_query(
            messages=messages,
            system_prompt=system,
            max_tokens=SPECIALIST_MAX_TOKENS,
            model=SPECIALIST_MODEL,
            temperature=SPECIALIST_TEMPERATURE,
        ):
            stream_callback(chunk)
            accumulated += chunk

        usage = client.last_stream_usage
        tokens_used = {
            "input": usage.get("input_tokens", 0),
            "output": usage.get("output_tokens", 0),
        }
        cost = AnthropicClient._estimate_cost(
            SPECIALIST_MODEL,
            tokens_used["input"],
            tokens_used["output"],
        )
        result = parse_specialist_response(accumulated)
        result.tokens_used = tokens_used
        result.cost_usd = cost
        return result
    else:
        # Non-streaming query
        response = client.query(
            system_prompt=system,
            user_prompt=user_message,
            model=SPECIALIST_MODEL,
            max_tokens=SPECIALIST_MAX_TOKENS,
            temperature=SPECIALIST_TEMPERATURE,
        )
        tokens_used = {
            "input": response.input_tokens,
            "output": response.output_tokens,
        }
        result = parse_specialist_response(response.content)
        result.tokens_used = tokens_used
        result.cost_usd = response.cost_usd
        return result


def invoke_specialist_scoring(
    sections: dict[str, str],
    rubric: dict,
    goal: str = "",
    client: Optional[AnthropicClient] = None,
) -> dict:
    """Call Opus to score an entire strategy.

    Args:
        sections: All written sections {name: content}.
        rubric: Scoring rubric from plan config.
        goal: The user's stated goal (for relevance scoring).
        client: Optional AnthropicClient instance.

    Returns:
        Dict with per-section scores and overall assessment.
    """
    if client is None:
        client = AnthropicClient(default_model=SPECIALIST_MODEL)

    system = (
        "You are a senior GTM strategy evaluator. "
        "Score each section against the rubric. Be rigorous and specific.\n\n"
        "## Scoring Rubric\n"
        "{}\n\n"
        "## Output Format\n"
        "Respond with valid JSON only — no markdown fences, no extra text.\n"
        "Schema:\n"
        '{{"sections": {{"<name>": {{"score": <1-5>, "reasoning": "<why>"}}}}, '
        '"overall_score": <1-5>, "overall_assessment": "<summary>", '
        '"top_improvements": ["<suggestion>"]}}'
    ).format(json.dumps(rubric, indent=2))

    parts = []
    if goal:
        parts.append("## User Goal\n{}".format(goal))
    parts.append("## Sections to Evaluate")
    for name, content in sections.items():
        parts.append("### {}\n{}".format(name, content))
    user_message = "\n\n".join(parts)

    response = client.query(
        system_prompt=system,
        user_prompt=user_message,
        model=SPECIALIST_MODEL,
        max_tokens=SPECIALIST_MAX_TOKENS,
        temperature=0.2,
    )

    try:
        return json.loads(response.content)
    except (json.JSONDecodeError, ValueError):
        logger.warning(
            "Specialist scoring returned non-JSON: %s", response.content[:200]
        )
        return {
            "sections": {},
            "overall_score": 0,
            "overall_assessment": response.content,
            "top_improvements": [],
            "tokens_used": {
                "input": response.input_tokens,
                "output": response.output_tokens,
            },
            "cost_usd": response.cost_usd,
        }


def _build_specialist_system_prompt(context: SpecialistContext) -> str:
    """Build the system prompt for Opus."""
    return (
        "{persona}\n\n"
        "You are performing a specific task as part of a GTM strategy build.\n\n"
        "## Your Task\n"
        "{task}\n\n"
        "## Scoring Rubric\n"
        "You MUST self-evaluate your output against these criteria:\n"
        "{rubric}\n\n"
        "## Constraints\n"
        "{constraints}\n\n"
        "## Output Format\n"
        "Structure your response as:\n\n"
        "### Content\n"
        "[Your main output — the section content, analysis, or evaluation]\n\n"
        "### Self-Score\n"
        "Score: [1-5]\n"
        "Reasoning: [Why this score against the rubric]\n\n"
        "### Improvement Suggestions\n"
        "- [What could make this better]\n\n"
        "### Sources Used\n"
        "- [List which research sources you referenced]"
    ).format(
        persona=context.persona,
        task=context.task,
        rubric=json.dumps(context.rubric, indent=2),
        constraints=context.constraints,
    )


def _build_specialist_user_message(context: SpecialistContext) -> str:
    """Build the user message with full context for Opus."""
    parts = []

    # Research data (raw, full — this is critical)
    if context.research:
        parts.append("## Research Findings")
        for source, data in context.research.items():
            parts.append("### Source: {}".format(source))
            if isinstance(data, str):
                parts.append(data)
            else:
                parts.append(json.dumps(data, indent=2))

    # User corrections and answers
    if context.user_context:
        parts.append("## User Context (corrections and answers)")
        for item in context.user_context:
            parts.append("- {}".format(item))

    # Existing sections (to prevent repetition)
    if context.existing_sections:
        parts.append("## Already Written Sections (do NOT repeat this content)")
        for name, content in context.existing_sections.items():
            parts.append("### {}".format(name))
            if len(content) > 500:
                parts.append(content[:500] + "...")
            else:
                parts.append(content)

    return "\n\n".join(parts)


def parse_specialist_response(response_text: str) -> SpecialistResult:
    """Parse the structured response from Opus.

    Extracts content, self-score, improvement suggestions, and sources
    from a markdown-formatted response. Robust to minor formatting
    variations.
    """
    content = ""
    score = 0.0
    score_reasoning = ""
    suggestions = []
    sources = []

    # Split on ### headers
    sections = re.split(r"(?m)^###\s+", response_text)

    for section in sections:
        if not section.strip():
            continue

        # Get section title (first line) and body (rest)
        lines = section.split("\n", 1)
        title = lines[0].strip().lower()
        body = lines[1].strip() if len(lines) > 1 else ""

        if title == "content":
            content = body

        elif title == "self-score":
            # Extract score number
            score_match = re.search(r"Score:\s*([0-9]+(?:\.[0-9]+)?)", body)
            if score_match:
                try:
                    score = float(score_match.group(1))
                except ValueError:
                    pass
            # Extract reasoning
            reasoning_match = re.search(r"Reasoning:\s*(.+)", body, re.DOTALL)
            if reasoning_match:
                score_reasoning = reasoning_match.group(1).strip()

        elif title == "improvement suggestions":
            # Extract bullet points
            for line in body.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    suggestions.append(line[2:].strip())
                elif line.startswith("* "):
                    suggestions.append(line[2:].strip())

        elif title == "sources used":
            for line in body.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    sources.append(line[2:].strip())
                elif line.startswith("* "):
                    sources.append(line[2:].strip())

    # Fallback: if no ### Content header found, treat everything before
    # the first recognized header as content
    if not content and response_text.strip():
        # Take everything up to the first ### Self-Score or similar
        first_header = re.search(
            r"(?m)^###\s+(Self-Score|Improvement Suggestions|Sources Used)",
            response_text,
            re.IGNORECASE,
        )
        if first_header:
            content = response_text[: first_header.start()].strip()
        else:
            content = response_text.strip()

    return SpecialistResult(
        content=content,
        score=score,
        score_reasoning=score_reasoning,
        improvement_suggestions=suggestions,
        sources_used=sources,
    )
