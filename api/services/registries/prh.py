"""Finland PRH (Patent and Registration Office) adapter.

API: https://avoindata.prh.fi/opendata-ytj-api/v3
No authentication required. Returns JSON.
"""

import logging

import requests

from .base import BaseRegistryAdapter

logger = logging.getLogger(__name__)

PRH_BASE_URL = "https://avoindata.prh.fi/opendata-ytj-api/v3"

FINNISH_SUFFIXES = [
    r"\bOYJ?\s*$",          # OY, OYJ
    r"\bOY\s+AB\s*$",       # OY AB (bilingual)
    r"\bOSK\s*$",           # Osuuskunta
    r"\bAB\s*$",            # Aktiebolag (Swedish)
    r"\bKY\s*$",            # Kommandiittiyhtiö
    r"\bAY\s*$",            # Avoin yhtiö
    r"\bRY\s*$",            # Rekisteröity yhdistys
    r"\bRS\s*$",            # Rekisteröity säätiö
]


class PrhAdapter(BaseRegistryAdapter):
    country_code = "FI"
    country_names = ["Finland", "FI", "Suomi", "Finnland"]
    domain_tlds = [".fi"]
    legal_suffixes = FINNISH_SUFFIXES
    request_delay = 0.3
    timeout = 10

    def lookup_by_id(self, business_id):
        """Look up by Y-tunnus (business ID)."""
        url = f"{PRH_BASE_URL}/companies"
        params = {"businessId": business_id}
        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            companies = data.get("companies", [])
            if not companies:
                return None
            return _parse_prh_response(companies[0])
        except requests.RequestException as e:
            logger.warning("PRH lookup for %s failed: %s", business_id, e)
            return None

    def search_by_name(self, name, max_results=5):
        """Search PRH by company name."""
        url = f"{PRH_BASE_URL}/companies"
        params = {"name": name, "maxResults": max_results}
        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            companies = data.get("companies", [])

            candidates = []
            for item in companies:
                parsed = _parse_prh_response(item)
                parsed["similarity"] = self.name_similarity(
                    name, parsed.get("official_name", ""))
                candidates.append(parsed)

            candidates.sort(key=lambda c: c.get("similarity", 0), reverse=True)
            return candidates
        except requests.RequestException as e:
            logger.warning("PRH name search for '%s' failed: %s", name, e)
            return []


def _parse_prh_response(data):
    """Parse PRH company response into standardized format.

    Real API fields:
    - businessId: {value, registrationDate, source}
    - names: [{name, type, registrationDate, endDate, version, source}]
    - companyForms: [{type, descriptions: [{languageCode, description}]}]
    - addresses: [{type, street, postCode, postOffices: [{city}]}]
    - mainBusinessLine: {type, descriptions: [{languageCode, description}]}
    - registrationDate: string
    - tradeRegisterStatus: string
    """
    # Business ID
    bid = data.get("businessId", {}) or {}
    business_id = bid.get("value")

    # Name — use latest active name (no endDate, prefer TRADE_REGISTER type)
    official_name = None
    for name_entry in data.get("names", []):
        if not name_entry.get("endDate"):
            official_name = name_entry.get("name")
            if name_entry.get("type") == "TRADE_REGISTER":
                break  # prefer trade register name

    # Company form
    legal_form = ""
    legal_form_name = ""
    for form in data.get("companyForms", []):
        if form.get("type"):
            legal_form = form["type"]
            # Prefer English description
            for desc in form.get("descriptions", []):
                if desc.get("languageCode") == "EN":
                    legal_form_name = desc.get("description", "")
                    break
            if not legal_form_name:
                for desc in form.get("descriptions", []):
                    if desc.get("languageCode") == "FI":
                        legal_form_name = desc.get("description", "")
                        break
            break

    # Address — use first address
    address = ""
    city = ""
    postal = ""
    for addr in data.get("addresses", []):
        street = addr.get("street", "")
        postal = addr.get("postCode", "")
        post_offices = addr.get("postOffices", [])
        city = post_offices[0].get("city", "") if post_offices else ""
        if street:
            address = f"{street}, {postal} {city}".strip(", ")
            break

    # Main business line (NACE / TOL code)
    nace_codes = []
    bline = data.get("mainBusinessLine")
    if bline and isinstance(bline, dict):
        code = bline.get("type")
        desc = None
        for d in bline.get("descriptions", []):
            if d.get("languageCode") == "EN":
                desc = d.get("description")
                break
        if not desc:
            for d in bline.get("descriptions", []):
                if d.get("languageCode") == "FI":
                    desc = d.get("description")
                    break
        if code:
            nace_codes.append({"code": code, "description": desc})

    # Registration date
    date_established = bid.get("registrationDate") or data.get("registrationDate")

    # Status
    status = "active"
    tr_status = (data.get("tradeRegisterStatus") or "").lower()
    if tr_status in ("deregistered", "dissolved", "removed"):
        status = "dissolved"

    return {
        "ico": business_id,
        "dic": None,
        "official_name": official_name,
        "legal_form": legal_form,
        "legal_form_name": legal_form_name,
        "date_established": date_established,
        "date_dissolved": None,
        "registered_address": address or None,
        "address_city": city or None,
        "address_postal_code": postal or None,
        "nace_codes": nace_codes,
        "registration_court": None,
        "registration_number": None,
        "registered_capital": None,  # Not in open PRH API
        "directors": [],  # Not in open PRH API
        "registration_status": status,
        "insolvency_flag": False,
        "ares_updated_at": data.get("lastModified"),
        "_raw": data,
    }
