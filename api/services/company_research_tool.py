"""Company research tool for AI chat.

Exposes the existing CompanyResearchService as a callable tool so the AI
can perform deep company research during strategy creation on demand.

The tool:
- Looks up the tenant's own company (is_self=True) automatically
- Skips re-research if enrichment data already exists (unless force=True)
- Returns structured research results the AI can use for strategy grounding
- Rate limit: 1 call per turn (research is expensive)
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from ..models import db
from .tool_registry import ToolContext, ToolDefinition

logger = logging.getLogger(__name__)

# Status values that indicate enrichment already exists — skip re-research
ENRICHED_STATUSES = {"enriched_l2", "triage_passed", "enrichment_failed"}


def research_own_company(args: dict, ctx: ToolContext) -> dict:
    """Research the tenant's own company using the deep research pipeline.

    Looks up the tenant's is_self=True company record, checks if enrichment
    data already exists, and runs the 3-step research pipeline if needed
    (website scrape → Perplexity sonar-pro → Claude synthesis).

    Args:
        args: {
            "force": bool (optional) — re-run even if data already exists
        }
        ctx: ToolContext with tenant_id for company lookup.

    Returns:
        dict with research results, or {"error": "..."} on failure.
    """
    force = bool(args.get("force", False))

    # Look up the tenant's own company
    row = db.session.execute(
        text(
            "SELECT id, domain, name, status FROM companies "
            "WHERE tenant_id = :t AND is_self = true LIMIT 1"
        ),
        {"t": str(ctx.tenant_id)},
    ).fetchone()

    if not row:
        return {
            "error": (
                "No company profile found. Please complete the onboarding setup "
                "to register your company before running research."
            )
        }

    company_id, domain, company_name, company_status = (
        row[0],
        row[1],
        row[2],
        row[3],
    )

    if not domain:
        return {
            "error": (
                "Your company profile is missing a domain. "
                "Please update your company settings with your website domain "
                "before running research."
            )
        }

    # Check if enrichment data already exists
    if not force and company_status in ENRICHED_STATUSES:
        # Load and return existing enrichment data
        existing = _load_existing_enrichment(company_id)
        if existing:
            logger.info(
                "Returning cached enrichment for company %s (status=%s). "
                "Pass force=true to re-research.",
                company_id,
                company_status,
            )
            existing["cached"] = True
            existing["summary"] = (
                "Returning cached research data for {} ({}). "
                "Research was previously completed. "
                "Pass force=true to re-run research.".format(
                    company_name or domain, domain
                )
            )
            return existing

    # Run the research pipeline
    logger.info(
        "Running company research for tenant=%s company=%s domain=%s force=%s",
        ctx.tenant_id,
        company_id,
        domain,
        force,
    )

    try:
        from .research_service import ResearchService

        service = ResearchService()
        result = service.research_company(
            company_id=company_id,
            tenant_id=ctx.tenant_id,
            domain=domain,
            on_progress=None,  # Tool result is sufficient; agent executor handles events
        )
    except Exception as exc:
        logger.exception(
            "CompanyResearchService failed for domain=%s: %s", domain, exc
        )
        return {
            "error": "Research pipeline failed: {}".format(str(exc)),
            "domain": domain,
        }

    if not result.get("success"):
        return {
            "error": result.get("error", "Research failed for unknown reason."),
            "domain": domain,
            "steps_completed": result.get("steps_completed", []),
        }

    # Load the saved enrichment data from DB to return to the AI
    enrichment = _load_existing_enrichment(company_id)
    if enrichment:
        enrichment["cached"] = False
        enrichment["steps_completed"] = result.get("steps_completed", [])
        enrichment["cost_usd"] = result.get("enrichment_cost_usd", 0)
        enrichment["summary"] = (
            "Research complete for {} ({}). "
            "Completed {} steps, cost ${:.4f} USD.".format(
                result.get("company_name", company_name or domain),
                domain,
                len(result.get("steps_completed", [])),
                result.get("enrichment_cost_usd", 0),
            )
        )
        return enrichment

    # Fallback: return the raw result if enrichment load fails
    return {
        "success": True,
        "company_name": result.get("company_name", company_name or domain),
        "domain": domain,
        "steps_completed": result.get("steps_completed", []),
        "cost_usd": result.get("enrichment_cost_usd", 0),
        "summary": (
            "Research complete for {} — {} steps completed.".format(
                result.get("company_name", domain),
                len(result.get("steps_completed", [])),
            )
        ),
    }


def _load_existing_enrichment(company_id) -> dict | None:
    """Load existing enrichment data for a company from all enrichment tables.

    Mirrors the _load_enrichment_data function in playbook_routes but returns
    a flattened dict suitable for tool output.
    """
    from ..models import (
        Company,
        CompanyEnrichmentL1,
        CompanyEnrichmentL2,
        CompanyEnrichmentMarket,
        CompanyEnrichmentProfile,
        CompanyEnrichmentSignals,
    )

    result: dict = {}

    company = db.session.get(Company, company_id)
    if company:
        result["company"] = {
            "name": company.name,
            "domain": company.domain,
            "industry": company.industry,
            "industry_category": company.industry_category,
            "summary": company.summary,
            "company_size": company.company_size,
            "revenue_range": company.revenue_range,
            "hq_country": company.hq_country,
            "hq_city": company.hq_city,
        }

    l1 = db.session.get(CompanyEnrichmentL1, company_id)
    if l1:
        result["triage_notes"] = l1.triage_notes
        result["pre_score"] = float(l1.pre_score) if l1.pre_score else None
        result["confidence"] = float(l1.confidence) if l1.confidence else None

    l2 = db.session.get(CompanyEnrichmentL2, company_id)
    if l2:
        result["company_overview"] = l2.company_intel
        result["ai_opportunities"] = l2.ai_opportunities
        result["pain_hypothesis"] = l2.pain_hypothesis
        result["quick_wins"] = l2.quick_wins
        result["pitch_framing"] = l2.pitch_framing
        result["revenue_trend"] = l2.revenue_trend
        result["industry_pain_points"] = l2.industry_pain_points
        result["relevant_case_study"] = l2.relevant_case_study
        result["enriched_at"] = l2.enriched_at.isoformat() if l2.enriched_at else None

    profile = db.session.get(CompanyEnrichmentProfile, company_id)
    if profile:
        result["company_intel"] = profile.company_intel
        result["key_products"] = profile.key_products
        result["customer_segments"] = profile.customer_segments
        result["competitors"] = profile.competitors
        result["tech_stack"] = profile.tech_stack
        result["leadership_team"] = profile.leadership_team
        result["certifications"] = profile.certifications

    signals = db.session.get(CompanyEnrichmentSignals, company_id)
    if signals:
        result["digital_initiatives"] = signals.digital_initiatives
        result["hiring_signals"] = signals.hiring_signals
        result["ai_adoption_level"] = signals.ai_adoption_level
        result["growth_indicators"] = signals.growth_indicators

    market = db.session.get(CompanyEnrichmentMarket, company_id)
    if market:
        result["recent_news"] = market.recent_news
        result["funding_history"] = market.funding_history

    return result if result else None


# ---------------------------------------------------------------------------
# Tool definition for registry
# ---------------------------------------------------------------------------

COMPANY_RESEARCH_TOOLS = [
    ToolDefinition(
        name="research_own_company",
        description=(
            "Perform deep research on the user's own company using a 3-step "
            "pipeline: website scrape, Perplexity web search, and Claude "
            "synthesis. Returns structured company intelligence including "
            "overview, products, competitors, market position, pain hypotheses, "
            "and AI opportunities. Use this FIRST in the strategy phase to "
            "ground all recommendations in real data. Cached results are "
            "returned if research was previously completed — pass force=true "
            "to re-run. Expensive: max 1 call per turn."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "force": {
                    "type": "boolean",
                    "description": (
                        "If true, re-run research even if enrichment data "
                        "already exists. Default false (returns cached data)."
                    ),
                },
            },
            "required": [],
        },
        handler=research_own_company,
    ),
]
