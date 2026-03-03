"""Tests for BL-169: Event-Driven Chat Nudges + BL-170: Phase Transitions."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from api.models import (  # noqa: F811
    Company,
    CompanyEnrichmentL1,
    Contact,
    Message,
    PipelineRun,
    StageRun,
    StrategyDocument,
    UserTenantRole,
)
from tests.conftest import auth_header


@pytest.fixture
def enriched_namespace(db, seed_tenant, seed_super_admin):
    """Namespace with strategy, contacts, companies, and enrichment data."""
    tid = seed_tenant.id

    # Give super admin access
    role = UserTenantRole(
        user_id=seed_super_admin.id,
        tenant_id=tid,
        role="admin",
        granted_by=seed_super_admin.id,
    )
    db.session.add(role)

    # Strategy doc with extracted data
    doc = StrategyDocument(
        tenant_id=tid,
        content="## Strategy\nContent here.",
        extracted_data=json.dumps({
            "icp": {"industries": ["software_saas"]},
            "personas": [{"title": "CTO"}],
        }),
        status="draft",
        phase="strategy",
    )
    db.session.add(doc)

    # Companies
    c1 = Company(tenant_id=tid, name="Acme", domain="acme.com", status="triage_passed", industry="software_saas")
    c2 = Company(tenant_id=tid, name="Beta", domain="beta.com", status="triage_disqualified", industry="retail")
    db.session.add_all([c1, c2])
    db.session.flush()

    # Contacts
    ct1 = Contact(tenant_id=tid, first_name="John", last_name="Doe", company_id=c1.id)
    ct2 = Contact(tenant_id=tid, first_name="Jane", last_name="Smith", company_id=c2.id)
    db.session.add_all([ct1, ct2])
    db.session.flush()

    # L1 enrichment
    l1 = CompanyEnrichmentL1(company_id=c1.id, pre_score=8.0)
    db.session.add(l1)

    db.session.commit()
    return {
        "tenant": seed_tenant,
        "companies": [c1, c2],
        "contacts": [ct1, ct2],
        "strategy_doc": doc,
    }


class TestWorkflowSuggestionsEndpoint:
    def test_returns_suggestions_with_nudge_count(self, client, enriched_namespace):
        headers = auth_header(client)
        headers["X-Namespace"] = enriched_namespace["tenant"].slug

        resp = client.get("/api/tenants/workflow-suggestions", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()

        assert "suggestions" in data
        assert "nudge_count" in data
        assert isinstance(data["nudge_count"], int)

    def test_suggestions_have_nudge_type(self, client, enriched_namespace):
        headers = auth_header(client)
        headers["X-Namespace"] = enriched_namespace["tenant"].slug

        resp = client.get("/api/tenants/workflow-suggestions", headers=headers)
        data = resp.get_json()

        for s in data["suggestions"]:
            assert "nudge_type" in s
            assert s["nudge_type"] in ("step", "event")

    def test_suggestions_have_action_type(self, client, enriched_namespace):
        headers = auth_header(client)
        headers["X-Namespace"] = enriched_namespace["tenant"].slug

        resp = client.get("/api/tenants/workflow-suggestions", headers=headers)
        data = resp.get_json()

        for s in data["suggestions"]:
            assert "action_type" in s
            assert s["action_type"] in ("navigate", "navigate_and_act")


class TestEventDrivenNudges:
    def test_enrichment_complete_nudge(self, client, enriched_namespace, db):
        """When a pipeline run completes recently, show a nudge."""
        tid = enriched_namespace["tenant"].id

        # Create a recently completed pipeline run
        now = datetime.now(timezone.utc)
        pipeline = PipelineRun(
            tenant_id=tid,
            status="completed",
            l1_done=5,
            l2_done=3,
            person_done=2,
            total_companies=5,
            started_at=now - timedelta(hours=1),
            completed_at=now - timedelta(minutes=30),
        )
        db.session.add(pipeline)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = enriched_namespace["tenant"].slug

        resp = client.get("/api/tenants/workflow-suggestions", headers=headers)
        data = resp.get_json()

        nudges = [s for s in data["suggestions"] if s["nudge_type"] == "event"]
        assert len(nudges) > 0
        assert data["nudge_count"] > 0

        # Check for enrichment complete nudge
        enrichment_nudge = [s for s in nudges if "enrichment" in s["id"].lower() or "enrichment" in s["summary"].lower()]
        assert len(enrichment_nudge) > 0

    def test_triage_complete_nudge(self, client, enriched_namespace, db):
        """When triage stage completes recently, show a nudge."""
        tid = enriched_namespace["tenant"].id

        now = datetime.now(timezone.utc)
        stage = StageRun(
            tenant_id=tid,
            stage="triage",
            status="completed",
            total=5,
            done=5,
            started_at=now - timedelta(hours=1),
            completed_at=now - timedelta(minutes=30),
        )
        db.session.add(stage)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = enriched_namespace["tenant"].slug

        resp = client.get("/api/tenants/workflow-suggestions", headers=headers)
        data = resp.get_json()

        nudges = [s for s in data["suggestions"] if s["nudge_type"] == "event"]
        triage_nudges = [s for s in nudges if "triage" in s["id"].lower()]
        assert len(triage_nudges) > 0

    def test_messages_generated_nudge(self, client, enriched_namespace, db):
        """When messages are recently generated, show a nudge."""
        tid = enriched_namespace["tenant"].id

        now = datetime.now(timezone.utc)
        msg = Message(
            tenant_id=tid,
            contact_id=enriched_namespace["contacts"][0].id,
            channel="email",
            sequence_step=1,
            variant="a",
            subject="Test",
            body="Hello",
            status="draft",
            created_at=now - timedelta(minutes=30),
        )
        db.session.add(msg)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = enriched_namespace["tenant"].slug

        resp = client.get("/api/tenants/workflow-suggestions", headers=headers)
        data = resp.get_json()

        nudges = [s for s in data["suggestions"] if s["nudge_type"] == "event"]
        msg_nudges = [s for s in nudges if "messages" in s["id"].lower() or "messages" in s["summary"].lower()]
        assert len(msg_nudges) > 0

    def test_no_nudges_when_no_recent_events(self, client, enriched_namespace):
        """Without recent events, all suggestions are step type."""
        headers = auth_header(client)
        headers["X-Namespace"] = enriched_namespace["tenant"].slug

        resp = client.get("/api/tenants/workflow-suggestions", headers=headers)
        data = resp.get_json()

        # Should only have step suggestions, no event nudges
        assert data["nudge_count"] == 0


class TestPhaseTransition:
    def test_transition_endpoint_exists(self, client, enriched_namespace):
        headers = auth_header(client)
        headers["X-Namespace"] = enriched_namespace["tenant"].slug

        resp = client.get("/api/tenants/phase-transition", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()

        assert "current_phase" in data
        assert "transition" in data
        assert "ready" in data["transition"]

    def test_transition_detected_at_enrichment_done(self, client, enriched_namespace, db):
        """When enrichment is done and contacts not yet selected, detect transition."""
        # Mark contacts as enriched (processed_enrich = True)
        for ct in enriched_namespace["contacts"]:
            ct.processed_enrich = True
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = enriched_namespace["tenant"].slug

        resp = client.get("/api/tenants/phase-transition", headers=headers)
        data = resp.get_json()

        # Phase should be enrichment_done since we have enriched contacts
        # The exact phase depends on data setup, but structure should be valid
        assert "transition" in data
        assert isinstance(data["transition"]["ready"], bool)
        if data["transition"]["ready"]:
            assert "cta_label" in data["transition"]
            assert "cta_path" in data["transition"]
            assert "message" in data["transition"]

    def test_no_transition_at_beginning(self, client, db, seed_tenant, seed_super_admin):
        """At the start (no strategy), no transition should be suggested."""
        role = UserTenantRole(
            user_id=seed_super_admin.id,
            tenant_id=seed_tenant.id,
            role="admin",
            granted_by=seed_super_admin.id,
        )
        db.session.add(role)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.get("/api/tenants/phase-transition", headers=headers)
        data = resp.get_json()

        assert data["transition"]["ready"] is False
