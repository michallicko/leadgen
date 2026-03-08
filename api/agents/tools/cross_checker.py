"""Cross-check external findings against primary source (website).

Implements the "website-authoritative with consensus override" policy:
- Website vs 1 external source: trust website
- Website vs 2 external sources: trust website (lower confidence)
- Website vs 3+ external sources: flag as consensus conflict
- External fact with no website data: accept with note
- External fact matches website: confirmed
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)

Verdict = Literal["confirmed", "website_trusted", "consensus_conflict", "no_data"]

# Fields that are worth cross-checking between website and external sources
CROSS_CHECK_FIELDS = [
    "company_name",
    "team_size",
    "location",
    "founding_year",
    "industries",
    "products_services",
]


@dataclass
class CrossCheckResult:
    """Result of cross-checking a single field."""

    field: str
    website_value: str
    external_value: str
    external_sources: list[str] = field(default_factory=list)
    verdict: Verdict = "no_data"
    confidence: float = 0.5


def cross_check_findings(
    website_data: dict,
    external_findings: dict,
    policy: str = "website_authoritative_with_consensus_override",
) -> list[CrossCheckResult]:
    """Compare external findings against website data.

    Args:
        website_data: Dict from CompanyExtract (website primary source).
        external_findings: Dict with keys like 'competitors', 'market_data'.
        policy: Cross-check policy name (only one policy implemented).

    Returns:
        List of CrossCheckResult for each checked field.
    """
    results: list[CrossCheckResult] = []

    # Extract external claims about the company from market research
    external_claims = _extract_external_claims(external_findings)

    for check_field in CROSS_CHECK_FIELDS:
        website_val = website_data.get(check_field)
        external_val = external_claims.get(check_field)

        if external_val is None:
            # Nothing external to check
            continue

        ext_value_str = _normalize_value(external_val.get("value", ""))
        ext_sources = external_val.get("sources", [])
        ext_source_count = max(len(ext_sources), external_val.get("source_count", 0))
        web_value_str = _normalize_value(website_val)

        if not ext_value_str:
            continue

        if not web_value_str:
            # Website has no data for this field; accept external
            results.append(
                CrossCheckResult(
                    field=check_field,
                    website_value="",
                    external_value=ext_value_str,
                    external_sources=ext_sources,
                    verdict="no_data",
                    confidence=0.6,
                )
            )
            continue

        # Compare values
        if _values_match(web_value_str, ext_value_str):
            results.append(
                CrossCheckResult(
                    field=check_field,
                    website_value=web_value_str,
                    external_value=ext_value_str,
                    external_sources=ext_sources,
                    verdict="confirmed",
                    confidence=0.95,
                )
            )
        else:
            # Conflict — apply policy
            verdict, confidence = _apply_policy(ext_source_count)
            results.append(
                CrossCheckResult(
                    field=check_field,
                    website_value=web_value_str,
                    external_value=ext_value_str,
                    external_sources=ext_sources,
                    verdict=verdict,
                    confidence=confidence,
                )
            )

    return results


def needs_halt_gate(results: list[CrossCheckResult]) -> list[CrossCheckResult]:
    """Return cross-check results that require user input (consensus conflicts)."""
    return [r for r in results if r.verdict == "consensus_conflict"]


def _apply_policy(source_count: int) -> tuple[Verdict, float]:
    """Apply website-authoritative-with-consensus-override policy.

    Args:
        source_count: Number of external sources that agree on the conflicting value.

    Returns:
        Tuple of (verdict, confidence).
    """
    if source_count >= 3:
        return "consensus_conflict", 0.4
    elif source_count == 2:
        return "website_trusted", 0.65
    else:
        return "website_trusted", 0.8


def _normalize_value(value) -> str:
    """Normalize a value to a comparable string."""
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value).lower().strip()
    return str(value).lower().strip()


def _values_match(a: str, b: str) -> bool:
    """Check if two normalized values are a reasonable match.

    Uses word-level overlap for fuzzy matching. Avoids false positives
    from pure substring containment (e.g., "50" in "500").
    """
    if not a or not b:
        return False
    if a == b:
        return True
    # Check overlap of words (more reliable than substring)
    words_a = set(a.split())
    words_b = set(b.split())
    if words_a and words_b:
        overlap = len(words_a & words_b) / min(len(words_a), len(words_b))
        if overlap >= 0.6:
            return True
    return False


def _extract_external_claims(external_findings: dict) -> dict:
    """Extract company-level claims from external research findings.

    Scans competitor and market data for claims about the researched company.
    """
    claims: dict = {}

    # From market_data, extract facts that map to company fields
    for item in external_findings.get("market_data", []):
        fact = item.get("fact", "")
        source = item.get("source_url", "")
        # Simple heuristic: look for keywords
        fact_lower = fact.lower()
        if "employee" in fact_lower or "team" in fact_lower or "staff" in fact_lower:
            claims.setdefault(
                "team_size", {"value": fact, "sources": [], "source_count": 1}
            )
            if source:
                claims["team_size"]["sources"].append(source)
        if "founded" in fact_lower or "established" in fact_lower:
            claims.setdefault(
                "founding_year", {"value": fact, "sources": [], "source_count": 1}
            )
            if source:
                claims["founding_year"]["sources"].append(source)
        if (
            "headquarter" in fact_lower
            or "based in" in fact_lower
            or "located" in fact_lower
        ):
            claims.setdefault(
                "location", {"value": fact, "sources": [], "source_count": 1}
            )
            if source:
                claims["location"]["sources"].append(source)

    return claims
