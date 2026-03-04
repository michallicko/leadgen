"""Unit tests for CSV column mapping service."""

import json
from unittest.mock import MagicMock, patch

from api.services.csv_mapper import (
    TARGET_FIELDS,
    apply_mapping,
    build_mapping_prompt,
    extract_domain,
    normalize_enum,
    validate_and_fix_company,
)


class TestExtractDomain:
    def test_full_url(self):
        assert extract_domain("https://www.example.com/about") == "example.com"

    def test_http_url(self):
        assert extract_domain("http://example.org/page") == "example.org"

    def test_www_only(self):
        assert extract_domain("www.test.io") == "test.io"

    def test_plain_domain(self):
        assert extract_domain("acme.com") == "acme.com"

    def test_trailing_slash(self):
        assert extract_domain("https://example.com/") == "example.com"

    def test_with_query(self):
        assert extract_domain("https://example.com?q=1") == "example.com"

    def test_with_fragment(self):
        assert extract_domain("https://example.com#top") == "example.com"

    def test_empty(self):
        assert extract_domain("") is None
        assert extract_domain(None) is None

    def test_whitespace(self):
        assert extract_domain("  https://example.com  ") == "example.com"

    def test_case_insensitive(self):
        assert extract_domain("HTTPS://WWW.Example.COM/path") == "example.com"


class TestNormalizeEnum:
    def test_seniority_c_level(self):
        assert normalize_enum("seniority_level", "C-Level") == "c_level"

    def test_seniority_c_level_lowercase(self):
        assert normalize_enum("seniority_level", "c level") == "c_level"

    def test_seniority_vp(self):
        assert normalize_enum("seniority_level", "VP") == "vp"

    def test_seniority_vice_president(self):
        assert normalize_enum("seniority_level", "Vice President") == "vp"

    def test_department_hr(self):
        assert normalize_enum("department", "Human Resources") == "hr"

    def test_department_engineering(self):
        assert normalize_enum("department", "Engineering") == "engineering"

    def test_language_english(self):
        assert normalize_enum("language", "English") == "en"

    def test_language_code(self):
        assert normalize_enum("language", "de") == "de"

    def test_industry_saas(self):
        assert normalize_enum("industry", "SaaS") == "software_saas"

    def test_company_size_mid_market(self):
        assert normalize_enum("company_size", "Mid-Market") == "mid_market"

    def test_business_model_b2b(self):
        assert normalize_enum("business_model", "B2B") == "b2b"

    def test_unknown_field(self):
        assert normalize_enum("nonexistent", "anything") == "anything"

    def test_unknown_value_falls_back_to_other(self):
        # Unknown values now map to 'other' (or None if 'other' not in enum)
        # instead of passing through, to prevent PostgreSQL enum INSERT failures
        assert normalize_enum("seniority_level", "Unknown Role") == "other"

    def test_empty(self):
        assert normalize_enum("seniority_level", "") == ""
        assert normalize_enum("seniority_level", None) is None

    def test_whitespace_stripping(self):
        assert normalize_enum("seniority_level", "  VP  ") == "vp"


class TestSanitizeEnumValue:
    """Tests for sanitize_enum_value — the core enum validation function."""

    def test_exact_match(self):
        from api.services.csv_mapper import sanitize_enum_value

        assert sanitize_enum_value("contact_source", "event") == "event"

    def test_case_insensitive(self):
        from api.services.csv_mapper import sanitize_enum_value

        assert sanitize_enum_value("contact_source", "Event") == "event"

    def test_hyphen_to_underscore(self):
        from api.services.csv_mapper import sanitize_enum_value

        assert sanitize_enum_value("company_size", "mid-market") == "mid_market"

    def test_substring_match_event_in_text(self):
        from api.services.csv_mapper import sanitize_enum_value

        cf = {}
        result = sanitize_enum_value("contact_source", "Event Fest 2025", cf)
        assert result == "event"
        assert cf["original_contact_source"] == "Event Fest 2025"

    def test_substring_match_social_in_text(self):
        from api.services.csv_mapper import sanitize_enum_value

        cf = {}
        result = sanitize_enum_value("contact_source", "Social Media Campaign", cf)
        assert result == "social"
        assert cf["original_contact_source"] == "Social Media Campaign"

    def test_alias_lookup(self):
        from api.services.csv_mapper import sanitize_enum_value

        assert sanitize_enum_value("seniority_level", "Vice President") == "vp"

    def test_no_match_falls_back_to_other(self):
        from api.services.csv_mapper import sanitize_enum_value

        cf = {}
        result = sanitize_enum_value("contact_source", "xyz_unknown_123", cf)
        assert result == "other"
        assert cf["original_contact_source"] == "xyz_unknown_123"

    def test_no_match_no_other_returns_none(self):
        from api.services.csv_mapper import sanitize_enum_value

        # language enum has no 'other' value
        cf = {}
        result = sanitize_enum_value("language", "Klingon", cf)
        assert result is None
        assert cf["original_language"] == "Klingon"

    def test_none_value_returns_none(self):
        from api.services.csv_mapper import sanitize_enum_value

        assert sanitize_enum_value("contact_source", None) is None

    def test_empty_value_returns_none(self):
        from api.services.csv_mapper import sanitize_enum_value

        assert sanitize_enum_value("contact_source", "") is None

    def test_non_enum_field_passes_through(self):
        from api.services.csv_mapper import sanitize_enum_value

        assert sanitize_enum_value("first_name", "John") == "John"

    def test_apply_mapping_sanitizes_contact_source(self):
        """Integration: apply_mapping should sanitize enum fields."""
        row = {"Source": "Event Fest 2025", "First": "Jane"}
        mapping = {
            "mappings": [
                {"csv_header": "Source", "target": "contact.contact_source"},
                {"csv_header": "First", "target": "contact.first_name"},
            ]
        }
        result = apply_mapping(row, mapping)
        assert result["contact"]["contact_source"] == "event"
        assert (
            result["contact"]["_custom_fields"]["original_contact_source"]
            == "Event Fest 2025"
        )

    def test_apply_mapping_sanitizes_company_enum(self):
        """Integration: apply_mapping should sanitize company enum fields."""
        row = {"Model": "Non-Profit Organization", "Name": "Acme"}
        mapping = {
            "mappings": [
                {"csv_header": "Model", "target": "company.business_model"},
                {"csv_header": "Name", "target": "company.name"},
            ]
        }
        result = apply_mapping(row, mapping)
        assert result["company"]["business_model"] == "non_profit"


class TestBuildMappingPrompt:
    def test_includes_headers(self):
        prompt = build_mapping_prompt(["Name", "Email"], [])
        assert "Name" in prompt
        assert "Email" in prompt

    def test_includes_sample_rows(self):
        rows = [{"Name": "John", "Email": "john@test.com"}]
        prompt = build_mapping_prompt(["Name", "Email"], rows)
        assert "John" in prompt
        assert "john@test.com" in prompt

    def test_limits_to_5_rows(self):
        rows = [{"col": str(i)} for i in range(10)]
        prompt = build_mapping_prompt(["col"], rows)
        assert "Row 5" in prompt
        assert "Row 6" not in prompt


class TestApplyMapping:
    def test_simple_mapping(self):
        row = {"First": "John", "Last": "Doe", "Position": "CEO", "Company": "Acme"}
        mapping = {
            "mappings": [
                {
                    "csv_header": "First",
                    "target": "contact.first_name",
                    "confidence": 0.9,
                    "transform": None,
                },
                {
                    "csv_header": "Last",
                    "target": "contact.last_name",
                    "confidence": 0.9,
                    "transform": None,
                },
                {
                    "csv_header": "Position",
                    "target": "contact.job_title",
                    "confidence": 0.8,
                    "transform": None,
                },
                {
                    "csv_header": "Company",
                    "target": "company.name",
                    "confidence": 0.9,
                    "transform": None,
                },
            ],
        }
        result = apply_mapping(row, mapping)
        assert result["contact"]["first_name"] == "John"
        assert result["contact"]["last_name"] == "Doe"
        assert result["contact"]["job_title"] == "CEO"
        assert result["company"]["name"] == "Acme"

    def test_extract_domain_transform(self):
        row = {"Website": "https://www.acme.com/about"}
        mapping = {
            "mappings": [
                {
                    "csv_header": "Website",
                    "target": "company.domain",
                    "confidence": 0.9,
                    "transform": "extract_domain",
                },
            ],
        }
        result = apply_mapping(row, mapping)
        assert result["company"]["domain"] == "acme.com"

    def test_normalize_enum_transform(self):
        row = {"Level": "C-Level"}
        mapping = {
            "mappings": [
                {
                    "csv_header": "Level",
                    "target": "contact.seniority_level",
                    "confidence": 0.8,
                    "transform": "normalize_enum",
                },
            ],
        }
        result = apply_mapping(row, mapping)
        assert result["contact"]["seniority_level"] == "c_level"

    def test_first_last_name_separate_columns(self):
        row = {"First": "John", "Last": "Doe", "Email": "j@test.com"}
        mapping = {
            "mappings": [
                {
                    "csv_header": "First",
                    "target": "contact.first_name",
                    "confidence": 0.9,
                    "transform": None,
                },
                {
                    "csv_header": "Last",
                    "target": "contact.last_name",
                    "confidence": 0.9,
                    "transform": None,
                },
                {
                    "csv_header": "Email",
                    "target": "contact.email_address",
                    "confidence": 0.9,
                    "transform": None,
                },
            ],
        }
        result = apply_mapping(row, mapping)
        assert result["contact"]["first_name"] == "John"
        assert result["contact"]["last_name"] == "Doe"
        assert result["contact"]["email_address"] == "j@test.com"

    def test_unmapped_columns_ignored(self):
        row = {"Name": "John", "Internal ID": "12345"}
        mapping = {
            "mappings": [
                {
                    "csv_header": "Name",
                    "target": "contact.first_name",
                    "confidence": 0.9,
                    "transform": None,
                },
                {
                    "csv_header": "Internal ID",
                    "target": None,
                    "confidence": 0,
                    "transform": None,
                },
            ],
        }
        result = apply_mapping(row, mapping)
        assert result["contact"]["first_name"] == "John"
        assert "Internal ID" not in result["contact"]
        assert "Internal ID" not in result["company"]

    def test_empty_values_skipped(self):
        row = {"Name": "John", "Email": ""}
        mapping = {
            "mappings": [
                {
                    "csv_header": "Name",
                    "target": "contact.first_name",
                    "confidence": 0.9,
                    "transform": None,
                },
                {
                    "csv_header": "Email",
                    "target": "contact.email_address",
                    "confidence": 0.9,
                    "transform": None,
                },
            ],
        }
        result = apply_mapping(row, mapping)
        assert result["contact"]["first_name"] == "John"
        assert "email_address" not in result["contact"]


class TestCallClaudeForMapping:
    def test_successful_call(self):
        """Test that call_claude_for_mapping parses Claude's response."""
        import os

        os.environ["ANTHROPIC_API_KEY"] = "test-key"

        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps(
            {
                "mappings": [
                    {
                        "csv_header": "Name",
                        "target": "contact.first_name",
                        "confidence": 0.95,
                        "transform": None,
                    },
                ],
                "warnings": [],
            }
        )

        mock_response.model = "claude-sonnet-4-5-20250929"
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            from api.services.csv_mapper import call_claude_for_mapping

            result, usage_info = call_claude_for_mapping(["Name"], [{"Name": "John"}])

        assert len(result["mappings"]) == 1
        assert result["mappings"][0]["target"] == "contact.first_name"
        assert result["warnings"] == []
        assert usage_info["model"] == "claude-sonnet-4-5-20250929"
        assert usage_info["input_tokens"] == 100
        assert usage_info["output_tokens"] == 50

    def test_strips_markdown_fences(self):
        """Test that markdown code fences are stripped from response."""
        import os

        os.environ["ANTHROPIC_API_KEY"] = "test-key"

        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = '```json\n{"mappings": [], "warnings": []}\n```'
        mock_response.model = "claude-sonnet-4-5-20250929"
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 80
        mock_response.usage.output_tokens = 30

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            from api.services.csv_mapper import call_claude_for_mapping

            result, usage_info = call_claude_for_mapping(["Name"], [{"Name": "John"}])

        assert result["mappings"] == []
        assert usage_info["input_tokens"] == 80


class TestApplyMappingCustomFields:
    def test_custom_contact_field(self):
        row = {"Name": "John", "Alt Email": "alt@test.com"}
        mapping = {
            "mappings": [
                {
                    "csv_header": "Name",
                    "target": "contact.first_name",
                    "confidence": 0.9,
                    "transform": None,
                },
                {
                    "csv_header": "Alt Email",
                    "target": "contact.custom.email_secondary",
                    "confidence": 0.8,
                    "transform": None,
                },
            ],
            "combine_columns": [],
        }
        result = apply_mapping(row, mapping)
        assert result["contact"]["first_name"] == "John"
        assert result["contact"]["_custom_fields"]["email_secondary"] == "alt@test.com"

    def test_custom_company_field(self):
        row = {"Company": "Acme", "Tax ID": "DE123456"}
        mapping = {
            "mappings": [
                {
                    "csv_header": "Company",
                    "target": "company.name",
                    "confidence": 0.9,
                    "transform": None,
                },
                {
                    "csv_header": "Tax ID",
                    "target": "company.custom.tax_id",
                    "confidence": 0.8,
                    "transform": None,
                },
            ],
            "combine_columns": [],
        }
        result = apply_mapping(row, mapping)
        assert result["company"]["name"] == "Acme"
        assert result["company"]["_custom_fields"]["tax_id"] == "DE123456"

    def test_multiple_custom_fields(self):
        row = {"Name": "Jane", "Notes": "VIP", "Source ID": "ext-42"}
        mapping = {
            "mappings": [
                {
                    "csv_header": "Name",
                    "target": "contact.first_name",
                    "confidence": 0.9,
                    "transform": None,
                },
                {
                    "csv_header": "Notes",
                    "target": "contact.custom.internal_notes",
                    "confidence": 0.7,
                    "transform": None,
                },
                {
                    "csv_header": "Source ID",
                    "target": "contact.custom.source_id",
                    "confidence": 0.7,
                    "transform": None,
                },
            ],
            "combine_columns": [],
        }
        result = apply_mapping(row, mapping)
        assert result["contact"]["_custom_fields"]["internal_notes"] == "VIP"
        assert result["contact"]["_custom_fields"]["source_id"] == "ext-42"

    def test_empty_custom_field_skipped(self):
        row = {"Name": "John", "Notes": ""}
        mapping = {
            "mappings": [
                {
                    "csv_header": "Name",
                    "target": "contact.first_name",
                    "confidence": 0.9,
                    "transform": None,
                },
                {
                    "csv_header": "Notes",
                    "target": "contact.custom.notes",
                    "confidence": 0.7,
                    "transform": None,
                },
            ],
            "combine_columns": [],
        }
        result = apply_mapping(row, mapping)
        assert "_custom_fields" not in result["contact"]

    def test_mixed_standard_and_custom(self):
        row = {"Name": "Jane", "Email": "jane@test.com", "Priority": "High"}
        mapping = {
            "mappings": [
                {
                    "csv_header": "Name",
                    "target": "contact.first_name",
                    "confidence": 0.9,
                    "transform": None,
                },
                {
                    "csv_header": "Email",
                    "target": "contact.email_address",
                    "confidence": 0.9,
                    "transform": None,
                },
                {
                    "csv_header": "Priority",
                    "target": "contact.custom.priority",
                    "confidence": 0.7,
                    "transform": None,
                },
            ],
            "combine_columns": [],
        }
        result = apply_mapping(row, mapping)
        assert result["contact"]["first_name"] == "Jane"
        assert result["contact"]["email_address"] == "jane@test.com"
        assert result["contact"]["_custom_fields"]["priority"] == "High"


class TestValidateAndFixCompany:
    def test_valid_company_unchanged(self):
        assert validate_and_fix_company("Acme Corp") == "Acme Corp"

    def test_valid_short_company(self):
        """3-char company names are valid (e.g. 'IBM', 'SAP')."""
        assert validate_and_fix_company("IBM") == "IBM"

    def test_empty_string_with_email(self):
        assert validate_and_fix_company("", "john@acme.com") == "acme.com"

    def test_empty_string_no_email(self):
        assert validate_and_fix_company("") == "Unknown"

    def test_none_with_email(self):
        assert validate_and_fix_company(None, "jane@4pro.cz") == "4pro.cz"

    def test_none_no_email(self):
        assert validate_and_fix_company(None) == "Unknown"

    def test_whitespace_only(self):
        assert validate_and_fix_company("   ", "a@test.io") == "test.io"

    def test_date_iso(self):
        assert validate_and_fix_company("2021-12-04", "a@acme.com") == "acme.com"

    def test_date_iso_with_time(self):
        assert (
            validate_and_fix_company("2021-12-04 00:00:00", "a@acme.com") == "acme.com"
        )

    def test_date_us_format(self):
        assert validate_and_fix_company("12/04/2021", "a@test.com") == "test.com"

    def test_date_eu_format(self):
        assert validate_and_fix_company("04.12.2021", "a@test.com") == "test.com"

    def test_date_no_email(self):
        assert validate_and_fix_company("2021-12-04") == "Unknown"

    def test_pure_integer(self):
        assert validate_and_fix_company("12345", "a@corp.io") == "corp.io"

    def test_pure_decimal(self):
        assert validate_and_fix_company("123.45", "a@corp.io") == "corp.io"

    def test_pure_number_no_email(self):
        assert validate_and_fix_company("42") == "Unknown"

    def test_too_short_one_char(self):
        assert validate_and_fix_company("X", "a@bigco.com") == "bigco.com"

    def test_too_short_two_chars(self):
        assert validate_and_fix_company("AB", "a@bigco.com") == "bigco.com"

    def test_strips_whitespace(self):
        assert validate_and_fix_company("  Acme  ") == "Acme"

    def test_number_like_company_name(self):
        """Company names starting with digits but containing letters are valid."""
        assert validate_and_fix_company("1Year") == "1Year"
        assert validate_and_fix_company("3M Company") == "3M Company"

    def test_email_without_at_sign(self):
        """Invalid email should not crash, returns Unknown."""
        assert validate_and_fix_company("", "not-an-email") == "Unknown"


class TestApplyMappingCompanyValidation:
    def test_date_in_company_replaced_by_email_domain(self):
        row = {
            "Name": "John",
            "Email": "john@acme.com",
            "Company": "2021-12-04 00:00:00",
        }
        mapping = {
            "mappings": [
                {
                    "csv_header": "Name",
                    "target": "contact.first_name",
                    "confidence": 0.9,
                    "transform": None,
                },
                {
                    "csv_header": "Email",
                    "target": "contact.email_address",
                    "confidence": 0.9,
                    "transform": None,
                },
                {
                    "csv_header": "Company",
                    "target": "company.name",
                    "confidence": 0.9,
                    "transform": None,
                },
            ],
        }
        result = apply_mapping(row, mapping)
        assert result["company"]["name"] == "acme.com"

    def test_number_in_company_replaced(self):
        row = {"Name": "Jane", "Email": "jane@corp.io", "Company": "12345"}
        mapping = {
            "mappings": [
                {
                    "csv_header": "Name",
                    "target": "contact.first_name",
                    "confidence": 0.9,
                    "transform": None,
                },
                {
                    "csv_header": "Email",
                    "target": "contact.email_address",
                    "confidence": 0.9,
                    "transform": None,
                },
                {
                    "csv_header": "Company",
                    "target": "company.name",
                    "confidence": 0.9,
                    "transform": None,
                },
            ],
        }
        result = apply_mapping(row, mapping)
        assert result["company"]["name"] == "corp.io"

    def test_valid_company_not_touched(self):
        row = {"Name": "John", "Company": "Acme Inc"}
        mapping = {
            "mappings": [
                {
                    "csv_header": "Name",
                    "target": "contact.first_name",
                    "confidence": 0.9,
                    "transform": None,
                },
                {
                    "csv_header": "Company",
                    "target": "company.name",
                    "confidence": 0.9,
                    "transform": None,
                },
            ],
        }
        result = apply_mapping(row, mapping)
        assert result["company"]["name"] == "Acme Inc"


class TestTargetFields:
    def test_contact_fields_present(self):
        assert "first_name" in TARGET_FIELDS["contact"]
        assert "last_name" in TARGET_FIELDS["contact"]
        assert "email_address" in TARGET_FIELDS["contact"]
        assert "linkedin_url" in TARGET_FIELDS["contact"]

    def test_company_fields_present(self):
        assert "name" in TARGET_FIELDS["company"]
        assert "domain" in TARGET_FIELDS["company"]
        assert "industry" in TARGET_FIELDS["company"]
