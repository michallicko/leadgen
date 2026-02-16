"""Unit tests for the Finland PRH registry adapter."""
from unittest.mock import MagicMock, patch

import pytest
import requests

from api.services.registries.prh import PrhAdapter, _parse_prh_response


# --- Fixtures (real PRH v3 API format — uses numeric codes) ---

PRH_COMPANY = {
    "businessId": {
        "value": "2646674-9",
        "registrationDate": "2014-10-07",
        "source": "3",
    },
    "names": [
        {
            "name": "Wolt Oy",
            "type": "1",
            "registrationDate": "2025-05-12",
            "version": 1,
            "source": "1",
        },
        {
            "name": "Wolt Enterprises Oy",
            "type": "1",
            "registrationDate": "2014-10-29",
            "endDate": "2025-05-12",
            "version": 2,
            "source": "1",
        },
    ],
    "companyForms": [{
        "type": "16",
        "descriptions": [
            {"languageCode": "2", "description": "Aktiebolag"},
            {"languageCode": "3", "description": "Limited company"},
            {"languageCode": "1", "description": "Osakeyhtiö"},
        ],
        "registrationDate": "2014-10-29",
        "version": 1,
        "source": "1",
    }],
    "addresses": [{
        "type": 1,
        "street": "Pohjoinen Rautatiekatu",
        "postCode": "00100",
        "postOffices": [
            {"city": "HELSINGFORS", "languageCode": "2", "municipalityCode": "091"},
            {"city": "HELSINKI", "languageCode": "1", "municipalityCode": "091"},
        ],
        "buildingNumber": "21",
        "registrationDate": "2023-08-14",
        "source": "0",
    }],
    "mainBusinessLine": {
        "type": "96999",
        "descriptions": [
            {"languageCode": "2", "description": "Diverse övriga konsumenttjänster"},
            {"languageCode": "1", "description": "Muu muualla luokittelematon palvelutoiminta"},
            {"languageCode": "3", "description": "Other miscellaneous personal service activities n.e.c."},
        ],
        "typeCodeSet": "TOIMI4",
        "registrationDate": "2026-01-01",
        "source": "2",
    },
    "tradeRegisterStatus": "1",
    "registrationDate": "2014-10-29",
    "lastModified": "2026-01-02T07:49:26",
}

PRH_SEARCH_RESPONSE = {
    "totalResults": 1,
    "companies": [PRH_COMPANY],
}


# --- Parser tests ---

class TestParsePrhResponse:
    def test_full_response(self):
        result = _parse_prh_response(PRH_COMPANY)
        assert result["ico"] == "2646674-9"
        assert result["official_name"] == "Wolt Oy"
        assert result["legal_form"] == "16"
        assert result["legal_form_name"] == "Limited company"
        assert result["date_established"] == "2014-10-07"
        assert result["address_city"] == "HELSINKI"
        assert result["address_postal_code"] == "00100"
        assert "Pohjoinen Rautatiekatu" in result["registered_address"]
        assert result["registration_status"] == "active"
        assert len(result["nace_codes"]) == 1
        assert result["nace_codes"][0]["code"] == "96999"
        assert "personal service" in result["nace_codes"][0]["description"]
        assert result["directors"] == []
        assert result["registered_capital"] is None
        assert result["_raw"] is PRH_COMPANY

    def test_active_name_selected(self):
        """Should pick active name (no endDate), not historical."""
        result = _parse_prh_response(PRH_COMPANY)
        assert result["official_name"] == "Wolt Oy"

    def test_empty_response(self):
        result = _parse_prh_response({})
        assert result["ico"] is None
        assert result["official_name"] is None
        assert result["nace_codes"] == []
        assert result["registration_status"] == "active"

    def test_deregistered_status_string(self):
        """String status code (docs format)."""
        data = dict(PRH_COMPANY)
        data["tradeRegisterStatus"] = "DEREGISTERED"
        result = _parse_prh_response(data)
        assert result["registration_status"] == "dissolved"

    def test_deregistered_status_numeric(self):
        """Numeric status code '2' (v3 real format)."""
        data = dict(PRH_COMPANY)
        data["tradeRegisterStatus"] = "2"
        result = _parse_prh_response(data)
        assert result["registration_status"] == "dissolved"

    def test_finnish_description_fallback(self):
        """When no English description, use Finnish."""
        data = dict(PRH_COMPANY)
        data["companyForms"] = [{
            "type": "16",
            "descriptions": [
                {"languageCode": "1", "description": "Osakeyhtiö"},
            ],
        }]
        result = _parse_prh_response(data)
        assert result["legal_form_name"] == "Osakeyhtiö"

    def test_string_language_codes_compat(self):
        """Old-style string language codes (EN/FI) still work."""
        data = dict(PRH_COMPANY)
        data["companyForms"] = [{
            "type": "OY",
            "descriptions": [
                {"languageCode": "FI", "description": "Osakeyhtiö"},
                {"languageCode": "EN", "description": "Limited company"},
            ],
        }]
        result = _parse_prh_response(data)
        assert result["legal_form_name"] == "Limited company"


# --- Adapter tests ---

class TestPrhAdapter:
    def test_matches_finland(self):
        adapter = PrhAdapter()
        assert adapter.matches_company("Finland", None) is True
        assert adapter.matches_company("FI", None) is True
        assert adapter.matches_company("Suomi", None) is True
        assert adapter.matches_company(None, "wolt.fi") is True
        assert adapter.matches_company("Sweden", "firma.se") is False
        assert adapter.matches_company(None, None) is False

    def test_name_similarity_suffix_stripping(self):
        adapter = PrhAdapter()
        assert adapter.name_similarity("Wolt Enterprises", "Wolt Enterprises Oy") == 1.0
        sim = adapter.name_similarity("Wolt", "Wolt Enterprises Oy")
        assert sim > 0.2  # short query vs long name, low but nonzero

    @patch("api.services.registries.prh.requests.get")
    def test_lookup_by_id_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = PRH_SEARCH_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        adapter = PrhAdapter()
        result = adapter.lookup_by_id("2646674-9")
        assert result["ico"] == "2646674-9"
        assert result["official_name"] == "Wolt Oy"

    @patch("api.services.registries.prh.requests.get")
    def test_lookup_not_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"totalResults": 0, "companies": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        adapter = PrhAdapter()
        assert adapter.lookup_by_id("0000000-0") is None

    @patch("api.services.registries.prh.requests.get")
    def test_lookup_error(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("Network error")

        adapter = PrhAdapter()
        assert adapter.lookup_by_id("2646674-9") is None

    @patch("api.services.registries.prh.requests.get")
    def test_search_by_name(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = PRH_SEARCH_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        adapter = PrhAdapter()
        results = adapter.search_by_name("Wolt")
        assert len(results) == 1
        assert results[0]["ico"] == "2646674-9"
        assert "similarity" in results[0]

    @patch("api.services.registries.prh.requests.get")
    def test_search_empty(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"totalResults": 0, "companies": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        adapter = PrhAdapter()
        assert adapter.search_by_name("XYZNONEXISTENT") == []
