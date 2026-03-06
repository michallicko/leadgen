"""Tests for agent cost controls module (BL-273)."""

from unittest.mock import MagicMock


from api.agents.cost_controls import (
    BudgetCheck,
    BudgetStatus,
    OperationEstimate,
    check_budget,
    estimate_operation,
    get_tenant_budget,
    CONFIRMATION_THRESHOLD_CREDITS,
    DEFAULT_MONTHLY_TOKEN_LIMIT,
    OPERATION_ESTIMATES,
)


# ---------------------------------------------------------------------------
# BudgetStatus tests
# ---------------------------------------------------------------------------


class TestBudgetStatus:
    def test_enum_values(self):
        assert BudgetStatus.OK.value == "ok"
        assert BudgetStatus.WARNING.value == "warning"
        assert BudgetStatus.CRITICAL.value == "critical"
        assert BudgetStatus.EXCEEDED.value == "exceeded"


# ---------------------------------------------------------------------------
# BudgetCheck tests
# ---------------------------------------------------------------------------


class TestBudgetCheck:
    def test_to_dict_ok(self):
        check = BudgetCheck(
            tenant_id="t1",
            status=BudgetStatus.OK,
            usage_percent=30.0,
            tokens_used=300_000,
            tokens_limit=1_000_000,
            tokens_remaining=700_000,
        )
        d = check.to_dict()
        assert d["status"] == "ok"
        assert d["usage_percent"] == 30.0
        assert d["tokens_remaining"] == 700_000
        assert "warning_message" not in d
        assert "block" not in d

    def test_to_dict_warning(self):
        check = BudgetCheck(
            tenant_id="t1",
            status=BudgetStatus.WARNING,
            usage_percent=80.0,
            tokens_used=800_000,
            tokens_limit=1_000_000,
            tokens_remaining=200_000,
            warning_message="You've used 80% of budget",
        )
        d = check.to_dict()
        assert d["status"] == "warning"
        assert d["warning_message"] == "You've used 80% of budget"

    def test_to_dict_exceeded(self):
        check = BudgetCheck(
            tenant_id="t1",
            status=BudgetStatus.EXCEEDED,
            usage_percent=105.0,
            tokens_used=1_050_000,
            tokens_limit=1_000_000,
            tokens_remaining=0,
            warning_message="Limit reached",
            block=True,
        )
        d = check.to_dict()
        assert d["block"] is True


# ---------------------------------------------------------------------------
# OperationEstimate tests
# ---------------------------------------------------------------------------


class TestOperationEstimate:
    def test_to_dict(self):
        est = OperationEstimate(
            model="claude-haiku-4-5-20251001",
            operation_name="research",
            estimated_input_tokens=5000,
            estimated_output_tokens=2000,
            estimated_total_tokens=7000,
            estimated_cost_usd="0.012000",
            estimated_credits=12,
            requires_confirmation=False,
        )
        d = est.to_dict()
        assert d["model"] == "claude-haiku-4-5-20251001"
        assert d["operation"] == "research"
        assert d["estimated_total_tokens"] == 7000
        assert d["requires_confirmation"] is False

    def test_to_dict_with_budget(self):
        budget = BudgetCheck(
            tenant_id="t1",
            status=BudgetStatus.WARNING,
            usage_percent=80.0,
            tokens_used=800_000,
            tokens_limit=1_000_000,
            tokens_remaining=200_000,
        )
        est = OperationEstimate(
            model="claude-haiku-4-5-20251001",
            operation_name="research",
            estimated_input_tokens=5000,
            estimated_output_tokens=2000,
            estimated_total_tokens=7000,
            estimated_cost_usd="0.012000",
            estimated_credits=12,
            budget_after=budget,
            requires_confirmation=True,
        )
        d = est.to_dict()
        assert "budget_after" in d
        assert d["budget_after"]["status"] == "warning"


# ---------------------------------------------------------------------------
# estimate_operation tests (no DB)
# ---------------------------------------------------------------------------


class TestEstimateOperation:
    def test_known_operation(self):
        est = estimate_operation("claude-haiku-4-5-20251001", "research")
        assert est.operation_name == "research"
        assert est.estimated_input_tokens == OPERATION_ESTIMATES["research"]["input"]
        assert est.estimated_output_tokens == OPERATION_ESTIMATES["research"]["output"]
        assert est.estimated_credits >= 0

    def test_unknown_operation_uses_general(self):
        est = estimate_operation("claude-haiku-4-5-20251001", "something_custom")
        assert est.estimated_input_tokens == OPERATION_ESTIMATES["general"]["input"]

    def test_expensive_model_requires_confirmation(self):
        # Opus is expensive enough to trigger confirmation
        est = estimate_operation("claude-opus-4-6", "strategy_generation")
        # At Opus pricing, strategy_generation (8K in, 4K out) =
        # 8000/1M * 15 + 4000/1M * 75 = 0.12 + 0.30 = $0.42 = 420 credits
        assert est.requires_confirmation
        assert est.estimated_credits >= CONFIRMATION_THRESHOLD_CREDITS

    def test_cheap_operation_no_confirmation(self):
        est = estimate_operation("claude-haiku-4-5-20251001", "general")
        # Haiku general: 2000/1M * 0.80 + 1000/1M * 4.0 = 0.0016 + 0.004 = ~5.6 credits
        assert not est.requires_confirmation


# ---------------------------------------------------------------------------
# get_tenant_budget tests
# ---------------------------------------------------------------------------


class TestGetTenantBudget:
    def test_returns_defaults_when_no_row(self):
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        budget = get_tenant_budget(mock_session, "tenant-1")
        assert budget["monthly_token_limit"] == DEFAULT_MONTHLY_TOKEN_LIMIT
        assert budget["warn_at_percent"] == 75
        assert budget["hard_limit_percent"] == 100

    def test_returns_db_values(self):
        mock_session = MagicMock()
        mock_row = MagicMock()
        mock_row.monthly_token_limit = 5_000_000
        mock_row.warn_at_percent = 50
        mock_row.hard_limit_percent = 100
        mock_row.current_period_start = "2026-03-01"
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result

        budget = get_tenant_budget(mock_session, "tenant-1")
        assert budget["monthly_token_limit"] == 5_000_000
        assert budget["warn_at_percent"] == 50

    def test_returns_defaults_on_exception(self):
        mock_session = MagicMock()
        mock_session.execute.side_effect = Exception("DB error")

        budget = get_tenant_budget(mock_session, "tenant-1")
        assert budget["monthly_token_limit"] == DEFAULT_MONTHLY_TOKEN_LIMIT


# ---------------------------------------------------------------------------
# check_budget tests
# ---------------------------------------------------------------------------


class TestCheckBudget:
    def _make_mock_session(
        self,
        budget_limit: int = 1_000_000,
        tokens_used: int = 0,
    ):
        """Create a mock DB session for budget checks."""
        mock_session = MagicMock()

        # First call: get_tenant_budget
        budget_row = MagicMock()
        budget_row.monthly_token_limit = budget_limit
        budget_row.warn_at_percent = 75
        budget_row.hard_limit_percent = 100
        budget_row.current_period_start = "2026-03-01"

        # Second call: SUM tokens
        usage_row = MagicMock()
        usage_row.total_tokens = tokens_used

        budget_result = MagicMock()
        budget_result.fetchone.return_value = budget_row
        usage_result = MagicMock()
        usage_result.fetchone.return_value = usage_row

        mock_session.execute.side_effect = [budget_result, usage_result]
        return mock_session

    def test_ok_status(self):
        session = self._make_mock_session(tokens_used=100_000)
        result = check_budget(session, "t1")
        assert result.status == BudgetStatus.OK
        assert result.warning_message is None
        assert not result.block

    def test_warning_status(self):
        session = self._make_mock_session(tokens_used=800_000)
        result = check_budget(session, "t1")
        assert result.status == BudgetStatus.WARNING
        assert result.warning_message is not None
        assert not result.block

    def test_critical_status(self):
        session = self._make_mock_session(tokens_used=920_000)
        result = check_budget(session, "t1")
        assert result.status == BudgetStatus.CRITICAL
        assert not result.block

    def test_exceeded_status(self):
        session = self._make_mock_session(tokens_used=1_100_000)
        result = check_budget(session, "t1")
        assert result.status == BudgetStatus.EXCEEDED
        assert result.block

    def test_additional_tokens_counted(self):
        # 90K used + 15K additional = 105K out of 100K = exceeded
        session = self._make_mock_session(budget_limit=100_000, tokens_used=90_000)
        result = check_budget(session, "t1", additional_tokens=15_000)
        assert result.status == BudgetStatus.EXCEEDED
        assert result.tokens_used == 105_000

    def test_handles_db_error(self):
        mock_session = MagicMock()
        # First call succeeds (get_tenant_budget)
        budget_row = MagicMock()
        budget_row.monthly_token_limit = 1_000_000
        budget_row.warn_at_percent = 75
        budget_row.hard_limit_percent = 100
        budget_row.current_period_start = "2026-03-01"
        budget_result = MagicMock()
        budget_result.fetchone.return_value = budget_row
        # Second call fails (SUM query)
        mock_session.execute.side_effect = [budget_result, Exception("DB down")]

        result = check_budget(mock_session, "t1")
        # Should still return a result with 0 usage
        assert result.status == BudgetStatus.OK
