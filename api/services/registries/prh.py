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


def _is_english(lang_code):
    """Check if language code means English (string 'EN' or numeric '3')."""
    return str(lang_code) in ("EN", "3")


def _is_finnish(lang_code):
    """Check if language code means Finnish (string 'FI' or numeric '1')."""
    return str(lang_code) in ("FI", "1")


def _get_description(descriptions, prefer_english=True):
    """Extract description preferring English, falling back to Finnish.

    PRH v3 API uses numeric language codes: 1=FI, 2=SE, 3=EN.
    Some docs show string codes: "FI", "EN". We handle both.
    """
    en_desc = fi_desc = None
    for d in (descriptions or []):
        lc = d.get("languageCode", "")
        if _is_english(lc):
            en_desc = d.get("description", "")
        elif _is_finnish(lc):
            fi_desc = d.get("description", "")
    if prefer_english and en_desc:
        return en_desc
    return fi_desc or en_desc or ""


def _parse_prh_response(data):
    """Parse PRH company response into standardized format.

    Real API v3 fields (numeric codes):
    - businessId: {value, registrationDate, source}
    - names: [{name, type ("1"=trade register), registrationDate, endDate, version, source}]
    - companyForms: [{type ("16"=OY), descriptions: [{languageCode ("1"=FI,"3"=EN), description}]}]
    - addresses: [{type, street, postCode, postOffices: [{city, languageCode}]}]
    - mainBusinessLine: {type, descriptions: [{languageCode, description}]}
    - tradeRegisterStatus: "1" (registered) or "2" (deregistered)
    - registrationDate: string
    - lastModified: string
    """
    # Business ID
    bid = data.get("businessId", {}) or {}
    business_id = bid.get("value")

    # Name — use latest active name (no endDate), prefer trade register type
    official_name = None
    for name_entry in data.get("names", []):
        if not name_entry.get("endDate"):
            official_name = name_entry.get("name")
            # type "1" = trade register name in v3, "TRADE_REGISTER" in docs
            if str(name_entry.get("type", "")) in ("TRADE_REGISTER", "1"):
                break

    # Company form
    legal_form = ""
    legal_form_name = ""
    for form in data.get("companyForms", []):
        if form.get("type"):
            legal_form = form["type"]
            legal_form_name = _get_description(form.get("descriptions", []))
            break

    # Address — use first address, prefer Finnish city name
    address = ""
    city = ""
    postal = ""
    for addr in data.get("addresses", []):
        street = addr.get("street", "")
        postal = addr.get("postCode", "")
        post_offices = addr.get("postOffices", [])
        # Prefer Finnish city name, fall back to first
        city = ""
        for po in post_offices:
            if _is_finnish(po.get("languageCode", "")):
                city = po.get("city", "")
                break
        if not city and post_offices:
            city = post_offices[0].get("city", "")
        if street:
            address = f"{street}, {postal} {city}".strip(", ")
            break

    # Main business line (NACE / TOL code)
    nace_codes = []
    bline = data.get("mainBusinessLine")
    if bline and isinstance(bline, dict):
        code = bline.get("type")
        desc = _get_description(bline.get("descriptions", []))
        if code:
            nace_codes.append({"code": code, "description": desc or None})

    # Registration date
    date_established = bid.get("registrationDate") or data.get("registrationDate")

    # Status — v3 uses "1" (registered), "2" (deregistered); docs use string names
    status = "active"
    tr_status = str(data.get("tradeRegisterStatus") or "").lower()
    if tr_status in ("deregistered", "dissolved", "removed", "2"):
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
