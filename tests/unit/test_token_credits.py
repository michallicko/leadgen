"""Unit tests for the token credit system (BL-056)."""

from decimal import Decimal

import pytest

from api.models import NamespaceTokenBudget, db
from api.services.budget import (
    BudgetExceededError,
    check_budget,
    consume_credits,
    release_reservation,
    reserve_credits,
)
from api.services.llm_logger import compute_credits, log_llm_usage


# ── Credit Calculation ──────────────────────────────────────────────


class TestComputeCredits:
    def test_basic_conversion(self):
        """1 credit = $0.001, so $0.010 = 10 credits."""
        assert compute_credits(Decimal("0.010")) == 10

    def test_zero_cost(self):
        assert compute_credits(Decimal("0")) == 0

    def test_large_cost(self):
        """$1.00 = 1000 credits."""
        assert compute_credits(Decimal("1.000000")) == 1000

    def test_small_cost_rounds_down(self):
        """$0.0001 = 0 credits (int truncation)."""
        assert compute_credits(Decimal("0.000100")) == 0

    def test_float_input(self):
        """Should handle float input too."""
        assert compute_credits(0.015) == 15


# ── Budget Enforcement ──────────────────────────────────────────────


class TestCheckBudget:
    def test_no_budget_returns_none(self, app, db, seed_tenant):
        """No budget row = unlimited."""
        result = check_budget(seed_tenant.id)
        assert result is None

    def test_monitor_mode_never_blocks(self, app, db, seed_tenant):
        """Monitor mode should never raise."""
        budget = NamespaceTokenBudget(
            tenant_id=str(seed_tenant.id),
            total_budget=100,
            used_credits=200,  # Over budget!
            enforcement_mode="monitor",
        )
        db.session.add(budget)
        db.session.flush()

        result = check_budget(seed_tenant.id, estimated_credits=50)
        assert result is not None
        assert result.enforcement_mode == "monitor"

    def test_hard_mode_blocks_when_exhausted(self, app, db, seed_tenant):
        """Hard mode should raise when remaining <= 0."""
        budget = NamespaceTokenBudget(
            tenant_id=str(seed_tenant.id),
            total_budget=100,
            used_credits=100,
            enforcement_mode="hard",
        )
        db.session.add(budget)
        db.session.flush()

        with pytest.raises(BudgetExceededError) as exc_info:
            check_budget(seed_tenant.id, estimated_credits=10)
        assert exc_info.value.remaining == 0

    def test_hard_mode_blocks_when_insufficient(self, app, db, seed_tenant):
        """Hard mode should raise when estimated > remaining."""
        budget = NamespaceTokenBudget(
            tenant_id=str(seed_tenant.id),
            total_budget=100,
            used_credits=80,
            enforcement_mode="hard",
        )
        db.session.add(budget)
        db.session.flush()

        with pytest.raises(BudgetExceededError):
            check_budget(seed_tenant.id, estimated_credits=30)

    def test_hard_mode_allows_within_budget(self, app, db, seed_tenant):
        """Hard mode should allow when sufficient credits."""
        budget = NamespaceTokenBudget(
            tenant_id=str(seed_tenant.id),
            total_budget=1000,
            used_credits=100,
            enforcement_mode="hard",
        )
        db.session.add(budget)
        db.session.flush()

        result = check_budget(seed_tenant.id, estimated_credits=50)
        assert result is not None

    def test_soft_mode_allows_up_to_120pct(self, app, db, seed_tenant):
        """Soft mode should allow up to 120% of budget."""
        budget = NamespaceTokenBudget(
            tenant_id=str(seed_tenant.id),
            total_budget=100,
            used_credits=110,  # Over 100% but under 120%
            enforcement_mode="soft",
        )
        db.session.add(budget)
        db.session.flush()

        result = check_budget(seed_tenant.id)
        assert result is not None

    def test_soft_mode_blocks_over_120pct(self, app, db, seed_tenant):
        """Soft mode should block at 120%."""
        budget = NamespaceTokenBudget(
            tenant_id=str(seed_tenant.id),
            total_budget=100,
            used_credits=120,
            enforcement_mode="soft",
        )
        db.session.add(budget)
        db.session.flush()

        with pytest.raises(BudgetExceededError):
            check_budget(seed_tenant.id)


# ── Credit Reservation ─────────────────────────────────────────────


class TestCreditReservation:
    def test_reserve_credits(self, app, db, seed_tenant):
        budget = NamespaceTokenBudget(
            tenant_id=str(seed_tenant.id),
            total_budget=1000,
            used_credits=0,
            reserved_credits=0,
            enforcement_mode="hard",
        )
        db.session.add(budget)
        db.session.flush()

        reserve_credits(seed_tenant.id, 500)
        db.session.refresh(budget)
        assert budget.reserved_credits == 500
        assert budget.remaining_credits == 500

    def test_consume_with_reservation(self, app, db, seed_tenant):
        """Consuming should move credits from reserved to used."""
        budget = NamespaceTokenBudget(
            tenant_id=str(seed_tenant.id),
            total_budget=1000,
            used_credits=0,
            reserved_credits=500,
            enforcement_mode="hard",
        )
        db.session.add(budget)
        db.session.flush()

        consume_credits(seed_tenant.id, 400, reserved=500)
        db.session.refresh(budget)
        assert budget.used_credits == 400
        assert budget.reserved_credits == 0
        assert budget.remaining_credits == 600

    def test_release_reservation(self, app, db, seed_tenant):
        """Releasing should return reserved credits."""
        budget = NamespaceTokenBudget(
            tenant_id=str(seed_tenant.id),
            total_budget=1000,
            used_credits=0,
            reserved_credits=500,
            enforcement_mode="hard",
        )
        db.session.add(budget)
        db.session.flush()

        release_reservation(seed_tenant.id, 500)
        db.session.refresh(budget)
        assert budget.reserved_credits == 0
        assert budget.remaining_credits == 1000

    def test_reservation_affects_remaining(self, app, db, seed_tenant):
        """Reserved credits should reduce remaining."""
        budget = NamespaceTokenBudget(
            tenant_id=str(seed_tenant.id),
            total_budget=1000,
            used_credits=200,
            reserved_credits=300,
            enforcement_mode="hard",
        )
        db.session.add(budget)
        db.session.flush()

        assert budget.remaining_credits == 500

    def test_hard_blocks_considering_reservations(self, app, db, seed_tenant):
        """Hard mode should consider reserved credits."""
        budget = NamespaceTokenBudget(
            tenant_id=str(seed_tenant.id),
            total_budget=1000,
            used_credits=500,
            reserved_credits=400,
            enforcement_mode="hard",
        )
        db.session.add(budget)
        db.session.flush()

        # 100 remaining, trying to use 200
        with pytest.raises(BudgetExceededError):
            check_budget(seed_tenant.id, estimated_credits=200)


# ── Log LLM Usage with Credits ─────────────────────────────────────


class TestLogLlmUsageCredits:
    def test_log_stores_credits(self, app, db, seed_tenant):
        """log_llm_usage should compute and store credits_consumed."""
        entry = log_llm_usage(
            tenant_id=seed_tenant.id,
            operation="playbook_chat",
            model="claude-sonnet-4-5-20250929",
            input_tokens=1000,
            output_tokens=500,
        )
        db.session.flush()

        assert entry.credits_consumed > 0
        # $3/1M * 1000 + $15/1M * 500 = $0.003 + $0.0075 = $0.0105 → 10 credits
        assert entry.credits_consumed == 10

    def test_log_consumes_from_budget(self, app, db, seed_tenant):
        """log_llm_usage should consume credits from budget."""
        budget = NamespaceTokenBudget(
            tenant_id=str(seed_tenant.id),
            total_budget=1000,
            used_credits=0,
            enforcement_mode="monitor",
        )
        db.session.add(budget)
        db.session.flush()

        log_llm_usage(
            tenant_id=seed_tenant.id,
            operation="playbook_chat",
            model="claude-sonnet-4-5-20250929",
            input_tokens=1000,
            output_tokens=500,
        )
        db.session.flush()
        db.session.refresh(budget)

        assert budget.used_credits == 10

    def test_log_with_reservation_releases(self, app, db, seed_tenant):
        """log_llm_usage with reserved_credits should release reservation."""
        budget = NamespaceTokenBudget(
            tenant_id=str(seed_tenant.id),
            total_budget=1000,
            used_credits=0,
            reserved_credits=50,
            enforcement_mode="monitor",
        )
        db.session.add(budget)
        db.session.flush()

        log_llm_usage(
            tenant_id=seed_tenant.id,
            operation="playbook_chat",
            model="claude-sonnet-4-5-20250929",
            input_tokens=1000,
            output_tokens=500,
            reserved_credits=50,
        )
        db.session.flush()
        db.session.refresh(budget)

        assert budget.used_credits == 10
        assert budget.reserved_credits == 0

    def test_log_without_budget_still_records_credits(self, app, db, seed_tenant):
        """Even without a budget, credits_consumed should be set."""
        entry = log_llm_usage(
            tenant_id=seed_tenant.id,
            operation="test_op",
            model="claude-sonnet-4-5-20250929",
            input_tokens=1000,
            output_tokens=500,
        )
        db.session.flush()
        assert entry.credits_consumed == 10


# ── Model Properties ────────────────────────────────────────────────


class TestNamespaceTokenBudget:
    def test_remaining_credits(self, app, db, seed_tenant):
        budget = NamespaceTokenBudget(
            tenant_id=str(seed_tenant.id),
            total_budget=1000,
            used_credits=300,
            reserved_credits=200,
        )
        assert budget.remaining_credits == 500

    def test_remaining_credits_floor_at_zero(self, app, db, seed_tenant):
        budget = NamespaceTokenBudget(
            tenant_id=str(seed_tenant.id),
            total_budget=100,
            used_credits=150,
            reserved_credits=0,
        )
        assert budget.remaining_credits == 0

    def test_usage_pct(self, app, db, seed_tenant):
        budget = NamespaceTokenBudget(
            tenant_id=str(seed_tenant.id),
            total_budget=1000,
            used_credits=247,
        )
        assert budget.usage_pct == 24.7

    def test_usage_pct_zero_budget(self, app, db, seed_tenant):
        budget = NamespaceTokenBudget(
            tenant_id=str(seed_tenant.id),
            total_budget=0,
            used_credits=0,
        )
        assert budget.usage_pct == 0

    def test_to_dict(self, app, db, seed_tenant):
        budget = NamespaceTokenBudget(
            tenant_id=str(seed_tenant.id),
            total_budget=50000,
            used_credits=12340,
            reserved_credits=500,
            enforcement_mode="soft",
            alert_threshold_pct=80,
        )
        d = budget.to_dict()
        assert d["total_budget"] == 50000
        assert d["used_credits"] == 12340
        assert d["remaining_credits"] == 37160
        assert d["usage_pct"] == 24.7
        assert d["enforcement_mode"] == "soft"


# ── API Routes ──────────────────────────────────────────────────────


class TestTokenRoutes:
    def _auth_header(self, client, email="admin@test.com"):
        resp = client.post(
            "/api/auth/login",
            json={"email": email, "password": "testpass123"},
        )
        token = resp.get_json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_get_tokens_no_budget(self, client, seed_tenant, seed_super_admin):
        """Should return null budget when none configured."""
        from api.models import UserTenantRole
        role = UserTenantRole(
            user_id=seed_super_admin.id,
            tenant_id=seed_tenant.id,
            role="admin",
            granted_by=seed_super_admin.id,
        )
        db.session.add(role)
        db.session.commit()

        headers = self._auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/admin/tokens", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["budget"] is None
        assert data["current_period"]["total_calls"] == 0

    def test_get_tokens_with_budget(self, client, seed_tenant, seed_super_admin):
        """Should return budget info."""
        from api.models import UserTenantRole
        role = UserTenantRole(
            user_id=seed_super_admin.id,
            tenant_id=seed_tenant.id,
            role="admin",
            granted_by=seed_super_admin.id,
        )
        db.session.add(role)

        budget = NamespaceTokenBudget(
            tenant_id=str(seed_tenant.id),
            total_budget=50000,
            used_credits=12340,
            enforcement_mode="soft",
        )
        db.session.add(budget)
        db.session.commit()

        headers = self._auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/admin/tokens", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["budget"]["total_budget"] == 50000
        assert data["budget"]["usage_pct"] == 24.7

    def test_get_token_status(self, client, seed_tenant, seed_super_admin):
        """Status endpoint should return lightweight budget info."""
        from api.models import UserTenantRole
        role = UserTenantRole(
            user_id=seed_super_admin.id,
            tenant_id=seed_tenant.id,
            role="admin",
            granted_by=seed_super_admin.id,
        )
        db.session.add(role)

        budget = NamespaceTokenBudget(
            tenant_id=str(seed_tenant.id),
            total_budget=1000,
            used_credits=800,
            enforcement_mode="hard",
            alert_threshold_pct=80,
        )
        db.session.add(budget)
        db.session.commit()

        headers = self._auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/admin/tokens/status", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["budget"]["usage_pct"] == 80.0
        assert data["budget"]["enforcement_mode"] == "hard"

    def test_set_budget_super_admin_only(self, client, seed_tenant, seed_super_admin, seed_user_with_role):
        """Non-super-admin should get 403 on budget management."""
        # Give user admin role
        from api.models import UserTenantRole
        utr = UserTenantRole.query.filter_by(user_id=seed_user_with_role.id).first()
        utr.role = "admin"
        db.session.commit()

        headers = self._auth_header(client, email="user@test.com")
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.put(
            "/api/admin/tokens/budget",
            headers=headers,
            json={"total_budget": 50000},
        )
        assert resp.status_code == 403

    def test_set_budget_creates_new(self, client, seed_tenant, seed_super_admin):
        """Super admin should be able to create a budget."""
        from api.models import UserTenantRole
        role = UserTenantRole(
            user_id=seed_super_admin.id,
            tenant_id=seed_tenant.id,
            role="admin",
            granted_by=seed_super_admin.id,
        )
        db.session.add(role)
        db.session.commit()

        headers = self._auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.put(
            "/api/admin/tokens/budget",
            headers=headers,
            json={
                "total_budget": 50000,
                "enforcement_mode": "soft",
                "reset_period": "monthly",
                "reset_day": 1,
                "alert_threshold_pct": 80,
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["budget"]["total_budget"] == 50000
        assert data["budget"]["enforcement_mode"] == "soft"
        assert data["budget"]["reset_period"] == "monthly"

    def test_topup_credits(self, client, seed_tenant, seed_super_admin):
        """Super admin should be able to top up credits."""
        from api.models import UserTenantRole
        role = UserTenantRole(
            user_id=seed_super_admin.id,
            tenant_id=seed_tenant.id,
            role="admin",
            granted_by=seed_super_admin.id,
        )
        db.session.add(role)

        budget = NamespaceTokenBudget(
            tenant_id=str(seed_tenant.id),
            total_budget=50000,
            used_credits=45000,
            enforcement_mode="soft",
        )
        db.session.add(budget)
        db.session.commit()

        headers = self._auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post(
            "/api/admin/tokens/topup",
            headers=headers,
            json={"credits": 10000},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["added_credits"] == 10000
        assert data["new_total"] == 60000
