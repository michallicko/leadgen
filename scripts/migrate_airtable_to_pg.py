#!/usr/bin/env python3
"""
Airtable → PostgreSQL Data Migration

Migrates dashboard-facing tables from Airtable to PostgreSQL under the
'visionvolve' tenant. Uses ON CONFLICT upserts for idempotent re-runs.

Prerequisites:
  - Database created and migrations 001-004 applied
  - .env with AIRTABLE_TOKEN and DATABASE_URL

Usage:
  pip install requests psycopg2-binary python-dotenv
  python scripts/migrate_airtable_to_pg.py
"""

import json
import os
import sys
import time

import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv

load_dotenv()

AT_TOKEN = os.environ["AIRTABLE_TOKEN"]
DB_URL = os.environ["DATABASE_URL"]
AT_BASE = "https://api.airtable.com/v0/appFOpa3XSj5A70ZP"

# Airtable table IDs
OWNERS_TABLE = "tblOXp3JLhQooATNC"
COMPANIES_TABLE = "tblz8w67LPdeofgvw"
CONTACTS_TABLE = "tblWpp39X054tkp3C"
MESSAGES_TABLE = "tbljwTvb4yLsGwMyN"

# ── Enum Maps (Airtable display → PG enum) ──────────────────────────

COMPANY_STATUS_MAP = {
    "New": "new",
    "Enriched": "enriched",
    "Needs Review": "needs_review",
    "Synced": "synced",
    "Enrichment Failed": "enrichment_failed",
    "Enrichment L2 Failed": "enrichment_l2_failed",
    "Error pushing to Lemlist": "error_pushing_lemlist",
    "Triage: Passed": "triage_passed",
    "Enriched L2": "enriched_l2",
    "Triage: Review": "triage_review",
    "Triage: Disqualified": "triage_disqualified",
}

TIER_MAP = {
    "Tier 1 - Platinum": "tier_1_platinum",
    "Tier 2 - Gold": "tier_2_gold",
    "Tier 3 - Silver": "tier_3_silver",
    "Tier 4 - Bronze": "tier_4_bronze",
    "Tier 5 - Copper": "tier_5_copper",
    "Deprioritize": "deprioritize",
}

BUSINESS_MODEL_MAP = {
    "B2B": "b2b", "B2C": "b2c", "Marketplace": "marketplace",
    "Gov": "gov", "Non-profit": "non_profit", "Hybrid (B2B/B2C)": "hybrid",
}

COMPANY_SIZE_MAP = {
    "Micro (<20)": "micro", "Startup (20-49)": "startup",
    "SMB (50-199)": "smb", "Mid-market (200-1999)": "mid_market",
    "Enterprise (2000+)": "enterprise",
}

OWNERSHIP_TYPE_MAP = {
    "Bootstrapped": "bootstrapped", "VC-backed": "vc_backed",
    "PE-backed": "pe_backed", "Public": "public",
    "Family-owned": "family_owned", "State-owned": "state_owned",
    "Other": "other",
}

GEO_REGION_MAP = {
    "DACH": "dach", "Nordics": "nordics", "Benelux": "benelux",
    "CEE": "cee", "UK & Ireland": "uk_ireland",
    "Southern Europe": "southern_europe", "US": "us", "Other": "other",
}

INDUSTRY_MAP = {
    "Software & SaaS": "software_saas",
    "Information Technology": "it",
    "Professional Services": "professional_services",
    "Financial Services": "financial_services",
    "Healthcare & Life Sciences": "healthcare",
    "Manufacturing": "manufacturing",
    "Retail & E-Commerce": "retail",
    "Media & Entertainment": "media",
    "Energy & Utilities": "energy",
    "Telecommunications": "telecom",
    "Transportation & Logistics": "transport",
    "Construction & Real Estate": "construction",
    "Education": "education",
    "Public Sector": "public_sector",
    "Other": "other",
}

REVENUE_MAP = {
    "Micro (<€2M)": "micro", "Small (€2M-€10M)": "small",
    "Medium (€10M-€50M)": "medium", "Mid-market (€50M-€500M)": "mid_market",
    "Enterprise (€500M+)": "enterprise",
}

BUYING_STAGE_MAP = {
    "Unaware": "unaware", "Problem-aware": "problem_aware",
    "Exploring AI": "exploring_ai", "Looking for Partners": "looking_for_partners",
    "In Discussion": "in_discussion", "Proposal Sent": "proposal_sent",
    "Won": "won", "Lost": "lost",
}

ENGAGEMENT_STATUS_MAP = {
    "Cold": "cold", "Approached": "approached", "Prospect": "prospect",
    "Customer": "customer", "Churned": "churned",
}

CRM_STATUS_MAP = {
    "Cold": "cold", "Scheduled for Outreach": "scheduled_for_outreach",
    "Outreach": "outreach", "Prospect": "prospect",
    "Customer": "customer", "Churn": "churn",
}

CONFIDENCE_MAP = {"Low": "low", "Medium": "medium", "High": "high"}

BUSINESS_TYPE_MAP = {
    "Manufacturer": "manufacturer", "Distributor": "distributor",
    "Service provider": "service_provider", "SaaS": "saas",
    "Platform": "platform", "Other": "other",
}

COHORT_MAP = {"A": "a", "B": "b"}

SENIORITY_MAP = {
    "C-Level": "c_level", "VP": "vp", "Director": "director",
    "Manager": "manager", "Individual Contributor": "individual_contributor",
    "Founder": "founder", "Other": "other",
}

DEPARTMENT_MAP = {
    "Executive": "executive", "Engineering": "engineering",
    "Product": "product", "Sales": "sales", "Marketing": "marketing",
    "Customer Success": "customer_success", "Finance": "finance",
    "HR": "hr", "Operations": "operations", "Other": "other",
}

ICP_FIT_MAP = {
    "Strong Fit": "strong_fit", "Moderate Fit": "moderate_fit",
    "Weak Fit": "weak_fit", "Unknown": "unknown",
}

RELATIONSHIP_MAP = {
    "Prospect": "prospect", "Active": "active", "Dormant": "dormant",
    "Former": "former", "Partner": "partner", "Internal": "internal",
}

CONTACT_SOURCE_MAP = {
    "Inbound": "inbound", "Outbound": "outbound", "Referral": "referral",
    "Event": "event", "Social": "social", "Other": "other",
}

LANGUAGE_MAP = {"EN": "en", "DE": "de", "NL": "nl", "CS": "cs"}
TONE_MAP = {"professional": "professional", "casual": "casual", "bold": "bold", "empathetic": "empathetic"}
VARIANT_MAP = {"A": "a", "B": "b"}
MESSAGE_STATUS_MAP = {
    "draft": "draft", "approved": "approved", "rejected": "rejected",
    "sent": "sent", "delivered": "delivered", "replied": "replied",
}
CONTACT_MSG_STATUS_MAP = {
    "not_started": "not_started", "generating": "generating",
    "pending_review": "pending_review", "approved": "approved",
    "sent": "sent", "replied": "replied", "no_channel": "no_channel",
    "generation_failed": "generation_failed",
}

# Tag category mappings (multi-select fields → tag_category enum)
TAG_FIELDS = {
    "Risk / Exclusion Flags": "risk_exclusion_flag",
    "Primary Opportunity Theme(s)": "opportunity_theme",
    "Recent Trigger Events": "trigger_event",
    "AI Use Cases (Tags)": "ai_use_case",
    "Primary Pain Areas": "pain_area",
    "Opportunity Areas (High Value)": "opportunity_area",
    "Strategic Signals (Recent)": "strategic_signal",
}


# ── Airtable API helpers ─────────────────────────────────────────────

def at_headers():
    return {"Authorization": f"Bearer {AT_TOKEN}", "Content-Type": "application/json"}


def at_list_all(table_id, fields=None):
    """Fetch all records from an Airtable table, handling pagination."""
    records = []
    params = {"pageSize": "100"}
    if fields:
        params["fields[]"] = fields
    offset = None
    while True:
        url = f"{AT_BASE}/{table_id}"
        p = dict(params)
        if offset:
            p["offset"] = offset
        resp = requests.get(url, headers=at_headers(), params=p)
        if resp.status_code == 429:
            time.sleep(1.5)
            continue
        resp.raise_for_status()
        data = resp.json()
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
        time.sleep(0.25)
    return records


def safe_enum(mapping, value):
    """Map Airtable display value to PG enum, return None if unmapped."""
    if not value:
        return None
    result = mapping.get(value)
    if result is None and value.strip():
        print(f"  WARNING: unmapped enum value '{value}'")
    return result


def first_link(fields, key):
    """Get first record ID from a link field array."""
    links = fields.get(key) or []
    return links[0] if links else None


# ── Migration functions ──────────────────────────────────────────────

def get_tenant_id(cur):
    cur.execute("SELECT id FROM tenants WHERE slug = 'visionvolve'")
    row = cur.fetchone()
    if not row:
        print("ERROR: tenant 'visionvolve' not found. Run migration 003 first.")
        sys.exit(1)
    return row[0]


def migrate_owners(cur, tenant_id):
    print("\n=== Migrating Owners ===")
    records = at_list_all(OWNERS_TABLE)
    print(f"  Found {len(records)} owner records")

    for r in records:
        f = r["fields"]
        cur.execute("""
            INSERT INTO owners (tenant_id, name, email, linkedin_profile_url,
                signature_block, lemlist_configured, lemlist_default_campaign,
                default_tone, default_language, airtable_record_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (airtable_record_id) WHERE airtable_record_id IS NOT NULL
            DO UPDATE SET
                name = EXCLUDED.name,
                email = EXCLUDED.email,
                linkedin_profile_url = EXCLUDED.linkedin_profile_url,
                signature_block = EXCLUDED.signature_block,
                lemlist_configured = EXCLUDED.lemlist_configured,
                lemlist_default_campaign = EXCLUDED.lemlist_default_campaign,
                default_tone = EXCLUDED.default_tone,
                default_language = EXCLUDED.default_language
        """, (
            tenant_id,
            f.get("Name", ""),
            f.get("Email"),
            f.get("linkedin_profile_url"),
            f.get("signature_block"),
            bool(f.get("lemlist_configured")),
            f.get("lemlist_default_campaign"),
            safe_enum(TONE_MAP, f.get("default_tone")),
            safe_enum(LANGUAGE_MAP, f.get("default_language")),
            r["id"],
        ))
    print(f"  Upserted {len(records)} owners")


def migrate_batches(cur, tenant_id, company_records, contact_records):
    print("\n=== Migrating Batches ===")
    batch_names = set()

    # From companies batch_name field
    for r in company_records:
        bn = r["fields"].get("batch_name")
        if bn:
            batch_names.add(bn)

    # From contacts batch_name field (multiselect)
    for r in contact_records:
        bns = r["fields"].get("batch_name") or []
        for bn in bns:
            batch_names.add(bn)

    print(f"  Found {len(batch_names)} unique batch names")
    for name in sorted(batch_names):
        cur.execute("""
            INSERT INTO batches (tenant_id, name)
            VALUES (%s, %s)
            ON CONFLICT (tenant_id, name) DO NOTHING
        """, (tenant_id, name))
    print(f"  Upserted {len(batch_names)} batches")


def build_lookup(cur, table, key_col="airtable_record_id"):
    """Build airtable_record_id → uuid lookup for FK resolution."""
    cur.execute(f"SELECT {key_col}, id FROM {table} WHERE {key_col} IS NOT NULL")
    return {row[0]: row[1] for row in cur.fetchall()}


def build_batch_lookup(cur, tenant_id):
    """Build batch_name → uuid lookup."""
    cur.execute("SELECT name, id FROM batches WHERE tenant_id = %s", (tenant_id,))
    return {row[0]: row[1] for row in cur.fetchall()}


def migrate_companies(cur, tenant_id, records):
    print("\n=== Migrating Companies ===")
    print(f"  Found {len(records)} company records")

    owner_lookup = build_lookup(cur, "owners")
    batch_lookup = build_batch_lookup(cur, tenant_id)

    for r in records:
        f = r["fields"]

        # Resolve FKs
        owner_at = first_link(f, "Account Owner Link")
        owner_id = owner_lookup.get(owner_at) if owner_at else None
        batch_name = f.get("batch_name")
        batch_id = batch_lookup.get(batch_name) if batch_name else None

        cur.execute("""
            INSERT INTO companies (
                tenant_id, name, domain, batch_id, owner_id,
                status, tier, business_model, company_size, ownership_type,
                geo_region, industry, industry_category, revenue_range,
                buying_stage, engagement_status, crm_status,
                ai_adoption, news_confidence, business_type, cohort,
                summary, hq_city, hq_country, triage_notes, triage_score,
                verified_revenue_eur_m, verified_employees,
                enrichment_cost_usd, pre_score, batch_number,
                lemlist_synced, error_message, notes,
                airtable_record_id
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s
            )
            ON CONFLICT (airtable_record_id) WHERE airtable_record_id IS NOT NULL
            DO UPDATE SET
                name = EXCLUDED.name, domain = EXCLUDED.domain,
                batch_id = EXCLUDED.batch_id, owner_id = EXCLUDED.owner_id,
                status = EXCLUDED.status, tier = EXCLUDED.tier,
                business_model = EXCLUDED.business_model,
                company_size = EXCLUDED.company_size,
                ownership_type = EXCLUDED.ownership_type,
                geo_region = EXCLUDED.geo_region,
                industry = EXCLUDED.industry,
                industry_category = EXCLUDED.industry_category,
                revenue_range = EXCLUDED.revenue_range,
                buying_stage = EXCLUDED.buying_stage,
                engagement_status = EXCLUDED.engagement_status,
                crm_status = EXCLUDED.crm_status,
                ai_adoption = EXCLUDED.ai_adoption,
                news_confidence = EXCLUDED.news_confidence,
                business_type = EXCLUDED.business_type,
                cohort = EXCLUDED.cohort,
                summary = EXCLUDED.summary,
                hq_city = EXCLUDED.hq_city,
                hq_country = EXCLUDED.hq_country,
                triage_notes = EXCLUDED.triage_notes,
                triage_score = EXCLUDED.triage_score,
                verified_revenue_eur_m = EXCLUDED.verified_revenue_eur_m,
                verified_employees = EXCLUDED.verified_employees,
                enrichment_cost_usd = EXCLUDED.enrichment_cost_usd,
                pre_score = EXCLUDED.pre_score,
                batch_number = EXCLUDED.batch_number,
                lemlist_synced = EXCLUDED.lemlist_synced,
                error_message = EXCLUDED.error_message,
                notes = EXCLUDED.notes
        """, (
            tenant_id,
            f.get("Company", ""),
            f.get("Domain"),
            batch_id, owner_id,
            safe_enum(COMPANY_STATUS_MAP, f.get("Status")),
            safe_enum(TIER_MAP, f.get("Tier")),
            safe_enum(BUSINESS_MODEL_MAP, f.get("Business Model")),
            safe_enum(COMPANY_SIZE_MAP, f.get("Company Size")),
            safe_enum(OWNERSHIP_TYPE_MAP, f.get("Ownership Type")),
            safe_enum(GEO_REGION_MAP, f.get("Region / Geo Cluster")),
            safe_enum(INDUSTRY_MAP, f.get("Industry (Enum)")),
            f.get("Industry_category"),
            safe_enum(REVENUE_MAP, f.get("Revenue")),
            safe_enum(BUYING_STAGE_MAP, f.get("Buying Stage / Engagement Stage")),
            safe_enum(ENGAGEMENT_STATUS_MAP, f.get("Engagement Status")),
            safe_enum(CRM_STATUS_MAP, f.get("CRM Status")),
            safe_enum(CONFIDENCE_MAP, f.get("Industry GenAI Adoption")),
            safe_enum(CONFIDENCE_MAP, f.get("News Confidence")),
            safe_enum(BUSINESS_TYPE_MAP, f.get("Business Type")),
            safe_enum(COHORT_MAP, f.get("Cohort")),
            f.get("Company Summary"),
            f.get("HQ City"),
            f.get("HQ Country"),
            f.get("Triage Notes"),
            f.get("Triage Score"),
            f.get("Verified Revenue (€M)"),
            f.get("Verified Employees"),
            f.get("Enrichment Cost (USD)"),
            f.get("Pre-score"),
            f.get("Batch number"),
            bool(f.get("lemlist")),
            f.get("Error message"),
            f.get("Notes"),
            r["id"],
        ))

    print(f"  Upserted {len(records)} companies")

    # Enrichment L2 data
    print("  Migrating company_enrichment_l2...")
    company_lookup = build_lookup(cur, "companies")
    l2_count = 0
    for r in records:
        f = r["fields"]
        company_id = company_lookup.get(r["id"])
        if not company_id:
            continue
        # Check if any L2 fields are populated
        l2_fields = ["company_intel", "Recent News", "AI Opportunities",
                     "Pain Hypothesis", "Relevant Case Study"]
        if not any(f.get(k) for k in l2_fields):
            continue

        quick_wins = f.get("Quick Wins (JSON)")
        qw_json = None
        if quick_wins:
            try:
                qw_json = json.dumps(json.loads(quick_wins))
            except (json.JSONDecodeError, TypeError):
                qw_json = json.dumps(quick_wins)

        cur.execute("""
            INSERT INTO company_enrichment_l2 (
                company_id, company_intel, recent_news, ai_opportunities,
                pain_hypothesis, relevant_case_study, digital_initiatives,
                leadership_changes, hiring_signals, key_products,
                customer_segments, competitors, tech_stack, funding_history,
                eu_grants, leadership_team, ai_hiring, tech_partnerships,
                certifications, quick_wins, industry_pain_points,
                cross_functional_pain, adoption_barriers, competitor_ai_moves
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (company_id) DO UPDATE SET
                company_intel = EXCLUDED.company_intel,
                recent_news = EXCLUDED.recent_news,
                ai_opportunities = EXCLUDED.ai_opportunities,
                pain_hypothesis = EXCLUDED.pain_hypothesis,
                relevant_case_study = EXCLUDED.relevant_case_study,
                digital_initiatives = EXCLUDED.digital_initiatives,
                leadership_changes = EXCLUDED.leadership_changes,
                hiring_signals = EXCLUDED.hiring_signals,
                key_products = EXCLUDED.key_products,
                customer_segments = EXCLUDED.customer_segments,
                competitors = EXCLUDED.competitors,
                tech_stack = EXCLUDED.tech_stack,
                funding_history = EXCLUDED.funding_history,
                eu_grants = EXCLUDED.eu_grants,
                leadership_team = EXCLUDED.leadership_team,
                ai_hiring = EXCLUDED.ai_hiring,
                tech_partnerships = EXCLUDED.tech_partnerships,
                certifications = EXCLUDED.certifications,
                quick_wins = EXCLUDED.quick_wins,
                industry_pain_points = EXCLUDED.industry_pain_points,
                cross_functional_pain = EXCLUDED.cross_functional_pain,
                adoption_barriers = EXCLUDED.adoption_barriers,
                competitor_ai_moves = EXCLUDED.competitor_ai_moves
        """, (
            company_id,
            f.get("company_intel"),
            f.get("Recent News"),
            f.get("AI Opportunities"),
            f.get("Pain Hypothesis"),
            f.get("Relevant Case Study"),
            f.get("Digital Initiatives"),
            f.get("Leadership Changes"),
            f.get("Hiring Signals"),
            f.get("Key Products"),
            f.get("Customer Segments"),
            f.get("Competitors"),
            f.get("Tech Stack"),
            f.get("Funding History"),
            f.get("EU Grants"),
            f.get("Leadership Team"),
            f.get("AI Hiring"),
            f.get("Tech Partnerships"),
            f.get("Certifications"),
            qw_json,
            f.get("Industry Pain Points (AI)"),
            f.get("Cross-Functional Pain Points"),
            f.get("Adoption Barriers"),
            f.get("Competitor AI Moves"),
        ))
        l2_count += 1
    print(f"  Upserted {l2_count} company_enrichment_l2 rows")

    # Company tags (multi-select fields)
    print("  Migrating company_tags...")
    tag_count = 0
    for r in records:
        f = r["fields"]
        company_id = company_lookup.get(r["id"])
        if not company_id:
            continue
        for at_field, pg_category in TAG_FIELDS.items():
            values = f.get(at_field) or []
            for val in values:
                cur.execute("""
                    INSERT INTO company_tags (company_id, category, value)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (company_id, category, value) DO NOTHING
                """, (company_id, pg_category, val))
                tag_count += 1
    print(f"  Upserted {tag_count} company_tags")


def migrate_contacts(cur, tenant_id, records):
    print("\n=== Migrating Contacts ===")
    print(f"  Found {len(records)} contact records")

    company_lookup = build_lookup(cur, "companies")
    owner_lookup = build_lookup(cur, "owners")
    batch_lookup = build_batch_lookup(cur, tenant_id)

    for r in records:
        f = r["fields"]

        # Resolve FKs
        company_at = first_link(f, "Company")
        company_id = company_lookup.get(company_at) if company_at else None
        owner_at = first_link(f, "Owner")
        owner_id = owner_lookup.get(owner_at) if owner_at else None
        batch_names = f.get("batch_name") or []
        batch_name = batch_names[0] if batch_names else None
        batch_id = batch_lookup.get(batch_name) if batch_name else None

        cur.execute("""
            INSERT INTO contacts (
                tenant_id, company_id, owner_id, batch_id,
                full_name, job_title, email_address, linkedin_url,
                phone_number,
                seniority_level, department, location_city, location_country,
                icp_fit, relationship_status, contact_source, language,
                message_status,
                ai_champion, ai_champion_score, authority_score, contact_score,
                enrichment_cost_usd, processed_enrich, email_lookup,
                duplicity_check, duplicity_conflict, duplicity_detail,
                notes, error,
                airtable_record_id
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s
            )
            ON CONFLICT (airtable_record_id) WHERE airtable_record_id IS NOT NULL
            DO UPDATE SET
                company_id = EXCLUDED.company_id,
                owner_id = EXCLUDED.owner_id,
                batch_id = EXCLUDED.batch_id,
                full_name = EXCLUDED.full_name,
                job_title = EXCLUDED.job_title,
                email_address = EXCLUDED.email_address,
                linkedin_url = EXCLUDED.linkedin_url,
                phone_number = EXCLUDED.phone_number,
                seniority_level = EXCLUDED.seniority_level,
                department = EXCLUDED.department,
                location_city = EXCLUDED.location_city,
                location_country = EXCLUDED.location_country,
                icp_fit = EXCLUDED.icp_fit,
                relationship_status = EXCLUDED.relationship_status,
                contact_source = EXCLUDED.contact_source,
                language = EXCLUDED.language,
                message_status = EXCLUDED.message_status,
                ai_champion = EXCLUDED.ai_champion,
                ai_champion_score = EXCLUDED.ai_champion_score,
                authority_score = EXCLUDED.authority_score,
                contact_score = EXCLUDED.contact_score,
                enrichment_cost_usd = EXCLUDED.enrichment_cost_usd,
                processed_enrich = EXCLUDED.processed_enrich,
                email_lookup = EXCLUDED.email_lookup,
                duplicity_check = EXCLUDED.duplicity_check,
                duplicity_conflict = EXCLUDED.duplicity_conflict,
                duplicity_detail = EXCLUDED.duplicity_detail,
                notes = EXCLUDED.notes,
                error = EXCLUDED.error
        """, (
            tenant_id, company_id, owner_id, batch_id,
            f.get("Full Name", ""),
            f.get("Job Title"),
            f.get("Email Address"),
            f.get("LinkedIn URL"),
            f.get("Phone Number"),
            safe_enum(SENIORITY_MAP, f.get("Seniority Level")),
            safe_enum(DEPARTMENT_MAP, f.get("Department")),
            f.get("Location City"),
            f.get("Location Country"),
            safe_enum(ICP_FIT_MAP, f.get("ICP Fit")),
            safe_enum(RELATIONSHIP_MAP, f.get("Relationship Status")),
            safe_enum(CONTACT_SOURCE_MAP, f.get("Contact Source")),
            safe_enum(LANGUAGE_MAP, f.get("language")),
            safe_enum(CONTACT_MSG_STATUS_MAP, f.get("message_status")),
            bool(f.get("AI Champion")),
            f.get("AI Champion Score"),
            f.get("Authority Score"),
            f.get("Contact Score"),
            f.get("Enrichment Cost"),
            bool(f.get("processed_enrich")),
            bool(f.get("email_lookup")),
            bool(f.get("duplicity_check")),
            bool(f.get("duplicity_conflict")),
            f.get("duplicity_detail"),
            f.get("Notes"),
            f.get("error"),
            r["id"],
        ))

    print(f"  Upserted {len(records)} contacts")

    # Contact enrichment (Person Summary, LinkedIn Profile Summary)
    print("  Migrating contact_enrichment...")
    contact_lookup = build_lookup(cur, "contacts")
    enrich_count = 0
    for r in records:
        f = r["fields"]
        contact_id = contact_lookup.get(r["id"])
        if not contact_id:
            continue
        if not f.get("Person Summary") and not f.get("LinkedIn Profile Summary"):
            continue
        cur.execute("""
            INSERT INTO contact_enrichment (contact_id, person_summary, linkedin_profile_summary)
            VALUES (%s, %s, %s)
            ON CONFLICT (contact_id) DO UPDATE SET
                person_summary = EXCLUDED.person_summary,
                linkedin_profile_summary = EXCLUDED.linkedin_profile_summary
        """, (contact_id, f.get("Person Summary"), f.get("LinkedIn Profile Summary")))
        enrich_count += 1
    print(f"  Upserted {enrich_count} contact_enrichment rows")


def migrate_messages(cur, tenant_id, records):
    print("\n=== Migrating Messages ===")
    print(f"  Found {len(records)} message records")

    if not records:
        print("  No messages to migrate")
        return

    contact_lookup = build_lookup(cur, "contacts")
    owner_lookup = build_lookup(cur, "owners")
    batch_lookup = build_batch_lookup(cur, tenant_id)

    for r in records:
        f = r["fields"]

        contact_at = first_link(f, "Contact")
        contact_id = contact_lookup.get(contact_at) if contact_at else None
        if not contact_id:
            print(f"  WARNING: skipping message {r['id']} - contact not found")
            continue

        owner_at = first_link(f, "Owner")
        owner_id = owner_lookup.get(owner_at) if owner_at else None
        batch_name = f.get("batch_name")
        batch_id = batch_lookup.get(batch_name) if batch_name else None

        cur.execute("""
            INSERT INTO messages (
                tenant_id, contact_id, owner_id, batch_id,
                label, channel, sequence_step, variant,
                subject, body, status, tone, language,
                generation_cost_usd, approved_at, sent_at,
                review_notes, airtable_record_id
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s
            )
            ON CONFLICT (airtable_record_id) WHERE airtable_record_id IS NOT NULL
            DO UPDATE SET
                contact_id = EXCLUDED.contact_id,
                owner_id = EXCLUDED.owner_id,
                batch_id = EXCLUDED.batch_id,
                label = EXCLUDED.label,
                channel = EXCLUDED.channel,
                sequence_step = EXCLUDED.sequence_step,
                variant = EXCLUDED.variant,
                subject = EXCLUDED.subject,
                body = EXCLUDED.body,
                status = EXCLUDED.status,
                tone = EXCLUDED.tone,
                language = EXCLUDED.language,
                generation_cost_usd = EXCLUDED.generation_cost_usd,
                approved_at = EXCLUDED.approved_at,
                sent_at = EXCLUDED.sent_at,
                review_notes = EXCLUDED.review_notes
        """, (
            tenant_id, contact_id, owner_id, batch_id,
            f.get("label"),
            f.get("channel"),
            f.get("sequence_step", 1),
            safe_enum(VARIANT_MAP, f.get("variant")),
            f.get("subject"),
            f.get("body", ""),
            safe_enum(MESSAGE_STATUS_MAP, f.get("status")),
            safe_enum(TONE_MAP, f.get("tone")),
            safe_enum(LANGUAGE_MAP, f.get("language")),
            f.get("generation_cost"),
            f.get("approved_at"),
            f.get("sent_at"),
            f.get("review_notes"),
            r["id"],
        ))

    print(f"  Upserted {len(records)} messages")


# ── Main ─────────────────────────────────────────────────────────────

def main():
    print("Airtable → PostgreSQL Migration")
    print("=" * 50)

    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        tenant_id = get_tenant_id(cur)
        print(f"Tenant ID: {tenant_id}")

        # Pre-fetch Airtable data (companies + contacts needed for batch extraction)
        print("\nFetching Airtable data...")
        company_records = at_list_all(COMPANIES_TABLE)
        print(f"  Companies: {len(company_records)}")
        contact_records = at_list_all(CONTACTS_TABLE)
        print(f"  Contacts: {len(contact_records)}")
        message_records = at_list_all(MESSAGES_TABLE)
        print(f"  Messages: {len(message_records)}")

        # Migrate in FK dependency order
        migrate_owners(cur, tenant_id)
        migrate_batches(cur, tenant_id, company_records, contact_records)
        migrate_companies(cur, tenant_id, company_records)
        migrate_contacts(cur, tenant_id, contact_records)
        migrate_messages(cur, tenant_id, message_records)

        conn.commit()
        print("\n" + "=" * 50)
        print("Migration completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
