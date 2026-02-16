"""Unit tests for custom field definition CRUD routes."""

import json

import pytest

from api.models import CustomFieldDefinition, db
from tests.conftest import auth_header


class TestListCustomFields:
    def test_list_empty(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.get("/api/custom-fields", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["custom_fields"] == []

    def test_list_with_defs(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        tenant_id = seed_companies_contacts["tenant"].id

        cfd = CustomFieldDefinition(
            tenant_id=str(tenant_id), entity_type="contact",
            field_key="email_2", field_label="Email 2", field_type="email",
        )
        db.session.add(cfd)
        db.session.commit()

        resp = client.get("/api/custom-fields", headers=headers)
        body = resp.get_json()
        assert len(body["custom_fields"]) == 1
        assert body["custom_fields"][0]["field_key"] == "email_2"

    def test_list_filter_by_entity_type(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        tenant_id = seed_companies_contacts["tenant"].id

        db.session.add(CustomFieldDefinition(
            tenant_id=str(tenant_id), entity_type="contact",
            field_key="email_2", field_label="Email 2", field_type="email",
        ))
        db.session.add(CustomFieldDefinition(
            tenant_id=str(tenant_id), entity_type="company",
            field_key="tax_id", field_label="Tax ID", field_type="text",
        ))
        db.session.commit()

        resp = client.get("/api/custom-fields?entity_type=contact", headers=headers)
        body = resp.get_json()
        assert len(body["custom_fields"]) == 1
        assert body["custom_fields"][0]["entity_type"] == "contact"

    def test_list_excludes_inactive(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        tenant_id = seed_companies_contacts["tenant"].id

        db.session.add(CustomFieldDefinition(
            tenant_id=str(tenant_id), entity_type="contact",
            field_key="old_field", field_label="Old", is_active=False,
        ))
        db.session.commit()

        resp = client.get("/api/custom-fields", headers=headers)
        assert len(resp.get_json()["custom_fields"]) == 0


class TestCreateCustomField:
    def test_create_success(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.post("/api/custom-fields", headers=headers, json={
            "entity_type": "contact",
            "field_label": "Secondary Email",
            "field_type": "email",
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["field_key"] == "secondary_email"
        assert body["field_label"] == "Secondary Email"
        assert body["field_type"] == "email"
        assert body["is_active"] is True

    def test_create_auto_key(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.post("/api/custom-fields", headers=headers, json={
            "entity_type": "company",
            "field_label": "Tax ID #",
        })
        assert resp.status_code == 201
        assert resp.get_json()["field_key"] == "tax_id"

    def test_create_explicit_key(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.post("/api/custom-fields", headers=headers, json={
            "entity_type": "contact",
            "field_label": "My Custom",
            "field_key": "custom_key_1",
        })
        assert resp.status_code == 201
        assert resp.get_json()["field_key"] == "custom_key_1"

    def test_create_duplicate_key_conflict(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        client.post("/api/custom-fields", headers=headers, json={
            "entity_type": "contact", "field_label": "Email 2",
        })
        resp = client.post("/api/custom-fields", headers=headers, json={
            "entity_type": "contact", "field_label": "Email 2",
        })
        assert resp.status_code == 409

    def test_create_reactivates_deleted(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        # Create and delete
        resp1 = client.post("/api/custom-fields", headers=headers, json={
            "entity_type": "contact", "field_label": "Temp Field",
        })
        field_id = resp1.get_json()["id"]
        client.delete(f"/api/custom-fields/{field_id}", headers=headers)

        # Re-create same key
        resp2 = client.post("/api/custom-fields", headers=headers, json={
            "entity_type": "contact", "field_label": "Temp Field Renamed",
            "field_key": "temp_field",
        })
        assert resp2.status_code == 200
        assert resp2.get_json()["is_active"] is True
        assert resp2.get_json()["field_label"] == "Temp Field Renamed"

    def test_create_missing_label(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.post("/api/custom-fields", headers=headers, json={
            "entity_type": "contact",
        })
        assert resp.status_code == 400

    def test_create_invalid_entity_type(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.post("/api/custom-fields", headers=headers, json={
            "entity_type": "message", "field_label": "Nope",
        })
        assert resp.status_code == 400

    def test_create_with_select_options(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.post("/api/custom-fields", headers=headers, json={
            "entity_type": "contact",
            "field_label": "Priority",
            "field_type": "select",
            "options": ["High", "Medium", "Low"],
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["options"] == ["High", "Medium", "Low"]


class TestUpdateCustomField:
    def test_update_label(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.post("/api/custom-fields", headers=headers, json={
            "entity_type": "contact", "field_label": "Old Label",
        })
        field_id = resp.get_json()["id"]

        resp2 = client.put(f"/api/custom-fields/{field_id}", headers=headers, json={
            "field_label": "New Label",
        })
        assert resp2.status_code == 200
        assert resp2.get_json()["field_label"] == "New Label"

    def test_update_not_found(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.put(
            "/api/custom-fields/00000000-0000-0000-0000-000000000000",
            headers=headers, json={"field_label": "X"},
        )
        assert resp.status_code == 404


class TestDeleteCustomField:
    def test_soft_delete(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.post("/api/custom-fields", headers=headers, json={
            "entity_type": "contact", "field_label": "To Delete",
        })
        field_id = resp.get_json()["id"]

        resp2 = client.delete(f"/api/custom-fields/{field_id}", headers=headers)
        assert resp2.status_code == 200

        # Should not appear in list
        resp3 = client.get("/api/custom-fields", headers=headers)
        keys = [d["field_key"] for d in resp3.get_json()["custom_fields"]]
        assert "to_delete" not in keys

    def test_delete_not_found(self, client, seed_companies_contacts):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        resp = client.delete(
            "/api/custom-fields/00000000-0000-0000-0000-000000000000",
            headers=headers,
        )
        assert resp.status_code == 404
