"""Unit tests for onboarding status and settings endpoints."""
import json

import pytest
from tests.conftest import auth_header


@pytest.fixture
def seed_admin_with_tenant(db, seed_tenant, seed_super_admin):
    """Give super admin a role on the test tenant so namespace resolves."""
    from api.models import UserTenantRole

    role = UserTenantRole(
        user_id=seed_super_admin.id,
        tenant_id=seed_tenant.id,
        role="admin",
        granted_by=seed_super_admin.id,
    )
    db.session.add(role)
    db.session.commit()
    return seed_super_admin


class TestOnboardingStatus:
    def test_returns_empty_namespace_status(
        self, client, seed_admin_with_tenant, seed_tenant
    ):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/tenants/onboarding-status", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["contact_count"] == 0
        assert data["campaign_count"] == 0
        assert data["has_strategy"] is False
        assert data["onboarding_path"] is None
        assert data["checklist_dismissed"] is False

    def test_requires_namespace(self, client, seed_super_admin):
        headers = auth_header(client)
        # No X-Namespace header and user has no default namespace role
        resp = client.get("/api/tenants/onboarding-status", headers=headers)
        # The resolve_tenant will pick the first role from the token.
        # Super admin without any role mappings in token → should get 400
        # Actually, super_admin token has empty roles dict, resolve_tenant returns None
        assert resp.status_code == 404

    def test_counts_contacts(
        self, client, seed_admin_with_tenant, seed_tenant, db
    ):
        from api.models import Contact

        for i in range(3):
            c = Contact(
                tenant_id=seed_tenant.id,
                first_name=f"Test{i}",
                last_name=f"User{i}",
                email_address=f"test{i}@example.com",
            )
            db.session.add(c)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/tenants/onboarding-status", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["contact_count"] == 3

    def test_counts_campaigns(
        self, client, seed_admin_with_tenant, seed_tenant, db
    ):
        from api.models import Campaign

        c = Campaign(tenant_id=seed_tenant.id, name="Test Campaign")
        db.session.add(c)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/tenants/onboarding-status", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["campaign_count"] == 1

    def test_detects_strategy(
        self, client, seed_admin_with_tenant, seed_tenant, db
    ):
        from api.models import StrategyDocument

        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            content="# My Strategy\nThis is a real strategy.",
            status="draft",
        )
        db.session.add(doc)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/tenants/onboarding-status", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["has_strategy"] is True

    def test_empty_strategy_not_detected(
        self, client, seed_admin_with_tenant, seed_tenant, db
    ):
        from api.models import StrategyDocument

        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            content="",
            status="draft",
        )
        db.session.add(doc)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/tenants/onboarding-status", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["has_strategy"] is False

    def test_reflects_onboarding_settings(
        self, client, seed_admin_with_tenant, seed_tenant, db
    ):
        seed_tenant.settings = json.dumps(
            {"onboarding_path": "strategy", "checklist_dismissed": True}
        )
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/tenants/onboarding-status", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["onboarding_path"] == "strategy"
        assert data["checklist_dismissed"] is True


class TestOnboardingSettingsPatch:
    def test_set_onboarding_path(
        self, client, seed_admin_with_tenant, seed_tenant
    ):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.patch(
            "/api/tenants/onboarding-settings",
            headers=headers,
            json={"onboarding_path": "strategy"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["onboarding_path"] == "strategy"

    def test_set_checklist_dismissed(
        self, client, seed_admin_with_tenant, seed_tenant
    ):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.patch(
            "/api/tenants/onboarding-settings",
            headers=headers,
            json={"checklist_dismissed": True},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["checklist_dismissed"] is True

    def test_invalid_onboarding_path_rejected(
        self, client, seed_admin_with_tenant, seed_tenant
    ):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.patch(
            "/api/tenants/onboarding-settings",
            headers=headers,
            json={"onboarding_path": "invalid"},
        )
        assert resp.status_code == 400

    def test_clear_onboarding_path(
        self, client, seed_admin_with_tenant, seed_tenant
    ):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        # Set first
        client.patch(
            "/api/tenants/onboarding-settings",
            headers=headers,
            json={"onboarding_path": "import"},
        )
        # Clear
        resp = client.patch(
            "/api/tenants/onboarding-settings",
            headers=headers,
            json={"onboarding_path": None},
        )
        assert resp.status_code == 200
        assert resp.get_json()["onboarding_path"] is None

    def test_requires_namespace(self, client, seed_super_admin):
        headers = auth_header(client)
        resp = client.patch(
            "/api/tenants/onboarding-settings",
            headers=headers,
            json={"onboarding_path": "strategy"},
        )
        assert resp.status_code == 404

    def test_regular_user_can_update(
        self, client, seed_user_with_role, seed_tenant
    ):
        headers = auth_header(client, email="user@test.com")
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.patch(
            "/api/tenants/onboarding-settings",
            headers=headers,
            json={"onboarding_path": "templates"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["onboarding_path"] == "templates"
