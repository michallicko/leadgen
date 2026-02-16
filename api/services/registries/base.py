"""Base class for country-specific registry adapters."""

import json
import logging
import re
import time
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
