"""Tests for the RegistryOrchestrator (api.services.registries.orchestrator)."""

import pytest
from unittest.mock import patch, MagicMock

from api.services.registries.orchestrator import RegistryOrchestrator


@pytest.fixture
def orchestrator():
    return RegistryOrchestrator()


class TestFindApplicableAdapters:
    """Test adapter selection logic."""

    def test_czech_by_country(self, orchestrator):
        """Czech company gets CZ + CZ_ISIR adapters."""
        result = orchestrator.find_applicable_adapters("Czech Republic", None, None)
        keys = [k for k, _, _ in result]
        assert "CZ" in keys
        assert "CZ_ISIR" in keys

    def test_czech_by_domain(self, orchestrator):
        """Domain .cz gets CZ + CZ_ISIR adapters."""
        result = orchestrator.find_applicable_adapters(None, "example.cz", None)
        keys = [k for k, _, _ in result]
        assert "CZ" in keys
        assert "CZ_ISIR" in keys

    def test_norwegian_company(self, orchestrator):
        """Norwegian company gets NO adapter only (no ISIR)."""
        result = orchestrator.find_applicable_adapters("Norway", None, None)
        keys = [k for k, _, _ in result]
        assert "NO" in keys
        assert "CZ_ISIR" not in keys

    def test_finnish_by_domain(self, orchestrator):
        """Domain .fi gets FI adapter."""
        result = orchestrator.find_applicable_adapters(None, "yritys.fi", None)
        keys = [k for k, _, _ in result]
        assert "FI" in keys

    def test_french_company(self, orchestrator):
        """French company gets FR adapter."""
        result = orchestrator.find_applicable_adapters("France", None, None)
        keys = [k for k, _, _ in result]
        assert "FR" in keys

    def test_unsupported_country(self, orchestrator):
        """Unsupported country returns empty list."""
        result = orchestrator.find_applicable_adapters("Germany", None, None)
        assert result == []

    def test_no_inputs(self, orchestrator):
        """No country/domain returns empty list."""
        result = orchestrator.find_applicable_adapters(None, None, None)
        assert result == []

    def test_country_priority_over_domain(self, orchestrator):
        """hq_country takes priority over domain TLD."""
        result = orchestrator.find_applicable_adapters("Norway", "example.cz", None)
        keys = [k for k, _, _ in result]
        assert "NO" in keys
        assert "CZ" not in keys

    def test_isir_included_when_ico_present(self, orchestrator):
        """CZ_ISIR included when company has ICO."""
        result = orchestrator.find_applicable_adapters("CZ", None, "12345678")
        keys = [k for k, _, _ in result]
        assert "CZ_ISIR" in keys


class TestDetectCountry:
    """Test country detection helper."""

    def test_detect_cz(self, orchestrator):
        assert orchestrator._detect_country("Czech Republic", None) == "CZ"

    def test_detect_no(self, orchestrator):
        assert orchestrator._detect_country("Norway", None) == "NO"

    def test_detect_fi_domain(self, orchestrator):
        assert orchestrator._detect_country(None, "test.fi") == "FI"

    def test_detect_fr_domain(self, orchestrator):
        assert orchestrator._detect_country(None, "test.fr") == "FR"

    def test_detect_none(self, orchestrator):
        assert orchestrator._detect_country(None, None) is None

    def test_detect_unsupported(self, orchestrator):
        assert orchestrator._detect_country("Germany", "test.de") is None


class TestEnrichCompany:
    """Test the full enrich_company flow with mocked adapters."""

    @patch("api.services.registries.orchestrator.get_adapter")
    @patch("api.services.registries.orchestrator.get_all_adapters")
    def test_skip_when_no_registry(self, mock_all, mock_get, orchestrator):
        """Returns skipped when no applicable registry found."""
        mock_all.return_value = {}
        result = orchestrator.enrich_company(
            "comp-1", "tenant-1", "Unknown GmbH",
            hq_country="Germany",
        )
        assert result["status"] == "skipped"
        assert result["reason"] == "no_applicable_registry"

    @patch("api.services.registries.orchestrator.RegistryOrchestrator._store_legal_profile")
    @patch("api.services.registries.orchestrator.RegistryOrchestrator._promote_to_company")
    @patch("api.services.registries.orchestrator.get_adapter")
    @patch("api.services.registries.orchestrator.get_all_adapters")
    def test_enriched_czech_company(self, mock_all, mock_get, mock_promote,
                                     mock_store, orchestrator):
        """Czech company gets enriched through CZ adapter."""
        # Setup mock adapters
        mock_cz = MagicMock()
        mock_cz.country_code = "CZ"
        mock_cz.is_supplementary = False
        mock_cz.country_names = ["Czech Republic", "Czechia", "CZ"]
        mock_cz.domain_tlds = [".cz"]
        mock_cz.matches_company.return_value = True
        mock_cz.enrich_company.return_value = {
            "status": "enriched",
            "ico": "12345678",
            "official_name": "Test s.r.o.",
            "method": "ico_direct",
            "confidence": 1.0,
            "data": {
                "ico": "12345678",
                "official_name": "Test s.r.o.",
                "registration_status": "active",
                "date_established": "2015-01-01",
                "legal_form": "112",
                "registered_address": "Praha",
            },
        }

        mock_isir = MagicMock()
        mock_isir.country_code = "CZ"
        mock_isir.is_supplementary = True
        mock_isir.enrich_company.return_value = {
            "status": "enriched",
            "has_insolvency": False,
            "total_proceedings": 0,
            "active_proceedings": 0,
            "data": {
                "has_insolvency": False,
                "proceedings": [],
                "active_proceedings": 0,
            },
        }

        def get_adapter_side_effect(key):
            if key == "CZ":
                return mock_cz
            if key == "CZ_ISIR":
                return mock_isir
            return None

        mock_get.side_effect = get_adapter_side_effect
        mock_all.return_value = {"CZ": mock_cz, "CZ_ISIR": mock_isir}

        result = orchestrator.enrich_company(
            "comp-1", "tenant-1", "Test s.r.o.",
            reg_id="12345678", hq_country="CZ",
        )

        assert result["status"] == "enriched"
        assert result["registration_id"] == "12345678"
        assert result["credibility_score"] > 0
        assert "CZ" in result["adapters_run"]
        mock_store.assert_called_once()
        mock_promote.assert_called_once()

    @patch("api.services.registries.orchestrator.get_adapter")
    @patch("api.services.registries.orchestrator.get_all_adapters")
    def test_ambiguous_propagated(self, mock_all, mock_get, orchestrator):
        """Ambiguous result from adapter is propagated."""
        mock_adapter = MagicMock()
        mock_adapter.country_code = "NO"
        mock_adapter.is_supplementary = False
        mock_adapter.matches_company.return_value = True
        mock_adapter.enrich_company.return_value = {
            "status": "ambiguous",
            "candidates": [
                {"ico": "111", "official_name": "A", "similarity": 0.7},
                {"ico": "222", "official_name": "B", "similarity": 0.65},
            ],
        }

        mock_get.side_effect = lambda k: mock_adapter if k == "NO" else None
        mock_all.return_value = {"NO": mock_adapter}

        result = orchestrator.enrich_company(
            "comp-1", "tenant-1", "Some AS",
            hq_country="Norway",
        )

        assert result["status"] == "ambiguous"
        assert len(result["candidates"]) == 2


class TestAggregateResults:
    """Test result aggregation logic."""

    @patch("api.services.registries.orchestrator.get_adapter")
    def test_aggregate_main_adapter(self, mock_get, orchestrator):
        """Main adapter data is promoted to profile."""
        mock_adapter = MagicMock()
        mock_adapter.is_supplementary = False
        mock_get.return_value = mock_adapter

        results = {
            "NO": {
                "status": "enriched",
                "confidence": 0.95,
                "method": "name_auto",
                "data": {
                    "ico": "999888777",
                    "official_name": "Test AS",
                    "registration_status": "active",
                    "nace_codes": [{"code": "62"}],
                },
            }
        }

        profile = orchestrator._aggregate_results(results, "Norway", None)
        assert profile["registration_id"] == "999888777"
        assert profile["official_name"] == "Test AS"
        assert profile["registration_status"] == "active"

    @patch("api.services.registries.orchestrator.get_adapter")
    def test_aggregate_with_isir(self, mock_get, orchestrator):
        """ISIR data merges insolvency into profile."""
        mock_main = MagicMock()
        mock_main.is_supplementary = False

        mock_isir = MagicMock()
        mock_isir.is_supplementary = True

        def side_effect(key):
            return mock_main if key == "CZ" else mock_isir if key == "CZ_ISIR" else None

        mock_get.side_effect = side_effect

        results = {
            "CZ": {
                "status": "enriched",
                "confidence": 1.0,
                "method": "ico_direct",
                "data": {"ico": "123", "insolvency_flag": False},
            },
            "CZ_ISIR": {
                "status": "enriched",
                "data": {
                    "has_insolvency": True,
                    "proceedings": [{"case_number": "INS 1/2024", "is_active": True}],
                    "active_proceedings": 1,
                },
            },
        }

        profile = orchestrator._aggregate_results(results, "CZ", None)
        assert profile["insolvency_flag"] is True
        assert profile["active_insolvency_count"] == 1
        assert len(profile["insolvency_details"]) == 1
