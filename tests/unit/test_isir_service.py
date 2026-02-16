"""Unit tests for the ISIR insolvency register adapter."""
import json
from unittest.mock import MagicMock, patch

import pytest

from api.services.registries.isir import (
    PROCEEDING_STATUSES,
    _build_address,
    _build_case_number,
    _parse_proceeding,
    _parse_soap_response,
    _sanitize_ico,
    enrich_company,
    query_by_ico,
    store_result,
)


# --- SOAP response fixtures ---

SOAP_RESPONSE_WITH_DATA = b"""<?xml version='1.0' encoding='UTF-8'?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <ns2:getIsirWsCuzkDataResponse xmlns:ns2="http://isirws.cca.cz/types/">
      <data>
        <ic>26863154</ic>
        <cisloSenatu>25</cisloSenatu>
        <druhVec>INS</druhVec>
        <bcVec>10525</bcVec>
        <rocnik>2016</rocnik>
        <nazevOrganizace>Krajsky soud v Ostrave</nazevOrganizace>
        <nazevOsoby>OKD, a.s.</nazevOsoby>
        <druhAdresy>SIDLO FY</druhAdresy>
        <mesto>Karvina</mesto>
        <ulice>Stonavska</ulice>
        <cisloPopisne>2179</cisloPopisne>
        <psc>735 06</psc>
        <druhStavKonkursu>REORGANIZ</druhStavKonkursu>
        <urlDetailRizeni>https://isir.justice.cz/isir/ueu/evidence_upadcu_detail.do?id=ABC123</urlDetailRizeni>
        <dalsiDluznikVRizeni>F</dalsiDluznikVRizeni>
        <datumPmZahajeniUpadku>2016-05-09Z</datumPmZahajeniUpadku>
      </data>
      <stav>
        <pocetVysledku>1</pocetVysledku>
        <relevanceVysledku>2</relevanceVysledku>
        <casSynchronizace>2026-02-16T18:00:00.000Z</casSynchronizace>
      </stav>
    </ns2:getIsirWsCuzkDataResponse>
  </soap:Body>
</soap:Envelope>"""

SOAP_RESPONSE_EMPTY = b"""<?xml version='1.0' encoding='UTF-8'?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <ns2:getIsirWsCuzkDataResponse xmlns:ns2="http://isirws.cca.cz/types/">
      <stav>
        <kodChyby>WS2</kodChyby>
        <textChyby>Prazdny vysledek</textChyby>
        <popisChyby>Zadanym kriterium neodpovidaji zadne zaznamy</popisChyby>
      </stav>
    </ns2:getIsirWsCuzkDataResponse>
  </soap:Body>
</soap:Envelope>"""

SOAP_RESPONSE_ERROR = b"""<?xml version='1.0' encoding='UTF-8'?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <ns2:getIsirWsCuzkDataResponse xmlns:ns2="http://isirws.cca.cz/types/">
      <stav>
        <kodChyby>WS1</kodChyby>
        <textChyby>Nespravna kombinace parametru</textChyby>
      </stav>
    </ns2:getIsirWsCuzkDataResponse>
  </soap:Body>
</soap:Envelope>"""

SOAP_RESPONSE_MULTIPLE = b"""<?xml version='1.0' encoding='UTF-8'?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <ns2:getIsirWsCuzkDataResponse xmlns:ns2="http://isirws.cca.cz/types/">
      <data>
        <ic>12345678</ic>
        <cisloSenatu>10</cisloSenatu>
        <druhVec>INS</druhVec>
        <bcVec>5000</bcVec>
        <rocnik>2020</rocnik>
        <nazevOrganizace>Mestsky soud v Praze</nazevOrganizace>
        <nazevOsoby>TestCo s.r.o.</nazevOsoby>
        <mesto>Praha</mesto>
        <druhStavKonkursu>KONKURS</druhStavKonkursu>
        <urlDetailRizeni>https://isir.justice.cz/detail1</urlDetailRizeni>
        <dalsiDluznikVRizeni>F</dalsiDluznikVRizeni>
        <datumPmZahajeniUpadku>2020-01-15Z</datumPmZahajeniUpadku>
      </data>
      <data>
        <ic>12345678</ic>
        <cisloSenatu>10</cisloSenatu>
        <druhVec>INS</druhVec>
        <bcVec>3000</bcVec>
        <rocnik>2018</rocnik>
        <nazevOrganizace>Mestsky soud v Praze</nazevOrganizace>
        <nazevOsoby>TestCo s.r.o.</nazevOsoby>
        <mesto>Praha</mesto>
        <druhStavKonkursu>VYRIZENY</druhStavKonkursu>
        <urlDetailRizeni>https://isir.justice.cz/detail2</urlDetailRizeni>
        <dalsiDluznikVRizeni>F</dalsiDluznikVRizeni>
        <datumPmZahajeniUpadku>2018-06-01Z</datumPmZahajeniUpadku>
        <datumPmUkonceniUpadku>2019-12-31Z</datumPmUkonceniUpadku>
      </data>
      <stav>
        <pocetVysledku>2</pocetVysledku>
        <relevanceVysledku>2</relevanceVysledku>
      </stav>
    </ns2:getIsirWsCuzkDataResponse>
  </soap:Body>
</soap:Envelope>"""

SOAP_RESPONSE_COMPLETED = b"""<?xml version='1.0' encoding='UTF-8'?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <ns2:getIsirWsCuzkDataResponse xmlns:ns2="http://isirws.cca.cz/types/">
      <data>
        <ic>99999999</ic>
        <cisloSenatu>5</cisloSenatu>
        <druhVec>INS</druhVec>
        <bcVec>100</bcVec>
        <rocnik>2015</rocnik>
        <nazevOrganizace>Krajsky soud v Brne</nazevOrganizace>
        <nazevOsoby>OldCo a.s.</nazevOsoby>
        <mesto>Brno</mesto>
        <druhStavKonkursu>PRAVOMOCNE_SKONC</druhStavKonkursu>
        <urlDetailRizeni>https://isir.justice.cz/detail3</urlDetailRizeni>
        <dalsiDluznikVRizeni>F</dalsiDluznikVRizeni>
        <datumPmZahajeniUpadku>2015-03-01Z</datumPmZahajeniUpadku>
        <datumPmUkonceniUpadku>2017-06-30Z</datumPmUkonceniUpadku>
      </data>
      <stav>
        <pocetVysledku>1</pocetVysledku>
        <relevanceVysledku>2</relevanceVysledku>
      </stav>
    </ns2:getIsirWsCuzkDataResponse>
  </soap:Body>
</soap:Envelope>"""


# --- XML parsing tests ---

class TestParseSoapResponse:
    def test_parse_with_data(self):
        result = _parse_soap_response(SOAP_RESPONSE_WITH_DATA)
        assert result["total"] == 1
        assert result["error"] is None
        assert len(result["proceedings"]) == 1
        p = result["proceedings"][0]
        assert p["case_number"] == "INS 10525/2016"
        assert p["court"] == "Krajsky soud v Ostrave"
        assert p["status_code"] == "REORGANIZ"
        assert p["status"] == "reorganization"
        assert p["debtor_name"] == "OKD, a.s."
        assert p["started_at"] == "2016-05-09"
        assert p["ended_at"] is None
        assert p["is_active"] is True
        assert p["has_other_debtors"] is False

    def test_parse_empty_result(self):
        result = _parse_soap_response(SOAP_RESPONSE_EMPTY)
        assert result["total"] == 0
        assert result["error"] is None
        assert result["proceedings"] == []

    def test_parse_error(self):
        result = _parse_soap_response(SOAP_RESPONSE_ERROR)
        assert result["total"] == 0
        assert result["error"] is not None
        assert result["proceedings"] == []

    def test_parse_multiple_proceedings(self):
        result = _parse_soap_response(SOAP_RESPONSE_MULTIPLE)
        assert result["total"] == 2
        assert len(result["proceedings"]) == 2
        # First is active (KONKURS), second is completed (VYRIZENY)
        assert result["proceedings"][0]["is_active"] is True
        assert result["proceedings"][0]["status"] == "bankruptcy"
        assert result["proceedings"][1]["is_active"] is False
        assert result["proceedings"][1]["status"] == "completed"
        assert result["proceedings"][1]["ended_at"] == "2019-12-31"

    def test_parse_completed_proceeding(self):
        result = _parse_soap_response(SOAP_RESPONSE_COMPLETED)
        assert result["total"] == 1
        p = result["proceedings"][0]
        assert p["is_active"] is False
        assert p["status"] == "legally_concluded"
        assert p["ended_at"] == "2017-06-30"

    def test_parse_invalid_xml(self):
        result = _parse_soap_response(b"not xml at all")
        assert result["error"] == "xml_parse_error"
        assert result["proceedings"] == []

    def test_parse_raw_elements(self):
        result = _parse_soap_response(SOAP_RESPONSE_WITH_DATA)
        assert len(result["raw"]) == 1
        raw = result["raw"][0]
        assert raw["ic"] == "26863154"
        assert raw["druhVec"] == "INS"
        assert raw["bcVec"] == "10525"


# --- Helper function tests ---

class TestHelpers:
    def test_sanitize_ico(self):
        assert _sanitize_ico("  12345678  ") == "12345678"
        assert _sanitize_ico(12345678) == "12345678"

    def test_build_case_number(self):
        assert _build_case_number({"druhVec": "INS", "bcVec": "10525", "rocnik": "2016"}) == "INS 10525/2016"
        assert _build_case_number({"druhVec": "", "bcVec": "", "rocnik": ""}) == ""
        assert _build_case_number({}) == ""

    def test_build_address_full(self):
        raw = {"ulice": "Stonavska", "cisloPopisne": "2179", "mesto": "Karvina", "psc": "735 06"}
        assert _build_address(raw) == "Stonavska 2179, Karvina, 735 06"

    def test_build_address_partial(self):
        assert _build_address({"mesto": "Praha"}) == "Praha"
        assert _build_address({}) == ""

    def test_parse_proceeding_active(self):
        raw = {
            "druhVec": "INS", "bcVec": "100", "rocnik": "2023",
            "nazevOrganizace": "Court", "nazevOsoby": "Debtor",
            "druhStavKonkursu": "KONKURS",
            "datumPmZahajeniUpadku": "2023-01-01Z",
            "dalsiDluznikVRizeni": "T",
            "urlDetailRizeni": "https://example.com/detail",
        }
        p = _parse_proceeding(raw)
        assert p["is_active"] is True
        assert p["status"] == "bankruptcy"
        assert p["has_other_debtors"] is True
        assert p["case_number"] == "INS 100/2023"

    def test_proceeding_status_mapping(self):
        for code, status in PROCEEDING_STATUSES.items():
            raw = {"druhStavKonkursu": code, "druhVec": "", "bcVec": "", "rocnik": ""}
            p = _parse_proceeding(raw)
            assert p["status"] == status

    def test_inactive_statuses(self):
        inactive_codes = ["VYRIZENY", "PRAVOMOCNE_SKONC", "ODSKRTNUTO", "ODDLUZENI_SPLNENO"]
        for code in inactive_codes:
            raw = {"druhStavKonkursu": code, "druhVec": "", "bcVec": "", "rocnik": ""}
            p = _parse_proceeding(raw)
            assert p["is_active"] is False, f"{code} should be inactive"

    def test_active_statuses(self):
        active_codes = ["NEVYRIZENY", "MORATORIUM", "UPADEK", "KONKURS", "REORGANIZ", "ODDLUZENI"]
        for code in active_codes:
            raw = {"druhStavKonkursu": code, "druhVec": "", "bcVec": "", "rocnik": ""}
            p = _parse_proceeding(raw)
            assert p["is_active"] is True, f"{code} should be active"


# --- HTTP request tests ---

class TestQueryByIco:
    @patch("api.services.registries.isir.requests.post")
    def test_query_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = SOAP_RESPONSE_WITH_DATA
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = query_by_ico("26863154")
        assert result["total"] == 1
        assert result["proceedings"][0]["case_number"] == "INS 10525/2016"

        # Verify SOAP envelope was sent
        call_args = mock_post.call_args
        assert "isir_cuzk_ws" in call_args[0][0]
        assert b"26863154" in call_args[1]["data"]

    @patch("api.services.registries.isir.requests.post")
    def test_query_no_results(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = SOAP_RESPONSE_EMPTY
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = query_by_ico("27074358")
        assert result["total"] == 0
        assert result["proceedings"] == []
        assert result["error"] is None

    @patch("api.services.registries.isir.requests.post")
    def test_query_network_error(self, mock_post):
        import requests as req
        mock_post.side_effect = req.ConnectionError("timeout")

        result = query_by_ico("12345678")
        assert result["total"] == 0
        assert result["proceedings"] == []
        assert "timeout" in result["error"]

    @patch("api.services.registries.isir.requests.post")
    def test_query_http_error(self, mock_post):
        import requests as req
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req.HTTPError("500")
        mock_post.return_value = mock_resp

        result = query_by_ico("12345678")
        assert result["error"] is not None


# --- Enrichment orchestration tests ---

class TestEnrichCompany:
    @patch("api.services.registries.isir.store_result")
    @patch("api.services.registries.isir.query_by_ico")
    def test_enrich_with_insolvency(self, mock_query, mock_store):
        mock_query.return_value = {
            "proceedings": [
                {"is_active": True, "case_number": "INS 100/2023", "status": "bankruptcy"},
            ],
            "total": 1,
            "error": None,
            "raw": [{"ic": "12345678"}],
        }

        result = enrich_company("comp-1", "tenant-1", "12345678")
        assert result["status"] == "enriched"
        assert result["has_insolvency"] is True
        assert result["total_proceedings"] == 1
        assert result["active_proceedings"] == 1
        assert result["enrichment_cost_usd"] == 0

        mock_store.assert_called_once()

    @patch("api.services.registries.isir.store_result")
    @patch("api.services.registries.isir.query_by_ico")
    def test_enrich_no_insolvency(self, mock_query, mock_store):
        mock_query.return_value = {
            "proceedings": [],
            "total": 0,
            "error": None,
            "raw": [],
        }

        result = enrich_company("comp-2", "tenant-1", "27074358")
        assert result["status"] == "enriched"
        assert result["has_insolvency"] is False
        assert result["total_proceedings"] == 0
        assert result["active_proceedings"] == 0

        mock_store.assert_called_once()

    def test_enrich_no_ico(self):
        result = enrich_company("comp-3", "tenant-1", None)
        assert result["status"] == "skipped"
        assert result["reason"] == "no_ico"

    def test_enrich_empty_ico(self):
        result = enrich_company("comp-4", "tenant-1", "")
        assert result["status"] == "skipped"

    @patch("api.services.registries.isir.query_by_ico")
    def test_enrich_api_error(self, mock_query):
        mock_query.return_value = {
            "proceedings": [],
            "total": 0,
            "error": "Connection timeout",
            "raw": [],
        }

        result = enrich_company("comp-5", "tenant-1", "12345678")
        assert result["status"] == "error"
        assert "timeout" in result["error"].lower()

    @patch("api.services.registries.isir.store_result")
    @patch("api.services.registries.isir.query_by_ico")
    def test_enrich_mixed_active_inactive(self, mock_query, mock_store):
        mock_query.return_value = {
            "proceedings": [
                {"is_active": True, "case_number": "INS 500/2024"},
                {"is_active": False, "case_number": "INS 200/2018"},
            ],
            "total": 2,
            "error": None,
            "raw": [{}],
        }

        result = enrich_company("comp-6", "tenant-1", "12345678")
        assert result["total_proceedings"] == 2
        assert result["active_proceedings"] == 1


# --- Store result tests ---

class TestStoreResult:
    def test_store_insert(self, app, db):
        """Test inserting new insolvency data."""
        from api.models import db as appdb

        # Create test company and tenant
        appdb.session.execute(
            appdb.text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": "t1", "name": "Test", "slug": "test"},
        )
        appdb.session.execute(
            appdb.text("""INSERT INTO companies (id, tenant_id, name, status)
                          VALUES (:id, :tid, :name, :status)"""),
            {"id": "c1", "tid": "t1", "name": "Test Co", "status": "new"},
        )
        appdb.session.commit()

        store_result(
            company_id="c1",
            tenant_id="t1",
            ico="12345678",
            proceedings=[{"case_number": "INS 100/2023", "is_active": True}],
            raw=[{"ic": "12345678"}],
        )

        row = appdb.session.execute(
            appdb.text("SELECT * FROM company_insolvency_data WHERE company_id = :cid"),
            {"cid": "c1"},
        ).fetchone()

        assert row is not None
        assert row.ico == "12345678"
        assert bool(row.has_insolvency) is True
        assert row.total_proceedings == 1
        assert row.active_proceedings == 1

    def test_store_upsert(self, app, db):
        """Test updating existing insolvency data."""
        from api.models import db as appdb

        appdb.session.execute(
            appdb.text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": "t2", "name": "Test2", "slug": "test2"},
        )
        appdb.session.execute(
            appdb.text("""INSERT INTO companies (id, tenant_id, name, status)
                          VALUES (:id, :tid, :name, :status)"""),
            {"id": "c2", "tid": "t2", "name": "Test Co 2", "status": "new"},
        )
        appdb.session.commit()

        # First insert
        store_result("c2", "t2", "99999999", [], [])
        row = appdb.session.execute(
            appdb.text("SELECT has_insolvency FROM company_insolvency_data WHERE company_id = :cid"),
            {"cid": "c2"},
        ).fetchone()
        assert bool(row.has_insolvency) is False

        # Update with insolvency data
        store_result("c2", "t2", "99999999",
                     [{"case_number": "INS 50/2024", "is_active": True}],
                     [{"ic": "99999999"}])
        row = appdb.session.execute(
            appdb.text("SELECT has_insolvency, total_proceedings FROM company_insolvency_data WHERE company_id = :cid"),
            {"cid": "c2"},
        ).fetchone()
        assert bool(row.has_insolvency) is True
        assert row.total_proceedings == 1
