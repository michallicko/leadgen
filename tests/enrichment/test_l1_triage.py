"""Isolated tests for L1 Triage / Scoring (deterministic, no API calls).

Tests the triage evaluation rules, QC validation, and scoring algorithm.
No API calls = zero cost.

Run with:
    pytest tests/enrichment/test_l1_triage.py -v
"""

import pytest

# Import production code directly — no API calls needed
from api.services.triage_evaluator import evaluate_triage, DEFAULT_RULES
from api.services.l1_enricher import (
    _validate_research, _parse_revenue, _parse_employees,
    _parse_confidence, _name_similarity,
)


# ---------------------------------------------------------------------------
# Triage evaluator tests
# ---------------------------------------------------------------------------

@pytest.mark.enrichment
class TestTriageEvaluator:
    """Test the rules-based triage evaluator."""

    def test_all_pass_default_rules(self):
        """Company meeting all criteria should pass with default rules."""
        company = {
            "tier": "tier_1_platinum",
            "industry": "software_saas",
            "geo_region": "western_europe",
            "revenue_eur_m": 50,
            "employees": 500,
            "is_b2b": True,
            "qc_flags": [],
        }
        result = evaluate_triage(company, DEFAULT_RULES)
        assert result["passed"] is True
        assert result["reasons"] == []

    def test_not_b2b_fails(self):
        """Non-B2B company should fail when require_b2b is True."""
        company = {
            "tier": "tier_1_platinum",
            "industry": "retail",
            "geo_region": "western_europe",
            "revenue_eur_m": 100,
            "employees": 1000,
            "is_b2b": False,
            "qc_flags": [],
        }
        result = evaluate_triage(company, DEFAULT_RULES)
        assert result["passed"] is False
        assert any("B2B" in r for r in result["reasons"])

    def test_tier_blocklist(self):
        """Blocklisted tier should fail."""
        rules = {**DEFAULT_RULES, "tier_blocklist": ["tier_5_copper"]}
        company = {
            "tier": "tier_5_copper",
            "industry": "retail",
            "is_b2b": True,
            "qc_flags": [],
        }
        result = evaluate_triage(company, rules)
        assert result["passed"] is False
        assert any("blocklisted" in r for r in result["reasons"])

    def test_tier_allowlist(self):
        """Tier not in allowlist should fail."""
        rules = {**DEFAULT_RULES, "tier_allowlist": ["tier_1_platinum", "tier_2_gold"]}
        company = {
            "tier": "tier_3_silver",
            "industry": "it",
            "is_b2b": True,
            "qc_flags": [],
        }
        result = evaluate_triage(company, rules)
        assert result["passed"] is False
        assert any("allowlist" in r for r in result["reasons"])

    def test_industry_blocklist(self):
        """Blocklisted industry should fail."""
        rules = {**DEFAULT_RULES, "industry_blocklist": ["public_sector", "education"]}
        company = {
            "tier": "tier_2_gold",
            "industry": "education",
            "is_b2b": True,
            "qc_flags": [],
        }
        result = evaluate_triage(company, rules)
        assert result["passed"] is False

    def test_min_revenue_below_threshold(self):
        """Revenue below minimum should fail."""
        rules = {**DEFAULT_RULES, "min_revenue_eur_m": 10}
        company = {
            "tier": "tier_2_gold",
            "industry": "it",
            "revenue_eur_m": 5,
            "employees": 50,
            "is_b2b": True,
            "qc_flags": [],
        }
        result = evaluate_triage(company, rules)
        assert result["passed"] is False
        assert any("Revenue" in r for r in result["reasons"])

    def test_min_employees_below_threshold(self):
        """Employee count below minimum should fail."""
        rules = {**DEFAULT_RULES, "min_employees": 100}
        company = {
            "tier": "tier_2_gold",
            "industry": "it",
            "revenue_eur_m": 50,
            "employees": 20,
            "is_b2b": True,
            "qc_flags": [],
        }
        result = evaluate_triage(company, rules)
        assert result["passed"] is False
        assert any("Employees" in r for r in result["reasons"])

    def test_too_many_qc_flags(self):
        """Too many QC flags should fail."""
        rules = {**DEFAULT_RULES, "max_qc_flags": 2}
        company = {
            "tier": "tier_2_gold",
            "industry": "it",
            "is_b2b": True,
            "qc_flags": ["low_confidence", "incomplete_research",
                         "name_mismatch"],
        }
        result = evaluate_triage(company, rules)
        assert result["passed"] is False
        assert any("QC flags" in r for r in result["reasons"])

    def test_geo_allowlist(self):
        """Region not in geo allowlist should fail."""
        rules = {**DEFAULT_RULES, "geo_allowlist": ["nordics", "western_europe"]}
        company = {
            "tier": "tier_2_gold",
            "industry": "it",
            "geo_region": "north_america",
            "is_b2b": True,
            "qc_flags": [],
        }
        result = evaluate_triage(company, rules)
        assert result["passed"] is False

    def test_multiple_failures(self):
        """Multiple rule violations should all be reported."""
        rules = {
            **DEFAULT_RULES,
            "tier_blocklist": ["tier_5_copper"],
            "min_revenue_eur_m": 10,
            "min_employees": 50,
        }
        company = {
            "tier": "tier_5_copper",
            "industry": "retail",
            "revenue_eur_m": 2,
            "employees": 10,
            "is_b2b": False,
            "qc_flags": [],
        }
        result = evaluate_triage(company, rules)
        assert result["passed"] is False
        assert len(result["reasons"]) >= 3


# ---------------------------------------------------------------------------
# QC validation tests (from l1_enricher._validate_research)
# ---------------------------------------------------------------------------

@pytest.mark.enrichment
class TestQCValidation:
    """Test QC validation logic from L1 enricher."""

    def test_clean_research_no_flags(self):
        """Complete, high-quality research should produce no flags."""
        research = {
            "company_name": "ASML Holding",
            "summary": "ASML is the world's leading manufacturer of semiconductor lithography equipment.",
            "b2b": True,
            "hq": "Veldhoven, Netherlands",
            "industry": "manufacturing",
            "employees": 42000,
            "revenue_eur_m": 15000,
            "confidence": 0.95,
            "flags": [],
        }
        flags = _validate_research(research, "ASML Holding")
        assert flags == []

    def test_name_mismatch_flag(self):
        """Different company name should trigger name_mismatch."""
        research = {
            "company_name": "Completely Different Corp",
            "summary": "Some other company that does something entirely different.",
            "b2b": True,
            "hq": "London, UK",
            "industry": "it",
            "employees": 500,
            "revenue_eur_m": 10,
            "confidence": 0.5,
            "flags": [],
        }
        flags = _validate_research(research, "ASML Holding")
        assert "name_mismatch" in flags

    def test_incomplete_research_flag(self):
        """Missing critical fields should trigger incomplete_research."""
        research = {
            "company_name": "Test Co",
            "summary": "A test company.",
            "b2b": True,
            "hq": "unverified",
            "industry": "unknown",
            "employees": "unverified",
            "revenue_eur_m": "unverified",
            "confidence": 0.3,
            "flags": [],
        }
        flags = _validate_research(research, "Test Co")
        assert "incomplete_research" in flags

    def test_low_confidence_flag(self):
        """Low confidence should be flagged."""
        research = {
            "company_name": "Test Co",
            "summary": "A test company that provides various services in the market.",
            "b2b": True,
            "hq": "Prague, Czech Republic",
            "industry": "it",
            "employees": 100,
            "revenue_eur_m": 5,
            "confidence": 0.2,
            "flags": [],
        }
        flags = _validate_research(research, "Test Co")
        assert "low_confidence" in flags

    def test_b2b_unclear_flag(self):
        """Null B2B classification should trigger flag."""
        research = {
            "company_name": "Test Co",
            "summary": "A test company that provides various services in the market.",
            "b2b": None,
            "hq": "Berlin, Germany",
            "industry": "it",
            "employees": 100,
            "revenue_eur_m": 5,
            "confidence": 0.7,
            "flags": [],
        }
        flags = _validate_research(research, "Test Co")
        assert "b2b_unclear" in flags

    def test_revenue_implausible_flag(self):
        """Extreme revenue should trigger flag."""
        research = {
            "company_name": "Tiny Co",
            "summary": "A tiny company with somehow enormous revenue claims.",
            "b2b": True,
            "hq": "Oslo, Norway",
            "industry": "it",
            "employees": 5,
            "revenue_eur_m": 100000,
            "confidence": 0.8,
            "flags": [],
        }
        flags = _validate_research(research, "Tiny Co")
        assert "revenue_implausible" in flags

    def test_source_warning_from_perplexity_flags(self):
        """Perplexity flags containing 'not found' should trigger source_warning."""
        research = {
            "company_name": "Test Co",
            "summary": "A test company that provides various services in the market.",
            "b2b": True,
            "hq": "Prague, Czech Republic",
            "industry": "it",
            "employees": 50,
            "revenue_eur_m": 2,
            "confidence": 0.7,
            "flags": ["Company not found in any major database"],
        }
        flags = _validate_research(research, "Test Co")
        assert "source_warning" in flags

    def test_summary_too_short(self):
        """Very short summary should be flagged."""
        research = {
            "company_name": "Test Co",
            "summary": "A company.",
            "b2b": True,
            "hq": "Berlin, Germany",
            "industry": "it",
            "employees": 50,
            "revenue_eur_m": 5,
            "confidence": 0.7,
            "flags": [],
        }
        flags = _validate_research(research, "Test Co")
        assert "summary_too_short" in flags


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

@pytest.mark.enrichment
class TestParsers:
    """Test revenue, employee, and confidence parsing helpers."""

    @pytest.mark.parametrize("input_val,expected", [
        (42, 42.0),
        (42.5, 42.5),
        ("42", 42.0),
        ("42M", 42.0),
        ("1.5 billion", 1500.0),
        ("EUR 100 million", 100.0),
        ("unverified", None),
        ("unknown", None),
        (None, None),
        ("N/A", None),
        ("$2.3 billion", 2300.0),
    ])
    def test_parse_revenue(self, input_val, expected):
        result = _parse_revenue(input_val)
        assert result == expected, \
            "parse_revenue({!r}) = {}, expected {}".format(
                input_val, result, expected)

    @pytest.mark.parametrize("input_val,expected", [
        (500, 500),
        ("500", 500),
        ("1,234", 1234),
        ("200-300", 250),
        ("~500", 500),
        ("500+", 500),
        ("unverified", None),
        (None, None),
    ])
    def test_parse_employees(self, input_val, expected):
        result = _parse_employees(input_val)
        assert result == expected, \
            "parse_employees({!r}) = {}, expected {}".format(
                input_val, result, expected)

    @pytest.mark.parametrize("input_val,expected", [
        (0.8, 0.8),
        (0.0, 0.0),
        (1.0, 1.0),
        ("high", 0.9),
        ("medium", 0.6),
        ("low", 0.3),
        (None, None),
        (1.5, None),
    ])
    def test_parse_confidence(self, input_val, expected):
        result = _parse_confidence(input_val)
        assert result == expected, \
            "parse_confidence({!r}) = {}, expected {}".format(
                input_val, result, expected)


# ---------------------------------------------------------------------------
# Name similarity tests
# ---------------------------------------------------------------------------

@pytest.mark.enrichment
class TestNameSimilarity:
    """Test the bigram similarity function used for name matching QC."""

    def test_exact_match(self):
        assert _name_similarity("ASML", "ASML") == 1.0

    def test_suffix_stripped(self):
        """Common suffixes like Ltd, GmbH should be ignored."""
        # "Oyj" is not in the suffix strip list, so expect lower similarity
        assert _name_similarity("Kone Oyj", "Kone") >= 0.5
        assert _name_similarity("Delta GmbH", "Delta") > 0.8

    def test_different_names(self):
        """Completely different names should score low."""
        sim = _name_similarity("ASML Holding", "Bohdalice Metalworks")
        assert sim < 0.4

    def test_partial_match(self):
        """Partial name matches should have medium similarity."""
        sim = _name_similarity("Productboard", "Productboard Inc")
        assert sim > 0.7

    def test_empty_strings(self):
        assert _name_similarity("", "ASML") == 0.0
        assert _name_similarity("ASML", "") == 0.0
        assert _name_similarity("", "") == 0.0
