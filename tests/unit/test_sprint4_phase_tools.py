"""Tests for Sprint 4 phase tools: BL-114, BL-116, BL-117.

BL-114: Auto-advance to Contacts phase after ICP extraction (frontend logic,
        tested here via the backend extract + phase endpoints).
BL-116: apply_icp_filters chat tool.
BL-117: Auto-populate campaign generation_config from strategy.
"""

import json
import uuid

import pytest

from api.models import Campaign, Company, Contact, StrategyDocument
from api.services.icp_filter_tools import (
    ICP_FILTER_TOOLS,
    _map_icp_to_filters,
    apply_icp_filters,
)
from api.services.campaign_tools import create_campaign
from api.services.tool_registry import ToolContext


def auth_header(client, email="admin@test.com", password="testpass123"):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    token = resp.get_json()["access_token"]
    return {"Authorization": "Bearer {}".format(token)}


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
            "company_size": {"min": 50, "max": 500},
            "tech_signals": ["cloud-native"],
            "triggers": ["hiring"],
            "disqualifiers": ["bankrupt"],
        },
        "personas": [
            {"title": "CTO", "seniority": "C-Level"},
            {"title": "VP Engineering", "seniority": "VP"},
        ],
        "messaging": {
            "tone": "professional-casual",
            "themes": ["innovation", "efficiency"],
        },
        "channels": {
            "primary": "linkedin",
            "secondary": "email",
            "cadence": "weekly",
        },
        "metrics": {
            "reply_rate_target": 5,
            "meeting_rate_target": 2,
        },
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
def tool_ctx(seed_tenant, seed_super_admin):
    """ToolContext for handler tests."""
    return ToolContext(
        tenant_id=str(seed_tenant.id),
        user_id=str(seed_super_admin.id),
        turn_id=str(uuid.uuid4()),
    )


@pytest.fixture
def contacts_for_filter(db, seed_tenant):
    """Create companies and contacts matching/not matching ICP filters."""
    # Companies
    co1 = Company(
        tenant_id=seed_tenant.id,
        name="SaaS Corp",
        domain="saas.com",
        status="new",
        industry="software_saas",
        geo_region="Germany",
        company_size="100-500",
    )
    co2 = Company(
        tenant_id=seed_tenant.id,
        name="IT Ltd",
        domain="it.co.uk",
        status="new",
        industry="it",
        geo_region="UK",
        company_size="50-100",
    )
    co3 = Company(
        tenant_id=seed_tenant.id,
        name="Retail Shop",
        domain="retail.fr",
        status="new",
        industry="retail",
        geo_region="France",
        company_size="10-50",
    )
    db.session.add_all([co1, co2, co3])
    db.session.flush()

    # Contacts
    ct1 = Contact(
        tenant_id=seed_tenant.id,
        company_id=co1.id,
        first_name="Alice",
        last_name="Tech",
        seniority_level="C-Level",
    )
    ct2 = Contact(
        tenant_id=seed_tenant.id,
        company_id=co2.id,
        first_name="Bob",
        last_name="Eng",
        seniority_level="VP",
    )
    ct3 = Contact(
        tenant_id=seed_tenant.id,
        company_id=co3.id,
        first_name="Charlie",
        last_name="Retail",
        seniority_level="Manager",
    )
    db.session.add_all([ct1, ct2, ct3])
    db.session.commit()
    return [ct1, ct2, ct3]


# ===========================================================================
# BL-116: _map_icp_to_filters unit tests
# ===========================================================================


class TestMapIcpToFilters:
    def test_maps_industries(self):
        icp = {"industries": ["saas", "fintech"]}
        result = _map_icp_to_filters(icp)
        assert result["industries"] == ["saas", "fintech"]

    def test_maps_geographies(self):
        icp = {"geographies": ["Germany", "UK"]}
        result = _map_icp_to_filters(icp)
        assert result["geo_regions"] == ["Germany", "UK"]

    def test_maps_company_size_dict(self):
        icp = {"company_size": {"min": 50, "max": 500}}
        result = _map_icp_to_filters(icp)
        assert result["company_sizes"] == ["50-500"]

    def test_maps_company_size_list(self):
        icp = {"company_size": ["50-100", "100-500"]}
        result = _map_icp_to_filters(icp)
        assert result["company_sizes"] == ["50-100", "100-500"]

    def test_maps_personas_seniority(self):
        icp = {
            "personas": [
                {"title": "CTO", "seniority": "C-Level"},
                {"title": "VP Eng", "seniority": "VP"},
                {"title": "CEO", "seniority": "C-Level"},  # duplicate
            ]
        }
        result = _map_icp_to_filters(icp)
        assert sorted(result["seniority_levels"]) == ["C-Level", "VP"]

    def test_maps_personas_seniority_level_alternative(self):
        """Test the 'seniority_level' alternative field name."""
        icp = {
            "personas": [
                {"title": "Dir", "seniority_level": "Director"},
            ]
        }
        result = _map_icp_to_filters(icp)
        assert result["seniority_levels"] == ["Director"]

    def test_empty_icp_returns_empty(self):
        result = _map_icp_to_filters({})
        assert result == {}

    def test_ignores_non_list_industries(self):
        icp = {"industries": "saas"}  # should be a list
        result = _map_icp_to_filters(icp)
        assert "industries" not in result

    def test_full_icp(self):
        icp = {
            "industries": ["saas"],
            "geographies": ["DE"],
            "company_size": {"min": 10, "max": 100},
            "personas": [{"seniority": "VP"}],
        }
        result = _map_icp_to_filters(icp)
        assert "industries" in result
        assert "geo_regions" in result
        assert "company_sizes" in result
        assert "seniority_levels" in result


# ===========================================================================
# BL-116: apply_icp_filters handler tests
# ===========================================================================


class TestApplyIcpFilters:
    def test_returns_matches(self, app, db, seed_tenant, strategy_with_icp, contacts_for_filter, tool_ctx):
        with app.app_context():
            result = apply_icp_filters({}, tool_ctx)
        assert "total_matches" in result
        assert "filters_applied" in result
        assert "top_segments" in result
        assert result["total_matches"] >= 0
        assert "industries" in result["filters_applied"]

    def test_emits_filter_sync_side_effect(self, app, db, seed_tenant, strategy_with_icp, contacts_for_filter, tool_ctx):
        with app.app_context():
            result = apply_icp_filters({}, tool_ctx)
        assert "side_effect" in result
        se = result["side_effect"]
        assert se["type"] == "filter_sync"
        assert "payload" in se
        assert "id" in se["payload"]
        assert "filters" in se["payload"]
        assert "description" in se["payload"]

    def test_no_icp_data(self, app, db, seed_tenant, strategy_no_icp, tool_ctx):
        with app.app_context():
            result = apply_icp_filters({}, tool_ctx)
        assert result["total_matches"] == 0
        assert result["filters_applied"] == {}
        assert "No ICP data" in result["message"]

    def test_no_strategy_document(self, app, db, seed_tenant, tool_ctx):
        with app.app_context():
            result = apply_icp_filters({}, tool_ctx)
        assert "error" in result

    def test_tool_registered(self):
        """Verify ICP_FILTER_TOOLS has exactly one tool."""
        assert len(ICP_FILTER_TOOLS) == 1
        assert ICP_FILTER_TOOLS[0].name == "apply_icp_filters"


# ===========================================================================
# BL-117: create_campaign auto-populate from strategy (tool handler)
# ===========================================================================


class TestCreateCampaignAutoPopulate:
    def test_auto_populates_from_strategy(self, app, db, seed_tenant, strategy_with_icp, tool_ctx):
        with app.app_context():
            result = create_campaign(
                {"name": "Auto Campaign", "strategy_id": str(strategy_with_icp.id)},
                tool_ctx,
            )
        assert "campaign_id" in result
        assert "auto_populated_from_strategy" in result
        auto = result["auto_populated_from_strategy"]
        assert "target_criteria" in auto
        assert "channel" in auto
        assert "generation_config" in auto

        # Verify the campaign was actually created with strategy data
        with app.app_context():
            campaign = Campaign.query.get(result["campaign_id"])
            assert campaign is not None
            assert campaign.channel == "linkedin"
            assert campaign.strategy_id == str(strategy_with_icp.id)

    def test_explicit_args_override_strategy(self, app, db, seed_tenant, strategy_with_icp, tool_ctx):
        with app.app_context():
            result = create_campaign(
                {
                    "name": "Override Campaign",
                    "strategy_id": str(strategy_with_icp.id),
                    "channel": "email",
                    "target_criteria": {"industries": ["fintech"]},
                    "generation_config": {"tone": "formal"},
                },
                tool_ctx,
            )
        assert "campaign_id" in result

        with app.app_context():
            campaign = Campaign.query.get(result["campaign_id"])
            assert campaign.channel == "email"
            tc = json.loads(campaign.target_criteria) if isinstance(campaign.target_criteria, str) else campaign.target_criteria
            assert tc == {"industries": ["fintech"]}
            gc = json.loads(campaign.generation_config) if isinstance(campaign.generation_config, str) else campaign.generation_config
            assert gc == {"tone": "formal"}

    def test_no_strategy_creates_normally(self, app, db, seed_tenant, tool_ctx):
        with app.app_context():
            result = create_campaign({"name": "Plain Campaign"}, tool_ctx)
        assert "campaign_id" in result
        assert "auto_populated_from_strategy" not in result

    def test_strategy_without_extracted_data(self, app, db, seed_tenant, strategy_no_icp, tool_ctx):
        with app.app_context():
            result = create_campaign(
                {"name": "Empty Strategy Campaign", "strategy_id": str(strategy_no_icp.id)},
                tool_ctx,
            )
        assert "campaign_id" in result
        # No auto-populate reported since extracted_data is empty
        assert "auto_populated_from_strategy" not in result


# ===========================================================================
# BL-117: create_campaign REST endpoint auto-populate
# ===========================================================================


class TestCreateCampaignRESTAutoPopulate:
    def test_rest_auto_populates_from_strategy(self, client, seed_companies_contacts, db, seed_tenant):
        # First create a strategy doc with ICP
        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            content="# Strategy",
            extracted_data=json.dumps({
                "icp": {"industries": ["saas"]},
                "messaging": {"tone": "warm"},
                "channels": {"primary": "email"},
            }),
            status="draft",
            phase="strategy",
            version=1,
        )
        db.session.add(doc)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            "/api/campaigns",
            headers=headers,
            json={
                "name": "Strategy-linked Campaign",
                "strategy_id": str(doc.id),
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "id" in data

        # Verify campaign has auto-populated fields
        campaign = Campaign.query.get(data["id"])
        assert campaign.strategy_id == str(doc.id)
        assert campaign.channel == "email"

        tc = json.loads(campaign.target_criteria) if isinstance(campaign.target_criteria, str) else campaign.target_criteria
        assert tc.get("industries") == ["saas"]

        gc = json.loads(campaign.generation_config) if isinstance(campaign.generation_config, str) else campaign.generation_config
        assert gc.get("tone") == "warm"

    def test_rest_explicit_channel_overrides(self, client, seed_companies_contacts, db, seed_tenant):
        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            content="# Strategy",
            extracted_data=json.dumps({
                "channels": {"primary": "email"},
            }),
            status="draft",
            phase="strategy",
            version=1,
        )
        db.session.add(doc)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            "/api/campaigns",
            headers=headers,
            json={
                "name": "Overridden Campaign",
                "strategy_id": str(doc.id),
                "channel": "linkedin",
            },
        )
        assert resp.status_code == 201
        campaign = Campaign.query.get(resp.get_json()["id"])
        assert campaign.channel == "linkedin"

    def test_rest_no_strategy_works_normally(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            "/api/campaigns",
            headers=headers,
            json={"name": "Normal Campaign"},
        )
        assert resp.status_code == 201


# ===========================================================================
# BL-114: Phase advance endpoint tests (backend side)
# ===========================================================================


class TestPhaseAdvanceAfterExtract:
    def test_advance_to_contacts_requires_icp(self, client, seed_companies_contacts, db, seed_tenant):
        """Phase transition to contacts requires extracted ICP data."""
        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            content="# Strategy",
            extracted_data=json.dumps({}),
            status="draft",
            phase="strategy",
            version=1,
        )
        db.session.add(doc)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.put(
            "/api/playbook/phase",
            headers=headers,
            json={"phase": "contacts"},
        )
        assert resp.status_code == 422
        assert "ICP" in resp.get_json()["error"]

    def test_advance_to_contacts_succeeds_with_icp(self, client, seed_companies_contacts, db, seed_tenant):
        """Phase transition to contacts succeeds when ICP is extracted."""
        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            content="# Strategy",
            extracted_data=json.dumps({"icp": {"industries": ["saas"]}}),
            status="draft",
            phase="strategy",
            version=1,
        )
        db.session.add(doc)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.put(
            "/api/playbook/phase",
            headers=headers,
            json={"phase": "contacts"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["phase"] == "contacts"
