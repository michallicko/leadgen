"""Unit tests for Google Contacts parsing service (pure functions, no DB/Flask needed)."""
import pytest

from api.services.google_contacts import (
    _extract_domain,
    _split_name,
    parse_contacts_to_rows,
)


class TestExtractDomain:
    def test_normal_email(self):
        assert _extract_domain("john@acme.com") == "acme.com"

    def test_subdomain_email(self):
        assert _extract_domain("admin@mail.example.org") == "mail.example.org"

    def test_none_returns_none(self):
        assert _extract_domain(None) is None

    def test_empty_string_returns_none(self):
        assert _extract_domain("") is None

    def test_no_at_symbol_returns_none(self):
        assert _extract_domain("not-an-email") is None

    def test_uppercase_normalized(self):
        assert _extract_domain("John@ACME.COM") == "acme.com"


class TestSplitName:
    def test_full_name(self):
        assert _split_name("John Doe") == ("John", "Doe")

    def test_single_name(self):
        assert _split_name("John") == ("John", "")

    def test_empty_string(self):
        assert _split_name("") == ("", "")

    def test_none_returns_empty(self):
        assert _split_name(None) == ("", "")

    def test_three_part_name(self):
        # "Mary Jane Watson" -> first="Mary", last="Jane Watson"
        first, last = _split_name("Mary Jane Watson")
        assert first == "Mary"
        assert last == "Jane Watson"

    def test_whitespace_trimmed(self):
        assert _split_name("  John   Doe  ") == ("John", "Doe")


class TestParseBasicContact:
    def test_full_contact(self):
        raw = [{
            "resourceName": "people/c123",
            "names": [{"givenName": "John", "familyName": "Doe", "displayName": "John Doe"}],
            "emailAddresses": [{"value": "john@acme.com"}],
            "organizations": [{"name": "Acme Corp", "title": "CEO"}],
            "phoneNumbers": [{"value": "+1234567890"}],
        }]
        rows = parse_contacts_to_rows(raw)
        assert len(rows) == 1
        row = rows[0]

        assert row["contact"]["first_name"] == "John"
        assert row["contact"]["last_name"] == "Doe"
        assert row["contact"]["email_address"] == "john@acme.com"
        assert row["contact"]["job_title"] == "CEO"
        assert row["contact"]["phone_number"] == "+1234567890"
        assert row["contact"]["contact_source"] == "google_contacts"

        assert row["company"]["name"] == "Acme Corp"
        assert row["company"]["domain"] == "acme.com"

    def test_contact_missing_org(self):
        raw = [{
            "resourceName": "people/c456",
            "names": [{"givenName": "Jane", "familyName": "Smith"}],
            "emailAddresses": [{"value": "jane@beta.io"}],
        }]
        rows = parse_contacts_to_rows(raw)
        assert len(rows) == 1
        row = rows[0]

        assert row["contact"]["first_name"] == "Jane"
        assert row["contact"]["job_title"] == ""
        # company should have domain from email but no name
        assert "name" not in row["company"]
        assert row["company"]["domain"] == "beta.io"

    def test_contact_missing_name_uses_email_prefix(self):
        raw = [{
            "resourceName": "people/c789",
            "emailAddresses": [{"value": "noname@example.com"}],
        }]
        rows = parse_contacts_to_rows(raw)
        assert len(rows) == 1
        row = rows[0]
        assert row["contact"]["first_name"] == "noname"
        assert row["contact"]["last_name"] == ""

    def test_contact_multiple_emails_uses_first(self):
        raw = [{
            "resourceName": "people/c101",
            "names": [{"givenName": "Multi", "familyName": "Email"}],
            "emailAddresses": [
                {"value": "primary@first.com"},
                {"value": "secondary@second.com"},
            ],
        }]
        rows = parse_contacts_to_rows(raw)
        assert len(rows) == 1
        assert rows[0]["contact"]["email_address"] == "primary@first.com"
        assert rows[0]["company"]["domain"] == "first.com"

    def test_contact_no_name_no_email_skipped(self):
        raw = [{
            "resourceName": "people/c999",
            "phoneNumbers": [{"value": "+9999"}],
        }]
        rows = parse_contacts_to_rows(raw)
        assert len(rows) == 0

    def test_contact_with_display_name_only(self):
        """Names list with displayName but no givenName/familyName should split."""
        raw = [{
            "resourceName": "people/c200",
            "names": [{"displayName": "Alice Wonderland"}],
            "emailAddresses": [{"value": "alice@wonder.land"}],
        }]
        rows = parse_contacts_to_rows(raw)
        assert len(rows) == 1
        assert rows[0]["contact"]["first_name"] == "Alice"
        assert rows[0]["contact"]["last_name"] == "Wonderland"


class TestParseMultipleContacts:
    def test_batch_of_three(self):
        raw = [
            {
                "resourceName": "people/c1",
                "names": [{"givenName": "Alice", "familyName": "A"}],
                "emailAddresses": [{"value": "alice@a.com"}],
                "organizations": [{"name": "AlphaCo", "title": "VP"}],
            },
            {
                "resourceName": "people/c2",
                "names": [{"givenName": "Bob", "familyName": "B"}],
                "emailAddresses": [{"value": "bob@b.com"}],
                "organizations": [{"name": "BetaCo", "title": "CTO"}],
            },
            {
                "resourceName": "people/c3",
                "names": [{"givenName": "Carol", "familyName": "C"}],
                "emailAddresses": [{"value": "carol@c.com"}],
            },
        ]
        rows = parse_contacts_to_rows(raw)
        assert len(rows) == 3
        assert rows[0]["contact"]["first_name"] == "Alice"
        assert rows[1]["contact"]["first_name"] == "Bob"
        assert rows[2]["contact"]["first_name"] == "Carol"


class TestOutputFormat:
    def test_output_matches_dedup_format(self):
        """Verify output has the {"contact": {...}, "company": {...}} structure with expected keys."""
        raw = [{
            "resourceName": "people/c1",
            "names": [{"givenName": "Test", "familyName": "User"}],
            "emailAddresses": [{"value": "test@company.com"}],
            "organizations": [{"name": "TestCo", "title": "Engineer"}],
            "phoneNumbers": [{"value": "+1111"}],
        }]
        rows = parse_contacts_to_rows(raw)
        assert len(rows) == 1
        row = rows[0]

        # Top-level keys
        assert set(row.keys()) == {"contact", "company"}

        # Contact keys
        expected_contact_keys = {
            "first_name", "last_name", "email_address",
            "job_title", "phone_number", "contact_source",
        }
        assert set(row["contact"].keys()) == expected_contact_keys

        # Company keys (when org and email are present)
        assert "name" in row["company"]
        assert "domain" in row["company"]

    def test_output_no_company_keys_when_no_org_no_email(self):
        """When there's no org and no email, company dict should be empty."""
        raw = [{
            "resourceName": "people/c1",
            "names": [{"givenName": "Lonely", "familyName": "Person"}],
        }]
        rows = parse_contacts_to_rows(raw)
        assert len(rows) == 1
        assert rows[0]["company"] == {}
