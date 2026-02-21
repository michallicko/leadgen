"""Czech ISIR (Insolvenční rejstřík) insolvency register adapter.

Queries the ISIR CUZK SOAP web service to check for insolvency proceedings
against Czech companies by ICO. The service is free, no authentication needed.

Endpoint: https://isir.justice.cz:8443/isir_cuzk_ws/IsirWsCuzkService
Protocol: SOAP 1.1 (document/literal)
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import requests
from sqlalchemy import text

from .base import BaseRegistryAdapter

logger = logging.getLogger(__name__)

ISIR_ENDPOINT = "https://isir.justice.cz:8443/isir_cuzk_ws/IsirWsCuzkService"
ISIR_TIMEOUT = 15
ISIR_DELAY = 0.3

# SOAP envelope template for querying by ICO
_SOAP_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:typ="http://isirws.cca.cz/types/">
  <soapenv:Header/>
  <soapenv:Body>
    <typ:getIsirWsCuzkDataRequest>
      <ic>{ico}</ic>
      <maxPocetVysledku>{max_results}</maxPocetVysledku>
    </typ:getIsirWsCuzkDataRequest>
  </soapenv:Body>
</soapenv:Envelope>"""

# Namespace map for parsing SOAP response
_NS = {
    "soap": "http://schemas.xmlsoap.org/soap/envelope/",
    "ns2": "http://isirws.cca.cz/types/",
}

# druhStavKonkursu → human-readable status
PROCEEDING_STATUSES = {
    "NEVYRIZENY": "pending",
    "MORATORIUM": "moratorium",
    "UPADEK": "insolvency_declared",
    "KONKURS": "bankruptcy",
    "REORGANIZ": "reorganization",
    "ODDLUZENI": "debt_relief",
    "ODDLUZENI_SPLNENO": "debt_relief_completed",
    "KONKURS_PO_REORG": "bankruptcy_after_reorganization",
    "VYRIZENY": "completed",
    "PRAVOMOCNE_SKONC": "legally_concluded",
    "ODSKRTNUTO": "struck_off",
}


def query_by_ico(ico, max_results=20):
    """Query ISIR for insolvency proceedings by ICO.

    Returns dict with:
        - proceedings: list of parsed proceeding dicts
        - total: number of results
        - error: error code if any (WS1, WS2, etc.)
        - raw: list of raw XML element dicts
    """
    body = _SOAP_TEMPLATE.format(ico=_sanitize_ico(ico), max_results=max_results)

    try:
        resp = requests.post(
            ISIR_ENDPOINT,
            data=body.encode("utf-8"),
            headers={
                "Content-Type": "text/xml;charset=UTF-8",
                "SOAPAction": '""',
            },
            timeout=ISIR_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("ISIR query for ICO %s failed: %s", ico, e)
        return {"proceedings": [], "total": 0, "error": str(e), "raw": []}

    return _parse_soap_response(resp.content)


def _sanitize_ico(ico):
    """Strip whitespace and validate ICO format."""
    s = str(ico).strip()
    # Czech ICO is 8 digits, but don't enforce strictly
    return s


def _parse_soap_response(xml_bytes):
    """Parse ISIR CUZK SOAP response into structured data."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        logger.warning("ISIR XML parse error: %s", e)
        return {"proceedings": [], "total": 0, "error": "xml_parse_error", "raw": []}

    response_el = root.find(".//ns2:getIsirWsCuzkDataResponse", _NS)
    if response_el is None:
        return {
            "proceedings": [],
            "total": 0,
            "error": "no_response_element",
            "raw": [],
        }

    # Check status
    stav = response_el.find("stav")
    error_code = _text(stav, "kodChyby") if stav is not None else None
    total = int(_text(stav, "pocetVysledku") or "0") if stav is not None else 0

    if error_code == "WS2":
        # Empty result — no insolvency records
        return {"proceedings": [], "total": 0, "error": None, "raw": []}
    if error_code and error_code not in ("WS2",):
        error_text = _text(stav, "textChyby") or error_code
        return {"proceedings": [], "total": 0, "error": error_text, "raw": []}

    # Parse data elements
    proceedings = []
    raw_items = []
    for data_el in response_el.findall("data"):
        raw = _element_to_dict(data_el)
        raw_items.append(raw)
        proceedings.append(_parse_proceeding(raw))

    return {"proceedings": proceedings, "total": total, "error": None, "raw": raw_items}


def _parse_proceeding(raw):
    """Convert raw ISIR data dict to structured proceeding."""
    status_code = raw.get("druhStavKonkursu", "")
    case_number = _build_case_number(raw)

    return {
        "case_number": case_number,
        "court": raw.get("nazevOrganizace", ""),
        "status_code": status_code,
        "status": PROCEEDING_STATUSES.get(
            status_code, status_code.lower() if status_code else "unknown"
        ),
        "debtor_name": raw.get("nazevOsoby", ""),
        "debtor_address": _build_address(raw),
        "started_at": raw.get("datumPmZahajeniUpadku", "").replace("Z", "")
        if raw.get("datumPmZahajeniUpadku")
        else None,
        "ended_at": raw.get("datumPmUkonceniUpadku", "").replace("Z", "")
        if raw.get("datumPmUkonceniUpadku")
        else None,
        "detail_url": raw.get("urlDetailRizeni", ""),
        "has_other_debtors": raw.get("dalsiDluznikVRizeni") == "T",
        "is_active": status_code
        not in ("VYRIZENY", "PRAVOMOCNE_SKONC", "ODSKRTNUTO", "ODDLUZENI_SPLNENO"),
    }


def _build_case_number(raw):
    """Build case number from ISIR fields: 'INS 10525/2016'."""
    druh = raw.get("druhVec", "")
    bc = raw.get("bcVec", "")
    rocnik = raw.get("rocnik", "")
    if druh and bc and rocnik:
        return f"{druh} {bc}/{rocnik}"
    return ""


def _build_address(raw):
    """Build address string from ISIR fields."""
    parts = []
    if raw.get("ulice"):
        s = raw["ulice"]
        if raw.get("cisloPopisne"):
            s += " " + raw["cisloPopisne"]
        parts.append(s)
    if raw.get("mesto"):
        parts.append(raw["mesto"])
    if raw.get("psc"):
        parts.append(raw["psc"])
    return ", ".join(parts) if parts else ""


def _text(parent, tag):
    """Get text content of a child element, or None."""
    if parent is None:
        return None
    el = parent.find(tag)
    return el.text if el is not None else None


def _element_to_dict(el):
    """Convert an XML element and its children to a flat dict."""
    result = {}
    for child in el:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        result[tag] = child.text
    return result


def enrich_company(company_id, tenant_id, ico):
    """Run ISIR enrichment for a single company.

    Args:
        company_id: UUID of the company
        tenant_id: UUID of the tenant
        ico: Czech ICO number to query

    Returns dict with status, has_insolvency, total_proceedings, etc.
    """
    if not ico:
        return {"status": "skipped", "reason": "no_ico", "enrichment_cost_usd": 0}

    result = query_by_ico(ico)

    if result["error"]:
        return {
            "status": "error",
            "error": result["error"],
            "enrichment_cost_usd": 0,
        }

    proceedings = result["proceedings"]
    active = [p for p in proceedings if p.get("is_active")]

    store_result(
        company_id=company_id,
        tenant_id=tenant_id,
        ico=ico,
        proceedings=proceedings,
        raw=result["raw"],
    )

    return {
        "status": "enriched",
        "has_insolvency": len(proceedings) > 0,
        "total_proceedings": len(proceedings),
        "active_proceedings": len(active),
        "enrichment_cost_usd": 0,
    }


def store_result(company_id, tenant_id, ico, proceedings, raw):
    """Upsert company_insolvency_data row."""
    from ...models import db

    now = datetime.now(timezone.utc)
    active = [p for p in proceedings if p.get("is_active")]

    proceedings_json = json.dumps(proceedings, default=str)
    raw_json = json.dumps(raw, default=str)

    params = {
        "company_id": str(company_id),
        "tenant_id": str(tenant_id),
        "ico": ico,
        "has_insolvency": len(proceedings) > 0,
        "proceedings": proceedings_json,
        "total_proceedings": len(proceedings),
        "active_proceedings": len(active),
        "last_checked_at": now.isoformat(),
        "raw_response": raw_json,
        "updated_at": now.isoformat(),
    }

    existing = db.session.execute(
        text("SELECT id FROM company_insolvency_data WHERE company_id = :company_id"),
        {"company_id": str(company_id)},
    ).fetchone()

    if existing:
        db.session.execute(
            text("""
                UPDATE company_insolvency_data SET
                    ico = :ico, has_insolvency = :has_insolvency,
                    proceedings = :proceedings,
                    total_proceedings = :total_proceedings,
                    active_proceedings = :active_proceedings,
                    last_checked_at = :last_checked_at,
                    raw_response = :raw_response,
                    updated_at = :updated_at,
                    enrichment_cost_usd = 0
                WHERE company_id = :company_id
            """),
            params,
        )
    else:
        params["id"] = str(uuid.uuid4())
        db.session.execute(
            text("""
                INSERT INTO company_insolvency_data (
                    id, company_id, tenant_id, ico, has_insolvency,
                    proceedings, total_proceedings, active_proceedings,
                    last_checked_at, raw_response, enrichment_cost_usd
                ) VALUES (
                    :id, :company_id, :tenant_id, :ico, :has_insolvency,
                    :proceedings, :total_proceedings, :active_proceedings,
                    :last_checked_at, :raw_response, 0
                )
            """),
            params,
        )

    db.session.commit()


class IsirAdapter(BaseRegistryAdapter):
    """ISIR adapter for the unified registry orchestrator.

    Supplementary adapter — depends on CZ (ARES) to obtain the ICO first.
    Only provides insolvency data, not general company registration info.
    """

    country_code = "CZ"
    country_names = [
        "Czech Republic",
        "Czechia",
        "CZ",
        "Česká republika",
        "Ceska republika",
    ]
    domain_tlds = [".cz"]
    legal_suffixes = []
    request_delay = ISIR_DELAY
    timeout = ISIR_TIMEOUT

    provides_fields = ["insolvency_proceedings", "insolvency_flag"]
    requires_inputs = ["ico"]
    depends_on = ["CZ"]
    is_supplementary = True

    def lookup_by_id(self, ico):
        """Query ISIR by ICO, return structured result or None."""
        result = query_by_ico(ico)
        if result.get("error"):
            return None
        proceedings = result["proceedings"]
        active = [p for p in proceedings if p.get("is_active")]
        return {
            "has_insolvency": len(proceedings) > 0,
            "proceedings": proceedings,
            "total_proceedings": len(proceedings),
            "active_proceedings": len(active),
            "raw": result["raw"],
        }

    def search_by_name(self, name, max_results=5):
        """ISIR has no name search — requires ICO."""
        raise NotImplementedError("ISIR requires ICO, not name search")

    def enrich_company(
        self,
        company_id,
        tenant_id,
        name,
        reg_id=None,
        hq_country=None,
        domain=None,
        store=True,
    ):
        """Run ISIR enrichment. reg_id is the ICO."""
        ico = reg_id
        if not ico:
            return {"status": "skipped", "reason": "no_ico", "enrichment_cost_usd": 0}

        result_data = self.lookup_by_id(ico)
        if result_data is None:
            return {
                "status": "error",
                "error": "isir_query_failed",
                "enrichment_cost_usd": 0,
            }

        if store:
            store_result(
                company_id=company_id,
                tenant_id=tenant_id,
                ico=ico,
                proceedings=result_data["proceedings"],
                raw=result_data["raw"],
            )

        return {
            "status": "enriched",
            "has_insolvency": result_data["has_insolvency"],
            "total_proceedings": result_data["total_proceedings"],
            "active_proceedings": result_data["active_proceedings"],
            "data": result_data,
            "enrichment_cost_usd": 0,
        }
