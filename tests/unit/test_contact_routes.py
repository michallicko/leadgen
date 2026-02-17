"""Unit tests for contact routes."""
from tests.conftest import auth_header


class TestListContacts:
    def test_list_returns_paginated(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/contacts?page_size=5", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "contacts" in data
        assert data["total"] == 10
        assert data["page"] == 1
        assert data["page_size"] == 5
        assert data["pages"] == 2
        assert len(data["contacts"]) == 5

    def test_list_page_2(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/contacts?page=2&page_size=5", headers=headers)
        data = resp.get_json()
        assert data["page"] == 2
        assert len(data["contacts"]) == 5

    def test_search_by_name(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/contacts?search=John", headers=headers)
        data = resp.get_json()
        assert data["total"] == 1
        assert data["contacts"][0]["full_name"] == "John Doe"

    def test_search_by_email(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/contacts?search=jane@acme", headers=headers)
        data = resp.get_json()
        assert data["total"] == 1
        assert data["contacts"][0]["full_name"] == "Jane Smith"

    def test_search_by_title(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/contacts?search=CEO", headers=headers)
        data = resp.get_json()
        assert data["total"] >= 1

    def test_filter_by_batch(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/contacts?tag_name=batch-2", headers=headers)
        data = resp.get_json()
        assert data["total"] == 4  # Eve, Frank, Grace, Hank

    def test_filter_by_owner(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/contacts?owner_name=Bob", headers=headers)
        data = resp.get_json()
        for c in data["contacts"]:
            assert c["owner_name"] == "Bob"

    def test_filter_by_icp_fit(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/contacts?icp_fit=strong_fit", headers=headers)
        data = resp.get_json()
        assert data["total"] == 4  # John, Jane, Carol, Frank
        for c in data["contacts"]:
            assert c["icp_fit"] == "Strong Fit"

    def test_filter_by_message_status(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/contacts?message_status=approved", headers=headers)
        data = resp.get_json()
        assert data["total"] == 2  # Jane, Eve

    def test_filter_by_company_id(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        company_id = seed_companies_contacts["companies"][0].id  # Acme
        resp = client.get(f"/api/contacts?company_id={company_id}", headers=headers)
        data = resp.get_json()
        assert data["total"] == 2  # John, Jane

    def test_sort_by_contact_score_desc(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/contacts?sort=contact_score&sort_dir=desc", headers=headers)
        data = resp.get_json()
        scores = [c["contact_score"] for c in data["contacts"] if c["contact_score"] is not None]
        assert scores == sorted(scores, reverse=True)

    def test_display_values(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/contacts?search=John", headers=headers)
        data = resp.get_json()
        c = data["contacts"][0]
        assert c["icp_fit"] == "Strong Fit"
        assert c["company_name"] == "Acme Corp"

    def test_no_auth_returns_401(self, client, seed_companies_contacts):
        resp = client.get("/api/contacts")
        assert resp.status_code == 401

    def test_tenant_isolation(self, client, db, seed_companies_contacts):
        from api.models import Contact, Tenant
        other = Tenant(name="Other Corp", slug="other-corp", is_active=True)
        db.session.add(other)
        db.session.flush()
        ct = Contact(tenant_id=other.id, first_name="Hidden", last_name="Person")
        db.session.add(ct)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/contacts", headers=headers)
        data = resp.get_json()
        names = [c["full_name"] for c in data["contacts"]]
        assert "Hidden Person" not in names


class TestGetContact:
    def test_get_detail(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        contact_id = seed_companies_contacts["contacts"][0].id  # John Doe
        resp = client.get(f"/api/contacts/{contact_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["full_name"] == "John Doe"
        assert data["job_title"] == "CEO"
        assert data["company"]["name"] == "Acme Corp"

    def test_get_with_enrichment(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        contact_id = seed_companies_contacts["contacts"][0].id
        resp = client.get(f"/api/contacts/{contact_id}", headers=headers)
        data = resp.get_json()
        assert data["enrichment"] is not None
        assert data["enrichment"]["person_summary"] == "Experienced CEO with AI background"

    def test_get_with_messages(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        contact_id = seed_companies_contacts["contacts"][1].id  # Jane Smith
        resp = client.get(f"/api/contacts/{contact_id}", headers=headers)
        data = resp.get_json()
        assert len(data["messages"]) == 1
        assert data["messages"][0]["channel"] == "linkedin_connect"

    def test_get_not_found(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/contacts/00000000-0000-0000-0000-000000000000", headers=headers)
        assert resp.status_code == 404


class TestPatchContact:
    def test_update_notes(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        contact_id = seed_companies_contacts["contacts"][0].id
        resp = client.patch(
            f"/api/contacts/{contact_id}",
            json={"notes": "Updated notes"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_update_icp_fit(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        contact_id = seed_companies_contacts["contacts"][0].id
        resp = client.patch(
            f"/api/contacts/{contact_id}",
            json={"icp_fit": "weak_fit"},
            headers=headers,
        )
        assert resp.status_code == 200

    def test_update_multiple_fields(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        contact_id = seed_companies_contacts["contacts"][0].id
        resp = client.patch(
            f"/api/contacts/{contact_id}",
            json={"notes": "New notes", "language": "de", "department": "sales"},
            headers=headers,
        )
        assert resp.status_code == 200

    def test_disallowed_field_ignored(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        contact_id = seed_companies_contacts["contacts"][0].id
        resp = client.patch(
            f"/api/contacts/{contact_id}",
            json={"full_name": "Hacked Name"},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "No valid fields" in resp.get_json()["error"]

    def test_update_not_found(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.patch(
            "/api/contacts/00000000-0000-0000-0000-000000000000",
            json={"notes": "test"},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_no_auth_returns_401(self, client, seed_companies_contacts):
        contact_id = seed_companies_contacts["contacts"][0].id
        resp = client.patch(f"/api/contacts/{contact_id}", json={"notes": "x"})
        assert resp.status_code == 401
