"""Backward-compatibility shim — real implementation in registries.ares."""
# ruff: noqa: F401, F403
from .registries.ares import (  # noqa: F401
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
