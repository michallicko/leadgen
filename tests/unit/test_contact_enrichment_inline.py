"""Unit tests for BL-180: Inline enrichment results in contacts table."""

from api.models import Company, Contact, ContactEnrichment
from tests.conftest import auth_header


def _seed_contact_with_enrichment(db, tenant_id):
    """Create a company + contact with enrichment data."""
    co = Company(
        tenant_id=tenant_id,
        name="Enriched Corp",
        domain="enriched.com",
        tier="tier_1_platinum",
        status="enriched_l2",
    )
    db.session.add(co)
    db.session.flush()

    ct = Contact(
        tenant_id=tenant_id,
        company_id=co.id,
        first_name="Alice",
        last_name="Smith",
        email_address="alice@enriched.com",
        processed_enrich=True,
    )
    db.session.add(ct)
    db.session.flush()

    ce = ContactEnrichment(
        contact_id=ct.id,
        person_summary="Senior leader at Enriched Corp",
        ai_champion_score=75,
        authority_score=80,
    )
    db.session.add(ce)
    db.session.flush()

    return co, ct, ce


def _seed_contact_without_enrichment(db, tenant_id):
    """Create a company + contact without enrichment data."""
    co = Company(
        tenant_id=tenant_id,
        name="New Corp",
        domain="new.com",
        tier="tier_3_silver",
        status="new",
    )
    db.session.add(co)
    db.session.flush()

    ct = Contact(
        tenant_id=tenant_id,
        company_id=co.id,
        first_name="Bob",
        last_name="Jones",
        email_address="bob@new.com",
        processed_enrich=False,
    )
    db.session.add(ct)
    db.session.flush()
    return co, ct


class TestContactEnrichmentInline:
    def test_contacts_list_includes_enrichment_fields(
        self, client, seed_tenant, seed_super_admin, db
    ):
        _seed_contact_with_enrichment(db, seed_tenant.id)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/contacts", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] >= 1

        # Find the enriched contact
        alice = next((c for c in data["contacts"] if c["first_name"] == "Alice"), None)
        assert alice is not None
        assert alice["company_tier"] == "Tier 1 - Platinum"
        assert alice["enrichment_status"] == "enriched"

    def test_contacts_list_unenriched_contact(
        self, client, seed_tenant, seed_super_admin, db
    ):
        _seed_contact_without_enrichment(db, seed_tenant.id)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/contacts", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()

        bob = next((c for c in data["contacts"] if c["first_name"] == "Bob"), None)
        assert bob is not None
        assert bob["company_tier"] == "Tier 3 - Silver"
        assert bob["enrichment_status"] == "none"

    def test_contacts_list_enrichment_status_processed(
        self, client, seed_tenant, seed_super_admin, db
    ):
        """Contact that was processed_enrich but has no enrichment record."""
        co = Company(
            tenant_id=seed_tenant.id,
            name="Mid Corp",
            status="new",
        )
        db.session.add(co)
        db.session.flush()
        ct = Contact(
            tenant_id=seed_tenant.id,
            company_id=co.id,
            first_name="Charlie",
            last_name="Brown",
            processed_enrich=True,
        )
        db.session.add(ct)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/contacts", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()

        charlie = next(
            (c for c in data["contacts"] if c["first_name"] == "Charlie"), None
        )
        assert charlie is not None
        assert charlie["enrichment_status"] == "processed"
