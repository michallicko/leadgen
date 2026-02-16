"""Registry Orchestrator — unified entry point for all registry enrichment.

Automatically detects applicable registers based on company country/domain,
runs them in dependency order, aggregates results into a unified profile,
and computes a credibility score.
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import text

from ...models import db
from . import get_adapter, get_all_adapters
from .credibility import compute_credibility

logger = logging.getLogger(__name__)

# Country detection from domain TLD
_TLD_TO_COUNTRY = {
    ".cz": "CZ",
    ".no": "NO",
    ".fi": "FI",
    ".fr": "FR",
}


class RegistryOrchestrator:
    """Smart orchestrator for multi-registry enrichment."""

    def find_applicable_adapters(self, hq_country, domain, ico):
        """Return ordered list of (adapter_key, adapter, reason) for a company.

        Rules:
        - hq_country takes priority over domain TLD for country detection
        - Only one country's registers per company
        - ISIR added if CZ company has or may obtain ICO via ARES
        """
        country = self._detect_country(hq_country, domain)
        if not country:
            return []

        adapters = []

        # Main country adapter
        main_adapter = get_adapter(country)
        if main_adapter:
            reason = f"hq_country={hq_country}" if hq_country else f"domain={domain}"
            adapters.append((country, main_adapter, reason))

        # Supplementary adapters (e.g. CZ_ISIR for Czech companies)
        if country == "CZ":
            isir = get_adapter("CZ_ISIR")
            if isir and (ico or main_adapter):
                reason = "supplementary: insolvency check for CZ company"
                adapters.append(("CZ_ISIR", isir, reason))

        return adapters

    def enrich_company(self, company_id, tenant_id, name,
                       reg_id=None, hq_country=None, domain=None):
        """Run all applicable registers, aggregate, score, store.

        Args:
            company_id: UUID of the company
            tenant_id: UUID of the tenant
            name: Company name for registry search
            reg_id: Registration ID (ICO, org nr, etc.) if known
            hq_country: HQ country name or code
            domain: Company domain (used for TLD-based detection)

        Returns dict with status, adapters_run, credibility_score, etc.
        """
        applicable = self.find_applicable_adapters(hq_country, domain, reg_id)
        if not applicable:
            return {
                "status": "skipped",
                "reason": "no_applicable_registry",
                "enrichment_cost_usd": 0,
            }

        results = {}
        errors = {}
        current_ico = reg_id

        for adapter_key, adapter, reason in applicable:
            logger.info("Running %s for company %s (%s)",
                        adapter_key, company_id, reason)

            try:
                if adapter.is_supplementary:
                    # Supplementary adapters use ICO as reg_id
                    if not current_ico:
                        logger.info("Skipping %s — no ICO available",
                                    adapter_key)
                        continue
                    result = adapter.enrich_company(
                        company_id, tenant_id, name,
                        reg_id=current_ico, store=False,
                    )
                else:
                    result = adapter.enrich_company(
                        company_id, tenant_id, name,
                        reg_id=current_ico, hq_country=hq_country,
                        domain=domain, store=False,
                    )

                results[adapter_key] = result

                # After main adapter: extract ICO for supplementary adapters
                if (not adapter.is_supplementary
                        and result.get("status") == "enriched"
                        and result.get("ico")):
                    current_ico = result["ico"]

            except Exception as e:
                logger.exception("Adapter %s failed for company %s: %s",
                                 adapter_key, company_id, e)
                errors[adapter_key] = str(e)

        # Check if any adapter returned ambiguous — propagate
        for key, result in results.items():
            if result.get("status") == "ambiguous":
                return result

        # Aggregate results
        profile = self._aggregate_results(results, hq_country, domain)

        if not profile.get("registration_id") and not profile.get("insolvency_flag"):
            # Nothing useful found
            all_no_match = all(
                r.get("status") in ("no_match", "skipped")
                for r in results.values()
            )
            if all_no_match:
                return {
                    "status": "no_match",
                    "reason": "all_registries_returned_no_match",
                    "adapters_run": list(results.keys()),
                    "enrichment_cost_usd": 0,
                }

        # Compute credibility score
        cred = compute_credibility(profile)
        profile["credibility_score"] = cred["score"]
        profile["credibility_factors"] = cred["factors"]

        # Store unified profile
        self._store_legal_profile(company_id, profile)

        # Promote core fields to companies table
        self._promote_to_company(company_id, profile)

        adapters_run = [k for k in results if results[k].get("status") == "enriched"]

        return {
            "status": "enriched",
            "adapters_run": adapters_run,
            "registration_id": profile.get("registration_id"),
            "official_name": profile.get("official_name"),
            "credibility_score": cred["score"],
            "credibility_factors": cred["factors"],
            "has_insolvency": profile.get("insolvency_flag", False),
            "enrichment_cost_usd": 0,
        }

    def _detect_country(self, hq_country, domain):
        """Detect registry country from company attributes."""
        if hq_country:
            c = hq_country.strip()
            # Check all adapters for country match
            for key, adapter in get_all_adapters().items():
                if adapter.is_supplementary:
                    continue
                if adapter.matches_company(c, None):
                    return adapter.country_code
        if domain:
            d = domain.rstrip("/").lower()
            for tld, country in _TLD_TO_COUNTRY.items():
                if d.endswith(tld):
                    return country
        return None

    def _aggregate_results(self, results, hq_country, domain):
        """Merge adapter results into a unified profile dict."""
        profile = {
            "registration_country": self._detect_country(hq_country, domain),
            "source_data": {},
        }

        # Process main adapter result first
        main_result = None
        for key, result in results.items():
            adapter = get_adapter(key)
            if adapter and not adapter.is_supplementary:
                main_result = result
                break

        if main_result and main_result.get("status") == "enriched":
            data = main_result.get("data", {})
            profile.update({
                "registration_id": data.get("ico"),
                "tax_id": data.get("dic"),
                "official_name": data.get("official_name"),
                "legal_form": data.get("legal_form"),
                "legal_form_name": data.get("legal_form_name"),
                "registration_status": data.get("registration_status"),
                "date_established": data.get("date_established"),
                "date_dissolved": data.get("date_dissolved"),
                "registered_address": data.get("registered_address"),
                "address_city": data.get("address_city"),
                "address_postal_code": data.get("address_postal_code"),
                "nace_codes": data.get("nace_codes", []),
                "directors": data.get("directors", []),
                "registered_capital": data.get("registered_capital"),
                "registration_court": data.get("registration_court"),
                "registration_number": data.get("registration_number"),
                "insolvency_flag": data.get("insolvency_flag", False),
                "match_confidence": main_result.get("confidence"),
                "match_method": main_result.get("method"),
            })

            # Store source data
            for key, result in results.items():
                if result.get("status") == "enriched":
                    raw = result.get("raw_response") or result.get("data", {}).get("raw")
                    profile["source_data"][key] = raw or {}

        # Merge supplementary adapter data (ISIR)
        for key, result in results.items():
            adapter = get_adapter(key)
            if not adapter or not adapter.is_supplementary:
                continue
            if result.get("status") != "enriched":
                continue

            data = result.get("data", {})
            if key == "CZ_ISIR":
                proceedings = data.get("proceedings", [])
                active_count = data.get("active_proceedings", 0)
                profile["insolvency_flag"] = data.get("has_insolvency", False)
                profile["insolvency_details"] = proceedings
                profile["active_insolvency_count"] = active_count
                profile["source_data"]["CZ_ISIR"] = data.get("raw", {})

        return profile

    def _store_legal_profile(self, company_id, profile):
        """Upsert company_legal_profile row."""
        now = datetime.now(timezone.utc)

        params = {
            "company_id": str(company_id),
            "registration_id": profile.get("registration_id"),
            "registration_country": profile.get("registration_country"),
            "tax_id": profile.get("tax_id"),
            "official_name": profile.get("official_name"),
            "legal_form": profile.get("legal_form"),
            "legal_form_name": profile.get("legal_form_name"),
            "registration_status": profile.get("registration_status"),
            "date_established": profile.get("date_established"),
            "date_dissolved": profile.get("date_dissolved"),
            "registered_address": profile.get("registered_address"),
            "address_city": profile.get("address_city"),
            "address_postal_code": profile.get("address_postal_code"),
            "nace_codes": json.dumps(profile.get("nace_codes", []), default=str),
            "directors": json.dumps(profile.get("directors", []), default=str),
            "registered_capital": profile.get("registered_capital"),
            "registration_court": profile.get("registration_court"),
            "registration_number": profile.get("registration_number"),
            "insolvency_flag": profile.get("insolvency_flag", False),
            "insolvency_details": json.dumps(
                profile.get("insolvency_details", []), default=str),
            "active_insolvency_count": profile.get("active_insolvency_count", 0),
            "match_confidence": profile.get("match_confidence"),
            "match_method": profile.get("match_method"),
            "credibility_score": profile.get("credibility_score"),
            "credibility_factors": json.dumps(
                profile.get("credibility_factors", {})),
            "source_data": json.dumps(
                profile.get("source_data", {}), default=str),
            "enriched_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        existing = db.session.execute(
            text("SELECT company_id FROM company_legal_profile "
                 "WHERE company_id = :company_id"),
            {"company_id": str(company_id)},
        ).fetchone()

        if existing:
            db.session.execute(
                text("""
                    UPDATE company_legal_profile SET
                        registration_id = :registration_id,
                        registration_country = :registration_country,
                        tax_id = :tax_id,
                        official_name = :official_name,
                        legal_form = :legal_form,
                        legal_form_name = :legal_form_name,
                        registration_status = :registration_status,
                        date_established = :date_established,
                        date_dissolved = :date_dissolved,
                        registered_address = :registered_address,
                        address_city = :address_city,
                        address_postal_code = :address_postal_code,
                        nace_codes = :nace_codes,
                        directors = :directors,
                        registered_capital = :registered_capital,
                        registration_court = :registration_court,
                        registration_number = :registration_number,
                        insolvency_flag = :insolvency_flag,
                        insolvency_details = :insolvency_details,
                        active_insolvency_count = :active_insolvency_count,
                        match_confidence = :match_confidence,
                        match_method = :match_method,
                        credibility_score = :credibility_score,
                        credibility_factors = :credibility_factors,
                        source_data = :source_data,
                        enriched_at = :enriched_at,
                        updated_at = :updated_at,
                        enrichment_cost_usd = 0
                    WHERE company_id = :company_id
                """),
                params,
            )
        else:
            db.session.execute(
                text("""
                    INSERT INTO company_legal_profile (
                        company_id, registration_id, registration_country,
                        tax_id, official_name, legal_form, legal_form_name,
                        registration_status, date_established, date_dissolved,
                        registered_address, address_city, address_postal_code,
                        nace_codes, directors, registered_capital,
                        registration_court, registration_number,
                        insolvency_flag, insolvency_details,
                        active_insolvency_count,
                        match_confidence, match_method,
                        credibility_score, credibility_factors,
                        source_data, enriched_at, enrichment_cost_usd
                    ) VALUES (
                        :company_id, :registration_id, :registration_country,
                        :tax_id, :official_name, :legal_form, :legal_form_name,
                        :registration_status, :date_established, :date_dissolved,
                        :registered_address, :address_city, :address_postal_code,
                        :nace_codes, :directors, :registered_capital,
                        :registration_court, :registration_number,
                        :insolvency_flag, :insolvency_details,
                        :active_insolvency_count,
                        :match_confidence, :match_method,
                        :credibility_score, :credibility_factors,
                        :source_data, :enriched_at, 0
                    )
                """),
                params,
            )

        db.session.commit()

    def _promote_to_company(self, company_id, profile):
        """Promote core legal profile fields to the companies table."""
        db.session.execute(
            text("""
                UPDATE companies SET
                    ico = COALESCE(:reg_id, ico),
                    official_name = :official_name,
                    tax_id = :tax_id,
                    legal_form = :legal_form,
                    registration_status = :registration_status,
                    date_established = :date_established,
                    has_insolvency = :has_insolvency,
                    credibility_score = :credibility_score,
                    credibility_factors = :credibility_factors
                WHERE id = :company_id
            """),
            {
                "company_id": str(company_id),
                "reg_id": profile.get("registration_id"),
                "official_name": profile.get("official_name"),
                "tax_id": profile.get("tax_id"),
                "legal_form": profile.get("legal_form"),
                "registration_status": profile.get("registration_status"),
                "date_established": profile.get("date_established"),
                "has_insolvency": profile.get("insolvency_flag", False),
                "credibility_score": profile.get("credibility_score"),
                "credibility_factors": json.dumps(
                    profile.get("credibility_factors", {})),
            },
        )
        db.session.commit()
