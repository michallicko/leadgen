"""L2 Deep Research enrichment via Perplexity + Anthropic synthesis.

Migrates the n8n L2 workflow to native Python. Two-phase approach:
1. Research: Two Perplexity calls (News + Strategic Signals) using sonar-pro
2. Synthesis: Anthropic Claude synthesizes research into actionable intelligence

After enrichment, companies get status='enriched_l2' or
'enrichment_l2_failed' on error.
"""

import json
import logging
import re
import time
from datetime import datetime, timezone

from sqlalchemy import text

from ..models import db
from .anthropic_client import AnthropicClient
from .perplexity_client import PerplexityClient
from .stage_registry import get_model_for_stage

try:
    from .llm_logger import log_llm_usage
except ImportError:
    log_llm_usage = None

logger = logging.getLogger(__name__)

PERPLEXITY_MAX_TOKENS = 1200
PERPLEXITY_TEMPERATURE = 0.2
ANTHROPIC_MAX_TOKENS = 4000
ANTHROPIC_TEMPERATURE = 0.3
ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"

# ---------------------------------------------------------------------------
# Prompts: News & AI Maturity research
# ---------------------------------------------------------------------------

NEWS_SYSTEM_PROMPT = """You are researching recent company news for B2B sales intelligence. \
Your job is to find BUSINESS SIGNALS that indicate change, growth, or buying intent.

## DATE FILTERING
Current date is provided by the user. "Recent" means LAST 12 MONTHS ONLY.
- Discard results published before the cutoff date
- If ALL results are older than 12 months, return "None found" for every field

## SEARCH DISAMBIGUATION
Company names can be generic. Before including ANY result, verify:
1. The source mentions the company's WEBSITE DOMAIN or exact legal name
2. The content matches the company's INDUSTRY
Return "None found" rather than include wrong-company results.

## RELEVANCE: ONLY BUSINESS SIGNALS
Include: Funding, M&A, leadership hires/departures (VP+), expansion, major contracts, \
technology/digital initiatives, restructuring, revenue milestones.
Exclude: Product releases, thought leadership, awards, event appearances, PR.

## OUTPUT FORMAT
Return ONLY a JSON object. No markdown. No code fences. Start with {.

{
  "recent_news": "Business events from last 12 months. Format: 'Mon YYYY: Event'. Max 5. Or 'None found'",
  "funding": "Funding/investment with amount and date. Or 'None found'",
  "leadership_changes": "C-level or VP+ hires/departures. Or 'None found'",
  "expansion": "New markets, offices, major contracts. Or 'None found'",
  "workflow_ai_evidence": "AI/automation for documents, sales, admin. Or 'None found'",
  "digital_initiatives": "ERP, CRM, cloud implementations. Or 'None found'",
  "revenue_trend": "growing|stable|declining|restructuring with evidence. Or 'Unknown'",
  "growth_signals": "Concrete evidence: headcount growth, new offices. Or 'None found'",
  "ma_activity": "Recent mergers, acquisitions, or divestitures with dates. Or 'None found'",
  "news_confidence": "high|medium|low|none"
}"""

NEWS_USER_TEMPLATE = """Research recent business news and signals for:
Company: {company_name}
Website: {domain}
Country: {country}
Industry: {industry}

Current date: {current_date}

Search for: "{company_name}" combined with "{domain}"
Verify all results are about THIS company ({domain}), not similarly-named entities."""


# ---------------------------------------------------------------------------
# Prompts: Strategic Signals research
# ---------------------------------------------------------------------------

STRATEGIC_SYSTEM_PROMPT = """You are researching company intelligence for B2B sales qualification.

## SEARCH DISAMBIGUATION
Verify all results match the company's WEBSITE DOMAIN and INDUSTRY.
Exclude results about similarly-named entities.

## AI/TRANSFORMATION ROLE MATCHING
Only flag roles containing: AI, ML, data science, digital transformation, innovation, \
automation, RPA, prompt engineer, LLM, GenAI.
Do NOT flag generic IT roles.

## REGULATORY PRESSURE
Only include regulations with EVIDENCE of applicability to THIS specific company.
Do NOT apply regulations based solely on industry label.

## OUTPUT FORMAT
Return ONLY a JSON object. No markdown. Start with {.

{
  "leadership_team": "Key executives. Format: 'Role: Name'. Or 'Unknown'",
  "ai_transformation_roles": "Open AI/data/transformation roles. Or 'None found'",
  "other_hiring_signals": "Notable open roles by department. Or 'None found'",
  "eu_grants": "EU/national grants with program, amount, date. Or 'None found'",
  "certifications": "ISO, industry certifications. Or 'Unknown'",
  "regulatory_pressure": "Applicable regulations with deadlines. Or 'None identified'",
  "vendor_partnerships": "Technology partnerships or platform usage. Or 'Unknown'",
  "employee_sentiment": "Review ratings and themes. Or 'Not found'",
  "tech_stack_categories": "Known technology platforms by category (CRM, ERP, Cloud, MarTech, DevTools). Or 'Unknown'",
  "fiscal_year_end": "Company fiscal year end month, if known. Or 'Unknown'",
  "digital_maturity_score": "Rate digital maturity 1-10 based on website sophistication, social presence, and technology adoption. Or 'Unknown'",
  "it_spend_indicators": "Evidence of technology investment level (IT team size, cloud migration, tech purchases). Or 'Unknown'",
  "data_completeness": "high|medium|low"
}"""

STRATEGIC_USER_TEMPLATE = """Research company intelligence for B2B qualification:
Company: {company_name}
Website: {domain}
Country: {country}
Industry: {industry}
Size: {employees} employees

Current date: {current_date}

Search for: "{company_name}" combined with "{domain}"
Verify all results are about THIS company ({domain})."""


# ---------------------------------------------------------------------------
# Prompts: Anthropic AI Synthesis
# ---------------------------------------------------------------------------

SYNTHESIS_SYSTEM_PROMPT = """You are an AI transformation strategist for a B2B AI consulting firm \
targeting European mid-market businesses.

You receive a company profile (L1 data) and validated research signals (L2 data). \
Generate actionable sales intelligence.

RULES:
- Every opportunity must link to a specific finding from the research
- If research is thin, generate fewer opportunities — 2 strong beats 5 weak
- Quick wins MUST be achievable in 4-8 weeks with clear ROI
- Pain hypothesis = what keeps a senior leader awake, based on evidence

PITCH FRAMING:
- growth_acceleration: expansion, funding, hiring
- efficiency_protection: cost pressure, layoffs, flat revenue
- competitive_catch_up: competitors adopting AI, no AI initiatives found
- compliance_driven: regulatory deadlines, audit pressure

OUTPUT FORMAT: Return ONLY valid JSON. Start with {.

{
  "ai_opportunities": "Top 3-5 AI use cases with evidence and impact",
  "pain_hypothesis": "1-2 sentences based on evidence",
  "quick_wins": [{"use_case": "...", "evidence": "...", "impact": "...", "complexity": "low|medium"}],
  "industry_pain_points": "Top 3 industry-specific pain points",
  "cross_functional_pain": "Cross-department pain points",
  "adoption_barriers": "Likely objections or blockers",
  "competitor_ai_moves": "Competitor AI activity or null",
  "pitch_framing": "growth_acceleration|efficiency_protection|competitive_catch_up|compliance_driven",
  "executive_brief": "3-4 sentence summary for a sales rep"
}"""

SYNTHESIS_USER_TEMPLATE = """Generate AI opportunity analysis for {company_name} ({domain}):

=== COMPANY PROFILE (from L1) ===
Industry: {industry}
Size: {employees} employees
Revenue: {revenue}
Country: {country}
Summary: {summary}
Products: {products}
Customers: {customers}
Competitors: {competitors}

=== L2 RESEARCH: NEWS & SIGNALS ===
Recent News: {recent_news}
Funding: {funding}
Leadership Changes: {leadership_changes}
Digital Initiatives: {digital_initiatives}
Revenue Trend: {revenue_trend}
Growth Signals: {growth_signals}

=== L2 RESEARCH: STRATEGIC INTELLIGENCE ===
Leadership Team: {leadership_team}
AI/Transformation Roles: {ai_transformation_roles}
Hiring Signals: {other_hiring_signals}
EU Grants: {eu_grants}
Certifications: {certifications}
Regulatory Pressure: {regulatory_pressure}
Vendor Partnerships: {vendor_partnerships}
Employee Sentiment: {employee_sentiment}"""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def enrich_l2(company_id, tenant_id=None, previous_data=None, boost=False):
    """Run L2 deep research enrichment for a single company.

    Args:
        company_id: UUID string of the company
        tenant_id: UUID string (optional, read from company)
        previous_data: dict of prior L2 enrichment (for re-enrichment)
        boost: if True, use higher-quality Perplexity model

    Returns:
        dict with enrichment_cost_usd, or error key on failure.
    """
    start_time = time.time()
    total_cost = 0.0
    news_data = {}
    strategic_data = {}
    synthesis_data = {}

    try:
        # --- Load company + L1 data ---
        company, l1_data = _load_company_and_l1(company_id)
        if not company:
            return {"error": "Company not found", "enrichment_cost_usd": 0}

        if not tenant_id:
            tenant_id = company["tenant_id"]

        model = get_model_for_stage("l2", boost=boost)

        # --- Phase 1: Two Perplexity research calls ---
        try:
            news_data, news_cost = _research_news(company, l1_data, model)
            total_cost += news_cost
        except Exception as e:
            logger.error("L2 news research failed for %s: %s", company_id, e)
            _set_company_status(company_id, "enrichment_l2_failed", error_msg=str(e))
            return {"error": str(e), "enrichment_cost_usd": total_cost}

        try:
            strategic_data, strategic_cost = _research_strategic(
                company, l1_data, model
            )
            total_cost += strategic_cost
        except Exception as e:
            logger.error("L2 strategic research failed for %s: %s", company_id, e)
            # Save partial results from news
            _upsert_l2_enrichment(company_id, news_data, {}, {},
                                  total_cost, l1_data=l1_data)
            _set_company_status(company_id, "enrichment_l2_failed",
                                error_msg=str(e))
            return {"error": str(e), "enrichment_cost_usd": total_cost}

        # --- Phase 2: Anthropic synthesis ---
        try:
            synthesis_data, synthesis_cost = _synthesize(
                company, l1_data, news_data, strategic_data
            )
            total_cost += synthesis_cost
        except Exception as e:
            logger.warning(
                "L2 synthesis failed for %s: %s — saving research only", company_id, e
            )
            # Save research without synthesis
            _upsert_l2_enrichment(company_id, news_data, strategic_data, {},
                                  total_cost, l1_data=l1_data)
            _set_company_status(company_id, "enriched_l2")
            db.session.commit()
            return {"enrichment_cost_usd": total_cost, "synthesis_failed": True}

        # --- Save everything ---
        _upsert_l2_enrichment(company_id, news_data, strategic_data,
                              synthesis_data, total_cost, l1_data=l1_data)
        _set_company_status(company_id, "enriched_l2")

        # --- Log LLM usage ---
        duration_ms = int((time.time() - start_time) * 1000)
        if log_llm_usage:
            _log_usage(company_id, tenant_id, model, total_cost, duration_ms, boost)

        db.session.commit()
        return {"enrichment_cost_usd": total_cost}

    except Exception as e:
        logger.exception("L2 enrichment failed for %s: %s", company_id, e)
        db.session.rollback()
        try:
            _set_company_status(company_id, "enrichment_l2_failed", error_msg=str(e))
            db.session.commit()
        except Exception:
            pass
        return {"error": str(e), "enrichment_cost_usd": total_cost}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _load_company_and_l1(company_id):
    """Load company record and L1 enrichment data."""
    row = db.session.execute(
        text("""
            SELECT c.id, c.tenant_id, c.name, c.domain, c.industry,
                   c.verified_revenue_eur_m, c.verified_employees,
                   c.geo_region, c.tier, c.hq_city, c.hq_country,
                   l1.raw_response, l1.confidence, l1.qc_flags
            FROM companies c
            LEFT JOIN company_enrichment_l1 l1 ON l1.company_id = c.id
            WHERE c.id = :cid
        """),
        {"cid": company_id},
    ).fetchone()

    if not row:
        return None, None

    company = {
        "id": row[0],
        "tenant_id": row[1],
        "name": row[2],
        "domain": row[3] or "",
        "industry": row[4] or "",
        "revenue": row[5],
        "employees": row[6],
        "geo_region": row[7] or "",
        "tier": row[8] or "",
        "hq_city": row[9] or "",
        "hq_country": row[10] or "",
    }

    l1_raw = row[11]
    l1_data = {}
    if l1_raw:
        try:
            l1_data = json.loads(l1_raw) if isinstance(l1_raw, str) else l1_raw
        except (json.JSONDecodeError, TypeError):
            pass

    return company, l1_data


# ---------------------------------------------------------------------------
# Phase 1: Perplexity research
# ---------------------------------------------------------------------------


def _research_news(company, l1_data, model):
    """Call Perplexity for news and business signals."""
    client = PerplexityClient()
    user_prompt = NEWS_USER_TEMPLATE.format(
        company_name=company["name"],
        domain=company["domain"],
        country=company.get("hq_country") or company.get("geo_region") or "Unknown",
        industry=company["industry"],
        current_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )

    resp = client.query(
        system_prompt=NEWS_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        max_tokens=PERPLEXITY_MAX_TOKENS,
        temperature=PERPLEXITY_TEMPERATURE,
        search_recency_filter="month",
    )

    data = _parse_json(resp.content)
    return data, resp.cost_usd


def _research_strategic(company, l1_data, model):
    """Call Perplexity for strategic signals."""
    client = PerplexityClient()
    user_prompt = STRATEGIC_USER_TEMPLATE.format(
        company_name=company["name"],
        domain=company["domain"],
        country=company.get("hq_country") or company.get("geo_region") or "Unknown",
        industry=company["industry"],
        employees=company.get("employees") or "Unknown",
        current_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )

    resp = client.query(
        system_prompt=STRATEGIC_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        max_tokens=PERPLEXITY_MAX_TOKENS,
        temperature=PERPLEXITY_TEMPERATURE,
    )

    data = _parse_json(resp.content)
    return data, resp.cost_usd


# ---------------------------------------------------------------------------
# Phase 2: Anthropic synthesis
# ---------------------------------------------------------------------------


def _synthesize(company, l1_data, news_data, strategic_data):
    """Call Anthropic Claude to synthesize research into actionable intel."""
    client = AnthropicClient()

    user_prompt = SYNTHESIS_USER_TEMPLATE.format(
        company_name=company["name"],
        domain=company["domain"],
        industry=company["industry"],
        employees=company.get("employees") or "Unknown",
        revenue=company.get("revenue") or "Unknown",
        country=company.get("hq_country") or company.get("geo_region") or "Unknown",
        summary=l1_data.get("summary") or "Not available",
        products=l1_data.get("key_products") or l1_data.get("products") or "Unknown",
        customers=l1_data.get("customer_segments") or "Unknown",
        competitors=l1_data.get("competitors") or "Unknown",
        # News fields
        recent_news=news_data.get("recent_news") or "None",
        funding=news_data.get("funding") or "None",
        leadership_changes=news_data.get("leadership_changes") or "None",
        digital_initiatives=news_data.get("digital_initiatives") or "None",
        revenue_trend=news_data.get("revenue_trend") or "Unknown",
        growth_signals=news_data.get("growth_signals") or "None",
        # Strategic fields
        leadership_team=strategic_data.get("leadership_team") or "Unknown",
        ai_transformation_roles=strategic_data.get("ai_transformation_roles") or "None",
        other_hiring_signals=strategic_data.get("other_hiring_signals") or "None",
        eu_grants=strategic_data.get("eu_grants") or "None",
        certifications=strategic_data.get("certifications") or "Unknown",
        regulatory_pressure=strategic_data.get("regulatory_pressure") or "None",
        vendor_partnerships=strategic_data.get("vendor_partnerships") or "Unknown",
        employee_sentiment=strategic_data.get("employee_sentiment") or "Not found",
    )

    resp = client.query(
        system_prompt=SYNTHESIS_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=ANTHROPIC_MODEL,
        max_tokens=ANTHROPIC_MAX_TOKENS,
        temperature=ANTHROPIC_TEMPERATURE,
    )

    data = _parse_json(resp.content)
    if not data:
        raise ValueError(
            f"Failed to parse synthesis JSON response ({len(resp.content)} chars)"
        )
    return data, resp.cost_usd


# ---------------------------------------------------------------------------
# DB operations
# ---------------------------------------------------------------------------

def _upsert_l2_enrichment(company_id, news_data, strategic_data,
                          synthesis_data, total_cost, l1_data=None):
    """Insert or update the company_enrichment_l2 record.

    Includes Phase 1 (data loss fix) and Phase 2 (new high-value) columns.
    """
    quick_wins = synthesis_data.get("quick_wins")
    if quick_wins and not isinstance(quick_wins, str):
        quick_wins = json.dumps(quick_wins)

    params = _build_l2_params(company_id, news_data, strategic_data,
                              synthesis_data, quick_wins, total_cost,
                              l1_data=l1_data)

    # Column list shared by INSERT and ON CONFLICT UPDATE
    _COLUMNS = (
        "company_intel", "recent_news", "ai_opportunities",
        "pain_hypothesis", "relevant_case_study", "digital_initiatives",
        "leadership_changes", "hiring_signals", "key_products",
        "customer_segments", "competitors", "tech_stack",
        "funding_history", "eu_grants", "leadership_team",
        "ai_hiring", "tech_partnerships", "certifications",
        "quick_wins", "industry_pain_points", "cross_functional_pain",
        "adoption_barriers", "competitor_ai_moves",
        # Phase 1: previously lost fields
        "expansion", "workflow_ai_evidence", "revenue_trend",
        "growth_signals", "regulatory_pressure", "employee_sentiment",
        "pitch_framing",
        # Phase 2: new high-value fields
        "ma_activity", "tech_stack_categories", "fiscal_year_end",
        "digital_maturity_score", "it_spend_indicators",
    )

    col_list = ", ".join(_COLUMNS)
    val_list = ", ".join(f":{c}" for c in _COLUMNS)
    update_list = ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLUMNS)

    # Try PostgreSQL upsert first, fall back to SQLite
    try:
        db.session.execute(
            text(f"""
                INSERT INTO company_enrichment_l2 (
                    company_id, {col_list},
                    enriched_at, enrichment_cost_usd
                ) VALUES (
                    :cid, {val_list},
                    :enriched_at, :cost
                )
                ON CONFLICT (company_id) DO UPDATE SET
                    {update_list},
                    enriched_at = EXCLUDED.enriched_at,
                    enrichment_cost_usd = EXCLUDED.enrichment_cost_usd
            """),
            params,
        )
    except Exception:
        db.session.rollback()
        # SQLite fallback
        db.session.execute(
            text(f"""
                INSERT OR REPLACE INTO company_enrichment_l2 (
                    company_id, {col_list},
                    enriched_at, enrichment_cost_usd
                ) VALUES (
                    :cid, {val_list},
                    :enriched_at, :cost
                )
            """),
            params,
        )


def _build_l2_params(company_id, news_data, strategic_data,
                     synthesis_data, quick_wins, total_cost,
                     l1_data=None):
    """Build parameter dict for L2 upsert.

    Phase 1 fixes (data loss):
    - expansion, workflow_ai_evidence, revenue_trend, growth_signals from news_data
    - regulatory_pressure, employee_sentiment from strategic_data
    - pitch_framing from synthesis_data
    - key_products, customer_segments sourced from L1 / synthesis instead of None
    - tech_stack uses certifications/digital_initiatives context; tech_partnerships
      uses vendor_partnerships (no longer duplicated)
    - competitors uses L1 competitors; competitor_ai_moves is separate synthesis field

    Phase 2 additions:
    - ma_activity from news_data
    - tech_stack_categories, fiscal_year_end, digital_maturity_score,
      it_spend_indicators from strategic_data
    """
    l1 = l1_data or {}

    return {
        "cid": company_id,
        "company_intel": _to_text(synthesis_data.get("executive_brief")),
        "recent_news": _to_text(news_data.get("recent_news")),
        "ai_opportunities": _to_text(synthesis_data.get("ai_opportunities")),
        "pain_hypothesis": _to_text(synthesis_data.get("pain_hypothesis")),
        "relevant_case_study": None,
        "digital_initiatives": news_data.get("digital_initiatives"),
        "leadership_changes": news_data.get("leadership_changes"),
        "hiring_signals": strategic_data.get("other_hiring_signals"),
        # Fix #8: key_products from L1 data instead of hardcoded None
        "key_products": (l1.get("key_products")
                         or l1.get("products")
                         or synthesis_data.get("key_products")),
        # Fix #9: customer_segments from L1 data instead of hardcoded None
        "customer_segments": (l1.get("customer_segments")
                              or synthesis_data.get("customer_segments")),
        # Fix #10: competitors from L1 (named competitors), not synthesis ai_moves
        "competitors": l1.get("competitors") or synthesis_data.get("competitors"),
        # Fix #10: tech_stack = digital_initiatives tech detail (what they use)
        "tech_stack": news_data.get("digital_initiatives"),
        "funding_history": news_data.get("funding"),
        "eu_grants": strategic_data.get("eu_grants"),
        "leadership_team": strategic_data.get("leadership_team"),
        "ai_hiring": strategic_data.get("ai_transformation_roles"),
        # Fix #10: tech_partnerships = vendor_partnerships (who they partner with)
        "tech_partnerships": strategic_data.get("vendor_partnerships"),
        "certifications": strategic_data.get("certifications"),
        "quick_wins": quick_wins,
        "industry_pain_points": synthesis_data.get("industry_pain_points"),
        "cross_functional_pain": synthesis_data.get("cross_functional_pain"),
        "adoption_barriers": synthesis_data.get("adoption_barriers"),
        # Fix: competitor_ai_moves now properly stored from synthesis
        "competitor_ai_moves": synthesis_data.get("competitor_ai_moves"),
        # Phase 1 fixes: fields previously generated but not stored
        "expansion": news_data.get("expansion"),
        "workflow_ai_evidence": news_data.get("workflow_ai_evidence"),
        "revenue_trend": news_data.get("revenue_trend"),
        "growth_signals": news_data.get("growth_signals"),
        "regulatory_pressure": strategic_data.get("regulatory_pressure"),
        "employee_sentiment": strategic_data.get("employee_sentiment"),
        "pitch_framing": synthesis_data.get("pitch_framing"),
        # Phase 2: new high-value fields
        "ma_activity": news_data.get("ma_activity"),
        "tech_stack_categories": strategic_data.get("tech_stack_categories"),
        "fiscal_year_end": strategic_data.get("fiscal_year_end"),
        "digital_maturity_score": strategic_data.get("digital_maturity_score"),
        "it_spend_indicators": strategic_data.get("it_spend_indicators"),
        "enriched_at": datetime.now(timezone.utc),
        "cost": total_cost,
    }


def _set_company_status(company_id, status, error_msg=None):
    """Update company status and optional error message."""
    if error_msg:
        db.session.execute(
            text("""
                UPDATE companies
                SET status = :status, error_message = :err
                WHERE id = :cid
            """),
            {"cid": company_id, "status": status, "err": error_msg},
        )
    else:
        db.session.execute(
            text("""
                UPDATE companies SET status = :status WHERE id = :cid
            """),
            {"cid": company_id, "status": status},
        )


def _log_usage(company_id, tenant_id, model, total_cost, duration_ms, boost):
    """Log LLM usage for all L2 calls."""
    try:
        log_llm_usage(
            tenant_id=tenant_id,
            operation="l2_enrichment",
            provider="perplexity+anthropic",
            model=model,
            input_tokens=0,  # Aggregated — individual costs tracked per call
            output_tokens=0,
            duration_ms=duration_ms,
            metadata={
                "boost": boost,
                "cost_usd": total_cost,
                "entity_type": "company",
                "entity_id": company_id,
                "stage": "l2",
            },
        )
    except Exception as e:
        logger.warning("Failed to log L2 LLM usage: %s", e)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_code_fences(text):
    """Strip markdown code fences from LLM response."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (```json, ```JSON, or just ```)
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        else:
            text = text[3:]
    if text.rstrip().endswith("```"):
        text = text.rstrip()[:-3]
    return text.strip()


def _parse_json(content):
    """Parse JSON from API response, handling markdown fences."""
    if not content:
        return {}

    cleaned = _strip_code_fences(content)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON object in the response
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        truncated = not content.rstrip().endswith(("}", "]"))
        logger.warning(
            "Failed to parse JSON from L2 response (%d chars%s): %s...",
            len(content),
            ", appears truncated" if truncated else "",
            content[:200],
        )
        return {}
