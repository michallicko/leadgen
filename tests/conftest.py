"""Shared test fixtures for the leadgen pipeline test suite."""
import json
import os
import uuid

import pytest
from sqlalchemy import String, Text, event
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.schema import ColumnDefault

# Use SQLite for tests (no PG dependency needed for unit tests)
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-do-not-use-in-prod")
os.environ.setdefault("CORS_ORIGINS", "*")

from api import create_app
from api.models import db as _db
from api.auth import hash_password


def _uuid_default():
    return str(uuid.uuid4())


def _patch_pg_types_for_sqlite(app):
    """Replace PostgreSQL-specific column types with SQLite-compatible ones."""
    from sqlalchemy import text as sa_text
    with app.app_context():
        for table in _db.metadata.tables.values():
            for column in table.columns:
                if isinstance(column.type, UUID):
                    column.type = String(36)
                    if column.server_default is not None and "uuid_generate" in str(column.server_default.arg):
                        column.server_default = None
                        column.default = ColumnDefault(_uuid_default)
                elif isinstance(column.type, JSONB):
                    column.type = Text()
                    if column.server_default is not None:
                        column.server_default = None
                # Replace now() with CURRENT_TIMESTAMP for SQLite
                if column.server_default is not None:
                    default_text = str(column.server_default.arg)
                    if "now()" in default_text:
                        column.server_default = _db.DefaultClause(sa_text("CURRENT_TIMESTAMP"))

    # Register SQLite adapter for dicts (JSONB → TEXT)
    import sqlite3
    sqlite3.register_adapter(dict, lambda d: json.dumps(d))
    sqlite3.register_adapter(list, lambda l: json.dumps(l))


@pytest.fixture(scope="session")
def app():
    """Create Flask application for testing."""
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    _patch_pg_types_for_sqlite(app)
    return app


@pytest.fixture(scope="function")
def db(app):
    """Create fresh database tables for each test."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.rollback()
        _db.drop_all()


@pytest.fixture(scope="function")
def client(app, db):
    """Flask test client with clean DB."""
    with app.test_client() as client:
        with app.app_context():
            yield client


@pytest.fixture
def seed_tenant(db):
    """Create a test tenant."""
    from api.models import Tenant
    tenant = Tenant(name="Test Corp", slug="test-corp", is_active=True)
    db.session.add(tenant)
    db.session.commit()
    return tenant


@pytest.fixture
def seed_super_admin(db):
    """Create a super admin user."""
    from api.models import User
    user = User(
        email="admin@test.com",
        password_hash=hash_password("testpass123"),
        display_name="Admin User",
        is_super_admin=True,
        is_active=True,
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def seed_user_with_role(db, seed_tenant, seed_super_admin):
    """Create a regular user with a tenant role."""
    from api.models import User, UserTenantRole
    user = User(
        email="user@test.com",
        password_hash=hash_password("testpass123"),
        display_name="Regular User",
        is_super_admin=False,
        is_active=True,
    )
    db.session.add(user)
    db.session.flush()

    role = UserTenantRole(
        user_id=user.id,
        tenant_id=seed_tenant.id,
        role="viewer",
        granted_by=seed_super_admin.id,
    )
    db.session.add(role)
    db.session.commit()
    return user


def auth_header(client, email="admin@test.com", password="testpass123"):
    """Helper: login and return Authorization header dict."""
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
