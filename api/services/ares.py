"""ARES (Czech Administrative Register of Economic Subjects) enrichment service.

Provides lookup by ICO, name search with fuzzy matching, and VR (commercial register)
data extraction. All calls are direct HTTP — no n8n dependency.
"""

import logging
import re
import time
from datetime import datetime, timezone

import requests
from sqlalchemy import text

from ..models import db

logger = logging.getLogger(__name__)

ARES_BASE_URL = "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest"
ARES_TIMEOUT = 10  # seconds
ARES_DELAY = 0.5  # seconds between requests to avoid rate limiting

# Czech legal suffixes to strip for name matching
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


def lookup_by_ico(ico):
    """Look up a company by ICO (registration number).

    Returns parsed dict or None if not found.
    """
    url = f"{ARES_BASE_URL}/ekonomicke-subjekty/{ico}"
    try:
        resp = requests.get(url, timeout=ARES_TIMEOUT)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        return _parse_basic_response(data)
    except requests.RequestException as e:
        logger.warning("ARES lookup by ICO %s failed: %s", ico, e)
        return None


def lookup_vr(ico):
    """Look up commercial register (VR) data by ICO.

    Returns dict with directors and capital, or None.
    """
    url = f"{ARES_BASE_URL}/ekonomicke-subjekty-vr/{ico}"
    try:
        resp = requests.get(url, timeout=ARES_TIMEOUT)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        return _parse_vr_response(data)
    except requests.RequestException as e:
        logger.warning("ARES VR lookup for ICO %s failed: %s", ico, e)
        return None


def search_by_name(name, max_results=5):
    """Search ARES by company name.

    Returns list of candidate dicts with similarity scores.
    """
    url = f"{ARES_BASE_URL}/ekonomicke-subjekty/vyhledat"
    payload = {
        "obchodniJmeno": name,
        "start": 0,
        "pocet": max_results,
    }
    try:
        resp = requests.post(url, json=payload, timeout=ARES_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        candidates = []
        for item in data.get("ekonomickeSubjekty", []):
            parsed = _parse_basic_response(item)
            parsed["similarity"] = _name_similarity(name, parsed.get("official_name", ""))
            candidates.append(parsed)

        # Sort by similarity descending
        candidates.sort(key=lambda c: c.get("similarity", 0), reverse=True)
        return candidates
    except requests.RequestException as e:
        logger.warning("ARES name search for '%s' failed: %s", name, e)
        return []


def enrich_company(company_id, tenant_id, name, ico=None, hq_country=None, domain=None):
    """Orchestrate ARES enrichment for a single company.

    Returns dict with enrichment result or None if not applicable.
    """
    # Check if this is a Czech company
    if not _is_czech_company(ico, hq_country, domain):
        return {"status": "skipped", "reason": "not_czech"}

    result = None
    method = None
    confidence = 0.0
    raw_response = None
    raw_vr = None

    if ico:
        # Direct lookup by ICO
        result = lookup_by_ico(ico)
        if result:
            method = "ico_direct"
            confidence = 1.0
            raw_response = result.pop("_raw", None)
    else:
        # Search by name
        time.sleep(ARES_DELAY)
        candidates = search_by_name(name)

        if candidates:
            best = candidates[0]
            sim = best.get("similarity", 0)

            if sim >= 0.85:
                result = best
                method = "name_auto"
                confidence = sim
                raw_response = result.pop("_raw", None)
                ico = result.get("ico")
            elif sim >= 0.60:
                return {
                    "status": "ambiguous",
                    "candidates": [{
                        "ico": c.get("ico"),
                        "official_name": c.get("official_name"),
                        "registered_address": c.get("registered_address"),
                        "similarity": round(c.get("similarity", 0), 2),
                    } for c in candidates if c.get("similarity", 0) >= 0.60],
                }
            else:
                return {"status": "no_match", "reason": "similarity_too_low"}
        else:
            return {"status": "no_match", "reason": "no_results"}

    if not result:
        return {"status": "no_match", "reason": "ico_not_found"}

    # Fetch VR data if we have an ICO
    if ico:
        time.sleep(ARES_DELAY)
        vr_data = lookup_vr(ico)
        if vr_data:
            raw_vr = vr_data.pop("_raw", None)
            result.update(vr_data)

    # Store results
    _store_result(company_id, result, method, confidence, raw_response, raw_vr)

    return {
        "status": "enriched",
        "ico": result.get("ico"),
        "official_name": result.get("official_name"),
        "method": method,
        "confidence": confidence,
    }


def _is_czech_company(ico, hq_country, domain):
    """Determine if a company is Czech based on available signals."""
    if ico:
        return True
    if hq_country and hq_country.lower() in (
        "czech republic", "czechia", "cz", "česká republika", "ceska republika",
    ):
        return True
    if domain and domain.rstrip("/").endswith(".cz"):
        return True
    return False


def _parse_basic_response(data):
    """Extract fields from ARES basic response."""
    sidlo = data.get("sidlo", {}) or {}
    seznamRegistraci = data.get("seznamRegistraci", {}) or {}

    # Check insolvency from registry list
    insolvency_flag = False
    for reg in seznamRegistraci.get("registrace", []):
        if reg.get("registr") == "ISIR":
            insolvency_flag = True
            break

    # Determine registration status
    status = "unknown"
    if data.get("datumZaniku"):
        status = "dissolved"
    elif data.get("datumVzniku"):
        status = "active"

    # Parse NACE codes
    nace_codes = []
    for nace in data.get("czNace", []):
        nace_codes.append({
            "code": nace.get("kod"),
            "description": nace.get("nazev"),
        })

    return {
        "ico": data.get("ico"),
        "dic": data.get("dic"),
        "official_name": data.get("obchodniJmeno"),
        "legal_form": str(data.get("pravniForma", {}).get("kod", "")) if isinstance(data.get("pravniForma"), dict) else str(data.get("pravniForma", "")),
        "legal_form_name": data.get("pravniForma", {}).get("nazev", "") if isinstance(data.get("pravniForma"), dict) else "",
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
    """Extract directors and capital from VR response."""
    directors = []
    for organ in data.get("statutarniOrgany", []):
        for clen in organ.get("clenove", []):
            osoba = clen.get("osoba", {}) or {}
            director = {
                "name": _build_person_name(osoba),
                "role": organ.get("nazev", ""),
                "since": clen.get("datumVzniku"),
            }
            if director["name"]:
                directors.append(director)

    # Extract capital
    capital = None
    kapital = data.get("zakladniKapital")
    if kapital:
        if isinstance(kapital, dict):
            amount = kapital.get("vyse", {}).get("hodnota")
            currency = kapital.get("vyse", {}).get("mena", "CZK")
            if amount is not None:
                capital = f"{amount} {currency}"
        elif isinstance(kapital, (int, float)):
            capital = f"{kapital} CZK"

    # Extract court and file reference
    spisova = data.get("spisovaZnacka", {}) or {}

    return {
        "directors": directors,
        "registered_capital": capital,
        "registration_court": spisova.get("soud"),
        "registration_number": spisova.get("znacka") or spisova.get("spisZn"),
        "_raw": data,
    }


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


def _name_similarity(query, candidate):
    """Compute similarity between two company names, stripping Czech legal suffixes."""
    if not query or not candidate:
        return 0.0

    q = _normalize_name(query)
    c = _normalize_name(candidate)

    if not q or not c:
        return 0.0

    if q == c:
        return 1.0

    # One contains the other
    if q in c or c in q:
        return max(len(q), len(c)) and min(len(q), len(c)) / max(len(q), len(c))

    # Character-level bigram similarity (Dice coefficient)
    q_bigrams = set(_bigrams(q))
    c_bigrams = set(_bigrams(c))

    if not q_bigrams or not c_bigrams:
        return 0.0

    intersection = q_bigrams & c_bigrams
    return 2 * len(intersection) / (len(q_bigrams) + len(c_bigrams))


def _normalize_name(name):
    """Normalize a company name for comparison."""
    s = name.lower().strip()
    for pattern in CZECH_SUFFIXES:
        s = re.sub(pattern, "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _bigrams(s):
    """Generate character bigrams from a string."""
    return [s[i:i+2] for i in range(len(s) - 1)]


def _store_result(company_id, data, method, confidence, raw_response, raw_vr):
    """Upsert company_registry_data row and update companies.ico."""
    import json

    now = datetime.now(timezone.utc)

    # Parse dates if they're strings
    date_est = data.get("date_established")
    date_dis = data.get("date_dissolved")
    ares_updated = data.get("ares_updated_at")

    nace_json = json.dumps(data.get("nace_codes", []))
    directors_json = json.dumps(data.get("directors", []))
    raw_json = json.dumps(raw_response) if raw_response else "{}"
    raw_vr_json = json.dumps(raw_vr) if raw_vr else "{}"

    # Check if record exists
    existing = db.session.execute(
        text("SELECT company_id FROM company_registry_data WHERE company_id = :id"),
        {"id": str(company_id)},
    ).fetchone()

    if existing:
        db.session.execute(
            text("""
                UPDATE company_registry_data SET
                    ico = :ico, dic = :dic, official_name = :official_name,
                    legal_form = :legal_form, legal_form_name = :legal_form_name,
                    date_established = :date_established, date_dissolved = :date_dissolved,
                    registered_address = :registered_address, address_city = :address_city,
                    address_postal_code = :address_postal_code, nace_codes = :nace_codes,
                    registration_court = :registration_court,
                    registration_number = :registration_number,
                    registered_capital = :registered_capital, directors = :directors,
                    registration_status = :registration_status,
                    insolvency_flag = :insolvency_flag,
                    raw_response = :raw_response, raw_vr_response = :raw_vr_response,
                    match_confidence = :confidence, match_method = :method,
                    ares_updated_at = :ares_updated_at, enriched_at = :enriched_at,
                    enrichment_cost_usd = 0, updated_at = :updated_at
                WHERE company_id = :company_id
            """),
            _build_params(company_id, data, method, confidence,
                          nace_json, directors_json, raw_json, raw_vr_json, now),
        )
    else:
        db.session.execute(
            text("""
                INSERT INTO company_registry_data (
                    company_id, ico, dic, official_name, legal_form, legal_form_name,
                    date_established, date_dissolved, registered_address, address_city,
                    address_postal_code, nace_codes, registration_court, registration_number,
                    registered_capital, directors, registration_status, insolvency_flag,
                    raw_response, raw_vr_response, match_confidence, match_method,
                    ares_updated_at, enriched_at, enrichment_cost_usd
                ) VALUES (
                    :company_id, :ico, :dic, :official_name, :legal_form, :legal_form_name,
                    :date_established, :date_dissolved, :registered_address, :address_city,
                    :address_postal_code, :nace_codes, :registration_court, :registration_number,
                    :registered_capital, :directors, :registration_status, :insolvency_flag,
                    :raw_response, :raw_vr_response, :confidence, :method,
                    :ares_updated_at, :enriched_at, 0
                )
            """),
            _build_params(company_id, data, method, confidence,
                          nace_json, directors_json, raw_json, raw_vr_json, now),
        )

    # Update companies.ico if we found one
    ico = data.get("ico")
    if ico:
        db.session.execute(
            text("UPDATE companies SET ico = :ico WHERE id = :id"),
            {"ico": str(ico), "id": str(company_id)},
        )

    db.session.commit()


def _build_params(company_id, data, method, confidence,
                  nace_json, directors_json, raw_json, raw_vr_json, now):
    """Build parameter dict for SQL insert/update."""
    return {
        "company_id": str(company_id),
        "ico": data.get("ico"),
        "dic": data.get("dic"),
        "official_name": data.get("official_name"),
        "legal_form": data.get("legal_form"),
        "legal_form_name": data.get("legal_form_name"),
        "date_established": data.get("date_established"),
        "date_dissolved": data.get("date_dissolved"),
        "registered_address": data.get("registered_address"),
        "address_city": data.get("address_city"),
        "address_postal_code": data.get("address_postal_code"),
        "nace_codes": nace_json,
        "registration_court": data.get("registration_court"),
        "registration_number": data.get("registration_number"),
        "registered_capital": data.get("registered_capital"),
        "directors": directors_json,
        "registration_status": data.get("registration_status"),
        "insolvency_flag": data.get("insolvency_flag", False),
        "raw_response": raw_json,
        "raw_vr_response": raw_vr_json,
        "confidence": confidence,
        "method": method,
        "ares_updated_at": data.get("ares_updated_at"),
        "enriched_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
