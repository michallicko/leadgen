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

    provides_fields = [
        "registration_id", "official_name", "legal_form",
        "registration_status", "date_established", "registered_address",
        "nace_codes", "directors",
    ]
    requires_inputs = ["name"]

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
