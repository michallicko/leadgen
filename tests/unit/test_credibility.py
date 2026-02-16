"""Tests for the credibility scorer (api.services.registries.credibility)."""

import pytest
from datetime import date, timedelta

from api.services.registries.credibility import compute_credibility


class TestComputeCredibility:
    """Test the main compute_credibility function."""

    def test_perfect_score(self):
        """Company with all positive signals gets close to 100."""
        profile = {
            "registration_id": "12345678",
            "match_confidence": 1.0,
            "registration_status": "active",
            "insolvency_flag": False,
            "active_insolvency_count": 0,
            "insolvency_details": [],
            "date_established": "2010-01-01",
            "official_name": "Test Corp s.r.o.",
            "legal_form": "112",
            "registered_address": "Karlova 1, Praha",
            "nace_codes": [{"code": "62010"}],
            "registered_capital": "200000 CZK",
            "directors": [{"name": "Jan Novak"}],
        }
        result = compute_credibility(profile)
        assert result["score"] >= 90
        assert result["factors"]["registration_verified"] == 25
        assert result["factors"]["active_status"] == 20
        assert result["factors"]["no_insolvency"] == 20
        assert result["factors"]["directors_known"] == 10

    def test_empty_profile(self):
        """Empty profile gets unknown-status + no-insolvency-default score."""
        result = compute_credibility({})
        assert result["score"] == 25  # status=5 + no_insolvency=20
        assert result["factors"]["registration_verified"] == 0
        assert result["factors"]["active_status"] == 5
        assert result["factors"]["no_insolvency"] == 20
        assert result["factors"]["directors_known"] == 0

    def test_dissolved_company(self):
        """Dissolved company gets 0 for status."""
        profile = {
            "registration_id": "12345678",
            "match_confidence": 1.0,
            "registration_status": "dissolved",
        }
        result = compute_credibility(profile)
        assert result["factors"]["active_status"] == 0

    def test_active_insolvency(self):
        """Active insolvency gets 0 for no_insolvency factor."""
        profile = {
            "insolvency_flag": True,
            "active_insolvency_count": 2,
            "insolvency_details": [{"is_active": True}],
        }
        result = compute_credibility(profile)
        assert result["factors"]["no_insolvency"] == 0

    def test_historical_insolvency(self):
        """Historical-only insolvency gets 10 points."""
        profile = {
            "insolvency_flag": True,
            "active_insolvency_count": 0,
            "insolvency_details": [{"is_active": False}],
        }
        result = compute_credibility(profile)
        assert result["factors"]["no_insolvency"] == 10

    def test_young_company(self):
        """Company less than 1 year old gets 2 for business history."""
        recent = (date.today() - timedelta(days=180)).isoformat()
        profile = {"date_established": recent}
        result = compute_credibility(profile)
        assert result["factors"]["business_history"] == 2

    def test_established_company(self):
        """10+ year old company gets max business history."""
        old = (date.today() - timedelta(days=4000)).isoformat()
        profile = {"date_established": old}
        result = compute_credibility(profile)
        assert result["factors"]["business_history"] == 15

    def test_confidence_tiers(self):
        """Registration verified score depends on confidence level."""
        # 95%+
        r = compute_credibility({"registration_id": "123", "match_confidence": 0.98})
        assert r["factors"]["registration_verified"] == 25

        # 85-94%
        r = compute_credibility({"registration_id": "123", "match_confidence": 0.90})
        assert r["factors"]["registration_verified"] == 20

        # 60-84%
        r = compute_credibility({"registration_id": "123", "match_confidence": 0.70})
        assert r["factors"]["registration_verified"] == 10

        # < 60%
        r = compute_credibility({"registration_id": "123", "match_confidence": 0.50})
        assert r["factors"]["registration_verified"] == 5

    def test_data_completeness(self):
        """Full data gets 10 for completeness."""
        profile = {
            "official_name": "Foo",
            "legal_form": "112",
            "registered_address": "Addr",
            "nace_codes": [{"code": "62"}],
            "registered_capital": "100 CZK",
            "date_established": "2020-01-01",
        }
        result = compute_credibility(profile)
        assert result["factors"]["data_completeness"] == 10

    def test_partial_completeness(self):
        """Partial data gets proportional completeness score."""
        profile = {
            "official_name": "Foo",
            "legal_form": "112",
            "registered_address": "Addr",
        }
        result = compute_credibility(profile)
        assert result["factors"]["data_completeness"] == 5  # 3/6 * 10 = 5

    def test_score_capped_at_100(self):
        """Score never exceeds 100."""
        result = compute_credibility({
            "registration_id": "123",
            "match_confidence": 1.0,
            "registration_status": "active",
            "insolvency_flag": False,
            "active_insolvency_count": 0,
            "date_established": "2000-01-01",
            "official_name": "X", "legal_form": "Y", "registered_address": "Z",
            "nace_codes": [1], "registered_capital": "100", "directors": [{"name": "A"}],
        })
        assert result["score"] <= 100

    def test_returns_all_factors(self):
        """Result always includes all 6 factor keys."""
        result = compute_credibility({})
        expected_keys = {
            "registration_verified", "active_status", "no_insolvency",
            "business_history", "data_completeness", "directors_known",
        }
        assert set(result["factors"].keys()) == expected_keys
