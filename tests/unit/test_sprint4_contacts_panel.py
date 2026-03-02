"""Tests for BL-115: Contacts phase panel API endpoints.

Tests the new /api/playbook/contacts and /api/playbook/contacts/confirm
endpoints, plus the playbook_selections persistence via PUT /api/playbook.
"""
import json


def auth_header(client, email="admin@test.com", password="testpass123"):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_doc_with_icp(db, tenant_id, icp_data=None):
    """Create a StrategyDocument with extracted ICP data."""
    from api.models import StrategyDocument

    extracted = {"icp": icp_data} if icp_data else {}
    doc = StrategyDocument(
        tenant_id=tenant_id,
        content="# Test Strategy",
        status="active",
        version=1,
        extracted_data=json.dumps(extracted),
    )
    db.session.add(doc)
    db.session.commit()
    return doc


class TestPlaybookContacts:
    """Tests for GET /api/playbook/contacts."""

    def test_returns_contacts_with_icp_filters(
        self, client, seed_companies_contacts, db
    ):
        data = seed_companies_contacts
        tenant = data["tenant"]
        headers = auth_header(client)
        headers["X-Namespace"] = tenant.slug

        # Create strategy doc with ICP targeting software/IT industries
        _create_doc_with_icp(db, tenant.id, {
            "industries": ["software_saas", "it"],
        })

        resp = client.get("/api/playbook/contacts", headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()

        assert body["icp_source"] is True
        assert body["total"] >= 0
        assert "contacts" in body
        assert "filters" in body
        assert body["filters"]["applied_filters"]["industries"] == [
            "software_saas", "it"
        ]

    def test_returns_all_contacts_without_icp(
        self, client, seed_companies_contacts, db
    ):
        data = seed_companies_contacts
        tenant = data["tenant"]
        headers = auth_header(client)
        headers["X-Namespace"] = tenant.slug

        # Create strategy doc with empty ICP
        _create_doc_with_icp(db, tenant.id)

        resp = client.get("/api/playbook/contacts", headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()

        assert body["icp_source"] is False
        # Should return all non-disqualified contacts
        assert body["total"] == len(data["contacts"])

    def test_filter_override_query_params(
        self, client, seed_companies_contacts, db
    ):
        data = seed_companies_contacts
        tenant = data["tenant"]
        headers = auth_header(client)
        headers["X-Namespace"] = tenant.slug

        _create_doc_with_icp(db, tenant.id, {"industries": ["software_saas"]})

        # Override with a different filter
        resp = client.get(
            "/api/playbook/contacts?seniority_levels=c_level",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()

        # All returned contacts should have c_level seniority
        for ct in body["contacts"]:
            if ct["seniority_level"]:
                assert ct["seniority_level"] in ("C-Level", "c_level")

    def test_pagination(self, client, seed_companies_contacts, db):
        data = seed_companies_contacts
        tenant = data["tenant"]
        headers = auth_header(client)
        headers["X-Namespace"] = tenant.slug

        _create_doc_with_icp(db, tenant.id)

        # Request page 1 with per_page=3
        resp = client.get(
            "/api/playbook/contacts?per_page=3&page=1",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()

        assert body["page"] == 1
        assert body["per_page"] == 3
        assert len(body["contacts"]) <= 3
        assert body["pages"] >= 1

    def test_search_filter(self, client, seed_companies_contacts, db):
        data = seed_companies_contacts
        tenant = data["tenant"]
        headers = auth_header(client)
        headers["X-Namespace"] = tenant.slug

        _create_doc_with_icp(db, tenant.id)

        # Search for "John"
        resp = client.get(
            "/api/playbook/contacts?search=John",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()

        assert body["total"] >= 1
        for ct in body["contacts"]:
            searchable = " ".join(filter(None, [
                ct.get("full_name", ""),
                ct.get("email_address", ""),
                ct.get("job_title", ""),
            ])).lower()
            assert "john" in searchable

    def test_contact_response_shape(self, client, seed_companies_contacts, db):
        data = seed_companies_contacts
        tenant = data["tenant"]
        headers = auth_header(client)
        headers["X-Namespace"] = tenant.slug

        _create_doc_with_icp(db, tenant.id)

        resp = client.get("/api/playbook/contacts?per_page=1", headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()

        if body["contacts"]:
            ct = body["contacts"][0]
            # Verify expected fields
            assert "id" in ct
            assert "full_name" in ct
            assert "first_name" in ct
            assert "last_name" in ct
            assert "job_title" in ct
            assert "company_name" in ct
            assert "seniority_level" in ct
            assert "contact_score" in ct
            assert "icp_fit" in ct

    def test_no_strategy_document_returns_404(
        self, client, seed_tenant, seed_super_admin, db
    ):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        resp = client.get("/api/playbook/contacts", headers=headers)
        # The route auto-creates a doc on GET /api/playbook, but
        # /api/playbook/contacts requires an existing doc
        assert resp.status_code == 404

    def test_requires_auth(self, client, seed_tenant):
        resp = client.get(
            "/api/playbook/contacts",
            headers={"X-Namespace": seed_tenant.slug},
        )
        assert resp.status_code == 401

    def test_icp_with_personas_seniority(
        self, client, seed_companies_contacts, db
    ):
        """ICP with personas should extract seniority levels as filters."""
        data = seed_companies_contacts
        tenant = data["tenant"]
        headers = auth_header(client)
        headers["X-Namespace"] = tenant.slug

        _create_doc_with_icp(db, tenant.id, {
            "personas": [
                {"seniority": "c_level"},
                {"seniority": "director"},
            ],
        })

        resp = client.get("/api/playbook/contacts", headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()

        applied = body["filters"]["applied_filters"]
        assert "seniority_levels" in applied
        assert set(applied["seniority_levels"]) == {"c_level", "director"}


class TestConfirmContactSelection:
    """Tests for POST /api/playbook/contacts/confirm."""

    def test_confirm_saves_selections_and_advances_phase(
        self, client, seed_companies_contacts, db
    ):
        data = seed_companies_contacts
        tenant = data["tenant"]
        contacts = data["contacts"]
        headers = auth_header(client)
        headers["X-Namespace"] = tenant.slug

        # Create a doc with ICP (must be in contacts phase conceptually)
        doc = _create_doc_with_icp(db, tenant.id, {"industries": ["software_saas"]})
        doc.phase = "contacts"
        db.session.commit()

        # Confirm selection with 2 contacts
        contact_ids = [str(contacts[0].id), str(contacts[1].id)]
        resp = client.post(
            "/api/playbook/contacts/confirm",
            json={"selected_ids": contact_ids},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()

        assert body["success"] is True
        assert body["selected_count"] == 2
        assert body["phase"] == "messages"

        # Verify selections are persisted
        selections = body["playbook_selections"]
        # Handle SQLite text vs dict
        if isinstance(selections, str):
            selections = json.loads(selections)
        assert "contacts" in selections
        assert len(selections["contacts"]["selected_ids"]) == 2

    def test_confirm_with_empty_list_returns_error(
        self, client, seed_companies_contacts, db
    ):
        data = seed_companies_contacts
        tenant = data["tenant"]
        headers = auth_header(client)
        headers["X-Namespace"] = tenant.slug

        doc = _create_doc_with_icp(db, tenant.id)
        doc.phase = "contacts"
        db.session.commit()

        resp = client.post(
            "/api/playbook/contacts/confirm",
            json={"selected_ids": []},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_confirm_validates_contact_ids(
        self, client, seed_companies_contacts, db
    ):
        data = seed_companies_contacts
        tenant = data["tenant"]
        headers = auth_header(client)
        headers["X-Namespace"] = tenant.slug

        doc = _create_doc_with_icp(db, tenant.id)
        doc.phase = "contacts"
        db.session.commit()

        # Mix valid and invalid IDs
        valid_id = str(data["contacts"][0].id)
        resp = client.post(
            "/api/playbook/contacts/confirm",
            json={"selected_ids": [valid_id, "nonexistent-id-12345"]},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()

        # Should only include the valid ID
        selections = body["playbook_selections"]
        if isinstance(selections, str):
            selections = json.loads(selections)
        assert valid_id in selections["contacts"]["selected_ids"]

    def test_confirm_requires_auth(self, client, seed_tenant):
        resp = client.post(
            "/api/playbook/contacts/confirm",
            json={"selected_ids": ["some-id"]},
            headers={"X-Namespace": seed_tenant.slug},
        )
        assert resp.status_code == 401


class TestPlaybookSelectionsViaPUT:
    """Tests for playbook_selections persistence via PUT /api/playbook."""

    def test_save_playbook_selections(
        self, client, seed_tenant, seed_super_admin, db
    ):
        from api.models import StrategyDocument

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        doc = StrategyDocument(tenant_id=seed_tenant.id, version=1)
        db.session.add(doc)
        db.session.commit()

        resp = client.put(
            "/api/playbook",
            json={
                "playbook_selections": {
                    "contacts": {"selected_ids": ["id1", "id2"]}
                }
            },
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()

        selections = body["playbook_selections"]
        if isinstance(selections, str):
            selections = json.loads(selections)
        assert "contacts" in selections
        assert selections["contacts"]["selected_ids"] == ["id1", "id2"]

    def test_merge_playbook_selections(
        self, client, seed_tenant, seed_super_admin, db
    ):
        """PUT should merge into existing selections, not replace."""
        from api.models import StrategyDocument

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            version=1,
            playbook_selections=json.dumps({
                "contacts": {"selected_ids": ["old-id"]}
            }),
        )
        db.session.add(doc)
        db.session.commit()

        resp = client.put(
            "/api/playbook",
            json={
                "playbook_selections": {
                    "messages": {"draft_ids": ["msg1"]}
                }
            },
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()

        selections = body["playbook_selections"]
        if isinstance(selections, str):
            selections = json.loads(selections)
        # Both keys should exist
        assert "contacts" in selections
        assert "messages" in selections


class TestPhaseTransitionWithSelections:
    """Tests that phase transitions correctly validate selections."""

    def test_contacts_to_messages_requires_selections(
        self, client, seed_tenant, seed_super_admin, db
    ):
        from api.models import StrategyDocument

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug

        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            version=1,
            phase="contacts",
            extracted_data=json.dumps({"icp": {"industries": ["tech"]}}),
        )
        db.session.add(doc)
        db.session.commit()

        # Try to advance without selections
        resp = client.put(
            "/api/playbook/phase",
            json={"phase": "messages"},
            headers=headers,
        )
        assert resp.status_code == 422
        assert "contact" in resp.get_json()["error"].lower()

    def test_contacts_to_messages_succeeds_with_selections(
        self, client, seed_companies_contacts, db
    ):
        from api.models import StrategyDocument

        data = seed_companies_contacts
        tenant = data["tenant"]
        headers = auth_header(client)
        headers["X-Namespace"] = tenant.slug

        doc = StrategyDocument(
            tenant_id=tenant.id,
            version=1,
            phase="contacts",
            extracted_data=json.dumps({"icp": {"industries": ["tech"]}}),
            playbook_selections=json.dumps({
                "contacts": {"selected_ids": [str(data["contacts"][0].id)]}
            }),
        )
        db.session.add(doc)
        db.session.commit()

        resp = client.put(
            "/api/playbook/phase",
            json={"phase": "messages"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["phase"] == "messages"
