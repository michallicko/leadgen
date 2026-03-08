"""Orchestrates the full research pipeline: website fetch, market research, cross-check.

Pipeline steps:
1. Fetch company website (primary source of truth)
2. Research market/competitors via web search
3. Cross-check external findings against website data
4. Return aggregated findings with halt gates for conflicts

Each step emits SSE events via a callback so the frontend can show
real-time research progress.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Callable

from .cross_checker import cross_check_findings, needs_halt_gate
from .market_research import MarketResearchResult, research_market
from .web_fetch import WebsiteData, fetch_website

logger = logging.getLogger(__name__)


@dataclass
class ResearchFindings:
    """Aggregated output of the full research pipeline."""

    website: dict = field(default_factory=dict)
    market: dict = field(default_factory=dict)
    cross_checks: list[dict] = field(default_factory=list)
    halt_gates_needed: list[dict] = field(default_factory=list)
    confirmed_facts: dict = field(default_factory=dict)
    all_sources: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def run_research_pipeline(
    domain: str,
    goal: str = "",
    plan_config: dict | None = None,
    emit_finding: Callable[[str, str], None] | None = None,
) -> ResearchFindings:
    """Run the full research pipeline.

    Args:
        domain: Company domain to research (e.g., "acme.com").
        goal: Business goal context for market research.
        plan_config: Optional config dict with research_requirements.
        emit_finding: Optional callback(title, message) to emit SSE events.

    Returns:
        ResearchFindings with all data, cross-checks, and halt gates.
    """
    if plan_config is None:
        plan_config = {}
    if emit_finding is None:
        emit_finding = _noop_emit

    findings = ResearchFindings()

    # Step 1: Fetch website
    emit_finding("Fetching website", "Loading {}...".format(domain))
    website = fetch_website(domain)

    if website.error:
        findings.errors.append("Website fetch: {}".format(website.error))
        emit_finding("Website error", website.error)
    else:
        extracted = website.extracted
        services_preview = (
            ", ".join(extracted.products_services[:3])
            if extracted.products_services
            else "no services found"
        )
        emit_finding(
            "Read {}".format(domain),
            "Found: {} -- {}".format(extracted.company_name, services_preview),
        )

    findings.website = _website_to_dict(website)

    # Step 2: Market research
    emit_finding("Researching market", "Searching for competitors and market data...")
    company_name = website.extracted.company_name or domain
    industry = website.extracted.industries[0] if website.extracted.industries else ""
    location = website.extracted.location or ""

    market = research_market(
        company_name=company_name,
        industry=industry,
        location=location,
        goal=goal,
    )

    if market.error:
        findings.errors.append("Market research: {}".format(market.error))
        emit_finding("Market research note", market.error)
    elif market.competitors:
        names = [c.get("name", "?") for c in market.competitors[:3]]
        emit_finding("Found competitors", ", ".join(names))

    findings.market = _market_to_dict(market)

    # Step 3: Cross-check
    emit_finding("Cross-checking", "Verifying external data against website...")
    policy = plan_config.get("research_requirements", {}).get(
        "cross_check_policy", "website_authoritative_with_consensus_override"
    )
    checks = cross_check_findings(
        website_data=asdict(website.extracted),
        external_findings={
            "competitors": market.competitors,
            "market_data": market.market_data,
        },
        policy=policy,
    )

    halt_gates = needs_halt_gate(checks)
    if halt_gates:
        emit_finding(
            "Conflict detected",
            "{} finding(s) need your confirmation".format(len(halt_gates)),
        )

    # Aggregate confirmed facts
    confirmed: dict[str, str] = {}
    for check in checks:
        if check.verdict in ("confirmed", "website_trusted"):
            confirmed[check.field] = check.website_value

    findings.cross_checks = [asdict(c) for c in checks]
    findings.halt_gates_needed = [asdict(c) for c in halt_gates]
    findings.confirmed_facts = confirmed

    # Collect all sources
    all_sources: list[str] = list(website.pages_fetched)
    all_sources.extend(market.sources)
    for c in checks:
        all_sources.extend(c.external_sources)
    findings.all_sources = list(
        dict.fromkeys(all_sources)
    )  # deduplicate, preserve order

    return findings


def _noop_emit(title: str, message: str) -> None:
    """No-op emit callback."""
    pass


def _website_to_dict(website: WebsiteData) -> dict:
    """Convert WebsiteData to a serializable dict."""
    return {
        "url": website.url,
        "title": website.title,
        "description": website.description,
        "pages_fetched": website.pages_fetched,
        "raw_content": website.raw_content,
        "extracted": asdict(website.extracted),
        "error": website.error,
    }


def _market_to_dict(market: MarketResearchResult) -> dict:
    """Convert MarketResearchResult to a serializable dict."""
    return {
        "competitors": market.competitors,
        "market_data": market.market_data,
        "industry_trends": market.industry_trends,
        "sources": market.sources,
        "error": market.error,
    }
