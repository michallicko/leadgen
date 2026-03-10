"""Unit tests for IAM sync service."""
import pytest
from api.models import Tenant, User, UserTenantRole, db as _db
from api.services.iam_sync import find_or_create_local_user, sync_iam_roles


class TestFindOrCreateLocalUser:
    def test_create_new_user(self, client, db):
        """When no existing user matches, create a new one."""
        iam_user = {"id": "iam-uuid-001", "email": "new@test.com", "name": "New User"}
        user = find_or_create_local_user(iam_user)

        assert user is not None
        assert user.email == "new@test.com"
        assert user.display_name == "New User"
        assert user.iam_user_id == "iam-uuid-001"
        assert user.auth_provider == "iam"
        assert user.password_hash is None

    def test_find_by_iam_user_id(self, client, db):
        """If user already linked by iam_user_id, return them."""
        existing = User(
            email="linked@test.com",
            display_name="Linked",
            iam_user_id="iam-uuid-002",
            auth_provider="iam",
        )
        db.session.add(existing)
        db.session.commit()

        iam_user = {"id": "iam-uuid-002", "email": "linked@test.com", "name": "Linked"}
        user = find_or_create_local_user(iam_user)

        assert user.id == existing.id
        assert user.iam_user_id == "iam-uuid-002"

    def test_link_existing_user_by_email(self, client, db):
        """If user exists by email but not linked to IAM, link them."""
        existing = User(
            email="legacy@test.com",
            password_hash=None,
            display_name="Legacy",
        )
        db.session.add(existing)
        db.session.commit()

        iam_user = {"id": "iam-uuid-003", "email": "legacy@test.com", "name": "Legacy Updated"}
        user = find_or_create_local_user(iam_user)

        assert user.id == existing.id
        assert user.iam_user_id == "iam-uuid-003"
        assert user.auth_provider == "iam"
        assert user.display_name == "Legacy Updated"

    def test_update_display_name_on_existing_iam_user(self, client, db):
        """When an IAM-linked user logs in with a changed name, update it."""
        existing = User(
            email="nameduser@test.com",
            display_name="Old Name",
            iam_user_id="iam-uuid-004",
            auth_provider="iam",
        )
        db.session.add(existing)
        db.session.commit()

        iam_user = {"id": "iam-uuid-004", "email": "nameduser@test.com", "name": "New Name"}
        user = find_or_create_local_user(iam_user)

        assert user.display_name == "New Name"

    def test_create_user_without_name(self, client, db):
        """When IAM user has no name, use email as display_name."""
        iam_user = {"id": "iam-uuid-005", "email": "noname@test.com"}
        user = find_or_create_local_user(iam_user)

        assert user.display_name == "noname@test.com"


class TestSyncIamRoles:
    def test_grant_new_role(self, client, db, seed_tenant):
        """IAM permission for a known tenant creates a local role."""
        user = User(
            email="roletest@test.com",
            display_name="Role Test",
            iam_user_id="iam-role-001",
            auth_provider="iam",
        )
        db.session.add(user)
        db.session.commit()

        permissions = [
            {"app": "leadgen", "role": "editor", "scope": seed_tenant.slug},
        ]
        sync_iam_roles(user, permissions)

        roles = UserTenantRole.query.filter_by(user_id=user.id).all()
        assert len(roles) == 1
        assert roles[0].role == "editor"
        assert roles[0].tenant_id == seed_tenant.id

    def test_upgrade_existing_role(self, client, db, seed_tenant):
        """IAM says admin, local has viewer -> upgrade to admin."""
        user = User(
            email="upgrade@test.com",
            display_name="Upgrade",
            iam_user_id="iam-role-002",
            auth_provider="iam",
        )
        db.session.add(user)
        db.session.flush()

        role = UserTenantRole(user_id=user.id, tenant_id=seed_tenant.id, role="viewer")
        db.session.add(role)
        db.session.commit()

        permissions = [
            {"app": "leadgen", "role": "admin", "scope": seed_tenant.slug},
        ]
        sync_iam_roles(user, permissions)

        updated = UserTenantRole.query.filter_by(user_id=user.id, tenant_id=seed_tenant.id).first()
        assert updated.role == "admin"

    def test_downgrade_existing_role(self, client, db, seed_tenant):
        """IAM says viewer, local has admin -> downgrade to viewer."""
        user = User(
            email="downgrade@test.com",
            display_name="Downgrade",
            iam_user_id="iam-role-003",
            auth_provider="iam",
        )
        db.session.add(user)
        db.session.flush()

        role = UserTenantRole(user_id=user.id, tenant_id=seed_tenant.id, role="admin")
        db.session.add(role)
        db.session.commit()

        permissions = [
            {"app": "leadgen", "role": "viewer", "scope": seed_tenant.slug},
        ]
        sync_iam_roles(user, permissions)

        updated = UserTenantRole.query.filter_by(user_id=user.id, tenant_id=seed_tenant.id).first()
        assert updated.role == "viewer"

    def test_preserve_local_only_roles(self, client, db, seed_tenant):
        """Roles for tenants not in IAM permissions are preserved."""
        user = User(
            email="preserve@test.com",
            display_name="Preserve",
            iam_user_id="iam-role-004",
            auth_provider="iam",
        )
        db.session.add(user)
        db.session.flush()

        # Existing local role
        role = UserTenantRole(user_id=user.id, tenant_id=seed_tenant.id, role="admin")
        db.session.add(role)
        db.session.commit()

        # IAM has no permissions at all
        sync_iam_roles(user, [])

        # Local role should be preserved
        roles = UserTenantRole.query.filter_by(user_id=user.id).all()
        assert len(roles) == 1
        assert roles[0].role == "admin"

    def test_skip_unknown_tenant(self, client, db):
        """IAM scope for a non-existent tenant is silently skipped."""
        user = User(
            email="unknown@test.com",
            display_name="Unknown",
            iam_user_id="iam-role-005",
            auth_provider="iam",
        )
        db.session.add(user)
        db.session.commit()

        permissions = [
            {"app": "leadgen", "role": "editor", "scope": "nonexistent-tenant"},
        ]
        sync_iam_roles(user, permissions)

        roles = UserTenantRole.query.filter_by(user_id=user.id).all()
        assert len(roles) == 0

    def test_skip_non_leadgen_permissions(self, client, db, seed_tenant):
        """Permissions for other apps are ignored."""
        user = User(
            email="otherapp@test.com",
            display_name="OtherApp",
            iam_user_id="iam-role-006",
            auth_provider="iam",
        )
        db.session.add(user)
        db.session.commit()

        permissions = [
            {"app": "some-other-app", "role": "admin", "scope": seed_tenant.slug},
        ]
        sync_iam_roles(user, permissions)

        roles = UserTenantRole.query.filter_by(user_id=user.id).all()
        assert len(roles) == 0

    def test_super_admin_from_wildcard_scope(self, client, db):
        """IAM admin with wildcard scope promotes to is_super_admin."""
        user = User(
            email="superadmin@test.com",
            display_name="SuperAdmin",
            iam_user_id="iam-role-007",
            auth_provider="iam",
            is_super_admin=False,
        )
        db.session.add(user)
        db.session.commit()

        permissions = [
            {"app": "leadgen", "role": "admin", "scope": "*"},
        ]
        sync_iam_roles(user, permissions)

        db.session.refresh(user)
        assert user.is_super_admin is True

    def test_super_admin_from_no_scope(self, client, db):
        """IAM admin with no scope promotes to is_super_admin."""
        user = User(
            email="superadmin2@test.com",
            display_name="SuperAdmin2",
            iam_user_id="iam-role-008",
            auth_provider="iam",
            is_super_admin=False,
        )
        db.session.add(user)
        db.session.commit()

        permissions = [
            {"app": "leadgen", "role": "admin", "scope": None},
        ]
        sync_iam_roles(user, permissions)

        db.session.refresh(user)
        assert user.is_super_admin is True


class TestLogoutEndpoint:
    def test_logout_returns_ok(self, client, db):
        """Logout endpoint always returns 200 ok."""
        resp = client.post("/api/auth/logout", json={"refresh_token": "some-token"})
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"

    def test_logout_no_body(self, client, db):
        """Logout without body still returns 200."""
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200


class TestModelChanges:
    def test_user_iam_fields(self, client, db):
        """User model has iam_user_id and auth_provider fields."""
        user = User(
            email="fields@test.com",
            display_name="Fields",
            iam_user_id="iam-uuid-100",
            auth_provider="iam",
        )
        db.session.add(user)
        db.session.commit()

        found = User.query.filter_by(iam_user_id="iam-uuid-100").first()
        assert found is not None
        assert found.auth_provider == "iam"
        assert found.password_hash is None

    def test_to_dict_includes_iam_fields(self, client, db):
        """User.to_dict() includes iam_user_id and auth_provider."""
        user = User(
            email="dict@test.com",
            display_name="Dict",
            iam_user_id="iam-uuid-101",
            auth_provider="iam",
        )
        db.session.add(user)
        db.session.commit()

        d = user.to_dict()
        assert d["iam_user_id"] == "iam-uuid-101"
        assert d["auth_provider"] == "iam"

    def test_to_dict_default_auth_provider(self, client, db):
        """Legacy user without auth_provider defaults to 'local'."""
        user = User(
            email="legacy2@test.com",
            password_hash="$2b$12$fake",
            display_name="Legacy",
        )
        db.session.add(user)
        db.session.commit()

        d = user.to_dict()
        assert d["auth_provider"] == "local"
        assert d["iam_user_id"] is None
