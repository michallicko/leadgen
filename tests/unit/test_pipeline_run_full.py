"""Tests for BL-171: Unified Pipeline Runner — single-click full enrichment chain."""

from unittest.mock import patch

import pytest

from tests.conftest import auth_header


@pytest.fixture
def seed_pipeline_data(db, seed_tenant, seed_super_admin):
    """Seed minimal data for pipeline run-full endpoint testing."""
    from api.models import (
        Company,
        Owner,
        Tag,
        UserTenantRole,
    )

    role = UserTenantRole(
        user_id=seed_super_admin.id,
        tenant_id=seed_tenant.id,
        role="admin",
        granted_by=seed_super_admin.id,
    )
    db.session.add(role)

    tag = Tag(tenant_id=seed_tenant.id, name="pipeline-test", is_active=True)
    owner = Owner(tenant_id=seed_tenant.id, name="Alice", is_active=True)
    db.session.add_all([tag, owner])
    db.session.flush()

    # Some companies
    for i in range(3):
        c = Company(
            tenant_id=seed_tenant.id,
            name=f"Company {i}",
            domain=f"company{i}.com",
            status="new",
            tag_id=tag.id,
            owner_id=owner.id,
        )
        db.session.add(c)

    db.session.commit()
    return {
        "tenant": seed_tenant,
        "tag": tag,
        "owner": owner,
    }


class TestRunFullEndpoint:
    @patch("api.routes.pipeline_routes.start_dag_pipeline")
    def test_run_full_creates_pipeline(self, mock_dag, client, seed_pipeline_data):
        """Test that run-full creates a pipeline run with correct stages."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            "/api/pipeline/run-full",
            headers=headers,
            json={
                "tag_name": "pipeline-test",
                "owner": "Alice",
            },
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert "pipeline_run_id" in body
        assert "stage_run_ids" in body
        assert "stage_order" in body
        assert body["mode"] == "full_pipeline"

        # Should include core stages
        stage_ids = body["stage_run_ids"]
        assert "l1" in stage_ids
        assert "l2" in stage_ids
        assert "person" in stage_ids

        # DAG executor should have been called
        assert mock_dag.called

    @patch("api.routes.pipeline_routes.start_dag_pipeline")
    def test_run_full_with_skip_stages(self, mock_dag, client, seed_pipeline_data):
        """Test skipping stages from the full chain."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            "/api/pipeline/run-full",
            headers=headers,
            json={
                "tag_name": "pipeline-test",
                "skip_stages": ["person"],
            },
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert "person" not in body["stage_run_ids"]
        assert "l1" in body["stage_run_ids"]
        assert "l2" in body["stage_run_ids"]

    @patch("api.routes.pipeline_routes.start_dag_pipeline")
    def test_run_full_with_include_stages(self, mock_dag, client, seed_pipeline_data):
        """Test including extra stages beyond the core chain."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            "/api/pipeline/run-full",
            headers=headers,
            json={
                "tag_name": "pipeline-test",
                "include_stages": ["registry"],
            },
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert "registry" in body["stage_run_ids"]
        assert "l1" in body["stage_run_ids"]

    def test_run_full_requires_tag_name(self, client, seed_pipeline_data):
        """Test that tag_name is required."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            "/api/pipeline/run-full",
            headers=headers,
            json={},
        )
        assert resp.status_code == 400
        assert "tag_name" in resp.get_json()["error"]

    @patch("api.routes.pipeline_routes.start_dag_pipeline")
    def test_run_full_blocks_duplicate(self, mock_dag, client, seed_pipeline_data):
        """Test that a second run-full is blocked while first is running."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        # First run
        resp1 = client.post(
            "/api/pipeline/run-full",
            headers=headers,
            json={"tag_name": "pipeline-test"},
        )
        assert resp1.status_code == 201

        # Second run should fail
        resp2 = client.post(
            "/api/pipeline/run-full",
            headers=headers,
            json={"tag_name": "pipeline-test"},
        )
        assert resp2.status_code == 409

    def test_run_full_unknown_tag(self, client, seed_pipeline_data):
        """Test with a non-existent tag."""
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.post(
            "/api/pipeline/run-full",
            headers=headers,
            json={"tag_name": "nonexistent"},
        )
        assert resp.status_code == 404
