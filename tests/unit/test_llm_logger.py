"""Unit tests for the LLM usage logger service."""

from decimal import Decimal

import pytest

from api.services.llm_logger import compute_cost, log_llm_usage


class TestComputeCost:
    def test_sonnet_pricing(self):
        """Sonnet: $3/1M input, $15/1M output."""
        cost = compute_cost("anthropic", "claude-sonnet-4-5-20250929", 1000, 500)
        expected = Decimal("1000") * Decimal("3.00") / Decimal("1000000") + \
                   Decimal("500") * Decimal("15.00") / Decimal("1000000")
        assert cost == expected.quantize(Decimal("0.000001"))

    def test_zero_tokens(self):
        cost = compute_cost("anthropic", "claude-sonnet-4-5-20250929", 0, 0)
        assert cost == Decimal("0")

    def test_unknown_model_uses_wildcard(self):
        """Unknown Anthropic model should use the wildcard fallback."""
        cost = compute_cost("anthropic", "claude-future-model", 1000, 500)
        # Wildcard uses same pricing as sonnet ($3/$15)
        assert cost > Decimal("0")

    def test_unknown_provider_returns_zero(self):
        cost = compute_cost("openai", "gpt-4", 1000, 500)
        assert cost == Decimal("0")

    def test_large_token_count(self):
        """1M input tokens at $3/1M = $3.00."""
        cost = compute_cost("anthropic", "claude-sonnet-4-5-20250929", 1000000, 0)
        assert cost == Decimal("3.000000")

    def test_output_only(self):
        """1000 output tokens at $15/1M = $0.015."""
        cost = compute_cost("anthropic", "claude-sonnet-4-5-20250929", 0, 1000)
        assert cost == Decimal("0.015000")

    def test_haiku_pricing(self):
        """Haiku: $0.80/1M input, $4/1M output."""
        cost = compute_cost("anthropic", "claude-haiku-3-5-20241022", 10000, 5000)
        input_cost = Decimal("10000") * Decimal("0.80") / Decimal("1000000")
        output_cost = Decimal("5000") * Decimal("4.00") / Decimal("1000000")
        expected = (input_cost + output_cost).quantize(Decimal("0.000001"))
        assert cost == expected


class TestLogLlmUsage:
    def test_creates_entry_with_correct_cost(self, app, db, seed_tenant):
        """log_llm_usage should create an LlmUsageLog with computed cost."""
        entry = log_llm_usage(
            tenant_id=seed_tenant.id,
            operation="csv_column_mapping",
            model="claude-sonnet-4-5-20250929",
            input_tokens=500,
            output_tokens=200,
        )
        db.session.flush()

        assert entry.operation == "csv_column_mapping"
        assert entry.provider == "anthropic"
        assert entry.model == "claude-sonnet-4-5-20250929"
        assert entry.input_tokens == 500
        assert entry.output_tokens == 200
        assert float(entry.cost_usd) > 0

    def test_handles_optional_fields(self, app, db, seed_tenant, seed_super_admin):
        """Optional fields like user_id, duration_ms, metadata should work."""
        entry = log_llm_usage(
            tenant_id=seed_tenant.id,
            operation="test_op",
            model="claude-sonnet-4-5-20250929",
            input_tokens=100,
            output_tokens=50,
            user_id=seed_super_admin.id,
            duration_ms=1234,
            metadata={"job_id": "abc-123"},
        )
        db.session.flush()

        assert str(entry.user_id) == str(seed_super_admin.id)
        assert entry.duration_ms == 1234
        # extra (mapped to metadata column) may be stored as string in SQLite
        meta = entry.extra
        if isinstance(meta, str):
            import json
            meta = json.loads(meta)
        assert meta.get("job_id") == "abc-123"

    def test_no_user_id(self, app, db, seed_tenant):
        """user_id=None should be fine."""
        entry = log_llm_usage(
            tenant_id=seed_tenant.id,
            operation="test_op",
            model="claude-sonnet-4-5-20250929",
            input_tokens=100,
            output_tokens=50,
        )
        db.session.flush()
        assert entry.user_id is None
