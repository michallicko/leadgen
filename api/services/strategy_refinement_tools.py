"""Closed-loop strategy refinement from enrichment data (BL-168).

Provides a chat tool that analyzes enrichment results (L1, L2, person) and
suggests strategy updates based on real data from enriched companies. The AI
can call this tool to feed verified facts back into the strategy document,
replacing guesses with enrichment-backed insights.

Registered with the AGENT tool registry at app startup.
"""

from __future__ import annotations

import json
import logging
from collections import Counter

from sqlalchemy import text

from ..models import (
    Company,
    CompanyEnrichmentL1,
    CompanyEnrichmentL2,
    CompanyEnrichmentOpportunity,
    CompanyEnrichmentProfile,
    CompanyEnrichmentSignals,
    StrategyDocument,
    db,
)
from .tool_registry import ToolContext, ToolDefinition

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_jsonb(val):
    """Parse a JSONB value that might be a string (SQLite compat)."""
    if val is None:
        return {}
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _safe_text(val, max_len=200):
    """Return trimmed text or None."""
    if not val or not isinstance(val, str):
        return None
    text = val.strip()
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text if text else None


def _collect_enrichment_insights(tenant_id: str, limit: int = 50) -> dict:
    """Aggregate enrichment data across all enriched companies in the tenant.

    Returns a structured summary of patterns found in enrichment data:
    - industries: Counter of industries
    - competitors: list of mentioned competitors
    - ai_opportunities: list of AI opportunity themes
    - pain_points: list of pain hypotheses
    - tech_stacks: list of tech stack mentions
    - hiring_signals: list of hiring signal themes
    - company_count: total enriched companies
    """
    # Get enriched companies (those with L1 data)
    companies = (
        db.session.query(Company)
        .join(CompanyEnrichmentL1, Company.id == CompanyEnrichmentL1.company_id)
        .filter(Company.tenant_id == tenant_id)
        .limit(limit)
        .all()
    )

    if not companies:
        return {"company_count": 0}

    company_ids = [c.id for c in companies]

    # Aggregate industries
    industries = Counter()
    for c in companies:
        if c.industry:
            industries[c.industry] += 1

    # Aggregate L2 data (deep research)
    l2_data = (
        CompanyEnrichmentL2.query.filter(
            CompanyEnrichmentL2.company_id.in_(company_ids)
        ).all()
    )

    competitors_list = []
    ai_opportunities_list = []
    pain_points_list = []
    tech_stacks_list = []
    hiring_list = []

    for l2 in l2_data:
        if l2.competitors:
            competitors_list.append(_safe_text(l2.competitors, 300))
        if l2.ai_opportunities:
            ai_opportunities_list.append(_safe_text(l2.ai_opportunities, 300))
        if l2.pain_hypothesis:
            pain_points_list.append(_safe_text(l2.pain_hypothesis, 300))
        if l2.tech_stack:
            tech_stacks_list.append(_safe_text(l2.tech_stack, 300))
        if l2.hiring_signals:
            hiring_list.append(_safe_text(l2.hiring_signals, 300))

    # Aggregate profile data
    profiles = (
        CompanyEnrichmentProfile.query.filter(
            CompanyEnrichmentProfile.company_id.in_(company_ids)
        ).all()
    )
    customer_segments_list = []
    for p in profiles:
        if p.competitors and not any(
            c for c in competitors_list if c and p.competitors.strip()[:50] in (c or "")
        ):
            competitors_list.append(_safe_text(p.competitors, 300))
        if p.customer_segments:
            customer_segments_list.append(_safe_text(p.customer_segments, 300))

    # Aggregate opportunity data
    opportunities = (
        CompanyEnrichmentOpportunity.query.filter(
            CompanyEnrichmentOpportunity.company_id.in_(company_ids)
        ).all()
    )
    industry_pain_list = []
    quick_wins_list = []
    for opp in opportunities:
        if opp.industry_pain_points:
            industry_pain_list.append(_safe_text(opp.industry_pain_points, 300))
        if opp.ai_opportunities and not any(
            a
            for a in ai_opportunities_list
            if a and opp.ai_opportunities.strip()[:50] in (a or "")
        ):
            ai_opportunities_list.append(_safe_text(opp.ai_opportunities, 300))
        qw = _parse_jsonb(opp.quick_wins)
        if qw:
            quick_wins_list.append(qw)

    # Aggregate signals
    signals = (
        CompanyEnrichmentSignals.query.filter(
            CompanyEnrichmentSignals.company_id.in_(company_ids)
        ).all()
    )
    digital_initiatives_list = []
    for sig in signals:
        if sig.digital_initiatives:
            digital_initiatives_list.append(_safe_text(sig.digital_initiatives, 300))
        if sig.hiring_signals and not any(
            h
            for h in hiring_list
            if h and sig.hiring_signals.strip()[:50] in (h or "")
        ):
            hiring_list.append(_safe_text(sig.hiring_signals, 300))

    # Aggregate person enrichment data
    person_count = (
        db.session.execute(
            text(
                "SELECT COUNT(*) FROM contact_enrichment ce "
                "JOIN contacts ct ON ce.contact_id = ct.id "
                "WHERE ct.tenant_id = :tid"
            ),
            {"tid": tenant_id},
        ).scalar()
        or 0
    )

    # Filter out None values
    competitors_list = [c for c in competitors_list if c]
    ai_opportunities_list = [a for a in ai_opportunities_list if a]
    pain_points_list = [p for p in pain_points_list if p]
    tech_stacks_list = [t for t in tech_stacks_list if t]
    hiring_list = [h for h in hiring_list if h]
    customer_segments_list = [s for s in customer_segments_list if s]
    industry_pain_list = [p for p in industry_pain_list if p]
    digital_initiatives_list = [d for d in digital_initiatives_list if d]

    return {
        "company_count": len(companies),
        "l2_count": len(l2_data),
        "person_count": person_count,
        "industries": dict(industries.most_common(10)),
        "competitors": competitors_list[:10],
        "ai_opportunities": ai_opportunities_list[:10],
        "pain_points": pain_points_list[:10],
        "tech_stacks": tech_stacks_list[:10],
        "hiring_signals": hiring_list[:10],
        "customer_segments": customer_segments_list[:10],
        "industry_pain_points": industry_pain_list[:10],
        "digital_initiatives": digital_initiatives_list[:10],
        "quick_wins": quick_wins_list[:10],
    }


def _compare_with_strategy(insights: dict, extracted_data: dict) -> list[dict]:
    """Compare enrichment insights with current strategy to find refinement opportunities.

    Returns a list of suggested refinements with section, finding, and suggestion.
    """
    refinements = []

    # Check ICP alignment
    icp = extracted_data.get("icp", {})
    if isinstance(icp, str):
        try:
            icp = json.loads(icp)
        except (json.JSONDecodeError, ValueError):
            icp = {}

    strategy_industries = icp.get("industries", [])
    enrichment_industries = list(insights.get("industries", {}).keys())

    if enrichment_industries and strategy_industries:
        new_industries = [
            ind
            for ind in enrichment_industries[:5]
            if ind not in strategy_industries
        ]
        if new_industries:
            refinements.append(
                {
                    "section": "Ideal Customer Profile (ICP)",
                    "finding": "Enrichment found companies in industries not in your ICP: {}".format(
                        ", ".join(new_industries[:3])
                    ),
                    "suggestion": "Consider adding these industries to your ICP or marking them as disqualifiers.",
                    "data_source": "L1 enrichment industry distribution",
                }
            )

    # Check for competitive intelligence
    competitors = insights.get("competitors", [])
    strategy_competitors = extracted_data.get("competitors", [])
    if competitors and not strategy_competitors:
        refinements.append(
            {
                "section": "Competitive Positioning",
                "finding": "Enrichment revealed competitor mentions across {} companies.".format(
                    len(competitors)
                ),
                "suggestion": "Update Competitive Positioning section with verified competitor data from enrichment.",
                "data_source": "L2 deep research competitor analysis",
            }
        )

    # Check for AI opportunity patterns
    ai_opps = insights.get("ai_opportunities", [])
    if ai_opps and len(ai_opps) >= 3:
        refinements.append(
            {
                "section": "Value Proposition & Messaging",
                "finding": "Found {} AI opportunity themes across enriched companies.".format(
                    len(ai_opps)
                ),
                "suggestion": "Refine messaging angles to align with validated AI opportunity patterns.",
                "data_source": "L2 AI opportunity analysis",
            }
        )

    # Check for pain point patterns
    pain_points = insights.get("pain_points", [])
    if pain_points and len(pain_points) >= 2:
        refinements.append(
            {
                "section": "Buyer Personas",
                "finding": "Identified {} pain hypotheses from enrichment data.".format(
                    len(pain_points)
                ),
                "suggestion": "Update persona pain points with validated hypotheses from enrichment.",
                "data_source": "L2 pain hypothesis research",
            }
        )

    # Check hiring signals for channel strategy
    hiring = insights.get("hiring_signals", [])
    if hiring and len(hiring) >= 3:
        refinements.append(
            {
                "section": "Channel Strategy",
                "finding": "Hiring signal data from {} companies suggests active growth.".format(
                    len(hiring)
                ),
                "suggestion": "Companies actively hiring are more receptive to outreach. Consider timing your campaigns around hiring activity.",
                "data_source": "Enrichment hiring signals",
            }
        )

    # Check digital initiatives for messaging
    digital = insights.get("digital_initiatives", [])
    if digital and len(digital) >= 2:
        refinements.append(
            {
                "section": "Messaging Framework",
                "finding": "Found {} digital initiative themes across enriched companies.".format(
                    len(digital)
                ),
                "suggestion": "Reference specific digital transformation initiatives in your outreach for higher relevance.",
                "data_source": "Enrichment digital initiative signals",
            }
        )

    return refinements


# ---------------------------------------------------------------------------
# Tool handler
# ---------------------------------------------------------------------------


def analyze_enrichment_insights(args: dict, ctx: ToolContext) -> dict:
    """Analyze enrichment data and suggest strategy refinements.

    Reads L1, L2, and person enrichment results for the tenant's companies,
    identifies patterns, and compares them with the current strategy to
    suggest specific section updates.
    """
    # Get strategy document
    doc = StrategyDocument.query.filter_by(tenant_id=ctx.tenant_id).first()
    if not doc:
        return {"error": "No strategy document found"}

    extracted = _parse_jsonb(doc.extracted_data)

    # Collect enrichment insights
    insights = _collect_enrichment_insights(ctx.tenant_id)

    if insights.get("company_count", 0) == 0:
        return {
            "status": "no_data",
            "message": "No enriched companies found. Run enrichment first to get insights for strategy refinement.",
            "company_count": 0,
        }

    # Compare with strategy and generate refinement suggestions
    refinements = _compare_with_strategy(insights, extracted)

    return {
        "status": "ok",
        "insights_summary": {
            "companies_analyzed": insights["company_count"],
            "l2_enriched": insights.get("l2_count", 0),
            "persons_enriched": insights.get("person_count", 0),
            "top_industries": insights.get("industries", {}),
        },
        "enrichment_highlights": {
            "competitors_found": len(insights.get("competitors", [])),
            "ai_opportunities_found": len(insights.get("ai_opportunities", [])),
            "pain_points_found": len(insights.get("pain_points", [])),
            "hiring_signals_found": len(insights.get("hiring_signals", [])),
        },
        "suggested_refinements": refinements,
        "raw_insights": {
            "competitors": insights.get("competitors", [])[:5],
            "ai_opportunities": insights.get("ai_opportunities", [])[:5],
            "pain_points": insights.get("pain_points", [])[:5],
            "tech_stacks": insights.get("tech_stacks", [])[:5],
            "customer_segments": insights.get("customer_segments", [])[:5],
        },
    }


# ---------------------------------------------------------------------------
# Tool definitions for registry
# ---------------------------------------------------------------------------

STRATEGY_REFINEMENT_TOOLS = [
    ToolDefinition(
        name="analyze_enrichment_insights",
        description=(
            "Analyze enrichment data (L1 profiles, L2 deep research, person intel) "
            "across all enriched companies and generate strategy refinement "
            "suggestions. Returns: (1) insights summary with industry distribution, "
            "competitor mentions, AI opportunity patterns, pain points, and hiring "
            "signals, (2) a list of suggested refinements mapped to specific "
            "strategy sections (ICP, Competitive Positioning, Value Proposition, "
            "etc.), (3) raw enrichment highlights for the AI to reference when "
            "updating strategy content. Use this after enrichment completes to "
            "feed verified facts back into the strategy, replacing assumptions "
            "with real data. The tool does NOT modify the strategy -- it provides "
            "the analysis for the AI to then use update_strategy_section or "
            "append_to_section to apply approved changes."
        ),
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        handler=analyze_enrichment_insights,
    ),
]
