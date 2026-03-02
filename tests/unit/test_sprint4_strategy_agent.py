"""Tests for BL-122: Proactive Strategy Agent.

Tests cover:
- Auto-format selection (build_seeded_template with challenge_type)
- track_assumption tool (CRUD on extracted_data.assumptions)
- check_readiness tool (various readiness scenarios)
- build_seeded_template with challenge_type parameter
"""

import json
import uuid

import pytest

from api.models import StrategyDocument, db
from api.services.playbook_service import (
    build_seeded_template,
    _build_challenge_section,
    PHASE_INSTRUCTIONS,
)
from api.services.strategy_tools import (
    track_assumption,
    check_readiness,
    STRATEGY_TOOLS,
)
from api.services.tool_registry import ToolContext


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tenant_and_doc(db, seed_tenant):
    """Create a strategy document for the test tenant."""
    doc = StrategyDocument(
        tenant_id=seed_tenant.id,
        content="# GTM Strategy\n\n## Executive Summary\n\nTest strategy.",
        status="draft",
        version=1,
        extracted_data={},
    )
    db.session.add(doc)
    db.session.commit()
    return seed_tenant, doc


@pytest.fixture
def tool_ctx(tenant_and_doc):
    """Create a ToolContext for the test tenant."""
    tenant, doc = tenant_and_doc
    return ToolContext(
        tenant_id=str(tenant.id),
        user_id=str(uuid.uuid4()),
        document_id=str(doc.id),
        turn_id=str(uuid.uuid4()),
    )


# ---------------------------------------------------------------------------
# Auto-format selection: _build_challenge_section
# ---------------------------------------------------------------------------


class TestBuildChallengeSection:
    """Tests for _build_challenge_section which selects adaptive template sections."""

    def test_new_market_entry_saas(self):
        heading, content = _build_challenge_section("new_market_entry", "software_saas")
        assert heading == "ICP Matrix & Channel Prioritization"
        assert "ARR Targets" in content
        assert "Channel Prioritization" in content

    def test_new_market_entry_services(self):
        heading, content = _build_challenge_section("new_market_entry", "consulting")
        assert heading == "Partnership & Referral Strategy"
        assert "Referral Strategy" in content
        assert "Partnership Model" in content

    def test_new_market_entry_ecommerce(self):
        heading, content = _build_challenge_section("new_market_entry", "ecommerce")
        assert heading == "Funnel Analysis & Seasonal Calendar"
        assert "Funnel Analysis" in content
        assert "Seasonal Calendar" in content

    def test_new_market_entry_generic(self):
        heading, content = _build_challenge_section("new_market_entry", "healthcare")
        assert heading == "Market Entry Framework"
        assert "Entry Strategy" in content

    def test_scaling_pipeline(self):
        heading, content = _build_challenge_section("scaling_pipeline", "technology")
        assert heading == "Pipeline Velocity Analysis"
        assert "Pipeline Velocity Formula" in content
        assert "Conversion Optimization" in content

    def test_reengaging_cold_leads(self):
        heading, content = _build_challenge_section(
            "reengaging_cold_leads", "financial_services"
        )
        assert heading == "Re-engagement Strategy"
        assert "Re-engagement Sequences" in content
        assert "Segment Analysis" in content

    def test_launching_new_product(self):
        heading, content = _build_challenge_section(
            "launching_new_product", "saas"
        )
        assert heading == "Launch Playbook"
        assert "Positioning Matrix" in content
        assert "Launch Phases" in content

    def test_unknown_challenge_type(self):
        heading, content = _build_challenge_section("other", "technology")
        assert heading is None
        assert content is None

    def test_none_challenge_type(self):
        heading, content = _build_challenge_section(None, "technology")
        assert heading is None
        assert content is None

    def test_none_industry(self):
        heading, content = _build_challenge_section("scaling_pipeline", None)
        assert heading == "Pipeline Velocity Analysis"
        assert content is not None


# ---------------------------------------------------------------------------
# build_seeded_template with challenge_type
# ---------------------------------------------------------------------------


class TestBuildSeededTemplateWithChallengeType:
    """Test that build_seeded_template generates correct adaptive sections."""

    def test_empty_template_with_scaling_pipeline(self):
        result = build_seeded_template(
            objective="Scale outbound", challenge_type="scaling_pipeline"
        )
        assert "## Pipeline Velocity Analysis" in result
        assert "Pipeline Velocity Formula" in result

    def test_empty_template_without_challenge_type(self):
        result = build_seeded_template(objective="Grow revenue")
        assert "Pipeline Velocity Analysis" not in result
        # Standard sections should still be present
        assert "## Executive Summary" in result
        assert "## 90-Day Action Plan" in result

    def test_enrichment_template_with_new_market_entry_saas(self):
        enrichment = {
            "company": {
                "name": "TestCo",
                "industry": "software_saas",
                "company_size": "100-500",
            },
        }
        result = build_seeded_template(
            objective="Enter DACH market",
            enrichment_data=enrichment,
            challenge_type="new_market_entry",
        )
        assert "## ICP Matrix & Channel Prioritization" in result
        assert "ARR Targets" in result
        assert "TestCo" in result

    def test_enrichment_template_with_reengaging(self):
        enrichment = {
            "company": {
                "name": "BigCorp",
                "industry": "financial_services",
            },
        }
        result = build_seeded_template(
            objective="Revive cold leads",
            enrichment_data=enrichment,
            challenge_type="reengaging_cold_leads",
        )
        assert "## Re-engagement Strategy" in result
        assert "Re-engagement Sequences" in result

    def test_enrichment_template_no_challenge(self):
        enrichment = {
            "company": {
                "name": "NoCo",
                "industry": "technology",
            },
        }
        result = build_seeded_template(
            objective="Test", enrichment_data=enrichment
        )
        # No adaptive section without challenge_type
        assert "Pipeline Velocity" not in result
        assert "Launch Playbook" not in result

    def test_standard_sections_always_present(self):
        result = build_seeded_template(
            objective="Test", challenge_type="launching_new_product"
        )
        assert "## Executive Summary" in result
        assert "## Ideal Customer Profile (ICP)" in result
        assert "## Buyer Personas" in result
        assert "## Value Proposition & Messaging" in result
        assert "## Competitive Positioning" in result
        assert "## Channel Strategy" in result
        assert "## Messaging Framework" in result
        assert "## Metrics & KPIs" in result
        assert "## 90-Day Action Plan" in result
        # Plus the adaptive section
        assert "## Launch Playbook" in result


# ---------------------------------------------------------------------------
# track_assumption tool
# ---------------------------------------------------------------------------


class TestTrackAssumption:
    """Test the track_assumption tool handler."""

    def test_create_new_assumption(self, app, tenant_and_doc, tool_ctx):
        with app.app_context():
            result = track_assumption(
                {
                    "assumption_id": "icp_mid_market",
                    "text": "Mid-market SaaS companies are the primary ICP",
                    "status": "open",
                    "source": "initial research",
                },
                tool_ctx,
            )
            assert result["success"] is True
            assert result["assumption_id"] == "icp_mid_market"
            assert result["total_assumptions"] == 1
            assert result["confidence_score"] == 0.0

    def test_validate_assumption(self, app, tenant_and_doc, tool_ctx):
        with app.app_context():
            # Create
            track_assumption(
                {
                    "assumption_id": "channel_linkedin",
                    "text": "LinkedIn is the best channel",
                    "status": "open",
                    "source": "research",
                },
                tool_ctx,
            )
            # Validate
            result = track_assumption(
                {
                    "assumption_id": "channel_linkedin",
                    "text": "LinkedIn is the best channel",
                    "status": "validated",
                    "source": "user confirmed",
                },
                tool_ctx,
            )
            assert result["success"] is True
            assert result["confidence_score"] == 1.0
            assert result["discovery_round"] >= 1

    def test_invalidate_assumption(self, app, tenant_and_doc, tool_ctx):
        with app.app_context():
            # Create two assumptions
            track_assumption(
                {
                    "assumption_id": "a1",
                    "text": "Assumption 1",
                    "status": "open",
                    "source": "",
                },
                tool_ctx,
            )
            track_assumption(
                {
                    "assumption_id": "a2",
                    "text": "Assumption 2",
                    "status": "open",
                    "source": "",
                },
                tool_ctx,
            )
            # Invalidate one
            result = track_assumption(
                {
                    "assumption_id": "a1",
                    "text": "Assumption 1",
                    "status": "invalidated",
                    "source": "user feedback",
                },
                tool_ctx,
            )
            assert result["confidence_score"] == 0.5  # 1 of 2 resolved
            assert result["total_assumptions"] == 2

    def test_update_existing_assumption(self, app, tenant_and_doc, tool_ctx):
        with app.app_context():
            track_assumption(
                {
                    "assumption_id": "a1",
                    "text": "Original text",
                    "status": "open",
                    "source": "",
                },
                tool_ctx,
            )
            result = track_assumption(
                {
                    "assumption_id": "a1",
                    "text": "Updated text",
                    "status": "validated",
                    "source": "user confirmed",
                },
                tool_ctx,
            )
            # Should still only have 1 assumption
            assert result["total_assumptions"] == 1
            assert result["confidence_score"] == 1.0

    def test_invalid_status(self, app, tenant_and_doc, tool_ctx):
        with app.app_context():
            result = track_assumption(
                {
                    "assumption_id": "a1",
                    "text": "Test",
                    "status": "maybe",
                    "source": "",
                },
                tool_ctx,
            )
            assert "error" in result

    def test_missing_required_fields(self, app, tenant_and_doc, tool_ctx):
        with app.app_context():
            result = track_assumption(
                {"assumption_id": "", "text": "", "status": "open"},
                tool_ctx,
            )
            assert "error" in result

    def test_no_document(self, app, db, seed_tenant):
        with app.app_context():
            ctx = ToolContext(
                tenant_id=str(uuid.uuid4()),  # Non-existent tenant
                user_id=str(uuid.uuid4()),
            )
            result = track_assumption(
                {
                    "assumption_id": "a1",
                    "text": "Test",
                    "status": "open",
                },
                ctx,
            )
            assert "error" in result


# ---------------------------------------------------------------------------
# check_readiness tool
# ---------------------------------------------------------------------------


class TestCheckReadiness:
    """Test the check_readiness tool handler."""

    def test_empty_doc_not_ready(self, app, tenant_and_doc, tool_ctx):
        with app.app_context():
            result = check_readiness({}, tool_ctx)
            assert result["ready"] is False
            assert result["score"] < 1.0
            assert len(result["gaps"]) > 0

    def test_fully_populated_is_ready(self, app, db, tenant_and_doc, tool_ctx):
        _, doc = tenant_and_doc
        doc.extracted_data = json.dumps({
            "icp": {
                "disqualifiers": ["Companies under 10 employees", "Non-tech"],
            },
            "personas": [
                {"title_patterns": ["CTO"], "pain_points": ["Scale"]},
                {"title_patterns": ["VP Eng"], "pain_points": ["Hiring"]},
            ],
            "messaging": {
                "angles": ["AI automation", "Cost reduction"],
            },
            "channels": {
                "primary": "LinkedIn",
            },
        })
        doc.content = (
            "# Strategy\n\n"
            "## Executive Summary\n\nTest.\n\n"
            "## Channel Strategy\n\n"
            "LinkedIn is our primary channel because our target personas "
            "are active there. Decision-makers in tech companies respond "
            "best to peer-to-peer outreach on professional networks. We "
            "will run a multi-touch sequence combining connection requests, "
            "content sharing, and direct messages.\n\n"
            "## Metrics & KPIs\n\nTest.\n"
        )
        db.session.commit()

        result = check_readiness({}, tool_ctx)
        assert result["ready"] is True
        assert result["score"] >= 0.7
        assert result["checks_passed"] == 4
        assert result["gaps"] == []

    def test_partial_readiness(self, app, tenant_and_doc, tool_ctx):
        with app.app_context():
            _, doc = tenant_and_doc
            doc.extracted_data = json.dumps({
                "icp": {
                    "disqualifiers": ["Too small"],
                },
                "personas": [
                    {"title_patterns": ["CTO"], "pain_points": ["Scale"]},
                ],
                "messaging": {},
                "channels": {},
            })
            db.session.commit()

            result = check_readiness({}, tool_ctx)
            assert result["ready"] is False
            assert result["checks_passed"] < 4
            assert len(result["gaps"]) >= 2

    def test_readiness_with_assumptions(self, app, db, tenant_and_doc, tool_ctx):
        _, doc = tenant_and_doc
        doc.extracted_data = json.dumps({
            "icp": {"disqualifiers": ["Non-tech"]},
            "personas": [
                {"title_patterns": ["CTO"]},
                {"title_patterns": ["VP Eng"]},
            ],
            "messaging": {"angles": ["AI automation"]},
            "channels": {"primary": "LinkedIn"},
            "assumptions": [
                {"id": "a1", "text": "T1", "status": "validated", "source": "user"},
                {"id": "a2", "text": "T2", "status": "validated", "source": "user"},
            ],
            "confidence_score": 1.0,
        })
        doc.content = (
            "# Strategy\n\n"
            "## Channel Strategy\n\n"
            "LinkedIn is primary because our ICP lives there. We validated "
            "this through user interviews and the channel has 3x better "
            "response rates than email for B2B SaaS decision-makers.\n\n"
        )
        db.session.commit()
        db.session.expire_all()

        result = check_readiness({}, tool_ctx)
        assert result["ready"] is True
        assert result["assumption_confidence"] == 1.0
        assert result["assumptions_tracked"] == 2

    def test_no_document(self, app, db, seed_tenant):
        with app.app_context():
            ctx = ToolContext(
                tenant_id=str(uuid.uuid4()),
                user_id=str(uuid.uuid4()),
            )
            result = check_readiness({}, ctx)
            assert "error" in result


# ---------------------------------------------------------------------------
# STRATEGY_TOOLS registration
# ---------------------------------------------------------------------------


class TestToolRegistration:
    """Verify new tools are in the STRATEGY_TOOLS list."""

    def test_track_assumption_in_tools(self):
        names = [t.name for t in STRATEGY_TOOLS]
        assert "track_assumption" in names

    def test_check_readiness_in_tools(self):
        names = [t.name for t in STRATEGY_TOOLS]
        assert "check_readiness" in names

    def test_track_assumption_schema(self):
        tool = next(t for t in STRATEGY_TOOLS if t.name == "track_assumption")
        props = tool.input_schema["properties"]
        assert "assumption_id" in props
        assert "text" in props
        assert "status" in props
        assert "source" in props
        assert tool.input_schema["required"] == [
            "assumption_id",
            "text",
            "status",
        ]

    def test_check_readiness_schema(self):
        tool = next(t for t in STRATEGY_TOOLS if t.name == "check_readiness")
        assert tool.input_schema["required"] == []


# ---------------------------------------------------------------------------
# PHASE_INSTRUCTIONS["strategy"] prompt content
# ---------------------------------------------------------------------------


class TestStrategyPhasePrompt:
    """Verify the rewritten strategy phase instructions contain key elements."""

    def test_proactive_behavior(self):
        prompt = PHASE_INSTRUCTIONS["strategy"]
        assert "web_search" in prompt
        assert "get_strategy_document" in prompt
        assert "Strategic Brief" in prompt

    def test_convergence_tracking_instructions(self):
        prompt = PHASE_INSTRUCTIONS["strategy"]
        assert "track_assumption" in prompt
        assert "CONVERGENCE TRACKING" in prompt

    def test_readiness_detection(self):
        prompt = PHASE_INSTRUCTIONS["strategy"]
        assert "check_readiness" in prompt
        assert "READINESS DETECTION" in prompt

    def test_challenge_type_format_selection(self):
        prompt = PHASE_INSTRUCTIONS["strategy"]
        assert "challenge type" in prompt.lower()
        assert "New market entry" in prompt
        assert "Scaling pipeline" in prompt
        assert "Re-engaging cold leads" in prompt
        assert "Launching new product" in prompt

    def test_first_message_instructions(self):
        prompt = PHASE_INSTRUCTIONS["strategy"]
        assert "FIRST MESSAGE BEHAVIOR" in prompt
        assert "What We're Working With" in prompt
        assert "Strategic Bets" in prompt
        assert "Open Questions" in prompt
