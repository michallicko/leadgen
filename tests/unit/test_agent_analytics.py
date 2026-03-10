"""Tests for agent analytics module (BL-272)."""

from decimal import Decimal


from api.agents.analytics import (
    MetricsCollector,
    TurnMetrics,
    estimate_cost,
    estimate_operation_cost,
)


# ---------------------------------------------------------------------------
# Cost estimation tests
# ---------------------------------------------------------------------------


class TestEstimateCost:
    def test_haiku_pricing(self):
        cost = estimate_cost("claude-haiku-4-5-20251001", 1_000_000, 1_000_000)
        # Input: $0.80, Output: $4.00
        assert cost == Decimal("4.8")

    def test_sonnet_pricing(self):
        cost = estimate_cost("claude-sonnet-4-5-20241022", 1_000_000, 1_000_000)
        # Input: $3.00, Output: $15.00
        assert cost == Decimal("18.0")

    def test_opus_pricing(self):
        cost = estimate_cost("claude-opus-4-6", 1_000_000, 1_000_000)
        # Input: $15.00, Output: $75.00
        assert cost == Decimal("90.0")

    def test_small_token_count(self):
        cost = estimate_cost("claude-haiku-4-5-20251001", 1000, 500)
        # Input: 0.001 * 0.80 = 0.0008, Output: 0.0005 * 4.0 = 0.002
        expected = Decimal("0.0008") + Decimal("0.002")
        assert cost == expected

    def test_zero_tokens(self):
        cost = estimate_cost("claude-haiku-4-5-20251001", 0, 0)
        assert cost == Decimal("0")

    def test_unknown_model_uses_default(self):
        cost = estimate_cost("unknown-model", 1_000_000, 1_000_000)
        # Default: Input: $3.00, Output: $15.00
        assert cost == Decimal("18.0")


class TestEstimateOperationCost:
    def test_returns_breakdown(self):
        result = estimate_operation_cost("claude-haiku-4-5-20251001", 5000, 2000)
        assert result["model"] == "claude-haiku-4-5-20251001"
        assert result["estimated_input_tokens"] == 5000
        assert result["estimated_output_tokens"] == 2000
        assert "estimated_cost_usd" in result
        assert "estimated_credits" in result
        assert result["estimated_credits"] >= 0


# ---------------------------------------------------------------------------
# MetricsCollector tests
# ---------------------------------------------------------------------------


class TestMetricsCollector:
    def test_init_with_defaults(self):
        collector = MetricsCollector(tenant_id="t1")
        assert collector.tenant_id == "t1"
        assert collector.trace_id  # auto-generated

    def test_init_with_trace_id(self):
        collector = MetricsCollector(trace_id="trace-123", tenant_id="t1", user_id="u1")
        assert collector.trace_id == "trace-123"
        assert collector.user_id == "u1"

    def test_record_llm_call(self):
        collector = MetricsCollector(tenant_id="t1")
        collector.record_llm_call("claude-haiku-4-5-20251001", 1000, 500)
        metrics = collector.finalize(duration_ms=100)
        assert metrics.model == "claude-haiku-4-5-20251001"
        assert metrics.input_tokens == 1000
        assert metrics.output_tokens == 500
        assert metrics.cost_usd > 0

    def test_accumulates_multiple_llm_calls(self):
        collector = MetricsCollector(tenant_id="t1")
        collector.record_llm_call("claude-haiku-4-5-20251001", 1000, 500)
        collector.record_llm_call("claude-haiku-4-5-20251001", 2000, 1000)
        metrics = collector.finalize(duration_ms=200)
        assert metrics.input_tokens == 3000
        assert metrics.output_tokens == 1500

    def test_record_tool_call(self):
        collector = MetricsCollector(tenant_id="t1")
        collector.record_tool_call("web_search", 150, "success")
        collector.record_tool_call("research", 500, "error", "API timeout")
        metrics = collector.finalize(duration_ms=700)
        assert len(metrics.tool_calls) == 2
        assert metrics.tool_calls[0]["tool_name"] == "web_search"
        assert metrics.tool_calls[0]["status"] == "success"
        assert metrics.tool_calls[1]["error"] == "API timeout"

    def test_finalize_returns_turn_metrics(self):
        collector = MetricsCollector(
            trace_id="t-1", tenant_id="tenant-1", user_id="user-1", turn_index=3
        )
        collector.record_llm_call("claude-haiku-4-5-20251001", 500, 200)
        metrics = collector.finalize(duration_ms=50)

        assert isinstance(metrics, TurnMetrics)
        assert metrics.trace_id == "t-1"
        assert metrics.tenant_id == "tenant-1"
        assert metrics.user_id == "user-1"
        assert metrics.turn_index == 3
        assert metrics.duration_ms == 50

    def test_finalize_with_timer(self):
        collector = MetricsCollector(tenant_id="t1")
        collector.start_timer()
        # Do some work
        collector.record_llm_call("claude-haiku-4-5-20251001", 100, 50)
        metrics = collector.finalize()
        assert metrics.duration_ms >= 0


# ---------------------------------------------------------------------------
# TurnMetrics tests
# ---------------------------------------------------------------------------


class TestTurnMetrics:
    def test_dataclass_fields(self):
        metrics = TurnMetrics(
            trace_id="t-1",
            tenant_id="tenant-1",
            model="claude-haiku-4-5-20251001",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=Decimal("0.003"),
            duration_ms=100,
        )
        assert metrics.trace_id == "t-1"
        assert metrics.cost_usd == Decimal("0.003")
        assert metrics.tool_calls == []
