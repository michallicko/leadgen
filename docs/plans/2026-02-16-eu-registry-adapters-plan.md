# EU Registry Adapters (Phase 1) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add company registry enrichment for Norway (BRREG), Finland (PRH), and France (recherche-entreprises) — all free, zero-auth government APIs.

**Architecture:** Refactor the monolithic `api/services/ares.py` into a registry adapter pattern under `api/services/registries/`. Each country gets its own adapter class inheriting from `BaseRegistryAdapter`. The existing `company_registry_data` table is reused with a new `registry_country` column. Each country is a separate pipeline stage (`brreg`, `prh`, `recherche`).

**Tech Stack:** Python 3, Flask, SQLAlchemy, requests, pytest

**Working directory:** `/Users/michal/git/leadgen-pipeline/.worktrees/ares-enrichment/`
**Branch:** `feature/ares-enrichment`

---

### Task 1: Migration + Model — Add `registry_country` column

**Files:**
- Create: `migrations/013_registry_country.sql`
- Modify: `api/models.py:175-204`

**Step 1: Create the migration file**

```sql
-- migrations/013_registry_country.sql
-- Add registry_country to distinguish which country's register provided the data
ALTER TABLE company_registry_data ADD COLUMN IF NOT EXISTS registry_country TEXT DEFAULT 'CZ';
CREATE INDEX IF NOT EXISTS idx_registry_country ON company_registry_data(registry_country);
```

**Step 2: Add `registry_country` to the SQLAlchemy model**

In `api/models.py`, inside `CompanyRegistryData` class (after `match_method` at line 199), add:

```python
    registry_country = db.Column(db.Text, default="CZ")
```

**Step 3: Run tests to verify nothing breaks**

Run: `pytest tests/ -x -q`
Expected: All 320 tests pass (no regressions from adding a column)

**Step 4: Commit**

```bash
git add migrations/013_registry_country.sql api/models.py
git commit -m "Add registry_country column to company_registry_data"
git push
```

---

### Task 2: Base adapter + registry package

**Files:**
- Create: `api/services/registries/__init__.py`
- Create: `api/services/registries/base.py`

**Step 1: Create the registries package with adapter registry**

`api/services/registries/__init__.py`:

```python
"""Registry adapter pattern for multi-country company register lookups."""

from .base import BaseRegistryAdapter

# Lazy-loaded adapter instances (one per country code)
_adapters = {}


def get_adapter(country_code):
    """Return the registry adapter for a country code, or None if unsupported.

    Args:
        country_code: ISO 2-letter code (CZ, NO, FI, FR)
    """
    code = (country_code or "").upper().strip()
    if code in _adapters:
        return _adapters[code]

    adapter = _load_adapter(code)
    if adapter:
        _adapters[code] = adapter
    return adapter


def get_all_adapters():
    """Return dict of all registered adapters {country_code: adapter}."""
    # Ensure all adapters are loaded
    for code in ("CZ", "NO", "FI", "FR"):
        get_adapter(code)
    return dict(_adapters)


def get_adapter_for_company(hq_country, domain):
    """Find the appropriate adapter based on company attributes.

    Checks hq_country first, then domain TLD.
    Returns (adapter, country_code) or (None, None).
    """
    for code, adapter in get_all_adapters().items():
        if adapter.matches_company(hq_country, domain):
            return adapter, code
    return None, None


def _load_adapter(code):
    """Import and instantiate adapter for a country code."""
    try:
        if code == "CZ":
            from .ares import AresAdapter
            return AresAdapter()
        elif code == "NO":
            from .brreg import BrregAdapter
            return BrregAdapter()
        elif code == "FI":
            from .prh import PrhAdapter
            return PrhAdapter()
        elif code == "FR":
            from .recherche import RechercheAdapter
            return RechercheAdapter()
    except ImportError:
        pass
    return None
```

**Step 2: Create the base adapter class**

`api/services/registries/base.py`:

```python
"""Base class for country-specific registry adapters."""

import json
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from sqlalchemy import text

from ...models import db

logger = logging.getLogger(__name__)


class BaseRegistryAdapter(ABC):
    """Abstract base for government registry adapters.

    Each subclass implements a specific country's API. The base class provides
    shared name matching and result storage logic.
    """

    country_code = ""           # ISO 2-letter code (CZ, NO, FI, FR)
    country_names = []          # Accepted name variants ["Norway", "NO", "Norge"]
    domain_tlds = []            # Country TLDs [".no"]
    legal_suffixes = []         # Regex patterns for stripping legal form suffixes
    request_delay = 0.3         # Seconds between API calls
    timeout = 10                # HTTP timeout seconds

    @abstractmethod
    def lookup_by_id(self, reg_id):
        """Look up a company by registration number.

        Returns parsed dict with standardized keys or None.
        """

    @abstractmethod
    def search_by_name(self, name, max_results=5):
        """Search by company name.

        Returns list of candidate dicts, each with a 'similarity' score.
        """

    def matches_company(self, hq_country, domain):
        """Check if a company matches this adapter's country."""
        if hq_country:
            c = hq_country.strip().lower()
            if c in [n.lower() for n in self.country_names] or c == self.country_code.lower():
                return True
        if domain:
            d = domain.rstrip("/").lower()
            for tld in self.domain_tlds:
                if d.endswith(tld):
                    return True
        return False

    def enrich_company(self, company_id, tenant_id, name, reg_id=None,
                       hq_country=None, domain=None):
        """Orchestrate registry enrichment for a single company.

        Returns dict with status, method, confidence, etc.
        """
        import time

        result = None
        method = None
        confidence = 0.0
        raw_response = None

        if reg_id:
            result = self.lookup_by_id(reg_id)
            if result:
                method = "ico_direct"
                confidence = 1.0
                raw_response = result.pop("_raw", None)
        else:
            time.sleep(self.request_delay)
            candidates = self.search_by_name(name)

            if candidates:
                best = candidates[0]
                sim = best.get("similarity", 0)

                if sim >= 0.85:
                    result = best
                    method = "name_auto"
                    confidence = sim
                    raw_response = result.pop("_raw", None)
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
            return {"status": "no_match", "reason": "id_not_found"}

        self.store_result(company_id, result, method, confidence, raw_response)

        return {
            "status": "enriched",
            "ico": result.get("ico"),
            "official_name": result.get("official_name"),
            "method": method,
            "confidence": confidence,
        }

    def name_similarity(self, query, candidate):
        """Compute similarity between two names, stripping legal suffixes."""
        if not query or not candidate:
            return 0.0

        q = self._normalize_name(query)
        c = self._normalize_name(candidate)

        if not q or not c:
            return 0.0
        if q == c:
            return 1.0
        if q in c or c in q:
            return min(len(q), len(c)) / max(len(q), len(c))

        q_bigrams = set(self._bigrams(q))
        c_bigrams = set(self._bigrams(c))
        if not q_bigrams or not c_bigrams:
            return 0.0
        intersection = q_bigrams & c_bigrams
        return 2 * len(intersection) / (len(q_bigrams) + len(c_bigrams))

    def _normalize_name(self, name):
        """Normalize a company name for comparison."""
        s = name.lower().strip()
        for pattern in self.legal_suffixes:
            s = re.sub(pattern, "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    @staticmethod
    def _bigrams(s):
        return [s[i:i+2] for i in range(len(s) - 1)]

    def store_result(self, company_id, data, method, confidence, raw_response):
        """Upsert company_registry_data row."""
        now = datetime.now(timezone.utc)

        nace_json = json.dumps(data.get("nace_codes", []))
        directors_json = json.dumps(data.get("directors", []))
        raw_json = json.dumps(raw_response) if raw_response else "{}"

        params = {
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
            "raw_vr_response": "{}",
            "confidence": confidence,
            "method": method,
            "ares_updated_at": data.get("ares_updated_at"),
            "enriched_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "registry_country": self.country_code,
        }

        existing = db.session.execute(
            text("SELECT company_id FROM company_registry_data WHERE company_id = :company_id"),
            {"company_id": str(company_id)},
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
                        enrichment_cost_usd = 0, updated_at = :updated_at,
                        registry_country = :registry_country
                    WHERE company_id = :company_id
                """),
                params,
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
                        ares_updated_at, enriched_at, enrichment_cost_usd, registry_country
                    ) VALUES (
                        :company_id, :ico, :dic, :official_name, :legal_form, :legal_form_name,
                        :date_established, :date_dissolved, :registered_address, :address_city,
                        :address_postal_code, :nace_codes, :registration_court, :registration_number,
                        :registered_capital, :directors, :registration_status, :insolvency_flag,
                        :raw_response, :raw_vr_response, :confidence, :method,
                        :ares_updated_at, :enriched_at, 0, :registry_country
                    )
                """),
                params,
            )

        # Update companies.ico if we have a registration number
        ico = data.get("ico")
        if ico:
            db.session.execute(
                text("UPDATE companies SET ico = :ico WHERE id = :id"),
                {"ico": str(ico), "id": str(company_id)},
            )

        db.session.commit()
```

**Step 3: Run tests to ensure no import errors**

Run: `pytest tests/ -x -q`
Expected: All 320 tests pass

**Step 4: Commit**

```bash
git add api/services/registries/__init__.py api/services/registries/base.py
git commit -m "Add registry adapter base class and package"
git push
```

---

### Task 3: Refactor ARES into adapter pattern

Move the existing ARES code into the adapter pattern while keeping backward compatibility.

**Files:**
- Create: `api/services/registries/ares.py`
- Modify: `api/services/ares.py` (replace with shim)

**Step 1: Create the ARES adapter**

`api/services/registries/ares.py` — this is a refactoring of the existing `api/services/ares.py`. The core logic stays identical, but it inherits from `BaseRegistryAdapter`. Key changes:
- `lookup_by_ico` → `lookup_by_id` (adapter interface)
- `search_by_name` stays the same
- `_store_result` replaced by `BaseRegistryAdapter.store_result`
- `enrich_company` uses the base class version but adds VR lookup
- All Czech-specific parsers (`_parse_basic_response`, `_parse_vr_response`) stay as-is
- `_is_czech_company` replaced by `matches_company` from base

```python
"""Czech ARES (Administrative Register of Economic Subjects) adapter."""

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
        # Use base class for initial lookup
        result = super().enrich_company(
            company_id, tenant_id, name, reg_id, hq_country, domain)

        # If enriched, also fetch VR data
        if result.get("status") == "enriched" and result.get("ico"):
            time.sleep(self.request_delay)
            vr_data = self.lookup_vr(result["ico"])
            if vr_data:
                raw_vr = vr_data.pop("_raw", None)
                # Update the stored record with VR data
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


# ---- Parsers (unchanged from api/services/ares.py) ----

def _parse_basic_response(data):
    """Extract fields from ARES basic response."""
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
    """Extract directors and capital from VR response."""
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
    return _COURT_NAMES.get(code, code)


def _build_person_name(osoba):
    parts = []
    if osoba.get("jmeno"):
        parts.append(osoba["jmeno"])
    if osoba.get("prijmeni"):
        parts.append(osoba["prijmeni"])
    if not parts and osoba.get("obchodniJmeno"):
        return osoba["obchodniJmeno"]
    return " ".join(parts)


# ---- Backward compatibility exports ----
# These functions are importable from api.services.ares via the shim

def lookup_by_ico(ico):
    """Compat wrapper."""
    return AresAdapter().lookup_by_id(ico)

def lookup_vr(ico):
    """Compat wrapper."""
    return AresAdapter().lookup_vr(ico)

def search_by_name(name, max_results=5):
    """Compat wrapper."""
    return AresAdapter().search_by_name(name, max_results)

def enrich_company(company_id, tenant_id, name, ico=None, hq_country=None, domain=None):
    """Compat wrapper matching the old api.services.ares.enrich_company signature."""
    adapter = AresAdapter()
    if ico is None and not adapter.matches_company(hq_country, domain):
        return {"status": "skipped", "reason": "not_czech"}
    return adapter.enrich_company(company_id, tenant_id, name, reg_id=ico,
                                  hq_country=hq_country, domain=domain)

def _is_czech_company(ico, hq_country, domain):
    """Compat wrapper."""
    if ico:
        return True
    return AresAdapter().matches_company(hq_country, domain)

def _name_similarity(query, candidate):
    """Compat wrapper."""
    return AresAdapter().name_similarity(query, candidate)

def _normalize_name(name):
    """Compat wrapper."""
    return AresAdapter()._normalize_name(name)

def _bigrams(s):
    """Compat wrapper."""
    return BaseRegistryAdapter._bigrams(s)
```

**Step 2: Replace `api/services/ares.py` with a shim**

```python
"""Backward-compatibility shim — real implementation in registries.ares."""
# ruff: noqa: F401, F403
from .registries.ares import (
    AresAdapter,
    _bigrams,
    _build_person_name,
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
```

**Step 3: Run ALL tests including ARES tests**

Run: `pytest tests/ -x -q`
Expected: All 320 tests pass (shim ensures backward compat)

If ARES tests fail, check that all the compat wrapper function signatures match exactly what tests import and call.

**Step 4: Commit**

```bash
git add api/services/registries/ares.py api/services/ares.py
git commit -m "Refactor ARES into registry adapter pattern"
git push
```

---

### Task 4: Norway BRREG adapter + tests

**Files:**
- Create: `api/services/registries/brreg.py`
- Create: `tests/unit/test_brreg_service.py`

**Step 1: Create the BRREG adapter**

`api/services/registries/brreg.py`:

```python
"""Norway BRREG (Brønnøysund Register Centre) adapter.

API docs: https://data.brreg.no/enhetsregisteret/api/docs/index.html
No authentication required. Returns JSON.
"""

import logging

import requests

from .base import BaseRegistryAdapter

logger = logging.getLogger(__name__)

BRREG_BASE_URL = "https://data.brreg.no/enhetsregisteret/api"

# Norwegian legal form suffixes to strip for name matching
NORWEGIAN_SUFFIXES = [
    r"\bASA?\s*$",          # AS, ASA
    r"\bENK\s*$",           # Enkeltpersonforetak
    r"\bANS\s*$",           # Ansvarlig selskap
    r"\bDA\s*$",            # Selskap med delt ansvar
    r"\bNUF\s*$",           # Norskregistrert utenlandsk foretak
    r"\bBA\s*$",            # Selskap med begrenset ansvar
    r"\bSA\s*$",            # Samvirkeforetak
    r"\bSTI\s*$",           # Stiftelse
    r"\bKF\s*$",            # Kommunalt foretak
    r"\bIKS\s*$",           # Interkommunalt selskap
    r"\bSF\s*$",            # Statsforetak
]


class BrregAdapter(BaseRegistryAdapter):
    country_code = "NO"
    country_names = ["Norway", "NO", "Norge", "Norwegen"]
    domain_tlds = [".no"]
    legal_suffixes = NORWEGIAN_SUFFIXES
    request_delay = 0.3
    timeout = 10

    def lookup_by_id(self, org_nr):
        """Look up by organisasjonsnummer."""
        url = f"{BRREG_BASE_URL}/enheter/{org_nr}"
        try:
            resp = requests.get(url, timeout=self.timeout)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return _parse_brreg_response(resp.json())
        except requests.RequestException as e:
            logger.warning("BRREG lookup for %s failed: %s", org_nr, e)
            return None

    def search_by_name(self, name, max_results=5):
        """Search BRREG by company name."""
        url = f"{BRREG_BASE_URL}/enheter"
        params = {"navn": name, "size": max_results}
        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            # BRREG wraps results in _embedded.enheter
            enheter = data.get("_embedded", {}).get("enheter", [])
            candidates = []
            for item in enheter:
                parsed = _parse_brreg_response(item)
                parsed["similarity"] = self.name_similarity(
                    name, parsed.get("official_name", ""))
                candidates.append(parsed)

            candidates.sort(key=lambda c: c.get("similarity", 0), reverse=True)
            return candidates
        except requests.RequestException as e:
            logger.warning("BRREG name search for '%s' failed: %s", name, e)
            return []


def _parse_brreg_response(data):
    """Parse BRREG enheter response into standardized format.

    Real API fields:
    - organisasjonsnummer: string (9 digits)
    - navn: string
    - organisasjonsform: {kode, beskrivelse}
    - forretningsadresse / postadresse: {adresse[], postnummer, poststed, land, kommune}
    - naeringskode1/2/3: {kode, beskrivelse}
    - stiftelsesdato: string (founding date)
    - registreringsdatoEnhetsregisteret: string
    - konkurs: boolean (bankruptcy)
    - underAvvikling: boolean (winding up)
    - underTvangsavviklingEllerTvangsopplosning: boolean
    - antallAnsatte: int
    """
    org_form = data.get("organisasjonsform", {}) or {}

    # Address — prefer forretningsadresse (business), fallback to postadresse
    addr = data.get("forretningsadresse") or data.get("postadresse") or {}
    address_lines = addr.get("adresse", [])
    postal = addr.get("postnummer", "")
    city = addr.get("poststed", "")
    full_address = ", ".join(address_lines) if address_lines else ""
    if postal and city:
        full_address = f"{full_address}, {postal} {city}" if full_address else f"{postal} {city}"

    # NACE codes
    nace_codes = []
    for key in ("naeringskode1", "naeringskode2", "naeringskode3"):
        nace = data.get(key)
        if nace and isinstance(nace, dict):
            nace_codes.append({
                "code": nace.get("kode"),
                "description": nace.get("beskrivelse"),
            })

    # Insolvency / bankruptcy
    insolvency = bool(
        data.get("konkurs")
        or data.get("underAvvikling")
        or data.get("underTvangsavviklingEllerTvangsopplosning")
    )

    # Status
    status = "active"
    if insolvency or data.get("underAvvikling"):
        status = "dissolved"

    # Capital
    kapital = data.get("kapital", {}) or {}
    capital = None
    if kapital.get("belop") is not None:
        currency = kapital.get("valuta", "NOK")
        capital = f"{int(kapital['belop'])} {currency}"

    return {
        "ico": data.get("organisasjonsnummer"),
        "dic": None,
        "official_name": data.get("navn"),
        "legal_form": org_form.get("kode", ""),
        "legal_form_name": org_form.get("beskrivelse", ""),
        "date_established": data.get("stiftelsesdato"),
        "date_dissolved": None,
        "registered_address": full_address or None,
        "address_city": city or None,
        "address_postal_code": postal or None,
        "nace_codes": nace_codes,
        "registration_court": None,
        "registration_number": None,
        "registered_capital": capital,
        "directors": [],  # Not available in open BRREG API
        "registration_status": status,
        "insolvency_flag": insolvency,
        "ares_updated_at": data.get("registreringsdatoEnhetsregisteret"),
        "_raw": data,
    }
```

**Step 2: Create BRREG tests**

`tests/unit/test_brreg_service.py`:

```python
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

    def test_empty_response(self):
        result = _parse_brreg_response({})
        assert result["ico"] is None
        assert result["official_name"] is None
        assert result["nace_codes"] == []
        assert result["registration_status"] == "active"

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


class TestBrregAdapter:
    def test_matches_norway(self):
        adapter = BrregAdapter()
        assert adapter.matches_company("Norway", None) is True
        assert adapter.matches_company("NO", None) is True
        assert adapter.matches_company("Norge", None) is True
        assert adapter.matches_company(None, "equinor.no") is True
        assert adapter.matches_company("Germany", "firma.de") is False

    def test_name_similarity_suffix_stripping(self):
        adapter = BrregAdapter()
        assert adapter.name_similarity("Equinor", "EQUINOR ASA") == 1.0
        assert adapter.name_similarity("Equinor", "Equinor") == 1.0

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
```

**Step 3: Run tests**

Run: `pytest tests/unit/test_brreg_service.py -v`
Expected: All BRREG tests pass

Run: `pytest tests/ -x -q`
Expected: All tests pass (320 + new BRREG tests)

**Step 4: Commit**

```bash
git add api/services/registries/brreg.py tests/unit/test_brreg_service.py
git commit -m "Add Norway BRREG registry adapter with tests"
git push
```

---

### Task 5: Finland PRH adapter + tests

**Files:**
- Create: `api/services/registries/prh.py`
- Create: `tests/unit/test_prh_service.py`

**Step 1: Create the PRH adapter**

`api/services/registries/prh.py`:

```python
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

    # Name — use latest active name (no endDate, type TRADE_REGISTER preferred)
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
```

**Step 2: Create PRH tests**

`tests/unit/test_prh_service.py`:

```python
"""Unit tests for the Finland PRH registry adapter."""
from unittest.mock import MagicMock, patch

import pytest

from api.services.registries.prh import PrhAdapter, _parse_prh_response


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

    def test_old_name_excluded(self):
        """Should pick active name (no endDate), not historical."""
        result = _parse_prh_response(PRH_COMPANY)
        assert result["official_name"] == "Wolt Enterprises Oy"

    def test_empty_response(self):
        result = _parse_prh_response({})
        assert result["ico"] is None
        assert result["official_name"] is None
        assert result["nace_codes"] == []

    def test_deregistered_status(self):
        data = dict(PRH_COMPANY)
        data["tradeRegisterStatus"] = "DEREGISTERED"
        result = _parse_prh_response(data)
        assert result["registration_status"] == "dissolved"


class TestPrhAdapter:
    def test_matches_finland(self):
        adapter = PrhAdapter()
        assert adapter.matches_company("Finland", None) is True
        assert adapter.matches_company("FI", None) is True
        assert adapter.matches_company("Suomi", None) is True
        assert adapter.matches_company(None, "wolt.fi") is True
        assert adapter.matches_company("Sweden", "firma.se") is False

    def test_name_similarity_suffix_stripping(self):
        adapter = PrhAdapter()
        assert adapter.name_similarity("Wolt", "Wolt Enterprises Oy") > 0.5
        assert adapter.name_similarity("Wolt Enterprises", "Wolt Enterprises Oy") == 1.0

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
```

**Step 3: Run tests**

Run: `pytest tests/unit/test_prh_service.py -v`
Expected: All PRH tests pass

Run: `pytest tests/ -x -q`
Expected: All tests pass

**Step 4: Commit**

```bash
git add api/services/registries/prh.py tests/unit/test_prh_service.py
git commit -m "Add Finland PRH registry adapter with tests"
git push
```

---

### Task 6: France recherche-entreprises adapter + tests

**Files:**
- Create: `api/services/registries/recherche.py`
- Create: `tests/unit/test_recherche_service.py`

**Step 1: Create the recherche adapter**

`api/services/registries/recherche.py`:

```python
"""France recherche-entreprises adapter.

API: https://recherche-entreprises.api.gouv.fr
No authentication required. Returns JSON.
"""

import logging

import requests

from .base import BaseRegistryAdapter

logger = logging.getLogger(__name__)

RECHERCHE_BASE_URL = "https://recherche-entreprises.api.gouv.fr"

FRENCH_SUFFIXES = [
    r"\bSASU?\s*$",         # SAS, SASU
    r"\bSARL\s*$",          # SARL
    r"\bSA\s*$",            # SA
    r"\bSCI\s*$",           # SCI
    r"\bEURL\s*$",          # EURL
    r"\bSNC\s*$",           # Société en nom collectif
    r"\bSCA\s*$",           # Commandite par actions
    r"\bSCS\s*$",           # Commandite simple
    r"\bSEL(?:ARL|AS|AFA)?\s*$",  # Sociétés d'exercice libéral
]

# French nature_juridique → human-readable name (common ones)
_LEGAL_FORMS = {
    "5710": "SAS",
    "5720": "SASU",
    "5499": "SARL",
    "5498": "EURL",
    "5599": "SA à conseil d'administration",
    "5505": "SA à directoire",
    "6540": "SCI",
    "5460": "EIRL",
    "1000": "Entrepreneur individuel",
}


class RechercheAdapter(BaseRegistryAdapter):
    country_code = "FR"
    country_names = ["France", "FR", "French Republic"]
    domain_tlds = [".fr"]
    legal_suffixes = FRENCH_SUFFIXES
    request_delay = 0.2  # 7 req/s documented limit
    timeout = 10

    def lookup_by_id(self, siren):
        """Look up by SIREN number."""
        url = f"{RECHERCHE_BASE_URL}/search"
        params = {"q": siren}
        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            # Match exact SIREN
            for r in results:
                if r.get("siren") == str(siren):
                    return _parse_recherche_response(r)
            return None
        except requests.RequestException as e:
            logger.warning("recherche-entreprises lookup for %s failed: %s", siren, e)
            return None

    def search_by_name(self, name, max_results=5):
        """Search by company name."""
        url = f"{RECHERCHE_BASE_URL}/search"
        params = {"q": name, "per_page": max_results}
        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            candidates = []
            for item in data.get("results", []):
                parsed = _parse_recherche_response(item)
                parsed["similarity"] = self.name_similarity(
                    name, parsed.get("official_name", ""))
                candidates.append(parsed)

            candidates.sort(key=lambda c: c.get("similarity", 0), reverse=True)
            return candidates
        except requests.RequestException as e:
            logger.warning("recherche-entreprises search for '%s' failed: %s", name, e)
            return []


def _parse_recherche_response(data):
    """Parse recherche-entreprises result into standardized format.

    Real API fields:
    - siren: string (9 digits)
    - nom_complet: string
    - nom_raison_sociale: string
    - nature_juridique: string (code)
    - etat_administratif: "A" (active) or "C" (ceased)
    - siege: {adresse, code_postal, libelle_commune, date_creation, ...}
    - activite_principale: string (NAF code)
    - section_activite_principale: string
    - dirigeants: [{nom, prenoms, qualite, type_dirigeant}, ...]
    - categorie_entreprise: string (PME, ETI, GE)
    - tranche_effectif_salarie: string
    """
    siege = data.get("siege", {}) or {}

    # Address
    address = siege.get("adresse") or siege.get("geo_adresse") or ""
    city = siege.get("libelle_commune", "")
    postal = siege.get("code_postal", "")

    # Legal form
    nature = data.get("nature_juridique", "")
    legal_form = nature
    legal_form_name = _LEGAL_FORMS.get(nature, "")

    # NACE / NAF code
    nace_codes = []
    naf = data.get("activite_principale") or siege.get("activite_principale")
    if naf:
        nace_codes.append({"code": naf, "description": None})

    # Status
    etat = data.get("etat_administratif", "")
    status = "active" if etat == "A" else "dissolved" if etat == "C" else "unknown"

    # Directors
    directors = []
    for d in data.get("dirigeants", []):
        if d.get("type_dirigeant") == "personne physique":
            name_parts = []
            if d.get("prenoms"):
                name_parts.append(d["prenoms"])
            if d.get("nom"):
                name_parts.append(d["nom"])
            directors.append({
                "name": " ".join(name_parts),
                "role": d.get("qualite", ""),
                "since": None,
            })

    # Date
    date_est = siege.get("date_creation") or siege.get("date_debut_activite")

    return {
        "ico": data.get("siren"),
        "dic": None,
        "official_name": data.get("nom_complet") or data.get("nom_raison_sociale"),
        "legal_form": legal_form,
        "legal_form_name": legal_form_name,
        "date_established": date_est,
        "date_dissolved": siege.get("date_fermeture"),
        "registered_address": address or None,
        "address_city": city or None,
        "address_postal_code": postal or None,
        "nace_codes": nace_codes,
        "registration_court": None,
        "registration_number": None,
        "registered_capital": None,  # Not in recherche-entreprises API
        "directors": directors,
        "registration_status": status,
        "insolvency_flag": False,
        "ares_updated_at": data.get("date_mise_a_jour"),
        "_raw": data,
    }
```

**Step 2: Create recherche tests**

`tests/unit/test_recherche_service.py`:

```python
"""Unit tests for the France recherche-entreprises registry adapter."""
from unittest.mock import MagicMock, patch

import pytest

from api.services.registries.recherche import RechercheAdapter, _parse_recherche_response


RECHERCHE_RESULT = {
    "siren": "941953458",
    "nom_complet": "ALAN",
    "nom_raison_sociale": "ALAN",
    "nature_juridique": "5710",
    "etat_administratif": "A",
    "activite_principale": "65.12Z",
    "section_activite_principale": "K",
    "categorie_entreprise": "ETI",
    "tranche_effectif_salarie": "31",
    "date_mise_a_jour": "2025-01-15",
    "siege": {
        "adresse": "44 Rue Alexandre Dumas",
        "code_postal": "75011",
        "libelle_commune": "PARIS 11",
        "date_creation": "2016-02-23",
        "activite_principale": "65.12Z",
        "etat_administratif": "A",
    },
    "dirigeants": [
        {
            "nom": "HASCOET",
            "prenoms": "Jean-Charles",
            "qualite": "Président",
            "type_dirigeant": "personne physique",
        },
        {
            "siren": "123456789",
            "denomination": "Some Holding SAS",
            "qualite": "Directeur général",
            "type_dirigeant": "personne morale",
        },
    ],
}

RECHERCHE_SEARCH_RESPONSE = {
    "results": [RECHERCHE_RESULT],
    "total_results": 1,
    "page": 1,
    "per_page": 5,
    "total_pages": 1,
}


class TestParseRechercheResponse:
    def test_full_response(self):
        result = _parse_recherche_response(RECHERCHE_RESULT)
        assert result["ico"] == "941953458"
        assert result["official_name"] == "ALAN"
        assert result["legal_form"] == "5710"
        assert result["legal_form_name"] == "SAS"
        assert result["date_established"] == "2016-02-23"
        assert result["address_city"] == "PARIS 11"
        assert result["address_postal_code"] == "75011"
        assert "44 Rue Alexandre Dumas" in result["registered_address"]
        assert result["registration_status"] == "active"
        assert len(result["nace_codes"]) == 1
        assert result["nace_codes"][0]["code"] == "65.12Z"
        # Only physical persons as directors
        assert len(result["directors"]) == 1
        assert result["directors"][0]["name"] == "Jean-Charles HASCOET"
        assert result["directors"][0]["role"] == "Président"

    def test_ceased_company(self):
        data = dict(RECHERCHE_RESULT)
        data["etat_administratif"] = "C"
        result = _parse_recherche_response(data)
        assert result["registration_status"] == "dissolved"

    def test_empty_response(self):
        result = _parse_recherche_response({})
        assert result["ico"] is None
        assert result["official_name"] is None
        assert result["nace_codes"] == []
        assert result["directors"] == []

    def test_no_directors(self):
        data = dict(RECHERCHE_RESULT)
        data["dirigeants"] = []
        result = _parse_recherche_response(data)
        assert result["directors"] == []


class TestRechercheAdapter:
    def test_matches_france(self):
        adapter = RechercheAdapter()
        assert adapter.matches_company("France", None) is True
        assert adapter.matches_company("FR", None) is True
        assert adapter.matches_company(None, "alan.fr") is True
        assert adapter.matches_company("Germany", "firma.de") is False

    def test_name_similarity_suffix_stripping(self):
        adapter = RechercheAdapter()
        assert adapter.name_similarity("Alan", "ALAN") == 1.0
        sim = adapter.name_similarity("Société Générale", "SOCIETE GENERALE SA")
        assert sim > 0.8

    @patch("api.services.registries.recherche.requests.get")
    def test_lookup_by_id_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = RECHERCHE_SEARCH_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        adapter = RechercheAdapter()
        result = adapter.lookup_by_id("941953458")
        assert result["ico"] == "941953458"
        assert result["official_name"] == "ALAN"

    @patch("api.services.registries.recherche.requests.get")
    def test_lookup_no_match(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": [], "total_results": 0}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        adapter = RechercheAdapter()
        assert adapter.lookup_by_id("000000000") is None

    @patch("api.services.registries.recherche.requests.get")
    def test_search_by_name(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = RECHERCHE_SEARCH_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        adapter = RechercheAdapter()
        results = adapter.search_by_name("Alan")
        assert len(results) == 1
        assert results[0]["ico"] == "941953458"
        assert "similarity" in results[0]
```

**Step 3: Run tests**

Run: `pytest tests/unit/test_recherche_service.py -v`
Expected: All France tests pass

Run: `pytest tests/ -x -q`
Expected: All tests pass

**Step 4: Commit**

```bash
git add api/services/registries/recherche.py tests/unit/test_recherche_service.py
git commit -m "Add France recherche-entreprises registry adapter with tests"
git push
```

---

### Task 7: Pipeline engine integration

Wire the 3 new adapters into the pipeline engine so they can be run as enrichment stages.

**Files:**
- Modify: `api/services/pipeline_engine.py`

**Step 1: Add new stages to pipeline engine constants**

In `api/services/pipeline_engine.py`, update the following:

1. `AVAILABLE_STAGES` (line 29): add `"brreg"`, `"prh"`, `"recherche"`
2. `DIRECT_STAGES` (line 31): add `"brreg"`, `"prh"`, `"recherche"`
3. `STAGE_PREDECESSORS` (line 36-42): add entries for the 3 new stages
4. `ELIGIBILITY_QUERIES` (after "ares" query around line 80-89): add queries for each country

```python
# Line 29:
AVAILABLE_STAGES = {"l1", "l2", "person", "generate", "ares", "brreg", "prh", "recherche"}

# Line 31:
DIRECT_STAGES = {"ares", "brreg", "prh", "recherche"}

# Lines 36-42, add:
    "brreg": [],        # BRREG is independent
    "prh": [],          # PRH is independent
    "recherche": [],    # recherche is independent
```

Add eligibility queries after the "ares" query:

```python
    "brreg": """
        SELECT c.id FROM companies c
        LEFT JOIN company_registry_data crd ON crd.company_id = c.id
        WHERE c.tenant_id = :tenant_id AND c.batch_id = :batch_id
          AND crd.company_id IS NULL
          AND (c.hq_country IN ('Norway', 'NO', 'Norge')
               OR c.domain LIKE '%%.no')
          {owner_clause}
        ORDER BY c.name
    """,
    "prh": """
        SELECT c.id FROM companies c
        LEFT JOIN company_registry_data crd ON crd.company_id = c.id
        WHERE c.tenant_id = :tenant_id AND c.batch_id = :batch_id
          AND crd.company_id IS NULL
          AND (c.hq_country IN ('Finland', 'FI', 'Suomi')
               OR c.domain LIKE '%%.fi')
          {owner_clause}
        ORDER BY c.name
    """,
    "recherche": """
        SELECT c.id FROM companies c
        LEFT JOIN company_registry_data crd ON crd.company_id = c.id
        WHERE c.tenant_id = :tenant_id AND c.batch_id = :batch_id
          AND crd.company_id IS NULL
          AND (c.hq_country IN ('France', 'FR')
               OR c.domain LIKE '%%.fr')
          {owner_clause}
        ORDER BY c.name
    """,
```

**Step 2: Add processor functions and update dispatcher**

Add processor functions near `_process_ares` (around line 216):

```python
def _process_registry(company_id, tenant_id, adapter_code):
    """Process a company through a registry adapter (generic)."""
    from .registries import get_adapter

    adapter = get_adapter(adapter_code)
    if not adapter:
        return {"status": "error", "error": f"No adapter for {adapter_code}", "enrichment_cost_usd": 0}

    row = db.session.execute(
        text("""
            SELECT name, ico, hq_country, domain
            FROM companies WHERE id = :id AND tenant_id = :t
        """),
        {"id": company_id, "t": str(tenant_id)},
    ).fetchone()

    if not row:
        return {"status": "error", "error": "Company not found", "enrichment_cost_usd": 0}

    result = adapter.enrich_company(
        company_id=company_id,
        tenant_id=str(tenant_id),
        name=row[0],
        reg_id=row[1],
        hq_country=row[2],
        domain=row[3],
    )
    result["enrichment_cost_usd"] = 0
    return result
```

Update `_process_entity` (around line 245):

```python
def _process_entity(stage, entity_id, tenant_id=None):
    """Dispatch entity processing to the right backend (n8n or direct Python)."""
    if stage in DIRECT_STAGES:
        if stage == "ares":
            return _process_ares(entity_id, tenant_id)
        # All other direct stages use the generic registry processor
        _STAGE_TO_ADAPTER = {"brreg": "NO", "prh": "FI", "recherche": "FR"}
        adapter_code = _STAGE_TO_ADAPTER.get(stage)
        if adapter_code:
            return _process_registry(entity_id, tenant_id, adapter_code)
        raise ValueError(f"No direct processor for stage: {stage}")
    return call_n8n_webhook(stage, {_data_key_for_stage(stage): entity_id})
```

**Step 3: Run tests**

Run: `pytest tests/ -x -q`
Expected: All tests pass

**Step 4: Commit**

```bash
git add api/services/pipeline_engine.py
git commit -m "Add BRREG/PRH/recherche stages to pipeline engine"
git push
```

---

### Task 8: Route integration

Add the 3 new stages to enrichment and pipeline route configurations.

**Files:**
- Modify: `api/routes/enrich_routes.py:18,21-27`
- Modify: `api/routes/pipeline_routes.py:22`
- Modify: `api/routes/company_routes.py:415-477`

**Step 1: Update enrich_routes.py**

Add new stages to `ENRICHMENT_STAGES` (line 18) and `STATIC_COST_DEFAULTS` (lines 21-27):

```python
ENRICHMENT_STAGES = ["l1", "l2", "person", "generate", "ares", "brreg", "prh", "recherche"]

STATIC_COST_DEFAULTS = {
    "l1": 0.02,
    "l2": 0.08,
    "person": 0.04,
    "generate": 0.03,
    "ares": 0.00,
    "brreg": 0.00,
    "prh": 0.00,
    "recherche": 0.00,
}
```

**Step 2: Update pipeline_routes.py**

Add new stages to `ALL_STAGES` (line 22):

```python
ALL_STAGES = ["l1", "triage", "l2", "person", "generate", "review", "ares", "brreg", "prh", "recherche"]
```

**Step 3: Generalize on-demand endpoints**

In `api/routes/company_routes.py`, replace the ARES-specific `enrich-registry` endpoint with a generic one that accepts a `country` parameter. Keep the existing endpoint for backward compat and add a new generic one:

After the existing `confirm-registry` route (line 477), add:

```python
@companies_bp.route("/api/companies/<company_id>/enrich-registry/<country>", methods=["POST"])
@require_auth
def enrich_registry_country(company_id, country):
    """On-demand registry lookup for a specific country adapter."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    row = db.session.execute(
        db.text("SELECT name, ico, hq_country, domain FROM companies WHERE id = :id AND tenant_id = :t"),
        {"id": company_id, "t": tenant_id},
    ).fetchone()
    if not row:
        return jsonify({"error": "Company not found"}), 404

    from ..services.registries import get_adapter
    adapter = get_adapter(country.upper())
    if not adapter:
        return jsonify({"error": f"No registry adapter for country: {country}"}), 400

    body = request.get_json(silent=True) or {}
    reg_id = body.get("ico") or body.get("reg_id")

    result = adapter.enrich_company(
        company_id=company_id,
        tenant_id=str(tenant_id),
        name=row[0],
        reg_id=reg_id or row[1],
        hq_country=row[2],
        domain=row[3],
    )
    return jsonify(result)
```

**Step 4: Run tests**

Run: `pytest tests/ -x -q`
Expected: All tests pass

**Step 5: Commit**

```bash
git add api/routes/enrich_routes.py api/routes/pipeline_routes.py api/routes/company_routes.py
git commit -m "Add EU registry stages to enrichment and pipeline routes"
git push
```

---

### Task 9: Dashboard enrichment wizard modules

Add Norway, Finland, and France modules to the enrichment wizard.

**Files:**
- Modify: `dashboard/enrich.html`

**Step 1: Add stage metadata**

In `dashboard/enrich.html`, update `STAGE_META` (around line 472-478) to add the new stages:

```javascript
  var STAGE_META = {
    l1: { name: 'L1 Company Research', color: 'var(--l1-color)' },
    l2: { name: 'L2 Deep Research', color: 'var(--l2-color)' },
    person: { name: 'Person Enrichment', color: 'var(--person-color)' },
    generate: { name: 'Message Generation', color: 'var(--generate-color)' },
    ares: { name: 'Czech Registry (ARES)', color: 'var(--ares-color)' },
    brreg: { name: 'Norway Registry (BRREG)', color: 'var(--ares-color)' },
    prh: { name: 'Finland Registry (PRH)', color: 'var(--ares-color)' },
    recherche: { name: 'France Registry (INSEE)', color: 'var(--ares-color)' }
  };
```

**Step 2: Update enabledStages**

Update `enabledStages` (around line 481):

```javascript
  var enabledStages = { l1: true, l2: true, person: true, generate: true, ares: true, brreg: true, prh: true, recherche: true };
```

**Step 3: Run tests to check nothing breaks**

Run: `pytest tests/ -x -q`
Expected: All tests pass (dashboard is not tested by pytest, but no regression)

**Step 4: Commit**

```bash
git add dashboard/enrich.html
git commit -m "Add Norway/Finland/France registry modules to enrichment wizard"
git push
```

---

### Task 10: Live API verification

Test each adapter against real APIs (like we did with ARES).

**Step 1: Test Norway BRREG**

```bash
curl -s "https://data.brreg.no/enhetsregisteret/api/enheter/923609016" | python3 -m json.tool | head -20
```

Expected: Equinor ASA data

**Step 2: Test Finland PRH**

```bash
curl -s "https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=2611017-6" | python3 -m json.tool | head -20
```

Expected: Wolt Enterprises Oy data

**Step 3: Test France recherche-entreprises**

```bash
curl -s "https://recherche-entreprises.api.gouv.fr/search?q=941953458" | python3 -m json.tool | head -20
```

Expected: ALAN data

**Step 4: If any parser doesn't match the live response, fix it** (like we did with ARES). Update test fixtures to match real response format, fix parsers, re-run tests.

**Step 5: Commit any fixes**

```bash
git add -A
git commit -m "Fix parsers for live API format (NO/FI/FR)"
git push
```

---

### Task 11: Documentation + Backlog

**Files:**
- Modify: `docs/ARCHITECTURE.md`
- Modify: `CHANGELOG.md`
- Modify: `BACKLOG.md`
- Create or update: `docs/adr/004-eu-registry-adapters.md`

**Step 1: Write ADR-004**

```markdown
# ADR-004: EU Registry Adapter Pattern
**Date**: 2026-02-16 | **Status**: Accepted

## Context
ARES enrichment (ADR-003) proved the value of free government registry data. Norway, Finland, and France have similar zero-auth APIs. Adding each as a monolithic service would duplicate code.

## Decision
Refactor into a registry adapter pattern: `BaseRegistryAdapter` ABC with per-country subclasses. Shared name matching, result storage, and pipeline dispatch. One pipeline stage per country for independent control.

## Consequences
- New countries can be added by creating a single adapter file
- Existing ARES code maintains backward compatibility via import shim
- Each country is an independent pipeline stage (user chooses which to run)
- All data goes into the same `company_registry_data` table with `registry_country` discriminator
```

**Step 2: Update ARCHITECTURE.md**

Add EU registry adapters to the external dependencies section.

**Step 3: Update CHANGELOG.md**

Add entries for the 3 new adapters under `[Unreleased] > Added`.

**Step 4: Update BACKLOG.md**

Update BL-017 to note NO/FI/FR as done alongside ARES.

**Step 5: Commit**

```bash
git add docs/adr/004-eu-registry-adapters.md docs/ARCHITECTURE.md CHANGELOG.md BACKLOG.md
git commit -m "Add EU registry adapter documentation, ADR-004, changelog"
git push
```

---

### Task 12: Full test suite verification

**Step 1: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests pass (320 original + ~30 new = ~350 total)

**Step 2: Self-review changed files**

Check for:
- Security: No secrets, proper input validation
- Consistency: Same patterns as ARES
- Edge cases: Empty responses, network errors, missing fields

**Step 3: Done — ready for finishing-a-development-branch skill**
