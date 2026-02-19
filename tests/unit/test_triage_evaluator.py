"""Unit tests for rules-based triage evaluation logic."""

import pytest

from api.services.triage_evaluator import evaluate_triage, DEFAULT_RULES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_company(**overrides):
    """Build a company data dict with sensible defaults."""
    base = {
        "tier": "tier_1",
        "industry": "software_saas",
        "geo_region": "dach",
        "revenue_eur_m": 10.0,
        "employees": 120,
        "is_b2b": True,
        "qc_flags": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Test: Default rules
# ---------------------------------------------------------------------------

class TestDefaultRules:
    """Test DEFAULT_RULES structure and values."""

    def test_default_rules_has_expected_keys(self):
        expected = {
            "tier_allowlist", "tier_blocklist",
            "industry_blocklist", "industry_allowlist",
            "geo_allowlist",
            "min_revenue_eur_m", "min_employees",
            "require_b2b", "max_qc_flags",
        }
        assert expected.issubset(set(DEFAULT_RULES.keys()))

    def test_default_rules_require_b2b(self):
        assert DEFAULT_RULES["require_b2b"] is True

    def test_default_max_qc_flags(self):
        assert DEFAULT_RULES["max_qc_flags"] == 3


# ---------------------------------------------------------------------------
# Test: Tier filtering
# ---------------------------------------------------------------------------

class TestTierFiltering:
    """Test tier allowlist and blocklist rules."""

    def test_tier_in_allowlist_passes(self):
        rules = {"tier_allowlist": ["tier_1", "tier_2"]}
        result = evaluate_triage(_make_company(tier="tier_1"), rules)
        assert result["passed"] is True

    def test_tier_not_in_allowlist_fails(self):
        rules = {"tier_allowlist": ["tier_1", "tier_2"]}
        result = evaluate_triage(_make_company(tier="tier_3"), rules)
        assert result["passed"] is False
        assert any("tier" in r.lower() for r in result["reasons"])

    def test_empty_tier_allowlist_passes_all(self):
        """Empty allowlist means no tier filter."""
        rules = {"tier_allowlist": []}
        result = evaluate_triage(_make_company(tier="tier_5"), rules)
        assert result["passed"] is True

    def test_tier_in_blocklist_fails(self):
        rules = {"tier_blocklist": ["tier_4", "tier_5"]}
        result = evaluate_triage(_make_company(tier="tier_4"), rules)
        assert result["passed"] is False

    def test_tier_not_in_blocklist_passes(self):
        rules = {"tier_blocklist": ["tier_4"]}
        result = evaluate_triage(_make_company(tier="tier_1"), rules)
        assert result["passed"] is True

    def test_none_tier_fails_allowlist(self):
        """Company without tier assigned fails tier allowlist."""
        rules = {"tier_allowlist": ["tier_1"]}
        result = evaluate_triage(_make_company(tier=None), rules)
        assert result["passed"] is False


# ---------------------------------------------------------------------------
# Test: Industry filtering
# ---------------------------------------------------------------------------

class TestIndustryFiltering:
    """Test industry allowlist and blocklist rules."""

    def test_industry_in_blocklist_fails(self):
        rules = {"industry_blocklist": ["other", "public_sector"]}
        result = evaluate_triage(_make_company(industry="other"), rules)
        assert result["passed"] is False
        assert any("industry" in r.lower() for r in result["reasons"])

    def test_industry_not_in_blocklist_passes(self):
        rules = {"industry_blocklist": ["other"]}
        result = evaluate_triage(_make_company(industry="software_saas"), rules)
        assert result["passed"] is True

    def test_industry_in_allowlist_passes(self):
        rules = {"industry_allowlist": ["software_saas", "it"]}
        result = evaluate_triage(_make_company(industry="software_saas"), rules)
        assert result["passed"] is True

    def test_industry_not_in_allowlist_fails(self):
        rules = {"industry_allowlist": ["software_saas", "it"]}
        result = evaluate_triage(_make_company(industry="manufacturing"), rules)
        assert result["passed"] is False

    def test_empty_industry_allowlist_passes_all(self):
        rules = {"industry_allowlist": []}
        result = evaluate_triage(_make_company(industry="anything"), rules)
        assert result["passed"] is True


# ---------------------------------------------------------------------------
# Test: Geo filtering
# ---------------------------------------------------------------------------

class TestGeoFiltering:
    """Test geo_region allowlist."""

    def test_geo_in_allowlist_passes(self):
        rules = {"geo_allowlist": ["dach", "nordics"]}
        result = evaluate_triage(_make_company(geo_region="dach"), rules)
        assert result["passed"] is True

    def test_geo_not_in_allowlist_fails(self):
        rules = {"geo_allowlist": ["dach"]}
        result = evaluate_triage(_make_company(geo_region="us"), rules)
        assert result["passed"] is False

    def test_empty_geo_allowlist_passes_all(self):
        rules = {"geo_allowlist": []}
        result = evaluate_triage(_make_company(geo_region="anywhere"), rules)
        assert result["passed"] is True


# ---------------------------------------------------------------------------
# Test: Revenue filtering
# ---------------------------------------------------------------------------

class TestRevenueFiltering:
    """Test minimum revenue floor."""

    def test_revenue_above_floor_passes(self):
        rules = {"min_revenue_eur_m": 5.0}
        result = evaluate_triage(_make_company(revenue_eur_m=10.0), rules)
        assert result["passed"] is True

    def test_revenue_below_floor_fails(self):
        rules = {"min_revenue_eur_m": 5.0}
        result = evaluate_triage(_make_company(revenue_eur_m=2.0), rules)
        assert result["passed"] is False
        assert any("revenue" in r.lower() for r in result["reasons"])

    def test_none_revenue_fails_floor(self):
        """Company without revenue data fails revenue floor."""
        rules = {"min_revenue_eur_m": 5.0}
        result = evaluate_triage(_make_company(revenue_eur_m=None), rules)
        assert result["passed"] is False

    def test_none_min_revenue_passes_all(self):
        """No min_revenue rule means no revenue filter."""
        rules = {"min_revenue_eur_m": None}
        result = evaluate_triage(_make_company(revenue_eur_m=0.5), rules)
        assert result["passed"] is True


# ---------------------------------------------------------------------------
# Test: Employee filtering
# ---------------------------------------------------------------------------

class TestEmployeeFiltering:
    """Test minimum employee count."""

    def test_employees_above_min_passes(self):
        rules = {"min_employees": 50}
        result = evaluate_triage(_make_company(employees=120), rules)
        assert result["passed"] is True

    def test_employees_below_min_fails(self):
        rules = {"min_employees": 50}
        result = evaluate_triage(_make_company(employees=10), rules)
        assert result["passed"] is False

    def test_none_employees_fails_min(self):
        rules = {"min_employees": 50}
        result = evaluate_triage(_make_company(employees=None), rules)
        assert result["passed"] is False

    def test_none_min_employees_passes_all(self):
        rules = {"min_employees": None}
        result = evaluate_triage(_make_company(employees=1), rules)
        assert result["passed"] is True


# ---------------------------------------------------------------------------
# Test: B2B requirement
# ---------------------------------------------------------------------------

class TestB2BRequirement:
    """Test require_b2b rule."""

    def test_b2b_true_passes(self):
        rules = {"require_b2b": True}
        result = evaluate_triage(_make_company(is_b2b=True), rules)
        assert result["passed"] is True

    def test_b2b_false_fails(self):
        rules = {"require_b2b": True}
        result = evaluate_triage(_make_company(is_b2b=False), rules)
        assert result["passed"] is False
        assert any("b2b" in r.lower() for r in result["reasons"])

    def test_b2b_none_fails(self):
        """Unknown B2B classification fails when B2B required."""
        rules = {"require_b2b": True}
        result = evaluate_triage(_make_company(is_b2b=None), rules)
        assert result["passed"] is False

    def test_require_b2b_false_passes_non_b2b(self):
        """When require_b2b is False, non-B2B companies pass."""
        rules = {"require_b2b": False}
        result = evaluate_triage(_make_company(is_b2b=False), rules)
        assert result["passed"] is True


# ---------------------------------------------------------------------------
# Test: QC flag count
# ---------------------------------------------------------------------------

class TestQCFlagCount:
    """Test max_qc_flags rule."""

    def test_flags_below_max_passes(self):
        rules = {"max_qc_flags": 3}
        result = evaluate_triage(_make_company(qc_flags=["a", "b"]), rules)
        assert result["passed"] is True

    def test_flags_at_max_passes(self):
        """Exactly at max is still OK."""
        rules = {"max_qc_flags": 3}
        result = evaluate_triage(_make_company(qc_flags=["a", "b", "c"]), rules)
        assert result["passed"] is True

    def test_flags_above_max_fails(self):
        rules = {"max_qc_flags": 3}
        result = evaluate_triage(_make_company(qc_flags=["a", "b", "c", "d"]), rules)
        assert result["passed"] is False
        assert any("qc" in r.lower() or "flag" in r.lower() for r in result["reasons"])

    def test_none_qc_flags_treated_as_zero(self):
        rules = {"max_qc_flags": 3}
        result = evaluate_triage(_make_company(qc_flags=None), rules)
        assert result["passed"] is True

    def test_none_max_qc_flags_passes_all(self):
        """No max_qc_flags rule means no QC filter."""
        rules = {"max_qc_flags": None}
        result = evaluate_triage(_make_company(qc_flags=["a"] * 10), rules)
        assert result["passed"] is True


# ---------------------------------------------------------------------------
# Test: Combined scenarios
# ---------------------------------------------------------------------------

class TestCombinedRules:
    """Test multiple rules applied together."""

    def test_all_rules_pass(self):
        rules = {
            "tier_allowlist": ["tier_1", "tier_2"],
            "industry_blocklist": ["other"],
            "require_b2b": True,
            "max_qc_flags": 3,
            "min_revenue_eur_m": 5.0,
        }
        company = _make_company(
            tier="tier_1", industry="software_saas",
            is_b2b=True, qc_flags=[], revenue_eur_m=10.0,
        )
        result = evaluate_triage(company, rules)
        assert result["passed"] is True
        assert result["reasons"] == []

    def test_multiple_rules_fail(self):
        rules = {
            "tier_allowlist": ["tier_1"],
            "industry_blocklist": ["other"],
            "require_b2b": True,
            "max_qc_flags": 2,
        }
        company = _make_company(
            tier="tier_3", industry="other",
            is_b2b=False, qc_flags=["a", "b", "c"],
        )
        result = evaluate_triage(company, rules)
        assert result["passed"] is False
        assert len(result["reasons"]) >= 3  # tier + industry + b2b + qc

    def test_empty_rules_pass_all(self):
        """Empty rules dict means no filtering — everything passes."""
        result = evaluate_triage(_make_company(), {})
        assert result["passed"] is True
        assert result["reasons"] == []

    def test_default_rules_pass_good_company(self):
        """A good company should pass default rules."""
        result = evaluate_triage(_make_company(), DEFAULT_RULES)
        assert result["passed"] is True

    def test_result_has_required_keys(self):
        """evaluate_triage always returns {passed, reasons}."""
        result = evaluate_triage(_make_company(), {})
        assert "passed" in result
        assert "reasons" in result
        assert isinstance(result["passed"], bool)
        assert isinstance(result["reasons"], list)
