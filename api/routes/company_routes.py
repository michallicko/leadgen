import json
import math

from flask import Blueprint, jsonify, request

from ..auth import require_auth, require_role, resolve_tenant
from ..display import (
    display_business_model,
    display_buying_stage,
    display_cohort,
    display_company_size,
    display_confidence,
    display_crm_status,
    display_engagement_status,
    display_geo_region,
    display_icp_fit,
    display_industry,
    display_ownership_type,
    display_revenue_range,
    display_status,
    display_tier,
)
from ..models import db

companies_bp = Blueprint("companies", __name__)


def _iso(v):
    """Safely convert a datetime or string to ISO format."""
    if v is None:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def _parse_jsonb(v):
    """Parse a JSONB value that may be a string (SQLite) or dict (Postgres)."""
    if v is None:
        return {}
    if isinstance(v, str):
        return json.loads(v) if v else {}
    return v

ALLOWED_SORT = {
    "name", "domain", "status", "tier", "triage_score", "hq_country",
    "industry", "contact_count", "created_at",
}


@companies_bp.route("/api/companies", methods=["GET"])
@require_auth
def list_companies():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    page = max(1, request.args.get("page", 1, type=int))
    page_size = min(100, max(1, request.args.get("page_size", 25, type=int)))
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()
    tier = request.args.get("tier", "").strip()
    tag_name = request.args.get("tag_name", "").strip()
    owner_name = request.args.get("owner_name", "").strip()
    sort = request.args.get("sort", "name").strip()
    sort_dir = request.args.get("sort_dir", "asc").strip().lower()

    if sort not in ALLOWED_SORT:
        sort = "name"
    if sort_dir not in ("asc", "desc"):
        sort_dir = "asc"

    where = ["c.tenant_id = :tenant_id"]
    params = {"tenant_id": tenant_id}

    if search:
        where.append("(LOWER(c.name) LIKE LOWER(:search) OR LOWER(c.domain) LIKE LOWER(:search))")
        params["search"] = f"%{search}%"
    if status:
        where.append("c.status = :status")
        params["status"] = status
    if tier:
        where.append("c.tier = :tier")
        params["tier"] = tier
    if tag_name:
        where.append("b.name = :tag_name")
        params["tag_name"] = tag_name
    if owner_name:
        where.append("o.name = :owner_name")
        params["owner_name"] = owner_name

    # Custom field filters: cf_{key}=value
    cf_idx = 0
    for param_key, param_val in request.args.items():
        if param_key.startswith("cf_") and param_val.strip():
            field_key = param_key[3:]
            dialect = db.engine.dialect.name
            if dialect == "sqlite":
                where.append(f"json_extract(c.custom_fields, '$.{field_key}') = :cf_val_{cf_idx}")
            else:
                where.append(f"c.custom_fields ->> :cf_key_{cf_idx} = :cf_val_{cf_idx}")
                params[f"cf_key_{cf_idx}"] = field_key
            params[f"cf_val_{cf_idx}"] = param_val.strip()
            cf_idx += 1

    where_clause = " AND ".join(where)

    # Count query
    total = db.session.execute(
        db.text(f"""
            SELECT COUNT(*)
            FROM companies c
            LEFT JOIN tags b ON c.tag_id = b.id
            LEFT JOIN owners o ON c.owner_id = o.id
            WHERE {where_clause}
        """),
        params,
    ).scalar() or 0

    pages = max(1, math.ceil(total / page_size))
    offset = (page - 1) * page_size

    # Sort mapping for computed columns
    sort_col = "contact_count" if sort == "contact_count" else f"c.{sort}"
    order = f"{sort_col} {'ASC' if sort_dir == 'asc' else 'DESC'} NULLS LAST"

    rows = db.session.execute(
        db.text(f"""
            SELECT
                c.id, c.name, c.domain, c.status, c.tier,
                o.name AS owner_name, b.name AS tag_name,
                c.industry, c.hq_country, c.triage_score,
                (SELECT COUNT(*) FROM contacts ct WHERE ct.company_id = c.id) AS contact_count,
                c.created_at
            FROM companies c
            LEFT JOIN tags b ON c.tag_id = b.id
            LEFT JOIN owners o ON c.owner_id = o.id
            WHERE {where_clause}
            ORDER BY {order}
            LIMIT :limit OFFSET :offset
        """),
        {**params, "limit": page_size, "offset": offset},
    ).fetchall()

    companies = []
    for r in rows:
        companies.append({
            "id": str(r[0]),
            "name": r[1],
            "domain": r[2],
            "status": display_status(r[3]),
            "tier": display_tier(r[4]),
            "owner_name": r[5],
            "tag_name": r[6],
            "industry": display_industry(r[7]),
            "hq_country": r[8],
            "triage_score": float(r[9]) if r[9] is not None else None,
            "contact_count": r[10] or 0,
        })

    return jsonify({
        "companies": companies,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    })


@companies_bp.route("/api/companies/<company_id>", methods=["GET"])
@require_auth
def get_company(company_id):
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    row = db.session.execute(
        db.text("""
            SELECT
                c.id, c.name, c.domain, c.status, c.tier,
                c.business_model, c.company_size, c.ownership_type,
                c.geo_region, c.industry, c.industry_category,
                c.revenue_range, c.buying_stage, c.engagement_status,
                c.crm_status, c.ai_adoption, c.news_confidence,
                c.business_type, c.cohort,
                c.summary, c.hq_city, c.hq_country,
                c.triage_notes, c.triage_score,
                c.verified_revenue_eur_m, c.verified_employees,
                c.enrichment_cost_usd, c.pre_score,
                c.lemlist_synced, c.error_message, c.notes, c.custom_fields,
                c.created_at, c.updated_at,
                o.name AS owner_name, b.name AS tag_name,
                c.ico,
                c.website_url, c.linkedin_url, c.logo_url,
                c.last_enriched_at, c.data_quality_score
            FROM companies c
            LEFT JOIN owners o ON c.owner_id = o.id
            LEFT JOIN tags b ON c.tag_id = b.id
            WHERE c.id = :id AND c.tenant_id = :tenant_id
        """),
        {"id": company_id, "tenant_id": tenant_id},
    ).fetchone()

    if not row:
        return jsonify({"error": "Company not found"}), 404

    company = {
        "id": str(row[0]),
        "name": row[1],
        "domain": row[2],
        "status": display_status(row[3]),
        "tier": display_tier(row[4]),
        "business_model": display_business_model(row[5]),
        "company_size": display_company_size(row[6]),
        "ownership_type": display_ownership_type(row[7]),
        "geo_region": display_geo_region(row[8]),
        "industry": display_industry(row[9]),
        "industry_category": row[10],
        "revenue_range": display_revenue_range(row[11]),
        "buying_stage": display_buying_stage(row[12]),
        "engagement_status": display_engagement_status(row[13]),
        "crm_status": display_crm_status(row[14]),
        "ai_adoption": display_confidence(row[15]),
        "news_confidence": display_confidence(row[16]),
        "business_type": row[17],
        "cohort": display_cohort(row[18]),
        "summary": row[19],
        "hq_city": row[20],
        "hq_country": row[21],
        "triage_notes": row[22],
        "triage_score": float(row[23]) if row[23] is not None else None,
        "verified_revenue_eur_m": float(row[24]) if row[24] is not None else None,
        "verified_employees": float(row[25]) if row[25] is not None else None,
        "enrichment_cost_usd": float(row[26]) if row[26] is not None else None,
        "pre_score": float(row[27]) if row[27] is not None else None,
        "lemlist_synced": row[28],
        "error_message": row[29],
        "notes": row[30],
        "custom_fields": _parse_jsonb(row[31]),
        "created_at": _iso(row[32]),
        "updated_at": _iso(row[33]),
        "owner_name": row[34],
        "tag_name": row[35],
        "ico": row[36],
        "website_url": row[37],
        "linkedin_url": row[38],
        "logo_url": row[39],
        "last_enriched_at": _iso(row[40]),
        "data_quality_score": float(row[41]) if row[41] is not None else None,
    }

    # L1 enrichment
    l1_row = db.session.execute(
        db.text("""
            SELECT triage_notes, pre_score, research_query, raw_response,
                   confidence, quality_score, qc_flags,
                   enriched_at, enrichment_cost_usd
            FROM company_enrichment_l1
            WHERE company_id = :id
        """),
        {"id": company_id},
    ).fetchone()

    if l1_row:
        company["enrichment_l1"] = {
            "triage_notes": l1_row[0],
            "pre_score": float(l1_row[1]) if l1_row[1] is not None else None,
            "research_query": l1_row[2],
            "raw_response": _parse_jsonb(l1_row[3]),
            "confidence": float(l1_row[4]) if l1_row[4] is not None else None,
            "quality_score": l1_row[5],
            "qc_flags": _parse_jsonb(l1_row[6]),
            "enriched_at": _iso(l1_row[7]),
            "enrichment_cost_usd": float(l1_row[8]) if l1_row[8] is not None else None,
        }
    else:
        company["enrichment_l1"] = None

    # L2 enrichment modules
    l2_modules = {}

    # Profile
    prof_row = db.session.execute(
        db.text("""
            SELECT company_intel, key_products, customer_segments, competitors,
                   tech_stack, leadership_team, certifications,
                   enriched_at, enrichment_cost_usd
            FROM company_enrichment_profile
            WHERE company_id = :id
        """),
        {"id": company_id},
    ).fetchone()
    if prof_row:
        l2_modules.update({
            "company_intel": prof_row[0],
            "key_products": prof_row[1],
            "customer_segments": prof_row[2],
            "competitors": prof_row[3],
            "tech_stack": prof_row[4],
            "leadership_team": prof_row[5],
            "certifications": prof_row[6],
        })

    # Signals
    sig_row = db.session.execute(
        db.text("""
            SELECT digital_initiatives, leadership_changes, hiring_signals,
                   ai_hiring, tech_partnerships, competitor_ai_moves,
                   ai_adoption_level, news_confidence, growth_indicators,
                   job_posting_count, hiring_departments,
                   enriched_at, enrichment_cost_usd
            FROM company_enrichment_signals
            WHERE company_id = :id
        """),
        {"id": company_id},
    ).fetchone()
    if sig_row:
        l2_modules.update({
            "digital_initiatives": sig_row[0],
            "leadership_changes": sig_row[1],
            "hiring_signals": sig_row[2],
            "ai_hiring": sig_row[3],
            "tech_partnerships": sig_row[4],
            "competitor_ai_moves": sig_row[5],
            "ai_adoption_level": sig_row[6],
            "news_confidence": sig_row[7],
            "growth_indicators": sig_row[8],
            "job_posting_count": sig_row[9],
            "hiring_departments": _parse_jsonb(sig_row[10]),
        })

    # Market
    mkt_row = db.session.execute(
        db.text("""
            SELECT recent_news, funding_history, eu_grants,
                   media_sentiment, press_releases, thought_leadership,
                   enriched_at, enrichment_cost_usd
            FROM company_enrichment_market
            WHERE company_id = :id
        """),
        {"id": company_id},
    ).fetchone()
    if mkt_row:
        l2_modules.update({
            "recent_news": mkt_row[0],
            "funding_history": mkt_row[1],
            "eu_grants": mkt_row[2],
            "media_sentiment": mkt_row[3],
            "press_releases": mkt_row[4],
            "thought_leadership": mkt_row[5],
        })

    # Opportunity
    opp_row = db.session.execute(
        db.text("""
            SELECT pain_hypothesis, relevant_case_study, ai_opportunities,
                   quick_wins, industry_pain_points, cross_functional_pain,
                   adoption_barriers,
                   enriched_at, enrichment_cost_usd
            FROM company_enrichment_opportunity
            WHERE company_id = :id
        """),
        {"id": company_id},
    ).fetchone()
    if opp_row:
        l2_modules.update({
            "pain_hypothesis": opp_row[0],
            "relevant_case_study": opp_row[1],
            "ai_opportunities": opp_row[2],
            "quick_wins": _parse_jsonb(opp_row[3]),
            "industry_pain_points": opp_row[4],
            "cross_functional_pain": opp_row[5],
            "adoption_barriers": opp_row[6],
        })

    # Compute aggregate enriched_at / cost from available modules
    enriched_ats = []
    total_cost = 0.0
    for mod_row in [prof_row, sig_row, mkt_row, opp_row]:
        if mod_row:
            if mod_row[-2]:  # enriched_at
                enriched_ats.append(mod_row[-2])
            if mod_row[-1]:  # enrichment_cost_usd
                total_cost += float(mod_row[-1])

    if l2_modules:
        l2_modules["enriched_at"] = _iso(max(enriched_ats)) if enriched_ats else None
        l2_modules["enrichment_cost_usd"] = total_cost if total_cost > 0 else None
        company["enrichment_l2"] = l2_modules
    else:
        # Fallback: try old company_enrichment_l2 table (backward compat during migration)
        l2_row = db.session.execute(
            db.text("""
                SELECT company_intel, recent_news, ai_opportunities,
                       pain_hypothesis, relevant_case_study, digital_initiatives,
                       leadership_changes, hiring_signals, key_products,
                       customer_segments, competitors, tech_stack,
                       funding_history, eu_grants, leadership_team,
                       ai_hiring, tech_partnerships, certifications,
                       quick_wins, industry_pain_points, cross_functional_pain,
                       adoption_barriers, competitor_ai_moves,
                       enriched_at, enrichment_cost_usd
                FROM company_enrichment_l2
                WHERE company_id = :id
            """),
            {"id": company_id},
        ).fetchone()
        if l2_row:
            company["enrichment_l2"] = {
                "company_intel": l2_row[0], "recent_news": l2_row[1],
                "ai_opportunities": l2_row[2], "pain_hypothesis": l2_row[3],
                "relevant_case_study": l2_row[4], "digital_initiatives": l2_row[5],
                "leadership_changes": l2_row[6], "hiring_signals": l2_row[7],
                "key_products": l2_row[8], "customer_segments": l2_row[9],
                "competitors": l2_row[10], "tech_stack": l2_row[11],
                "funding_history": l2_row[12], "eu_grants": l2_row[13],
                "leadership_team": l2_row[14], "ai_hiring": l2_row[15],
                "tech_partnerships": l2_row[16], "certifications": l2_row[17],
                "quick_wins": l2_row[18], "industry_pain_points": l2_row[19],
                "cross_functional_pain": l2_row[20], "adoption_barriers": l2_row[21],
                "competitor_ai_moves": l2_row[22],
                "enriched_at": _iso(l2_row[23]),
                "enrichment_cost_usd": float(l2_row[24]) if l2_row[24] is not None else None,
            }
        else:
            company["enrichment_l2"] = None

    # Legal profile (unified registry data)
    lp_row = db.session.execute(
        db.text("""
            SELECT registration_id, tax_id, official_name, legal_form,
                   legal_form_name, date_established, date_dissolved,
                   registered_address, address_city, address_postal_code,
                   nace_codes, registration_court, registration_number,
                   registered_capital, directors, registration_status,
                   insolvency_flag, insolvency_details, active_insolvency_count,
                   match_confidence, match_method, enriched_at,
                   registration_country, credibility_score, credibility_factors
            FROM company_legal_profile
            WHERE company_id = :id
        """),
        {"id": company_id},
    ).fetchone()

    if lp_row:
        company["registry_data"] = {
            "ico": lp_row[0],
            "dic": lp_row[1],
            "official_name": lp_row[2],
            "legal_form": lp_row[3],
            "legal_form_name": lp_row[4],
            "date_established": str(lp_row[5]) if lp_row[5] else None,
            "date_dissolved": str(lp_row[6]) if lp_row[6] else None,
            "registered_address": lp_row[7],
            "address_city": lp_row[8],
            "address_postal_code": lp_row[9],
            "nace_codes": _parse_jsonb(lp_row[10]),
            "registration_court": lp_row[11],
            "registration_number": lp_row[12],
            "registered_capital": lp_row[13],
            "directors": _parse_jsonb(lp_row[14]),
            "registration_status": lp_row[15],
            "insolvency_flag": lp_row[16],
            "insolvency_details": _parse_jsonb(lp_row[17]),
            "active_insolvency_count": lp_row[18] or 0,
            "match_confidence": float(lp_row[19]) if lp_row[19] is not None else None,
            "match_method": lp_row[20],
            "enriched_at": _iso(lp_row[21]),
            "registration_country": lp_row[22],
            "credibility_score": lp_row[23],
            "credibility_factors": _parse_jsonb(lp_row[24]),
        }
    else:
        # Fallback: read from legacy company_registry_data table
        reg_row = db.session.execute(
            db.text("""
                SELECT ico, dic, official_name, legal_form, legal_form_name,
                       date_established, date_dissolved, registered_address,
                       address_city, address_postal_code, nace_codes,
                       registration_court, registration_number, registered_capital,
                       directors, registration_status, insolvency_flag,
                       match_confidence, match_method, ares_updated_at,
                       enriched_at, registry_country
                FROM company_registry_data
                WHERE company_id = :id
            """),
            {"id": company_id},
        ).fetchone()

        if reg_row:
            company["registry_data"] = {
                "ico": reg_row[0],
                "dic": reg_row[1],
                "official_name": reg_row[2],
                "legal_form": reg_row[3],
                "legal_form_name": reg_row[4],
                "date_established": str(reg_row[5]) if reg_row[5] else None,
                "date_dissolved": str(reg_row[6]) if reg_row[6] else None,
                "registered_address": reg_row[7],
                "address_city": reg_row[8],
                "address_postal_code": reg_row[9],
                "nace_codes": _parse_jsonb(reg_row[10]),
                "registration_court": reg_row[11],
                "registration_number": reg_row[12],
                "registered_capital": reg_row[13],
                "directors": _parse_jsonb(reg_row[14]),
                "registration_status": reg_row[15],
                "insolvency_flag": reg_row[16],
                "match_confidence": float(reg_row[17]) if reg_row[17] is not None else None,
                "match_method": reg_row[18],
                "enriched_at": _iso(reg_row[20]),
                "registration_country": reg_row[21],
            }
        else:
            company["registry_data"] = None

    # Tags
    tag_rows = db.session.execute(
        db.text("SELECT category, value FROM company_tags WHERE company_id = :id ORDER BY category, value"),
        {"id": company_id},
    ).fetchall()
    company["tags"] = [{"category": r[0], "value": r[1]} for r in tag_rows]

    # Contacts summary
    contact_rows = db.session.execute(
        db.text("""
            SELECT ct.id, ct.first_name, ct.last_name, ct.job_title, ct.email_address,
                   ct.contact_score, ct.icp_fit, ct.message_status
            FROM contacts ct
            WHERE ct.company_id = :id
            ORDER BY ct.contact_score DESC NULLS LAST
        """),
        {"id": company_id},
    ).fetchall()
    company["contacts"] = [{
        "id": str(r[0]),
        "full_name": ((r[1] or "") + " " + (r[2] or "")).strip(),
        "first_name": r[1],
        "last_name": r[2],
        "job_title": r[3],
        "email_address": r[4],
        "contact_score": r[5],
        "icp_fit": display_icp_fit(r[6]),
        "message_status": r[7],
    } for r in contact_rows]

    return jsonify(company)


@companies_bp.route("/api/companies/<company_id>", methods=["PATCH"])
@require_role("editor")
def update_company(company_id):
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    body = request.get_json(silent=True) or {}
    allowed = {
        "status", "tier", "notes", "triage_notes",
        "buying_stage", "engagement_status", "crm_status", "cohort",
    }
    fields = {k: v for k, v in body.items() if k in allowed}
    custom_fields_update = body.get("custom_fields")

    if not fields and not custom_fields_update:
        return jsonify({"error": "No valid fields to update"}), 400

    # Verify company belongs to tenant
    row = db.session.execute(
        db.text("SELECT id, custom_fields FROM companies WHERE id = :id AND tenant_id = :t"),
        {"id": company_id, "t": tenant_id},
    ).fetchone()
    if not row:
        return jsonify({"error": "Company not found"}), 404

    set_parts = []
    params = {"id": company_id}
    for k, v in fields.items():
        set_parts.append(f"{k} = :{k}")
        params[k] = v

    if custom_fields_update and isinstance(custom_fields_update, dict):
        existing_cf = _parse_jsonb(row[1])
        existing_cf.update(custom_fields_update)
        set_parts.append("custom_fields = :custom_fields")
        params["custom_fields"] = json.dumps(existing_cf)

    db.session.execute(
        db.text(f"UPDATE companies SET {', '.join(set_parts)} WHERE id = :id"),
        params,
    )
    db.session.commit()

    return jsonify({"ok": True})


@companies_bp.route("/api/companies/<company_id>/enrich-registry", methods=["POST"])
@require_auth
def enrich_registry(company_id):
    """On-demand unified registry lookup for a single company."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    # Verify company belongs to tenant
    row = db.session.execute(
        db.text("SELECT name, ico, hq_country, domain FROM companies WHERE id = :id AND tenant_id = :t"),
        {"id": company_id, "t": tenant_id},
    ).fetchone()
    if not row:
        return jsonify({"error": "Company not found"}), 404

    body = request.get_json(silent=True) or {}
    ico_override = body.get("ico")

    from ..services.registries.orchestrator import RegistryOrchestrator
    orchestrator = RegistryOrchestrator()
    result = orchestrator.enrich_company(
        company_id=company_id,
        tenant_id=str(tenant_id),
        name=row[0],
        reg_id=ico_override or row[1],
        hq_country=row[2],
        domain=row[3],
    )

    return jsonify(result)


@companies_bp.route("/api/companies/<company_id>/confirm-registry", methods=["POST"])
@require_auth
def confirm_registry(company_id):
    """Confirm an ARES match from a list of candidates by providing the ICO."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    row = db.session.execute(
        db.text("SELECT name, hq_country, domain FROM companies WHERE id = :id AND tenant_id = :t"),
        {"id": company_id, "t": tenant_id},
    ).fetchone()
    if not row:
        return jsonify({"error": "Company not found"}), 404

    body = request.get_json(silent=True) or {}
    ico = body.get("ico")
    if not ico:
        return jsonify({"error": "ico is required"}), 400

    from ..services.ares import enrich_company
    result = enrich_company(
        company_id=company_id,
        tenant_id=str(tenant_id),
        name=row[0],
        ico=ico,
        hq_country=row[1],
        domain=row[2],
    )

    return jsonify(result)


@companies_bp.route("/api/companies/<company_id>/enrich-registry/<country>", methods=["POST"])
@require_auth
def enrich_registry_country(company_id, country):
    """On-demand registry lookup for a specific country adapter."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    row = db.session.execute(
        db.text("SELECT name, ico, hq_country, domain FROM companies WHERE id = :id AND tenant_id = :t"),
        {"id": company_id, "t": tenant_id},
    ).fetchone()
    if not row:
        return jsonify({"error": "Company not found"}), 404

    from ..services.registries import get_adapter
    adapter = get_adapter(country.upper())
    if not adapter:
        return jsonify({"error": f"No registry adapter for country: {country}"}), 400

    body = request.get_json(silent=True) or {}
    reg_id = body.get("ico") or body.get("reg_id")

    result = adapter.enrich_company(
        company_id=company_id,
        tenant_id=str(tenant_id),
        name=row[0],
        reg_id=reg_id or row[1],
        hq_country=row[2],
        domain=row[3],
    )
    return jsonify(result)
