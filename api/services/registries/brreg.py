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
    r"\bASA?\s*$",  # AS, ASA
    r"\bENK\s*$",  # Enkeltpersonforetak
    r"\bANS\s*$",  # Ansvarlig selskap
    r"\bDA\s*$",  # Selskap med delt ansvar
    r"\bNUF\s*$",  # Norskregistrert utenlandsk foretak
    r"\bBA\s*$",  # Selskap med begrenset ansvar
    r"\bSA\s*$",  # Samvirkeforetak
    r"\bSTI\s*$",  # Stiftelse
    r"\bKF\s*$",  # Kommunalt foretak
    r"\bIKS\s*$",  # Interkommunalt selskap
    r"\bSF\s*$",  # Statsforetak
]


class BrregAdapter(BaseRegistryAdapter):
    country_code = "NO"
    country_names = ["Norway", "NO", "Norge", "Norwegen"]
    domain_tlds = [".no"]
    legal_suffixes = NORWEGIAN_SUFFIXES
    request_delay = 0.3
    timeout = 10

    provides_fields = [
        "registration_id",
        "official_name",
        "legal_form",
        "registration_status",
        "date_established",
        "registered_address",
        "nace_codes",
        "registered_capital",
        "insolvency_flag",
    ]
    requires_inputs = ["name"]

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
                    name, parsed.get("official_name", "")
                )
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
    - kapital: {belop, antallAksjer, type, valuta, innfortDato}
    """
    org_form = data.get("organisasjonsform", {}) or {}

    # Address — prefer forretningsadresse (business), fallback to postadresse
    addr = data.get("forretningsadresse") or data.get("postadresse") or {}
    address_lines = addr.get("adresse", [])
    postal = addr.get("postnummer", "")
    city = addr.get("poststed", "")
    full_address = ", ".join(address_lines) if address_lines else ""
    if postal and city:
        full_address = (
            f"{full_address}, {postal} {city}" if full_address else f"{postal} {city}"
        )

    # NACE codes
    nace_codes = []
    for key in ("naeringskode1", "naeringskode2", "naeringskode3"):
        nace = data.get(key)
        if nace and isinstance(nace, dict):
            nace_codes.append(
                {
                    "code": nace.get("kode"),
                    "description": nace.get("beskrivelse"),
                }
            )

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
