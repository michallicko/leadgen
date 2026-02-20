"""Tests for browser extension API routes."""
import pytest

from tests.conftest import auth_header


class TestUploadLeads:
    """POST /api/extension/leads"""

    def test_creates_contacts_and_companies(self, client, seed_companies_contacts):
        """Given new leads, creates contacts and companies."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        leads = [
            {
                "name": "Jane Newperson",
                "job_title": "CTO",
                "company_name": "NewCorp Inc",
                "linkedin_url": "https://www.linkedin.com/in/janenewperson",
                "company_domain": "https://newcorp.com",
                "revenue_range": "$10M-50M",
                "company_size": "51-200",
                "industry": "Technology",
            }
        ]
        resp = client.post(
            "/api/extension/leads",
            json={"leads": leads, "source": "sales_navigator", "tag": "test-import"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["created_contacts"] == 1
        assert data["created_companies"] == 1
        assert data["skipped_duplicates"] == 0

    def test_deduplicates_by_linkedin_url(self, client, seed_companies_contacts):
        """Given duplicate linkedin_url, skips the duplicate."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        leads = [
            {
                "name": "Dedup Person",
                "job_title": "CTO",
                "company_name": "DedupCorp",
                "linkedin_url": "https://www.linkedin.com/in/dedupperson",
            }
        ]
        # First upload
        client.post(
            "/api/extension/leads",
            json={"leads": leads, "source": "sales_navigator", "tag": "import-1"},
            headers=headers,
        )
        # Second upload -- same linkedin_url
        resp = client.post(
            "/api/extension/leads",
            json={"leads": leads, "source": "sales_navigator", "tag": "import-2"},
            headers=headers,
        )
        data = resp.get_json()
        assert data["created_contacts"] == 0
        assert data["skipped_duplicates"] == 1

    def test_links_to_existing_company(self, client, seed_companies_contacts):
        """Given a lead whose company already exists, links to it without creating new."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        # "Acme Corp" is seeded in seed_companies_contacts
        leads = [
            {
                "name": "New Person",
                "job_title": "Engineer",
                "company_name": "Acme Corp",
                "linkedin_url": "https://www.linkedin.com/in/newperson-acme",
            }
        ]
        resp = client.post(
            "/api/extension/leads",
            json={"leads": leads, "source": "sales_navigator", "tag": "test"},
            headers=headers,
        )
        data = resp.get_json()
        assert data["created_contacts"] == 1
        assert data["created_companies"] == 0  # reused existing

    def test_requires_auth(self, client, db):
        """Given no auth header, returns 401."""
        resp = client.post(
            "/api/extension/leads",
            json={"leads": [], "source": "test", "tag": "test"},
        )
        assert resp.status_code == 401

    def test_sets_owner_and_import_source(self, client, seed_companies_contacts):
        """Given leads, sets owner_id from user and import_source on contact."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        leads = [
            {
                "name": "Tagged Person",
                "job_title": "PM",
                "company_name": "TagCorp",
                "linkedin_url": "https://www.linkedin.com/in/taggedperson",
            }
        ]
        resp = client.post(
            "/api/extension/leads",
            json={"leads": leads, "source": "sales_navigator", "tag": "sn-import"},
            headers=headers,
        )
        assert resp.status_code == 200

        # Verify contact has import_source set
        from api.models import Contact
        contact = Contact.query.filter_by(
            linkedin_url="https://www.linkedin.com/in/taggedperson"
        ).first()
        assert contact is not None
        assert contact.import_source == "sales_navigator"
        assert contact.is_stub is False

    def test_validates_leads_field(self, client, seed_companies_contacts):
        """Given no leads field in body, returns 400."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.post(
            "/api/extension/leads",
            json={"source": "test"},
            headers=headers,
        )
        assert resp.status_code == 400


class TestUploadActivities:
    """POST /api/extension/activities"""

    def test_creates_activities(self, client, seed_companies_contacts):
        """Given new events, creates activity records."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        # Use an existing contact's linkedin_url from seed data
        events = [
            {
                "event_type": "message",
                "timestamp": "2026-02-20T10:30:00Z",
                "contact_linkedin_url": "https://www.linkedin.com/in/johndoe",
                "external_id": "ext_001",
                "payload": {
                    "contact_name": "John Doe",
                    "message": "Hey, interested in your product",
                    "direction": "received",
                },
            }
        ]
        resp = client.post(
            "/api/extension/activities",
            json={"events": events},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["created"] == 1
        assert data["skipped_duplicates"] == 0

    def test_deduplicates_by_external_id(self, client, seed_companies_contacts):
        """Given duplicate external_id, skips the duplicate."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        events = [
            {
                "event_type": "message",
                "external_id": "ext_dedup",
                "timestamp": "2026-02-20T10:30:00Z",
                "contact_linkedin_url": "https://www.linkedin.com/in/someone",
                "payload": {"contact_name": "Someone", "message": "Hi"},
            }
        ]
        client.post(
            "/api/extension/activities",
            json={"events": events},
            headers=headers,
        )
        resp = client.post(
            "/api/extension/activities",
            json={"events": events},
            headers=headers,
        )
        data = resp.get_json()
        assert data["created"] == 0
        assert data["skipped_duplicates"] == 1

    def test_creates_stub_contact_for_unknown_linkedin_url(
        self, client, seed_companies_contacts
    ):
        """Given activity with unknown linkedin_url, creates stub contact."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        events = [
            {
                "event_type": "message",
                "external_id": "ext_stub",
                "timestamp": "2026-02-20T10:30:00Z",
                "contact_linkedin_url": "https://www.linkedin.com/in/unknown-person",
                "payload": {"contact_name": "Unknown Person", "message": "Hello"},
            }
        ]
        resp = client.post(
            "/api/extension/activities",
            json={"events": events},
            headers=headers,
        )
        assert resp.status_code == 200

        from api.models import Contact
        stub = Contact.query.filter_by(
            linkedin_url="https://www.linkedin.com/in/unknown-person"
        ).first()
        assert stub is not None
        assert stub.is_stub is True
        assert stub.import_source == "activity_stub"
        assert stub.first_name == "Unknown"
        assert stub.last_name == "Person"

    def test_links_to_existing_contact(self, client, seed_companies_contacts):
        """Given activity with known linkedin_url, links to existing contact."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        events = [
            {
                "event_type": "message",
                "external_id": "ext_existing",
                "timestamp": "2026-02-20T10:30:00Z",
                "contact_linkedin_url": "https://www.linkedin.com/in/johndoe",
                "payload": {"contact_name": "John Doe", "message": "Hi"},
            }
        ]
        resp = client.post(
            "/api/extension/activities",
            json={"events": events},
            headers=headers,
        )
        assert resp.status_code == 200

        from api.models import Activity, Contact
        # Should NOT create a stub -- should link to existing John Doe
        john = Contact.query.filter_by(
            linkedin_url="https://www.linkedin.com/in/johndoe"
        ).first()
        activity = Activity.query.filter_by(external_id="ext_existing").first()
        assert activity is not None
        assert activity.contact_id == john.id

    def test_requires_auth(self, client, db):
        """Given no auth header, returns 401."""
        resp = client.post(
            "/api/extension/activities",
            json={"events": []},
        )
        assert resp.status_code == 401

    def test_validates_events_field(self, client, seed_companies_contacts):
        """Given no events field in body, returns 400."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.post(
            "/api/extension/activities",
            json={"source": "test"},
            headers=headers,
        )
        assert resp.status_code == 400


class TestExtensionStatus:
    """GET /api/extension/status"""

    def test_returns_status_when_no_data(self, client, seed_companies_contacts):
        """Given no extension data, returns zeroed status."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/extension/status", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["connected"] is False
        assert data["total_leads_imported"] == 0
        assert data["total_activities_synced"] == 0
        assert data["last_lead_sync"] is None
        assert data["last_activity_sync"] is None

    def test_returns_stats_after_imports(self, client, seed_companies_contacts):
        """Given prior imports, returns correct counts and timestamps."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        # Upload some leads
        client.post(
            "/api/extension/leads",
            json={
                "leads": [
                    {
                        "name": "Status Test",
                        "linkedin_url": "https://linkedin.com/in/statustest",
                        "company_name": "StatusCorp",
                    }
                ],
                "source": "sales_navigator",
                "tag": "status-test",
            },
            headers=headers,
        )
        # Upload some activities
        client.post(
            "/api/extension/activities",
            json={
                "events": [
                    {
                        "event_type": "message",
                        "external_id": "status_ext_001",
                        "timestamp": "2026-02-20T10:30:00Z",
                        "contact_linkedin_url": "https://linkedin.com/in/statustest",
                        "payload": {"contact_name": "Status Test", "message": "Hi"},
                    }
                ]
            },
            headers=headers,
        )

        resp = client.get("/api/extension/status", headers=headers)
        data = resp.get_json()
        assert data["connected"] is True
        assert data["total_leads_imported"] == 1
        assert data["total_activities_synced"] == 1
        assert data["last_lead_sync"] is not None
        assert data["last_activity_sync"] is not None

    def test_requires_auth(self, client, db):
        """Given no auth header, returns 401."""
        resp = client.get("/api/extension/status")
        assert resp.status_code == 401
