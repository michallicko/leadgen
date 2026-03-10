"""Tests for BL-168: Closed-Loop Strategy Refinement from Enrichment Data."""

import json

import pytest

from api.models import (  # noqa: F811
    Company,
    CompanyEnrichmentL1,
    CompanyEnrichmentL2,
    CompanyEnrichmentOpportunity,
    CompanyEnrichmentProfile,
    StrategyDocument,
)
from api.services.strategy_refinement_tools import (
    _collect_enrichment_insights,
    _compare_with_strategy,
    analyze_enrichment_insights,
)
from api.services.tool_registry import ToolContext


@pytest.fixture
def seed_enrichment_data(db, seed_tenant):
    """Create companies with enrichment data for strategy refinement testing."""
    tenant_id = seed_tenant.id

    # Create strategy document
    doc = StrategyDocument(
        tenant_id=tenant_id,
        content="## Ideal Customer Profile (ICP)\nTargeting SaaS companies.",
        extracted_data=json.dumps({
            "icp": {
                "industries": ["software_saas"],
                "company_size": {"min": 50, "max": 500},
            },
            "personas": [
                {"title": "CTO", "pain_points": ["legacy systems"]},
            ],
        }),
        status="draft",
        phase="strategy",
    )
    db.session.add(doc)

    # Create companies with enrichment
    companies = []
    for i, (name, industry) in enumerate([
        ("Acme SaaS", "software_saas"),
        ("Beta Manufacturing", "manufacturing"),
        ("Gamma Healthcare", "healthcare"),
    ]):
        c = Company(
            tenant_id=tenant_id,
            name=name,
            domain="{}.com".format(name.lower().replace(" ", "")),
            status="enriched_l2",
            industry=industry,
        )
        db.session.add(c)
        companies.append(c)
    db.session.flush()

    # L1 enrichment for all
    for c in companies:
        l1 = CompanyEnrichmentL1(
            company_id=c.id,
            triage_notes="Good fit",
            pre_score=8.0,
        )
        db.session.add(l1)

    # L2 enrichment for all
    l2_data = [
        {
            "competitors": "Competitor A, Competitor B",
            "ai_opportunities": "Process automation, Chatbot deployment",
            "pain_hypothesis": "Manual data entry causing bottlenecks",
            "tech_stack": "AWS, Python, React",
            "hiring_signals": "Hiring 3 ML engineers",
        },
        {
            "competitors": "Competitor C, Competitor D",
            "ai_opportunities": "Quality control AI, Predictive maintenance",
            "pain_hypothesis": "Supply chain visibility gaps",
            "tech_stack": "Azure, Java, Angular",
            "hiring_signals": "Hiring data scientists",
        },
        {
            "competitors": "Competitor E",
            "ai_opportunities": "Patient triage AI",
            "pain_hypothesis": "Staff shortage and burnout",
            "tech_stack": "GCP, Python",
            "hiring_signals": "Hiring IT director",
        },
    ]
    for c, data in zip(companies, l2_data):
        l2 = CompanyEnrichmentL2(company_id=c.id, **data)
        db.session.add(l2)

    # Profile data
    for c in companies:
        profile = CompanyEnrichmentProfile(
            company_id=c.id,
            customer_segments="Enterprise B2B",
        )
        db.session.add(profile)

    # Opportunity data
    for c in companies:
        opp = CompanyEnrichmentOpportunity(
            company_id=c.id,
            industry_pain_points="Digital transformation pressure",
            ai_opportunities="Workflow automation",
        )
        db.session.add(opp)

    db.session.commit()
    return {"tenant": seed_tenant, "companies": companies, "doc": doc}


class TestCollectEnrichmentInsights:
    def test_returns_empty_when_no_enrichment(self, db, seed_tenant):
        result = _collect_enrichment_insights(str(seed_tenant.id))
        assert result["company_count"] == 0

    def test_collects_industry_distribution(self, db, seed_enrichment_data):
        tenant_id = str(seed_enrichment_data["tenant"].id)
        result = _collect_enrichment_insights(tenant_id)

        assert result["company_count"] == 3
        assert "software_saas" in result["industries"]
        assert "manufacturing" in result["industries"]
        assert "healthcare" in result["industries"]

    def test_collects_competitor_data(self, db, seed_enrichment_data):
        tenant_id = str(seed_enrichment_data["tenant"].id)
        result = _collect_enrichment_insights(tenant_id)

        assert len(result["competitors"]) > 0
        assert any("Competitor" in c for c in result["competitors"])

    def test_collects_ai_opportunities(self, db, seed_enrichment_data):
        tenant_id = str(seed_enrichment_data["tenant"].id)
        result = _collect_enrichment_insights(tenant_id)

        assert len(result["ai_opportunities"]) > 0

    def test_collects_pain_points(self, db, seed_enrichment_data):
        tenant_id = str(seed_enrichment_data["tenant"].id)
        result = _collect_enrichment_insights(tenant_id)

        assert len(result["pain_points"]) > 0

    def test_collects_hiring_signals(self, db, seed_enrichment_data):
        tenant_id = str(seed_enrichment_data["tenant"].id)
        result = _collect_enrichment_insights(tenant_id)

        assert len(result["hiring_signals"]) > 0


class TestCompareWithStrategy:
    def test_finds_new_industries(self):
        insights = {
            "industries": {"software_saas": 2, "manufacturing": 1, "healthcare": 1},
            "competitors": ["Comp A"],
            "ai_opportunities": ["AI1", "AI2", "AI3"],
            "pain_points": ["Pain1", "Pain2"],
            "hiring_signals": ["H1", "H2", "H3"],
            "digital_initiatives": ["D1", "D2"],
        }
        extracted = {
            "icp": {"industries": ["software_saas"]},
        }

        refinements = _compare_with_strategy(insights, extracted)

        # Should suggest ICP update for new industries
        icp_refinements = [r for r in refinements if r["section"] == "Ideal Customer Profile (ICP)"]
        assert len(icp_refinements) == 1
        assert "manufacturing" in icp_refinements[0]["finding"] or "healthcare" in icp_refinements[0]["finding"]

    def test_suggests_competitive_positioning_update(self):
        insights = {
            "industries": {},
            "competitors": ["Comp A", "Comp B"],
            "ai_opportunities": [],
            "pain_points": [],
            "hiring_signals": [],
            "digital_initiatives": [],
        }
        extracted = {}  # No competitors in strategy

        refinements = _compare_with_strategy(insights, extracted)

        competitive = [r for r in refinements if r["section"] == "Competitive Positioning"]
        assert len(competitive) == 1

    def test_suggests_messaging_update_with_ai_patterns(self):
        insights = {
            "industries": {},
            "competitors": [],
            "ai_opportunities": ["AI1", "AI2", "AI3"],
            "pain_points": [],
            "hiring_signals": [],
            "digital_initiatives": [],
        }
        extracted = {"icp": {}}

        refinements = _compare_with_strategy(insights, extracted)

        messaging = [r for r in refinements if r["section"] == "Value Proposition & Messaging"]
        assert len(messaging) == 1


class TestAnalyzeEnrichmentInsightsTool:
    def test_returns_no_data_when_no_enrichment(self, db, seed_tenant):
        # Create strategy doc
        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            content="Strategy content",
            extracted_data=json.dumps({"icp": {"industries": ["tech"]}}),
        )
        db.session.add(doc)
        db.session.commit()

        ctx = ToolContext(tenant_id=str(seed_tenant.id))
        result = analyze_enrichment_insights({}, ctx)

        assert result["status"] == "no_data"
        assert result["company_count"] == 0

    def test_returns_insights_with_enrichment_data(self, db, seed_enrichment_data):
        tenant_id = str(seed_enrichment_data["tenant"].id)
        ctx = ToolContext(tenant_id=tenant_id)
        result = analyze_enrichment_insights({}, ctx)

        assert result["status"] == "ok"
        assert result["insights_summary"]["companies_analyzed"] == 3
        assert len(result["suggested_refinements"]) > 0
        assert "raw_insights" in result

    def test_returns_error_without_strategy(self, db, seed_tenant):
        ctx = ToolContext(tenant_id=str(seed_tenant.id))
        result = analyze_enrichment_insights({}, ctx)
        assert "error" in result
