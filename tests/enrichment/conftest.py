"""Shared fixtures for enrichment node tests.

These tests call REAL LLM APIs (Perplexity, Anthropic).
Tests are skipped gracefully if API keys are not set.

Required env vars:
    PERPLEXITY_API_KEY  — for Perplexity sonar API calls
    ANTHROPIC_API_KEY   — for Anthropic Claude calls + quality scoring
"""

import json
import os
import re

import pytest

from tests.enrichment.utils.cost_tracker import CostTracker


# ---------------------------------------------------------------------------
# Pytest configuration
# ---------------------------------------------------------------------------

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "enrichment: enrichment node tests (real API calls)")
    config.addinivalue_line("markers", "slow: tests that take >10s (synthesis nodes)")
    config.addinivalue_line("markers", "costly: tests with multiple API calls")


# ---------------------------------------------------------------------------
# Fixture data loaders
# ---------------------------------------------------------------------------

_FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_json(filename):
    path = os.path.join(_FIXTURES_DIR, filename)
    with open(path) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def companies_fixtures():
    """Load all test companies from fixtures/companies.json."""
    return _load_json("companies.json")


@pytest.fixture(scope="session")
def contacts_fixtures():
    """Load all test contacts from fixtures/contacts.json."""
    return _load_json("contacts.json")


@pytest.fixture(scope="session")
def pre_enriched_fixtures():
    """Load pre-enriched data from fixtures/pre_enriched.json."""
    return _load_json("pre_enriched.json")


# ---------------------------------------------------------------------------
# Parametrize helpers
# ---------------------------------------------------------------------------

def get_company_keys():
    """Return all company fixture keys for parametrize."""
    data = _load_json("companies.json")
    return list(data.keys())


def get_contact_keys():
    """Return all contact fixture keys for parametrize."""
    data = _load_json("contacts.json")
    return list(data.keys())


# ---------------------------------------------------------------------------
# API client fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def perplexity_api_key():
    """Get Perplexity API key from env, skip if not set."""
    key = os.environ.get("PERPLEXITY_API_KEY", "")
    if not key:
        pytest.skip("PERPLEXITY_API_KEY not set")
    return key


@pytest.fixture(scope="session")
def anthropic_api_key():
    """Get Anthropic API key from env, skip if not set."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return key


@pytest.fixture(scope="session")
def perplexity_client(perplexity_api_key):
    """Create a Perplexity API client using the real API key."""
    # Import from the project's own client
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from api.services.perplexity_client import PerplexityClient
    return PerplexityClient(api_key=perplexity_api_key)


@pytest.fixture(scope="session")
def anthropic_client(anthropic_api_key):
    """Create an Anthropic API client using the real API key."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from api.services.anthropic_client import AnthropicClient
    return AnthropicClient(api_key=anthropic_api_key)


# ---------------------------------------------------------------------------
# Cost tracking
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def cost_tracker():
    """Session-scoped cost tracker — collects all API call costs."""
    tracker = CostTracker()
    yield tracker
    # Print summary and save report at end of session
    if tracker.calls:
        tracker.print_summary()
        report_path = tracker.save_report()
        print("Cost report saved: {}".format(report_path))


# ---------------------------------------------------------------------------
# Helper: call Perplexity with cost tracking
# ---------------------------------------------------------------------------

def call_perplexity(client, system_prompt, user_prompt, cost_tracker,
                    test_name, node_name="unknown", model="sonar",
                    max_tokens=600, temperature=0.1):
    """Call Perplexity API and log cost. Returns parsed dict or raw string.

    Strips markdown fences and parses JSON. Returns raw string if parsing fails.
    """
    resp = client.query(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    cost_tracker.log_call(
        provider="perplexity",
        model=model,
        input_tokens=resp.input_tokens,
        output_tokens=resp.output_tokens,
        cost_usd=resp.cost_usd,
        test_name=test_name,
        node_name=node_name,
    )

    return _parse_json(resp.content)


def call_anthropic(client, system_prompt, user_prompt, cost_tracker,
                   test_name, node_name="unknown",
                   model="claude-sonnet-4-5-20250929",
                   max_tokens=2000, temperature=0.3):
    """Call Anthropic API and log cost. Returns parsed dict."""
    resp = client.query(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    cost_tracker.log_call(
        provider="anthropic",
        model=model,
        input_tokens=resp.input_tokens,
        output_tokens=resp.output_tokens,
        cost_usd=resp.cost_usd,
        test_name=test_name,
        node_name=node_name,
    )

    return _parse_json(resp.content)


def _parse_json(content):
    """Parse JSON from LLM response, stripping markdown fences."""
    if not content:
        return {}
    cleaned = content.strip()
    # Strip all markdown code fences (may appear anywhere)
    cleaned = re.sub(r"```(?:json)?\s*\n?", "", cleaned)
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to extract the outermost JSON object with brace matching
        start = cleaned.find("{")
        if start != -1:
            depth = 0
            in_string = False
            escape_next = False
            for i in range(start, len(cleaned)):
                c = cleaned[i]
                if escape_next:
                    escape_next = False
                    continue
                if c == "\\":
                    escape_next = True
                    continue
                if c == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(cleaned[start:i + 1])
                        except json.JSONDecodeError:
                            break
    # Return raw string if parsing fails
    return content
