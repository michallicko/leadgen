"""Unit tests for the Finland PRH registry adapter."""
from unittest.mock import MagicMock, patch

import pytest
import requests

from api.services.registries.prh import PrhAdapter, _parse_prh_response


# --- Fixtures (real PRH API format) ---

PRH_COMPANY = {
    "businessId": {
        "value": "2611017-6",
        "registrationDate": "2013-10-04",
        "source": "YTJ",
    },
    "names": [
        {
            "name": "Wolt Enterprises Oy",
            "type": "TRADE_REGISTER",
            "registrationDate": "2014-10-10",
            "endDate": None,
            "version": 2,
            "source": "TRADE_REGISTER",
        },
        {
            "name": "Wolt Oy",
            "type": "TRADE_REGISTER",
            "registrationDate": "2013-10-04",
            "endDate": "2014-10-10",
            "version": 1,
            "source": "TRADE_REGISTER",
        },
    ],
    "companyForms": [{
        "type": "OY",
        "descriptions": [
            {"languageCode": "FI", "description": "Osakeyhtiö"},
            {"languageCode": "EN", "description": "Limited company"},
        ],
        "registrationDate": "2013-10-04",
        "version": 1,
        "source": "TRADE_REGISTER",
    }],
    "addresses": [{
        "type": 1,
        "street": "Arkadiankatu 6",
        "postCode": "00100",
        "postOffices": [{"city": "HELSINKI", "languageCode": "FI"}],
        "registrationDate": "2021-01-01",
        "source": "TRADE_REGISTER",
    }],
    "mainBusinessLine": {
        "type": "62010",
        "descriptions": [
            {"languageCode": "FI", "description": "Ohjelmistojen suunnittelu ja valmistus"},
            {"languageCode": "EN", "description": "Computer programming activities"},
        ],
        "typeCodeSet": "TOL2008",
        "registrationDate": "2014-11-01",
        "source": "TRADE_REGISTER",
    },
    "tradeRegisterStatus": "REGISTERED",
    "registrationDate": "2013-10-04",
    "lastModified": "2024-01-15T08:30:00Z",
}

PRH_SEARCH_RESPONSE = {
    "totalResults": 1,
    "companies": [PRH_COMPANY],
}


# --- Parser tests ---

class TestParsePrhResponse:
    def test_full_response(self):
        result = _parse_prh_response(PRH_COMPANY)
        assert result["ico"] == "2611017-6"
        assert result["official_name"] == "Wolt Enterprises Oy"
        assert result["legal_form"] == "OY"
        assert result["legal_form_name"] == "Limited company"
        assert result["date_established"] == "2013-10-04"
        assert result["address_city"] == "HELSINKI"
        assert result["address_postal_code"] == "00100"
        assert "Arkadiankatu 6" in result["registered_address"]
        assert result["registration_status"] == "active"
        assert len(result["nace_codes"]) == 1
        assert result["nace_codes"][0]["code"] == "62010"
        assert result["nace_codes"][0]["description"] == "Computer programming activities"
        assert result["directors"] == []
        assert result["registered_capital"] is None
        assert result["_raw"] is PRH_COMPANY

    def test_active_name_selected(self):
        """Should pick active name (no endDate), not historical."""
        result = _parse_prh_response(PRH_COMPANY)
        assert result["official_name"] == "Wolt Enterprises Oy"

    def test_empty_response(self):
        result = _parse_prh_response({})
        assert result["ico"] is None
        assert result["official_name"] is None
        assert result["nace_codes"] == []
        assert result["registration_status"] == "active"

    def test_deregistered_status(self):
        data = dict(PRH_COMPANY)
        data["tradeRegisterStatus"] = "DEREGISTERED"
        result = _parse_prh_response(data)
        assert result["registration_status"] == "dissolved"

    def test_finnish_description_fallback(self):
        """When no English description, use Finnish."""
        data = dict(PRH_COMPANY)
        data["companyForms"] = [{
            "type": "OY",
            "descriptions": [
                {"languageCode": "FI", "description": "Osakeyhtiö"},
            ],
        }]
        result = _parse_prh_response(data)
        assert result["legal_form_name"] == "Osakeyhtiö"


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
        result = adapter.lookup_by_id("2611017-6")
        assert result["ico"] == "2611017-6"
        assert result["official_name"] == "Wolt Enterprises Oy"

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
        assert adapter.lookup_by_id("2611017-6") is None

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
        assert results[0]["ico"] == "2611017-6"
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
