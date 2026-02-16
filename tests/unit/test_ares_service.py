"""Unit tests for the ARES enrichment service."""
import json
from unittest.mock import MagicMock, patch

import pytest

from api.services.ares import (
    _bigrams,
    _is_czech_company,
    _name_similarity,
    _normalize_name,
    _parse_basic_response,
    _parse_vr_response,
    enrich_company,
    lookup_by_ico,
    lookup_vr,
    search_by_name,
)


# --- Fixtures (real ARES API format) ---

ARES_BASIC_RESPONSE = {
    "ico": "27082440",
    "dic": "CZ27082440",
    "obchodniJmeno": "Alza.cz a.s.",
    "pravniForma": "121",
    "datumVzniku": "2003-08-26",
    "datumZaniku": None,
    "sidlo": {
        "textovaAdresa": "Jankovcova 1522/53, Holešovice, 17000 Praha 7",
        "nazevObce": "Praha",
        "psc": 17000,
    },
    "czNace": ["47250", "620", "461"],
    "seznamRegistraci": {
        "stavZdrojeVr": "AKTIVNI",
        "stavZdrojeRos": "AKTIVNI",
        "stavZdrojeIsir": "NEEXISTUJICI",
    },
    "datumAktualizace": "2026-01-30",
}

ARES_VR_RESPONSE = {
    "icoId": "27082440",
    "zaznamy": [{
        "statutarniOrgany": [
            {
                "nazevOrganu": "Statutární orgán - představenstvo",
                "clenoveOrganu": [
                    {
                        "fyzickaOsoba": {"jmeno": "ALEŠ", "prijmeni": "ZAVORAL"},
                        "clenstvi": {
                            "clenstvi": {"vznikClenstvi": "2022-11-09"},
                            "funkce": {"nazev": "předseda představenstva"},
                        },
                    },
                    {
                        "fyzickaOsoba": {"jmeno": "PETR", "prijmeni": "BENA"},
                        "clenstvi": {
                            "clenstvi": {"vznikClenstvi": "2025-03-31"},
                            "funkce": {"nazev": "člen představenstva"},
                        },
                    },
                    {
                        "fyzickaOsoba": {"jmeno": "JAN", "prijmeni": "NOVÁK"},
                        "datumVymazu": "2022-01-01",
                        "clenstvi": {
                            "clenstvi": {
                                "vznikClenstvi": "2018-06-01",
                                "zanikClenstvi": "2022-01-01",
                            },
                        },
                    },
                ],
            }
        ],
        "zakladniKapital": [
            {
                "datumZapisu": "2017-05-23",
                "vklad": {"typObnos": "KORUNY", "hodnota": "2000000;00"},
                "splaceni": {"typObnos": "PROCENTA", "hodnota": "100"},
            },
            {
                "datumZapisu": "2003-08-06",
                "datumVymazu": "2017-05-23",
                "vklad": {"typObnos": "KORUNY", "hodnota": "100000;00"},
            },
        ],
        "spisovaZnacka": [
            {"soud": "MSPH", "oddil": "B", "vlozka": 8573},
        ],
    }],
}


# --- Parser tests ---

class TestParseBasicResponse:
    def test_parse_full_response(self):
        result = _parse_basic_response(ARES_BASIC_RESPONSE)
        assert result["ico"] == "27082440"
        assert result["dic"] == "CZ27082440"
        assert result["official_name"] == "Alza.cz a.s."
        assert result["legal_form"] == "121"
        assert result["legal_form_name"] == ""  # real API doesn't include name
        assert result["date_established"] == "2003-08-26"
        assert result["date_dissolved"] is None
        assert result["registered_address"] == "Jankovcova 1522/53, Holešovice, 17000 Praha 7"
        assert result["address_city"] == "Praha"
        assert result["address_postal_code"] == "17000"
        assert result["registration_status"] == "active"
        assert result["insolvency_flag"] is False
        assert len(result["nace_codes"]) == 3
        assert result["nace_codes"][0]["code"] == "47250"
        assert result["nace_codes"][0]["description"] is None  # real API: code only
        assert result["_raw"] is ARES_BASIC_RESPONSE

    def test_parse_dissolved_company(self):
        data = dict(ARES_BASIC_RESPONSE)
        data["datumZaniku"] = "2022-01-01"
        result = _parse_basic_response(data)
        assert result["registration_status"] == "dissolved"

    def test_parse_insolvency_flag(self):
        data = dict(ARES_BASIC_RESPONSE)
        data["seznamRegistraci"] = {"stavZdrojeIsir": "AKTIVNI"}
        result = _parse_basic_response(data)
        assert result["insolvency_flag"] is True

    def test_parse_empty_response(self):
        result = _parse_basic_response({})
        assert result["ico"] is None
        assert result["registration_status"] == "unknown"
        assert result["nace_codes"] == []

    def test_parse_dict_pravni_forma(self):
        """Backward compat: some responses may use dict format."""
        data = dict(ARES_BASIC_RESPONSE)
        data["pravniForma"] = {"kod": "112", "nazev": "s.r.o."}
        result = _parse_basic_response(data)
        assert result["legal_form"] == "112"
        assert result["legal_form_name"] == "s.r.o."


class TestParseVrResponse:
    def test_parse_full_vr(self):
        result = _parse_vr_response(ARES_VR_RESPONSE)
        # Should have 2 current directors (Jan Novák has datumVymazu → filtered out)
        assert len(result["directors"]) == 2
        assert result["directors"][0]["name"] == "ALEŠ ZAVORAL"
        assert "představenstvo" in result["directors"][0]["role"].lower()
        assert result["directors"][0]["since"] == "2022-11-09"
        assert result["registered_capital"] == "2000000 CZK"
        assert result["registration_court"] == "Městský soud v Praze"
        assert result["registration_number"] == "B 8573"

    def test_parse_empty_vr(self):
        result = _parse_vr_response({})
        assert result["directors"] == []
        assert result["registered_capital"] is None

    def test_parse_numeric_capital(self):
        data = {"zakladniKapital": 500000}
        result = _parse_vr_response(data)
        assert result["registered_capital"] == "500000 CZK"

    def test_removed_directors_filtered(self):
        """Directors with datumVymazu should be excluded."""
        result = _parse_vr_response(ARES_VR_RESPONSE)
        names = [d["name"] for d in result["directors"]]
        assert "JAN NOVÁK" not in names

    def test_historical_capital_skipped(self):
        """Capital entries with datumVymazu should use latest only."""
        result = _parse_vr_response(ARES_VR_RESPONSE)
        # Latest is 2000000, historical was 100000
        assert result["registered_capital"] == "2000000 CZK"


# --- Name matching tests ---

class TestNameSimilarity:
    def test_exact_match(self):
        assert _name_similarity("Alza", "Alza") == 1.0

    def test_czech_suffix_stripping(self):
        sim = _name_similarity("Alza", "Alza a.s.")
        assert sim == 1.0

    def test_sro_stripping(self):
        sim = _name_similarity("Firma XYZ", "Firma XYZ s.r.o.")
        assert sim == 1.0

    def test_different_names(self):
        sim = _name_similarity("Apple", "Microsoft")
        assert sim < 0.5

    def test_similar_names(self):
        sim = _name_similarity("Alza CZ", "Alza Czech")
        assert sim > 0.5

    def test_empty_strings(self):
        assert _name_similarity("", "Alza") == 0.0
        assert _name_similarity("Alza", "") == 0.0
        assert _name_similarity("", "") == 0.0


class TestNormalizeName:
    def test_basic_normalize(self):
        assert _normalize_name("  Alza.cz  ") == "alza.cz"

    def test_strip_sro(self):
        assert _normalize_name("Firma s.r.o.") == "firma"

    def test_strip_as(self):
        assert _normalize_name("Alza a.s.") == "alza"


class TestIsCzechCompany:
    def test_with_ico(self):
        assert _is_czech_company("12345678", None, None) is True

    def test_with_cz_country(self):
        assert _is_czech_company(None, "Czech Republic", None) is True
        assert _is_czech_company(None, "CZ", None) is True

    def test_with_cz_domain(self):
        assert _is_czech_company(None, None, "firma.cz") is True

    def test_not_czech(self):
        assert _is_czech_company(None, "Germany", "firma.de") is False

    def test_all_none(self):
        assert _is_czech_company(None, None, None) is False


# --- HTTP lookup tests (mocked) ---

class TestLookupByIco:
    @patch("api.services.registries.ares.requests.get")
    def test_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = ARES_BASIC_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = lookup_by_ico("27082440")
        assert result["ico"] == "27082440"
        assert result["official_name"] == "Alza.cz a.s."
        mock_get.assert_called_once()

    @patch("api.services.registries.ares.requests.get")
    def test_not_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        result = lookup_by_ico("99999999")
        assert result is None

    @patch("api.services.registries.ares.requests.get")
    def test_request_error(self, mock_get):
        import requests as req
        mock_get.side_effect = req.ConnectionError("Network error")

        result = lookup_by_ico("27082440")
        assert result is None


class TestLookupVr:
    @patch("api.services.registries.ares.requests.get")
    def test_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = ARES_VR_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = lookup_vr("27082440")
        assert len(result["directors"]) == 2
        assert result["registered_capital"] == "2000000 CZK"


class TestSearchByName:
    @patch("api.services.registries.ares.requests.post")
    def test_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "ekonomickeSubjekty": [ARES_BASIC_RESPONSE],
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = search_by_name("Alza")
        assert len(result) == 1
        assert result[0]["ico"] == "27082440"
        assert "similarity" in result[0]

    @patch("api.services.registries.ares.requests.post")
    def test_empty_results(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ekonomickeSubjekty": []}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = search_by_name("XYZ Nonexistent Corp")
        assert result == []


# --- Enrich company integration tests (mocked) ---

class TestEnrichCompany:
    @patch("api.services.registries.ares.time")
    @patch("api.services.registries.ares.AresAdapter._update_vr_data")
    @patch("api.services.registries.ares.AresAdapter.lookup_vr")
    @patch("api.services.registries.ares.AresAdapter.lookup_by_id")
    @patch("api.services.registries.base.BaseRegistryAdapter.store_result")
    def test_ico_direct_lookup(self, mock_store, mock_lookup, mock_vr, mock_update_vr, mock_time):
        mock_time.sleep = MagicMock()
        mock_lookup.return_value = {
            "ico": "27074358",
            "official_name": "Alza.cz a.s.",
            "_raw": {"test": True},
        }
        mock_vr.return_value = {
            "directors": [{"name": "Jan Novak", "role": "CEO", "since": "2020-01-01"}],
            "registered_capital": "1000000 CZK",
            "_raw": {"vr": True},
        }

        result = enrich_company(
            company_id="abc-123",
            tenant_id="tenant-1",
            name="Alza",
            ico="27074358",
            hq_country="CZ",
            domain="alza.cz",
        )

        assert result["status"] == "enriched"
        assert result["ico"] == "27074358"
        assert result["method"] == "ico_direct"
        assert result["confidence"] == 1.0
        mock_store.assert_called_once()

    def test_not_czech_skipped(self):
        result = enrich_company(
            company_id="abc-123",
            tenant_id="tenant-1",
            name="German Corp",
            ico=None,
            hq_country="Germany",
            domain="german.de",
        )
        assert result["status"] == "skipped"
        assert result["reason"] == "not_czech"

    @patch("api.services.registries.ares.time")
    @patch("api.services.registries.ares.AresAdapter.search_by_name")
    @patch("api.services.registries.base.BaseRegistryAdapter.store_result")
    @patch("api.services.registries.ares.AresAdapter.lookup_vr")
    @patch("api.services.registries.base.time")
    def test_name_search_auto_match(self, mock_base_time, mock_vr, mock_store, mock_search, mock_ares_time):
        mock_base_time.sleep = MagicMock()
        mock_ares_time.sleep = MagicMock()
        mock_search.return_value = [{
            "ico": "12345678",
            "official_name": "Firma Test s.r.o.",
            "similarity": 0.92,
            "_raw": {"test": True},
        }]
        mock_vr.return_value = None

        result = enrich_company(
            company_id="abc-123",
            tenant_id="tenant-1",
            name="Firma Test",
            ico=None,
            hq_country="CZ",
            domain=None,
        )

        assert result["status"] == "enriched"
        assert result["method"] == "name_auto"
        assert result["confidence"] == 0.92

    @patch("api.services.registries.ares.AresAdapter.search_by_name")
    @patch("api.services.registries.base.time")
    def test_name_search_ambiguous(self, mock_time, mock_search):
        mock_time.sleep = MagicMock()
        mock_search.return_value = [
            {"ico": "11111111", "official_name": "Firma A s.r.o.", "similarity": 0.75, "registered_address": "Praha"},
            {"ico": "22222222", "official_name": "Firma B a.s.", "similarity": 0.65, "registered_address": "Brno"},
        ]

        result = enrich_company(
            company_id="abc-123",
            tenant_id="tenant-1",
            name="Firma",
            ico=None,
            hq_country="CZ",
            domain=None,
        )

        assert result["status"] == "ambiguous"
        assert len(result["candidates"]) == 2

    @patch("api.services.registries.ares.AresAdapter.search_by_name")
    @patch("api.services.registries.base.time")
    def test_name_search_no_match(self, mock_time, mock_search):
        mock_time.sleep = MagicMock()
        mock_search.return_value = []

        result = enrich_company(
            company_id="abc-123",
            tenant_id="tenant-1",
            name="Unknown Corp",
            ico=None,
            hq_country="CZ",
            domain=None,
        )

        assert result["status"] == "no_match"


class TestBigrams:
    def test_basic(self):
        assert _bigrams("abc") == ["ab", "bc"]

    def test_short(self):
        assert _bigrams("a") == []

    def test_empty(self):
        assert _bigrams("") == []
