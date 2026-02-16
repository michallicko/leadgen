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
    for code in ("CZ", "NO", "FI", "FR"):
        get_adapter(code)
    return dict(_adapters)


def get_adapter_for_company(hq_country, domain):
    """Find the appropriate adapter based on company attributes.

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
