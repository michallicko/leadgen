"""Tests for ICP Tiers and Buyer Personas CRUD endpoints (BL-198, BL-199)."""

import json


def auth_header(client, email="admin@test.com", password="testpass123"):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# ICP Tiers (BL-198)
# ---------------------------------------------------------------------------


class TestGetTiers:
    def test_returns_empty_list_when_no_tiers(
        self, client, seed_tenant, seed_super_admin
    ):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/playbook/strategy/tiers", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["tiers"] == []

    def test_returns_existing_tiers(self, client, seed_tenant, seed_super_admin, db):
        from api.models import StrategyDocument

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        tiers_data = [
            {
                "name": "Enterprise SaaS",
                "priority": 1,
                "criteria": {"industries": ["SaaS"]},
            },
            {"name": "Mid-Market", "priority": 2},
        ]
        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            extracted_data=json.dumps({"tiers": tiers_data}),
        )
        db.session.add(doc)
        db.session.commit()
        resp = client.get("/api/playbook/strategy/tiers", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["tiers"]) == 2
        assert data["tiers"][0]["name"] == "Enterprise SaaS"

    def test_requires_auth(self, client, seed_tenant):
        resp = client.get(
            "/api/playbook/strategy/tiers", headers={"X-Namespace": seed_tenant.slug}
        )
        assert resp.status_code == 401


class TestUpdateTiers:
    def test_creates_tiers_on_empty_doc(self, client, seed_tenant, seed_super_admin):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        tiers = [
            {"name": "Tier 1", "priority": 1, "criteria": {"industries": ["SaaS"]}},
        ]
        resp = client.put(
            "/api/playbook/strategy/tiers", json={"tiers": tiers}, headers=headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert len(data["tiers"]) == 1

    def test_replaces_existing_tiers(self, client, seed_tenant, seed_super_admin, db):
        from api.models import StrategyDocument

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            extracted_data=json.dumps(
                {"tiers": [{"name": "Old Tier"}], "icp": {"industries": ["SaaS"]}}
            ),
        )
        db.session.add(doc)
        db.session.commit()
        new_tiers = [{"name": "New Tier 1"}, {"name": "New Tier 2"}]
        resp = client.put(
            "/api/playbook/strategy/tiers", json={"tiers": new_tiers}, headers=headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["tiers"]) == 2
        assert data["tiers"][0]["name"] == "New Tier 1"

    def test_preserves_other_extracted_data(
        self, client, seed_tenant, seed_super_admin, db
    ):
        from api.models import StrategyDocument

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            extracted_data=json.dumps(
                {"icp": {"industries": ["SaaS"]}, "personas": [{"name": "VP Eng"}]}
            ),
        )
        db.session.add(doc)
        db.session.commit()
        resp = client.put(
            "/api/playbook/strategy/tiers",
            json={"tiers": [{"name": "New Tier"}]},
            headers=headers,
        )
        assert resp.status_code == 200
        # Verify icp and personas are preserved
        resp2 = client.get("/api/playbook", headers=headers)
        extracted = resp2.get_json()["extracted_data"]
        if isinstance(extracted, str):
            extracted = json.loads(extracted)
        assert extracted.get("icp") == {"industries": ["SaaS"]}
        assert len(extracted.get("personas", [])) == 1

    def test_rejects_non_array_tiers(self, client, seed_tenant, seed_super_admin):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.put(
            "/api/playbook/strategy/tiers",
            json={"tiers": "not an array"},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_requires_auth(self, client, seed_tenant):
        resp = client.put(
            "/api/playbook/strategy/tiers",
            json={"tiers": []},
            headers={"X-Namespace": seed_tenant.slug},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Buyer Personas (BL-199)
# ---------------------------------------------------------------------------


class TestGetPersonas:
    def test_returns_empty_list_when_no_personas(
        self, client, seed_tenant, seed_super_admin
    ):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/playbook/strategy/personas", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["personas"] == []

    def test_returns_existing_personas(self, client, seed_tenant, seed_super_admin, db):
        from api.models import StrategyDocument

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        personas_data = [
            {"name": "VP Engineering", "role": "VP Eng", "seniority": "VP"},
            {"name": "CTO", "role": "CTO", "seniority": "C-Level"},
        ]
        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            extracted_data=json.dumps({"personas": personas_data}),
        )
        db.session.add(doc)
        db.session.commit()
        resp = client.get("/api/playbook/strategy/personas", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["personas"]) == 2
        assert data["personas"][0]["name"] == "VP Engineering"

    def test_requires_auth(self, client, seed_tenant):
        resp = client.get(
            "/api/playbook/strategy/personas", headers={"X-Namespace": seed_tenant.slug}
        )
        assert resp.status_code == 401


class TestUpdatePersonas:
    def test_creates_personas_on_empty_doc(self, client, seed_tenant, seed_super_admin):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        personas = [
            {"name": "VP Eng", "role": "VP Engineering", "pain_points": ["Slow CI"]},
        ]
        resp = client.put(
            "/api/playbook/strategy/personas",
            json={"personas": personas},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert len(data["personas"]) == 1

    def test_replaces_existing_personas(
        self, client, seed_tenant, seed_super_admin, db
    ):
        from api.models import StrategyDocument

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            extracted_data=json.dumps({"personas": [{"name": "Old Persona"}]}),
        )
        db.session.add(doc)
        db.session.commit()
        new_personas = [{"name": "Persona A"}, {"name": "Persona B"}]
        resp = client.put(
            "/api/playbook/strategy/personas",
            json={"personas": new_personas},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["personas"]) == 2

    def test_preserves_other_extracted_data(
        self, client, seed_tenant, seed_super_admin, db
    ):
        from api.models import StrategyDocument

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            extracted_data=json.dumps(
                {"icp": {"industries": ["SaaS"]}, "tiers": [{"name": "T1"}]}
            ),
        )
        db.session.add(doc)
        db.session.commit()
        resp = client.put(
            "/api/playbook/strategy/personas",
            json={"personas": [{"name": "New Persona"}]},
            headers=headers,
        )
        assert resp.status_code == 200
        resp2 = client.get("/api/playbook", headers=headers)
        extracted = resp2.get_json()["extracted_data"]
        if isinstance(extracted, str):
            extracted = json.loads(extracted)
        assert extracted.get("icp") == {"industries": ["SaaS"]}
        assert len(extracted.get("tiers", [])) == 1

    def test_rejects_non_array_personas(self, client, seed_tenant, seed_super_admin):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.put(
            "/api/playbook/strategy/personas",
            json={"personas": "not an array"},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_requires_auth(self, client, seed_tenant):
        resp = client.put(
            "/api/playbook/strategy/personas",
            json={"personas": []},
            headers={"X-Namespace": seed_tenant.slug},
        )
        assert resp.status_code == 401
