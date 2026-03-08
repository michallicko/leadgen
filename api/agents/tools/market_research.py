"""Market and competitor research using web search.

Uses the Perplexity sonar API (via the existing PerplexityClient) to find
competitors, market data, and industry trends for a given company.

If the Perplexity API key is not configured, returns a stub result with
an explanatory message.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MarketResearchResult:
    """Aggregated market research findings."""

    competitors: list[dict] = field(default_factory=list)
    market_data: list[dict] = field(default_factory=list)
    industry_trends: list[dict] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    error: str | None = None


def _create_perplexity_client(api_key: str):
    """Create a PerplexityClient instance. Separated for testability."""
    from ...services.perplexity_client import PerplexityClient

    return PerplexityClient(
        api_key=api_key,
        default_model="sonar",
        timeout=15,
        max_retries=1,
    )


def research_market(
    company_name: str,
    industry: str = "",
    location: str = "",
    goal: str = "",
) -> MarketResearchResult:
    """Research the market segment and competitors via Perplexity search.

    Performs up to 3 searches:
    1. Direct competitors in the same market/location
    2. Market size and segment data
    3. Industry trends relevant to the company's goal

    Args:
        company_name: Name of the company to research around.
        industry: Industry vertical (e.g., "B2B SaaS").
        location: Geographic focus (e.g., "Europe").
        goal: Business goal context for more relevant results.

    Returns:
        MarketResearchResult with competitors, market data, and trends.
    """
    api_key = os.environ.get("PERPLEXITY_API_KEY", "")
    if not api_key:
        logger.warning("PERPLEXITY_API_KEY not set, returning stub market research")
        return MarketResearchResult(
            error="Market research unavailable: Perplexity API key not configured."
        )

    client = _create_perplexity_client(api_key)

    result = MarketResearchResult()

    # Search 1: Competitors
    try:
        competitor_query = "Who are the main competitors of {} in {}?".format(
            company_name,
            " ".join(filter(None, [industry, location])) or "their market",
        )
        resp = client.query(
            system_prompt=(
                "You are a market research analyst. Return a JSON array of competitor objects "
                "with keys: name, description, url (if known). Max 5 competitors. "
                "Return ONLY valid JSON array, no markdown."
            ),
            user_prompt=competitor_query,
            max_tokens=600,
            temperature=0.1,
        )
        competitors = _parse_json_array(resp.content)
        result.competitors = competitors[:5]
        if hasattr(resp, "citations") and resp.citations:
            result.sources.extend(resp.citations)
    except Exception as exc:
        logger.warning("Competitor search failed for %s: %s", company_name, exc)

    # Search 2: Market data
    try:
        market_query = "What is the market size and growth for {} {}?".format(
            industry or "the industry of " + company_name,
            "in " + location if location else "",
        )
        resp = client.query(
            system_prompt=(
                "You are a market analyst. Return key market facts as a JSON array of objects "
                "with keys: fact, confidence (high/medium/low). Max 5 facts. "
                "Return ONLY valid JSON array, no markdown."
            ),
            user_prompt=market_query,
            max_tokens=600,
            temperature=0.1,
        )
        market_data = _parse_json_array(resp.content)
        result.market_data = market_data[:5]
        if hasattr(resp, "citations") and resp.citations:
            result.sources.extend(resp.citations)
    except Exception as exc:
        logger.warning("Market data search failed for %s: %s", company_name, exc)

    # Search 3: Industry trends (only if goal is provided)
    if goal:
        try:
            trend_query = "Latest trends in {} relevant to: {}".format(
                industry or "the industry of " + company_name, goal
            )
            resp = client.query(
                system_prompt=(
                    "You are a trend analyst. Return trending insights as a JSON array of objects "
                    "with keys: trend, relevance (high/medium/low). Max 5 trends. "
                    "Return ONLY valid JSON array, no markdown."
                ),
                user_prompt=trend_query,
                max_tokens=600,
                temperature=0.1,
            )
            trends = _parse_json_array(resp.content)
            result.industry_trends = trends[:5]
            if hasattr(resp, "citations") and resp.citations:
                result.sources.extend(resp.citations)
        except Exception as exc:
            logger.warning("Trend search failed for %s: %s", company_name, exc)

    # Deduplicate sources
    result.sources = list(dict.fromkeys(result.sources))
    return result


def _parse_json_array(text: str) -> list[dict]:
    """Parse a JSON array from LLM output, handling markdown fences."""
    text = text.strip()
    # Strip markdown fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        return []
    except (json.JSONDecodeError, ValueError):
        logger.debug("Failed to parse JSON array from: %.200s", text)
        return []
