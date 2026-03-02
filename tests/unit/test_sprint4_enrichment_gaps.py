"""Tests for Sprint 4 enrichment gap tool: BL-120.

BL-120: get_enrichment_gaps chat tool — strategy-aware enrichment readiness.
Crosses ICP filters with entity_stage_completions to classify contacts by
enrichment status and generate recommendations.
"""

import json
import uuid

import pytest

from api.models import (
    Company,
    Contact,
    EntityStageCompletion,
    StrategyDocument,
)
from api.services.enrichment_gap_tools import (
    ENRICHMENT_TOOLS,
    STAGE_L1,
    STAGE_L2,
    STAGE_PERSON,
    _build_segments,
    _generate_recommendations,
    get_enrichment_gaps,
)
from api.services.tool_registry import ToolContext, register_tool


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def strategy_with_icp(db, seed_tenant):
    """Strategy document with full extracted ICP data."""
    extracted = {
        "icp": {
            "industries": ["software_saas", "it"],
            "geographies": ["Germany", "UK"],
        },
        "personas": [
            {"title": "CTO", "seniority": "c_level"},
            {"title": "VP Engineering", "seniority": "director"},
        ],
    }
    doc = StrategyDocument(
        tenant_id=seed_tenant.id,
        content="# Strategy\n\n## Executive Summary\n\nTest strategy.",
        extracted_data=json.dumps(extracted),
        status="draft",
        phase="strategy",
        version=1,
    )
    db.session.add(doc)
    db.session.commit()
    return doc


@pytest.fixture
def strategy_no_icp(db, seed_tenant):
    """Strategy document with no ICP data."""
    doc = StrategyDocument(
        tenant_id=seed_tenant.id,
        content="# Strategy\n\nEmpty.",
        extracted_data=json.dumps({}),
        status="draft",
        phase="strategy",
        version=1,
    )
    db.session.add(doc)
    db.session.commit()
    return doc


@pytest.fixture
def strategy_empty_extracted(db, seed_tenant):
    """Strategy document with empty string extracted_data."""
    doc = StrategyDocument(
        tenant_id=seed_tenant.id,
        content="# Strategy",
        extracted_data=None,
        status="draft",
        phase="strategy",
        version=1,
    )
    db.session.add(doc)
    db.session.commit()
    return doc


@pytest.fixture
def tool_ctx(seed_tenant, seed_super_admin):
    """ToolContext for handler tests."""
    return ToolContext(
        tenant_id=str(seed_tenant.id),
        user_id=str(seed_super_admin.id),
        turn_id=str(uuid.uuid4()),
    )


@pytest.fixture
def tag_for_enrichment(db, seed_tenant):
    """Tag for entity_stage_completions."""
    from api.models import Tag

    tag = Tag(tenant_id=seed_tenant.id, name="test-tag", is_active=True)
    db.session.add(tag)
    db.session.flush()
    return tag


@pytest.fixture
def enrichment_contacts(db, seed_tenant, tag_for_enrichment):
    """Create companies and contacts with various enrichment levels.

    Returns dict with companies, contacts, and their enrichment state descriptions.

    Layout:
    - co1 (software_saas, Germany): fully enriched (L1+L2 done)
      - ct1 (c_level): person enrichment done -> fully_enriched
      - ct2 (director): no person enrichment -> needs_person
    - co2 (it, UK): L1 only
      - ct3 (c_level): -> needs_l2
    - co3 (software_saas, Germany): no enrichment
      - ct4 (c_level): -> needs_l1
      - ct5 (director): -> needs_l1
    - co4 (retail, France): fully enriched but not matching ICP
      - ct6 (manager): should NOT appear in ICP-filtered results
    """
    tag = tag_for_enrichment

    # Companies
    co1 = Company(
        tenant_id=seed_tenant.id,
        name="SaaS Corp",
        domain="saas.com",
        status="enriched_l2",
        industry="software_saas",
        geo_region="Germany",
        company_size="100-500",
    )
    co2 = Company(
        tenant_id=seed_tenant.id,
        name="IT Solutions Ltd",
        domain="itsol.co.uk",
        status="triage_passed",
        industry="it",
        geo_region="UK",
        company_size="50-100",
    )
    co3 = Company(
        tenant_id=seed_tenant.id,
        name="SaaS Startup",
        domain="startup.de",
        status="new",
        industry="software_saas",
        geo_region="Germany",
        company_size="50-100",
    )
    co4 = Company(
        tenant_id=seed_tenant.id,
        name="Retail Shop",
        domain="shop.fr",
        status="enriched_l2",
        industry="retail",
        geo_region="France",
        company_size="10-50",
    )
    db.session.add_all([co1, co2, co3, co4])
    db.session.flush()

    # Contacts
    ct1 = Contact(
        tenant_id=seed_tenant.id,
        company_id=co1.id,
        first_name="Alice",
        last_name="CTO",
        seniority_level="c_level",
    )
    ct2 = Contact(
        tenant_id=seed_tenant.id,
        company_id=co1.id,
        first_name="Bob",
        last_name="VP",
        seniority_level="director",
    )
    ct3 = Contact(
        tenant_id=seed_tenant.id,
        company_id=co2.id,
        first_name="Charlie",
        last_name="CTO",
        seniority_level="c_level",
    )
    ct4 = Contact(
        tenant_id=seed_tenant.id,
        company_id=co3.id,
        first_name="Dave",
        last_name="CEO",
        seniority_level="c_level",
    )
    ct5 = Contact(
        tenant_id=seed_tenant.id,
        company_id=co3.id,
        first_name="Eve",
        last_name="Dir",
        seniority_level="director",
    )
    ct6 = Contact(
        tenant_id=seed_tenant.id,
        company_id=co4.id,
        first_name="Frank",
        last_name="Manager",
        seniority_level="manager",
    )
    db.session.add_all([ct1, ct2, ct3, ct4, ct5, ct6])
    db.session.flush()

    # Entity stage completions
    # co1: L1 + L2 completed (company-level)
    db.session.add(EntityStageCompletion(
        tenant_id=seed_tenant.id,
        tag_id=tag.id,
        entity_type="company",
        entity_id=co1.id,
        stage=STAGE_L1,
        status="completed",
    ))
    db.session.add(EntityStageCompletion(
        tenant_id=seed_tenant.id,
        tag_id=tag.id,
        entity_type="company",
        entity_id=co1.id,
        stage=STAGE_L2,
        status="completed",
    ))

    # ct1: person enrichment completed
    db.session.add(EntityStageCompletion(
        tenant_id=seed_tenant.id,
        tag_id=tag.id,
        entity_type="contact",
        entity_id=ct1.id,
        stage=STAGE_PERSON,
        status="completed",
    ))

    # co2: L1 only
    db.session.add(EntityStageCompletion(
        tenant_id=seed_tenant.id,
        tag_id=tag.id,
        entity_type="company",
        entity_id=co2.id,
        stage=STAGE_L1,
        status="completed",
    ))

    # co4: fully enriched (but retail/France — outside ICP)
    db.session.add(EntityStageCompletion(
        tenant_id=seed_tenant.id,
        tag_id=tag.id,
        entity_type="company",
        entity_id=co4.id,
        stage=STAGE_L1,
        status="completed",
    ))
    db.session.add(EntityStageCompletion(
        tenant_id=seed_tenant.id,
        tag_id=tag.id,
        entity_type="company",
        entity_id=co4.id,
        stage=STAGE_L2,
        status="completed",
    ))
    db.session.add(EntityStageCompletion(
        tenant_id=seed_tenant.id,
        tag_id=tag.id,
        entity_type="contact",
        entity_id=ct6.id,
        stage=STAGE_PERSON,
        status="completed",
    ))

    db.session.commit()

    return {
        "companies": [co1, co2, co3, co4],
        "contacts": [ct1, ct2, ct3, ct4, ct5, ct6],
        "tag": tag,
    }


# ===========================================================================
# Tool registration
# ===========================================================================


class TestToolRegistration:
    def test_enrichment_tools_has_one_tool(self):
        assert len(ENRICHMENT_TOOLS) == 1
        assert ENRICHMENT_TOOLS[0].name == "get_enrichment_gaps"

    def test_tool_appears_in_registry(self, app, db):
        """After app init, get_enrichment_gaps should be registered."""
        from api.services.tool_registry import get_tool, get_tools_for_api

        # Re-register since autouse fixture clears registry
        for t in ENRICHMENT_TOOLS:
            try:
                register_tool(t)
            except ValueError:
                pass

        tool = get_tool("get_enrichment_gaps")
        assert tool is not None
        assert tool.name == "get_enrichment_gaps"

        api_tools = get_tools_for_api()
        names = [t["name"] for t in api_tools]
        assert "get_enrichment_gaps" in names


# ===========================================================================
# Core handler tests
# ===========================================================================


class TestGetEnrichmentGaps:
    def test_returns_correct_summary(
        self, app, db, seed_tenant, strategy_with_icp, enrichment_contacts, tool_ctx
    ):
        """Verify enrichment classification for contacts matching ICP."""
        with app.app_context():
            result = get_enrichment_gaps({}, tool_ctx)

        assert "error" not in result
        assert result["total_matches"] == 5  # ct1-ct5 match ICP, ct6 does not

        s = result["enrichment_summary"]
        assert s["fully_enriched"] == 1  # ct1 (co1 L1+L2 + person)
        assert s["needs_person"] == 1  # ct2 (co1 L1+L2, no person)
        assert s["needs_l2"] == 1  # ct3 (co2 L1 only)
        assert s["needs_l1"] == 2  # ct4, ct5 (co3 no enrichment)

    def test_excludes_non_icp_contacts(
        self, app, db, seed_tenant, strategy_with_icp, enrichment_contacts, tool_ctx
    ):
        """Contacts outside ICP filters (retail/France) should not appear."""
        with app.app_context():
            result = get_enrichment_gaps({}, tool_ctx)

        # ct6 is retail/France/manager — not in ICP industries/geos/seniorities
        assert result["total_matches"] == 5

    def test_segments_by_default(
        self, app, db, seed_tenant, strategy_with_icp, enrichment_contacts, tool_ctx
    ):
        """Default group_by is ['industry', 'seniority_level']."""
        with app.app_context():
            result = get_enrichment_gaps({}, tool_ctx)

        assert "segments" in result
        segments = result["segments"]
        assert len(segments) > 0

        # Check that segments have the expected structure
        for seg in segments:
            assert "name" in seg
            assert "total" in seg
            assert "fully_enriched" in seg
            assert "gaps" in seg
            assert "needs_person" in seg["gaps"]
            assert "needs_l2" in seg["gaps"]
            assert "needs_l1" in seg["gaps"]

    def test_recommendations_present(
        self, app, db, seed_tenant, strategy_with_icp, enrichment_contacts, tool_ctx
    ):
        """Result should include recommendations."""
        with app.app_context():
            result = get_enrichment_gaps({}, tool_ctx)

        assert "recommendations" in result
        assert len(result["recommendations"]) > 0


# ===========================================================================
# Error / edge cases
# ===========================================================================


class TestEnrichmentGapsErrors:
    def test_no_strategy_document(self, app, db, seed_tenant, tool_ctx):
        """No strategy document returns error."""
        with app.app_context():
            result = get_enrichment_gaps({}, tool_ctx)

        assert "error" in result
        assert result["total_matches"] == 0

    def test_empty_icp(self, app, db, seed_tenant, strategy_no_icp, tool_ctx):
        """Strategy with no ICP data returns error."""
        with app.app_context():
            result = get_enrichment_gaps({}, tool_ctx)

        assert "error" in result
        assert "ICP" in result["error"]
        assert result["total_matches"] == 0

    def test_null_extracted_data(
        self, app, db, seed_tenant, strategy_empty_extracted, tool_ctx
    ):
        """Strategy with None extracted_data returns error."""
        with app.app_context():
            result = get_enrichment_gaps({}, tool_ctx)

        assert "error" in result
        assert result["total_matches"] == 0

    def test_icp_with_no_mappable_fields(self, app, db, seed_tenant, tool_ctx):
        """ICP with only unmappable fields (like triggers) returns error."""
        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            content="# Strategy",
            extracted_data=json.dumps({
                "icp": {
                    "triggers": ["hiring"],
                    "disqualifiers": ["bankrupt"],
                }
            }),
            status="draft",
            phase="strategy",
            version=1,
        )
        db.session.add(doc)
        db.session.commit()

        with app.app_context():
            result = get_enrichment_gaps({}, tool_ctx)

        assert "error" in result
        assert "no mappable" in result["error"].lower()


# ===========================================================================
# Filter overrides
# ===========================================================================


class TestEnrichmentGapsFilterOverrides:
    def test_override_narrows_results(
        self, app, db, seed_tenant, strategy_with_icp, enrichment_contacts, tool_ctx
    ):
        """Override filters to restrict to a single industry."""
        with app.app_context():
            result = get_enrichment_gaps(
                {"filters": {"industries": ["it"]}},
                tool_ctx,
            )

        # Only co2/ct3 matches "it" industry + ICP geo/seniority
        assert result["total_matches"] == 1
        assert result["enrichment_summary"]["needs_l2"] == 1

    def test_override_broadens_results(
        self, app, db, seed_tenant, strategy_with_icp, enrichment_contacts, tool_ctx
    ):
        """Override with broader geo to include France contacts."""
        with app.app_context():
            result = get_enrichment_gaps(
                {"filters": {"geo_regions": ["Germany", "UK", "France"]}},
                tool_ctx,
            )

        # Now ct6 (France/retail) might appear if industry also matches
        # But ct6's industry is "retail" and ICP industries override still
        # includes software_saas + it. So ct6 still excluded by industry.
        # The geo override just adds France to the allowed geos.
        assert result["total_matches"] >= 5


# ===========================================================================
# Segment grouping
# ===========================================================================


class TestEnrichmentGapsGrouping:
    def test_group_by_industry_only(
        self, app, db, seed_tenant, strategy_with_icp, enrichment_contacts, tool_ctx
    ):
        """Group by industry produces segments keyed by industry."""
        with app.app_context():
            result = get_enrichment_gaps(
                {"group_by": ["industry"]},
                tool_ctx,
            )

        segments = result["segments"]
        names = [s["name"] for s in segments]
        # Should have software_saas and it segments
        assert any("software_saas" in n for n in names)
        assert any("it" in n for n in names)

    def test_group_by_seniority_only(
        self, app, db, seed_tenant, strategy_with_icp, enrichment_contacts, tool_ctx
    ):
        """Group by seniority_level produces segments keyed by seniority."""
        with app.app_context():
            result = get_enrichment_gaps(
                {"group_by": ["seniority_level"]},
                tool_ctx,
            )

        segments = result["segments"]
        names = [s["name"] for s in segments]
        assert any("c_level" in n for n in names)
        assert any("director" in n for n in names)


# ===========================================================================
# Recommendations logic
# ===========================================================================


class TestRecommendations:
    def test_low_match_count(self):
        """When total < 10, suggest broadening ICP."""
        recs = _generate_recommendations(
            total=3,
            summary={"fully_enriched": 1, "needs_person": 1, "needs_l2": 1, "needs_l1": 0},
            segments=[],
        )
        assert any("broadening" in r.lower() for r in recs)

    def test_high_person_gap(self):
        """When >30% need person enrichment, recommend it."""
        recs = _generate_recommendations(
            total=10,
            summary={"fully_enriched": 2, "needs_person": 5, "needs_l2": 2, "needs_l1": 1},
            segments=[],
        )
        assert any("person enrichment" in r.lower() for r in recs)

    def test_high_l2_gap(self):
        """When >30% need L2, recommend deep research."""
        recs = _generate_recommendations(
            total=10,
            summary={"fully_enriched": 2, "needs_person": 1, "needs_l2": 5, "needs_l1": 2},
            segments=[],
        )
        assert any("l2" in r.lower() or "deep research" in r.lower() for r in recs)

    def test_high_l1_gap(self):
        """When >30% need L1, recommend starting enrichment."""
        recs = _generate_recommendations(
            total=10,
            summary={"fully_enriched": 1, "needs_person": 1, "needs_l2": 1, "needs_l1": 7},
            segments=[],
        )
        assert any("l1" in r.lower() for r in recs)

    def test_high_enrichment_congratulates(self):
        """When >=80% fully enriched, congratulate and suggest messaging."""
        recs = _generate_recommendations(
            total=10,
            summary={"fully_enriched": 9, "needs_person": 1, "needs_l2": 0, "needs_l1": 0},
            segments=[],
        )
        assert any("message generation" in r.lower() or "ready" in r.lower() for r in recs)

    def test_zero_matches(self):
        """When no contacts match, suggest broadening."""
        recs = _generate_recommendations(
            total=0,
            summary={"fully_enriched": 0, "needs_person": 0, "needs_l2": 0, "needs_l1": 0},
            segments=[],
        )
        assert any("broadening" in r.lower() or "no contacts" in r.lower() for r in recs)

    def test_segment_with_high_gaps(self):
        """Segments with >50% gaps should be called out."""
        segments = [
            {
                "name": "software_saas / c_level",
                "total": 5,
                "fully_enriched": 1,
                "gaps": {"needs_person": 2, "needs_l2": 1, "needs_l1": 1},
            }
        ]
        recs = _generate_recommendations(
            total=20,
            summary={"fully_enriched": 14, "needs_person": 3, "needs_l2": 2, "needs_l1": 1},
            segments=segments,
        )
        assert any("software_saas / c_level" in r for r in recs)


# ===========================================================================
# Build segments unit tests
# ===========================================================================


class TestBuildSegments:
    def test_groups_by_single_dimension(self):
        contacts = [
            {"industry": "saas", "seniority_level": "c_level", "category": "fully_enriched"},
            {"industry": "saas", "seniority_level": "director", "category": "needs_person"},
            {"industry": "it", "seniority_level": "c_level", "category": "needs_l1"},
        ]
        segments = _build_segments(contacts, ["industry"])
        assert len(segments) == 2
        saas_seg = next(s for s in segments if s["name"] == "saas")
        assert saas_seg["total"] == 2
        assert saas_seg["fully_enriched"] == 1
        assert saas_seg["gaps"]["needs_person"] == 1

    def test_groups_by_two_dimensions(self):
        contacts = [
            {"industry": "saas", "seniority_level": "c_level", "category": "fully_enriched"},
            {"industry": "saas", "seniority_level": "c_level", "category": "needs_l1"},
            {"industry": "saas", "seniority_level": "director", "category": "needs_person"},
        ]
        segments = _build_segments(contacts, ["industry", "seniority_level"])
        assert len(segments) == 2  # saas/c_level and saas/director
        clevel_seg = next(s for s in segments if "c_level" in s["name"])
        assert clevel_seg["total"] == 2

    def test_handles_missing_dimensions(self):
        contacts = [
            {"industry": None, "seniority_level": None, "category": "needs_l1"},
        ]
        segments = _build_segments(contacts, ["industry", "seniority_level"])
        assert len(segments) == 1
        assert segments[0]["name"] == "Unknown / Unknown"

    def test_sorted_by_total_descending(self):
        contacts = [
            {"industry": "it", "category": "needs_l1"},
            {"industry": "saas", "category": "needs_l1"},
            {"industry": "saas", "category": "needs_l2"},
            {"industry": "saas", "category": "fully_enriched"},
        ]
        segments = _build_segments(contacts, ["industry"])
        assert segments[0]["name"] == "saas"
        assert segments[0]["total"] == 3
        assert segments[1]["name"] == "it"
        assert segments[1]["total"] == 1
