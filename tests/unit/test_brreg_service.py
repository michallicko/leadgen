"""Unit tests for the Norway BRREG registry adapter."""
from unittest.mock import MagicMock, patch

import pytest

from api.services.registries.brreg import BrregAdapter, _parse_brreg_response


# --- Fixtures (real BRREG API format) ---

BRREG_RESPONSE = {
    "organisasjonsnummer": "923609016",
    "navn": "EQUINOR ASA",
    "organisasjonsform": {
        "kode": "ASA",
        "beskrivelse": "Allmennaksjeselskap",
    },
    "forretningsadresse": {
        "land": "Norge",
        "landkode": "NO",
        "postnummer": "4035",
        "poststed": "STAVANGER",
        "adresse": ["Forusbeen 50"],
        "kommune": "STAVANGER",
        "kommunenummer": "1103",
    },
    "naeringskode1": {
        "kode": "06.100",
        "beskrivelse": "Utvinning av råolje",
    },
    "naeringskode2": {
        "kode": "35.111",
        "beskrivelse": "Produksjon av elektrisitet fra vannkraft",
    },
    "stiftelsesdato": "2007-10-01",
    "registreringsdatoEnhetsregisteret": "2007-11-12",
    "antallAnsatte": 21000,
    "konkurs": False,
    "underAvvikling": False,
    "underTvangsavviklingEllerTvangsopplosning": False,
    "kapital": {
        "belop": 7971617834.0,
        "antallAksjer": 3183089082,
        "type": "Aksjekapital",
        "valuta": "NOK",
        "innfortDato": "2024-05-01",
    },
}

BRREG_SEARCH_RESPONSE = {
    "_embedded": {
        "enheter": [BRREG_RESPONSE],
    },
    "page": {"size": 5, "totalElements": 1, "totalPages": 1, "number": 0},
}


# --- Parser tests ---

class TestParseBrregResponse:
    def test_full_response(self):
        result = _parse_brreg_response(BRREG_RESPONSE)
        assert result["ico"] == "923609016"
        assert result["official_name"] == "EQUINOR ASA"
        assert result["legal_form"] == "ASA"
        assert result["legal_form_name"] == "Allmennaksjeselskap"
        assert result["date_established"] == "2007-10-01"
        assert result["address_city"] == "STAVANGER"
        assert result["address_postal_code"] == "4035"
        assert "Forusbeen 50" in result["registered_address"]
        assert result["registration_status"] == "active"
        assert result["insolvency_flag"] is False
        assert len(result["nace_codes"]) == 2
        assert result["nace_codes"][0]["code"] == "06.100"
        assert result["nace_codes"][0]["description"] == "Utvinning av råolje"
        assert result["registered_capital"] == "7971617834 NOK"
        assert result["directors"] == []
        assert result["_raw"] is BRREG_RESPONSE

    def test_bankruptcy_flag(self):
        data = dict(BRREG_RESPONSE)
        data["konkurs"] = True
        result = _parse_brreg_response(data)
        assert result["insolvency_flag"] is True
        assert result["registration_status"] == "dissolved"

    def test_winding_up(self):
        data = dict(BRREG_RESPONSE)
        data["underAvvikling"] = True
        result = _parse_brreg_response(data)
        assert result["insolvency_flag"] is True
        assert result["registration_status"] == "dissolved"

    def test_empty_response(self):
        result = _parse_brreg_response({})
        assert result["ico"] is None
        assert result["official_name"] is None
        assert result["nace_codes"] == []
        assert result["registration_status"] == "active"
        assert result["registered_capital"] is None

    def test_postadresse_fallback(self):
        data = dict(BRREG_RESPONSE)
        del data["forretningsadresse"]
        data["postadresse"] = {
            "postnummer": "0001",
            "poststed": "OSLO",
            "adresse": ["Postboks 1"],
        }
        result = _parse_brreg_response(data)
        assert result["address_city"] == "OSLO"
        assert "Postboks 1" in result["registered_address"]

    def test_no_capital(self):
        data = dict(BRREG_RESPONSE)
        del data["kapital"]
        result = _parse_brreg_response(data)
        assert result["registered_capital"] is None


# --- Adapter tests ---

class TestBrregAdapter:
    def test_matches_norway(self):
        adapter = BrregAdapter()
        assert adapter.matches_company("Norway", None) is True
        assert adapter.matches_company("NO", None) is True
        assert adapter.matches_company("Norge", None) is True
        assert adapter.matches_company(None, "equinor.no") is True
        assert adapter.matches_company("Germany", "firma.de") is False
        assert adapter.matches_company(None, None) is False

    def test_name_similarity_suffix_stripping(self):
        adapter = BrregAdapter()
        assert adapter.name_similarity("Equinor", "EQUINOR ASA") == 1.0
        assert adapter.name_similarity("Equinor", "Equinor") == 1.0
        sim = adapter.name_similarity("Equinor", "Statoil")
        assert sim < 0.5

    @patch("api.services.registries.brreg.requests.get")
    def test_lookup_by_id_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = BRREG_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        adapter = BrregAdapter()
        result = adapter.lookup_by_id("923609016")
        assert result["ico"] == "923609016"
        assert result["official_name"] == "EQUINOR ASA"

    @patch("api.services.registries.brreg.requests.get")
    def test_lookup_by_id_not_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        adapter = BrregAdapter()
        assert adapter.lookup_by_id("000000000") is None

    @patch("api.services.registries.brreg.requests.get")
    def test_lookup_by_id_error(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("Network error")

        adapter = BrregAdapter()
        assert adapter.lookup_by_id("923609016") is None

    @patch("api.services.registries.brreg.requests.get")
    def test_search_by_name_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = BRREG_SEARCH_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        adapter = BrregAdapter()
        results = adapter.search_by_name("Equinor")
        assert len(results) == 1
        assert results[0]["ico"] == "923609016"
        assert "similarity" in results[0]

    @patch("api.services.registries.brreg.requests.get")
    def test_search_empty(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"page": {"totalElements": 0}}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        adapter = BrregAdapter()
        assert adapter.search_by_name("XYZNONEXISTENT") == []


import requests
