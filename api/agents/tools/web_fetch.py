"""Fetch and parse company websites for structured data extraction.

Fetches a company's main page plus key subpages (about, services, team,
contact, products), strips boilerplate, and extracts structured company
data using an LLM (Haiku for speed and cost).

All HTTP fetches have a 15-second timeout and graceful error handling
so partial results are returned even if some pages fail.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Limits
MAX_TEXT_PER_PAGE = 10_000  # characters
MAX_SUBPAGES = 5
FETCH_TIMEOUT = 15  # seconds
USER_AGENT = "LeadgenBot/1.0 (research; +https://leadgen.visionvolve.com)"


@dataclass
class CompanyExtract:
    """Structured data extracted from a company website."""

    company_name: str = ""
    tagline: str = ""
    products_services: list[str] = field(default_factory=list)
    team_size: str | None = None
    location: str | None = None
    founding_year: str | None = None
    key_clients: list[str] = field(default_factory=list)
    industries: list[str] = field(default_factory=list)
    contact_info: dict = field(default_factory=dict)
    raw_about: str = ""


@dataclass
class WebsiteData:
    """Complete website fetch result with raw content and structured extraction."""

    url: str
    title: str
    description: str
    pages_fetched: list[str] = field(default_factory=list)
    raw_content: dict[str, str] = field(default_factory=dict)
    extracted: CompanyExtract = field(default_factory=CompanyExtract)
    error: str | None = None


def fetch_website(domain: str) -> WebsiteData:
    """Fetch a company website and extract structured data.

    Steps:
    1. Fetch main page (https://{domain})
    2. Parse HTML to clean text (strip nav, footer, scripts)
    3. Find and fetch key subpages: /about, /services, /team, /contact, /products
    4. Extract structured company data using LLM (Haiku)
    5. Return WebsiteData with raw content + structured extract

    Args:
        domain: Company domain (e.g., "acme.com")

    Returns:
        WebsiteData with raw content and structured extraction.
        On total failure, returns WebsiteData with error field set.
    """
    base_url = "https://{}".format(domain)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    # Step 1: Fetch main page
    try:
        main_response = session.get(
            base_url, timeout=FETCH_TIMEOUT, allow_redirects=True
        )
        main_response.raise_for_status()
        main_html = main_response.text
    except Exception as exc:
        logger.warning("Failed to fetch main page for %s: %s", domain, exc)
        return WebsiteData(
            url=base_url,
            title="",
            description="",
            error="Could not fetch website: {}".format(str(exc)[:200]),
        )

    main_text = html_to_text(main_html)
    title = _extract_title(main_html)
    description = _extract_meta_description(main_html)

    # Step 2: Find subpage links
    subpage_urls = _find_subpage_links(main_html, domain)

    # Step 3: Fetch subpages
    raw_content: dict[str, str] = {base_url: main_text}
    for url in subpage_urls[:MAX_SUBPAGES]:
        try:
            resp = session.get(url, timeout=FETCH_TIMEOUT, allow_redirects=True)
            resp.raise_for_status()
            raw_content[url] = html_to_text(resp.text)
        except Exception as exc:
            logger.debug("Failed to fetch subpage %s: %s", url, exc)
            continue

    # Step 4: Extract structured data using LLM
    extracted = _extract_company_data(raw_content, domain)

    return WebsiteData(
        url=base_url,
        title=title,
        description=description,
        pages_fetched=list(raw_content.keys()),
        raw_content=raw_content,
        extracted=extracted,
    )


def html_to_text(html: str) -> str:
    """Convert HTML to clean text, stripping navigation, footer, scripts, styles.

    Uses BeautifulSoup for robust parsing. Falls back to regex if BS4 fails.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")

        # Remove unwanted elements
        for tag_name in [
            "script",
            "style",
            "nav",
            "footer",
            "header",
            "noscript",
            "iframe",
        ]:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        text = soup.get_text(separator=" ", strip=True)
    except Exception:
        # Fallback: regex-based stripping
        text = re.sub(
            r"<(script|style|nav|footer|header|noscript)[^>]*>.*?</\1>",
            "",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        text = re.sub(r"<[^>]+>", " ", text)

    # Clean up whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_TEXT_PER_PAGE]


def _extract_title(html: str) -> str:
    """Extract the <title> tag content."""
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()[:200]
    return ""


def _extract_meta_description(html: str) -> str:
    """Extract the meta description content."""
    match = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']',
        html,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()[:500]
    # Also try the reverse attribute order
    match = re.search(
        r'<meta\s+content=["\']([^"\']*)["\'].*?name=["\']description["\']',
        html,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()[:500]
    return ""


def _find_subpage_links(html: str, domain: str) -> list[str]:
    """Find links to key subpages (about, services, team, contact, products)."""
    key_pages = [
        "about",
        "services",
        "team",
        "contact",
        "products",
        "portfolio",
        "clients",
        "our-work",
        "solutions",
        "pricing",
    ]
    links = re.findall(r'href=["\']([^"\']+)["\']', html)

    result: list[str] = []
    seen: set[str] = set()
    for link in links:
        lower = link.lower()
        if any(kp in lower for kp in key_pages):
            if link.startswith("/"):
                full_url = "https://{}{}".format(domain, link)
            elif link.startswith("http") and domain in link:
                full_url = link
            else:
                continue
            if full_url not in seen:
                seen.add(full_url)
                result.append(full_url)

    return result[:MAX_SUBPAGES]


def _extract_company_data(raw_content: dict[str, str], domain: str) -> CompanyExtract:
    """Use Haiku to extract structured company data from raw website text.

    Falls back to empty CompanyExtract if LLM call fails or API key is missing.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning(
            "ANTHROPIC_API_KEY not set, skipping LLM extraction for %s", domain
        )
        return CompanyExtract(company_name=domain)

    # Combine all page text with source labels
    all_text = "\n\n---\n\n".join(
        "[{}]\n{}".format(url, text[:3000]) for url, text in raw_content.items()
    )
    # Cap total to avoid token overflow
    all_text = all_text[:12000]

    prompt = """Extract structured company information from this website content.
Domain: {domain}

Website content:
{content}

Return a JSON object with these fields:
- company_name: string (the company's official name)
- tagline: string (main tagline or slogan)
- products_services: list of strings (what they offer)
- team_size: string or null (e.g., "50-100", "500+")
- location: string or null (headquarters location)
- founding_year: string or null (year founded)
- key_clients: list of strings (notable clients mentioned)
- industries: list of strings (industries they serve)
- contact_info: object with optional keys: email, phone, address
- raw_about: string (full about page text, max 500 chars)

Return ONLY valid JSON, no markdown fences.""".format(domain=domain, content=all_text)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()

        # Strip markdown fences if present
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)

        data = json.loads(text)
        return CompanyExtract(
            company_name=data.get("company_name", domain),
            tagline=data.get("tagline", ""),
            products_services=data.get("products_services", []),
            team_size=data.get("team_size"),
            location=data.get("location"),
            founding_year=data.get("founding_year"),
            key_clients=data.get("key_clients", []),
            industries=data.get("industries", []),
            contact_info=data.get("contact_info", {}),
            raw_about=data.get("raw_about", "")[:500],
        )
    except Exception as exc:
        logger.warning("LLM extraction failed for %s: %s", domain, exc)
        return CompanyExtract(company_name=domain)
