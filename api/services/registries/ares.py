"""Czech ARES (Administrative Register of Economic Subjects) adapter.

Provides lookup by ICO, name search with fuzzy matching, and VR (commercial register)
data extraction. All calls are direct HTTP — no n8n dependency.
"""

import logging
import re
import time

import requests
from sqlalchemy import text

from .base import BaseRegistryAdapter

logger = logging.getLogger(__name__)

ARES_BASE_URL = "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest"
ARES_TIMEOUT = 10
ARES_DELAY = 0.5

CZECH_SUFFIXES = [
    r"\bs\.r\.o\.\s*$",
    r"\bspol\.\s*s\s*r\.o\.\s*$",
    r"\ba\.s\.\s*$",
    r"\bk\.s\.\s*$",
    r"\bv\.o\.s\.\s*$",
    r"\bz\.s\.\s*$",
    r"\bz\.u\.\s*$",
    r"\bs\.p\.\s*$",
    r"\bo\.p\.s\.\s*$",
    r"\bSE\s*$",
    r",\s*$",
]


class AresAdapter(BaseRegistryAdapter):
    country_code = "CZ"
    country_names = ["Czech Republic", "Czechia", "CZ",
                     "Česká republika", "Ceska republika"]
    domain_tlds = [".cz"]
    legal_suffixes = CZECH_SUFFIXES
    request_delay = ARES_DELAY
    timeout = ARES_TIMEOUT

    def lookup_by_id(self, ico):
        """Look up by ICO."""
        url = f"{ARES_BASE_URL}/ekonomicke-subjekty/{ico}"
        try:
            resp = requests.get(url, timeout=self.timeout)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return _parse_basic_response(resp.json())
        except requests.RequestException as e:
            logger.warning("ARES lookup by ICO %s failed: %s", ico, e)
            return None

    def search_by_name(self, name, max_results=5):
        """Search ARES by company name."""
        url = f"{ARES_BASE_URL}/ekonomicke-subjekty/vyhledat"
        payload = {"obchodniJmeno": name, "start": 0, "pocet": max_results}
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            candidates = []
            for item in data.get("ekonomickeSubjekty", []):
                parsed = _parse_basic_response(item)
                parsed["similarity"] = self.name_similarity(
                    name, parsed.get("official_name", ""))
                candidates.append(parsed)
            candidates.sort(key=lambda c: c.get("similarity", 0), reverse=True)
            return candidates
        except requests.RequestException as e:
            logger.warning("ARES name search for '%s' failed: %s", name, e)
            return []

    def enrich_company(self, company_id, tenant_id, name, reg_id=None,
                       hq_country=None, domain=None):
        """ARES enrichment with VR (commercial register) follow-up."""
        # Use base class for initial lookup + store
        result = super().enrich_company(
            company_id, tenant_id, name, reg_id, hq_country, domain)

        # If enriched, also fetch VR data
        if result.get("status") == "enriched" and result.get("ico"):
            time.sleep(self.request_delay)
            vr_data = self.lookup_vr(result["ico"])
            if vr_data:
                raw_vr = vr_data.pop("_raw", None)
                self._update_vr_data(company_id, vr_data, raw_vr)

        return result

    def lookup_vr(self, ico):
        """Look up commercial register (VR) data."""
        url = f"{ARES_BASE_URL}/ekonomicke-subjekty-vr/{ico}"
        try:
            resp = requests.get(url, timeout=self.timeout)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return _parse_vr_response(resp.json())
        except requests.RequestException as e:
            logger.warning("ARES VR lookup for ICO %s failed: %s", ico, e)
            return None

    def _update_vr_data(self, company_id, vr_data, raw_vr):
        """Update stored registry data with VR (directors, capital, court)."""
        import json
        from ...models import db

        directors_json = json.dumps(vr_data.get("directors", []))
        raw_vr_json = json.dumps(raw_vr) if raw_vr else "{}"

        db.session.execute(
            text("""
                UPDATE company_registry_data SET
                    directors = :directors,
                    registered_capital = :capital,
                    registration_court = :court,
                    registration_number = :reg_number,
                    raw_vr_response = :raw_vr
                WHERE company_id = :company_id
            """),
            {
                "company_id": str(company_id),
                "directors": directors_json,
                "capital": vr_data.get("registered_capital"),
                "court": vr_data.get("registration_court"),
                "reg_number": vr_data.get("registration_number"),
                "raw_vr": raw_vr_json,
            },
        )
        db.session.commit()


# ---- Parsers (unchanged from original api/services/ares.py) ----

def _parse_basic_response(data):
    """Extract fields from ARES basic response.

    Handles the real ARES API format where:
    - pravniForma is a string code (e.g. "121"), not a dict
    - czNace is a flat list of code strings, not objects
    - seznamRegistraci has stavZdroje* keys (e.g. stavZdrojeIsir: "AKTIVNI")
    """
    sidlo = data.get("sidlo", {}) or {}
    seznamRegistraci = data.get("seznamRegistraci", {}) or {}

    insolvency_flag = False
    if seznamRegistraci.get("stavZdrojeIsir") == "AKTIVNI":
        insolvency_flag = True

    status = "unknown"
    if data.get("datumZaniku"):
        status = "dissolved"
    elif data.get("datumVzniku"):
        status = "active"

    nace_codes = []
    for nace in data.get("czNace", []):
        if isinstance(nace, str):
            nace_codes.append({"code": nace, "description": None})
        elif isinstance(nace, dict):
            nace_codes.append({"code": nace.get("kod"), "description": nace.get("nazev")})

    pravni_forma = data.get("pravniForma")
    if isinstance(pravni_forma, dict):
        legal_form = str(pravni_forma.get("kod", ""))
        legal_form_name = pravni_forma.get("nazev", "")
    else:
        legal_form = str(pravni_forma) if pravni_forma else ""
        legal_form_name = ""

    return {
        "ico": data.get("ico"),
        "dic": data.get("dic"),
        "official_name": data.get("obchodniJmeno"),
        "legal_form": legal_form,
        "legal_form_name": legal_form_name,
        "date_established": data.get("datumVzniku"),
        "date_dissolved": data.get("datumZaniku"),
        "registered_address": sidlo.get("textovaAdresa"),
        "address_city": sidlo.get("nazevObce"),
        "address_postal_code": str(sidlo.get("psc", "")) if sidlo.get("psc") else None,
        "nace_codes": nace_codes,
        "registration_status": status,
        "insolvency_flag": insolvency_flag,
        "ares_updated_at": data.get("datumAktualizace"),
        "_raw": data,
    }


def _parse_vr_response(data):
    """Extract directors and capital from VR response.

    Real API wraps everything in a `zaznamy` array. Each zaznam has
    statutarniOrgany, zakladniKapital, spisovaZnacka etc.
    """
    zaznamy = data.get("zaznamy", [data])

    directors = []
    capital = None
    court = None
    reg_number = None

    for zaznam in zaznamy:
        for organ in zaznam.get("statutarniOrgany", []):
            organ_name = organ.get("nazevOrganu") or organ.get("nazev", "")
            for clen in organ.get("clenoveOrganu", organ.get("clenove", [])):
                if clen.get("datumVymazu"):
                    continue
                osoba = clen.get("fyzickaOsoba") or clen.get("osoba", {}) or {}
                since = None
                clenstvi = clen.get("clenstvi", {})
                if isinstance(clenstvi, dict):
                    inner = clenstvi.get("clenstvi", {})
                    if isinstance(inner, dict):
                        since = inner.get("vznikClenstvi")
                if not since:
                    since = clen.get("datumVzniku")
                director = {
                    "name": _build_person_name(osoba),
                    "role": organ_name,
                    "since": since,
                }
                if director["name"]:
                    directors.append(director)

        kapital_list = zaznam.get("zakladniKapital")
        if isinstance(kapital_list, list):
            for kap in kapital_list:
                if kap.get("datumVymazu"):
                    continue
                vklad = kap.get("vklad", {})
                if isinstance(vklad, dict):
                    raw_val = vklad.get("hodnota", "")
                    amount = str(raw_val).split(";")[0] if raw_val else None
                    if amount:
                        capital = f"{amount} CZK"
                        break
        elif isinstance(kapital_list, dict):
            amount = kapital_list.get("vyse", {}).get("hodnota")
            currency = kapital_list.get("vyse", {}).get("mena", "CZK")
            if amount is not None:
                capital = f"{amount} {currency}"
        elif isinstance(kapital_list, (int, float)):
            capital = f"{kapital_list} CZK"

        spisova = zaznam.get("spisovaZnacka")
        if isinstance(spisova, list) and spisova:
            sp = spisova[0]
            soud_code = sp.get("soud", "")
            oddil = sp.get("oddil", "")
            vlozka = sp.get("vlozka", "")
            court = _resolve_court_name(soud_code) if soud_code else None
            if oddil and vlozka:
                reg_number = f"{oddil} {vlozka}"
        elif isinstance(spisova, dict):
            court = spisova.get("soud")
            reg_number = spisova.get("znacka") or spisova.get("spisZn")

    return {
        "directors": directors,
        "registered_capital": capital,
        "registration_court": court,
        "registration_number": reg_number,
        "_raw": data,
    }


_COURT_NAMES = {
    "MSPH": "Městský soud v Praze",
    "KSOS": "Krajský soud v Ostravě",
    "KSBR": "Krajský soud v Brně",
    "KSPL": "Krajský soud v Plzni",
    "KSUL": "Krajský soud v Ústí nad Labem",
    "KSHK": "Krajský soud v Hradci Králové",
    "KSCB": "Krajský soud v Českých Budějovicích",
}


def _resolve_court_name(code):
    """Resolve ARES court code to human-readable name."""
    return _COURT_NAMES.get(code, code)


def _build_person_name(osoba):
    """Build a person's full name from ARES osoba dict."""
    parts = []
    if osoba.get("jmeno"):
        parts.append(osoba["jmeno"])
    if osoba.get("prijmeni"):
        parts.append(osoba["prijmeni"])
    if not parts and osoba.get("obchodniJmeno"):
        return osoba["obchodniJmeno"]
    return " ".join(parts)


# ---- Backward compatibility wrappers ----
# These match the old api.services.ares function signatures exactly.

def lookup_by_ico(ico):
    """Compat wrapper for AresAdapter.lookup_by_id."""
    return AresAdapter().lookup_by_id(ico)


def lookup_vr(ico):
    """Compat wrapper for AresAdapter.lookup_vr."""
    return AresAdapter().lookup_vr(ico)


def search_by_name(name, max_results=5):
    """Compat wrapper for AresAdapter.search_by_name."""
    return AresAdapter().search_by_name(name, max_results)


def enrich_company(company_id, tenant_id, name, ico=None, hq_country=None, domain=None):
    """Compat wrapper matching the old api.services.ares.enrich_company signature."""
    adapter = AresAdapter()
    if ico is None and not adapter.matches_company(hq_country, domain):
        return {"status": "skipped", "reason": "not_czech"}
    return adapter.enrich_company(company_id, tenant_id, name, reg_id=ico,
                                  hq_country=hq_country, domain=domain)


def _is_czech_company(ico, hq_country, domain):
    """Compat wrapper for country detection."""
    if ico:
        return True
    return AresAdapter().matches_company(hq_country, domain)


def _name_similarity(query, candidate):
    """Compat wrapper for name similarity."""
    return AresAdapter().name_similarity(query, candidate)


def _normalize_name(name):
    """Compat wrapper for name normalization."""
    return AresAdapter()._normalize_name(name)


def _bigrams(s):
    """Compat wrapper for bigram generation."""
    return BaseRegistryAdapter._bigrams(s)
