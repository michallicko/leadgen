"""Unit tests for LLM usage API routes."""

import json

import pytest

from api.models import LlmUsageLog, db
from tests.conftest import auth_header


def _seed_llm_logs(db_session, tenant_id, user_id=None, count=3):
    """Insert sample LLM usage log entries."""
    entries = []
    for i in range(count):
        entry = LlmUsageLog(
            tenant_id=str(tenant_id),
            user_id=str(user_id) if user_id else None,
            operation="csv_column_mapping",
            provider="anthropic",
            model="claude-sonnet-4-5-20250929",
            input_tokens=500 + i * 100,
            output_tokens=200 + i * 50,
            cost_usd=0.004500 + i * 0.001,
            duration_ms=1000 + i * 200,
            extra=json.dumps({"test_index": i}),
        )
        db_session.add(entry)
        entries.append(entry)
    db_session.commit()
    return entries


class TestSummaryAccess:
    def test_requires_auth(self, client, db):
        """Unauthenticated requests should return 401."""
        resp = client.get("/api/llm-usage/summary")
        assert resp.status_code == 401

    def test_non_super_admin_forbidden(self, client, seed_user_with_role):
        """Regular users (even admin role) without is_super_admin should get 403."""
        headers = auth_header(client, email="user@test.com")
        resp = client.get("/api/llm-usage/summary", headers=headers)
        assert resp.status_code == 403

    def test_super_admin_allowed(self, client, seed_companies_contacts):
        """Super admin should get 200."""
        headers = auth_header(client)
        resp = client.get("/api/llm-usage/summary", headers=headers)
        assert resp.status_code == 200


class TestSummaryData:
    def test_empty_summary(self, client, seed_companies_contacts):
        """Summary with no log entries should return zeros."""
        headers = auth_header(client)
        resp = client.get("/api/llm-usage/summary", headers=headers)
        body = resp.get_json()
        assert body["total_cost_usd"] == 0
        assert body["total_calls"] == 0
        assert body["total_input_tokens"] == 0
        assert body["total_output_tokens"] == 0
        assert body["by_tenant"] == []
        assert body["by_operation"] == []
        assert body["by_model"] == []

    def test_summary_with_data(self, client, seed_companies_contacts):
        """Summary should aggregate seeded log entries."""
        tenant = seed_companies_contacts["tenant"]
        _seed_llm_logs(db.session, tenant.id, count=3)

        headers = auth_header(client)
        resp = client.get("/api/llm-usage/summary", headers=headers)
        body = resp.get_json()

        assert body["total_calls"] == 3
        assert body["total_cost_usd"] > 0
        assert body["total_input_tokens"] > 0
        assert body["total_output_tokens"] > 0

        # by_tenant should have one entry
        assert len(body["by_tenant"]) == 1
        assert body["by_tenant"][0]["tenant_slug"] == "test-corp"
        assert body["by_tenant"][0]["calls"] == 3

        # by_operation should have one entry
        assert len(body["by_operation"]) == 1
        assert body["by_operation"][0]["operation"] == "csv_column_mapping"

        # by_model should have one entry
        assert len(body["by_model"]) == 1
        assert body["by_model"][0]["model"] == "claude-sonnet-4-5-20250929"


class TestLogsAccess:
    def test_requires_auth(self, client, db):
        resp = client.get("/api/llm-usage/logs")
        assert resp.status_code == 401

    def test_non_super_admin_forbidden(self, client, seed_user_with_role):
        headers = auth_header(client, email="user@test.com")
        resp = client.get("/api/llm-usage/logs", headers=headers)
        assert resp.status_code == 403


class TestLogsData:
    def test_empty_logs(self, client, seed_companies_contacts):
        headers = auth_header(client)
        resp = client.get("/api/llm-usage/logs", headers=headers)
        body = resp.get_json()
        assert body["total"] == 0
        assert body["logs"] == []
        assert body["page"] == 1

    def test_logs_pagination(self, client, seed_companies_contacts):
        """Pagination should respect page and per_page params."""
        tenant = seed_companies_contacts["tenant"]
        _seed_llm_logs(db.session, tenant.id, count=5)

        headers = auth_header(client)

        # Get page 1 with 2 per page
        resp = client.get("/api/llm-usage/logs?per_page=2&page=1", headers=headers)
        body = resp.get_json()
        assert body["total"] == 5
        assert len(body["logs"]) == 2
        assert body["page"] == 1
        assert body["per_page"] == 2

        # Get page 2
        resp2 = client.get("/api/llm-usage/logs?per_page=2&page=2", headers=headers)
        body2 = resp2.get_json()
        assert len(body2["logs"]) == 2
        assert body2["page"] == 2

    def test_logs_filter_by_operation(self, client, seed_companies_contacts):
        """Filter logs by operation name."""
        tenant = seed_companies_contacts["tenant"]
        _seed_llm_logs(db.session, tenant.id, count=2)

        # Add a log with different operation
        other = LlmUsageLog(
            tenant_id=str(tenant.id),
            operation="message_generation",
            provider="anthropic",
            model="claude-sonnet-4-5-20250929",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.002,
        )
        db.session.add(other)
        db.session.commit()

        headers = auth_header(client)
        resp = client.get("/api/llm-usage/logs?operation=message_generation", headers=headers)
        body = resp.get_json()
        assert body["total"] == 1
        assert body["logs"][0]["operation"] == "message_generation"

    def test_logs_include_tenant_slug(self, client, seed_companies_contacts):
        """Log entries should include the tenant slug."""
        tenant = seed_companies_contacts["tenant"]
        _seed_llm_logs(db.session, tenant.id, count=1)

        headers = auth_header(client)
        resp = client.get("/api/llm-usage/logs", headers=headers)
        body = resp.get_json()
        assert body["logs"][0]["tenant_slug"] == "test-corp"
