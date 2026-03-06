"""HTML content extraction (BL-266).

Uses trafilatura for boilerplate removal and main content extraction.
Includes SSRF protection for URL fetching.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Cache TTL in seconds (24 hours)
CACHE_TTL = 86400

# Maximum number of cached URL entries before eviction
MAX_CACHE_SIZE = 500

# Simple in-memory cache (replaced by PG cache in production)
_url_cache: dict[str, tuple[float, dict]] = {}

# Blocked IP ranges for SSRF protection
_BLOCKED_PREFIXES = (
    "10.",
    "172.16.",
    "172.17.",
    "172.18.",
    "172.19.",
    "172.20.",
    "172.21.",
    "172.22.",
    "172.23.",
    "172.24.",
    "172.25.",
    "172.26.",
    "172.27.",
    "172.28.",
    "172.29.",
    "172.30.",
    "172.31.",
    "192.168.",
    "127.",
    "0.",
    "169.254.",
)

_BLOCKED_HOSTS = frozenset(
    {"localhost", "0.0.0.0", "[::]", "[::1]", "metadata.google.internal"}
)


@dataclass
class HTMLExtractionResult:
    """Result of HTML content extraction."""

    url: str
    title: str = ""
    content: str = ""
    description: str = ""
    word_count: int = 0
    error: Optional[str] = None
    cached: bool = False


def fetch_and_extract(url: str, use_cache: bool = True) -> HTMLExtractionResult:
    """Fetch a URL and extract main content.

    Args:
        url: The URL to fetch.
        use_cache: Whether to check/update the cache.

    Returns:
        HTMLExtractionResult with extracted content.
    """
    # Validate URL
    validation_error = validate_url(url)
    if validation_error:
        return HTMLExtractionResult(url=url, error=validation_error)

    # Check cache
    if use_cache:
        cached = _get_cached(url)
        if cached:
            cached["cached"] = True
            return HTMLExtractionResult(**cached)

    try:
        import trafilatura
    except ImportError:
        return HTMLExtractionResult(
            url=url, error="trafilatura not installed — run: pip install trafilatura"
        )

    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return HTMLExtractionResult(url=url, error="Failed to fetch URL")

        content = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            output_format="txt",
        )

        metadata = trafilatura.extract(
            downloaded,
            output_format="xml",
            include_comments=False,
        )

        title = ""
        description = ""
        if metadata:
            # Try to extract title from XML output
            import re

            title_match = re.search(r"title=\"([^\"]+)\"", metadata)
            if title_match:
                title = title_match.group(1)

        result_data = {
            "url": url,
            "title": title,
            "content": content or "",
            "description": description,
            "word_count": len((content or "").split()),
        }

        # Cache result
        if use_cache and content:
            _set_cached(url, result_data)

        return HTMLExtractionResult(**result_data)

    except Exception as exc:
        logger.exception("HTML extraction failed for %s", url)
        return HTMLExtractionResult(
            url=url, error="Extraction failed: {}".format(str(exc))
        )


def validate_url(url: str) -> Optional[str]:
    """Validate a URL for safety (SSRF protection).

    Args:
        url: URL to validate.

    Returns:
        Error message if invalid, None if safe.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return "Invalid URL format"

    if parsed.scheme not in ("http", "https"):
        return "Only http and https URLs are supported"

    hostname = parsed.hostname or ""

    if hostname in _BLOCKED_HOSTS:
        return "Access to {} is not allowed".format(hostname)

    # Check for private IP ranges
    for prefix in _BLOCKED_PREFIXES:
        if hostname.startswith(prefix):
            return "Access to private IP ranges is not allowed"

    if not hostname or "." not in hostname:
        return "Invalid hostname"

    return None


def _cache_key(url: str) -> str:
    """Generate a cache key from URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _get_cached(url: str) -> Optional[dict]:
    """Get cached extraction result."""
    key = _cache_key(url)
    if key in _url_cache:
        ts, data = _url_cache[key]
        if time.time() - ts < CACHE_TTL:
            return data.copy()
        del _url_cache[key]
    return None


def _set_cached(url: str, data: dict) -> None:
    """Cache an extraction result.

    Evicts the oldest half of entries when cache exceeds MAX_CACHE_SIZE.
    """
    if len(_url_cache) >= MAX_CACHE_SIZE:
        # Evict oldest half by timestamp
        sorted_keys = sorted(_url_cache, key=lambda k: _url_cache[k][0])
        for k in sorted_keys[: len(sorted_keys) // 2]:
            del _url_cache[k]

    key = _cache_key(url)
    _url_cache[key] = (time.time(), data.copy())
