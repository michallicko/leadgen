"""Unit tests for CSV column mapping service."""
import json
from unittest.mock import MagicMock, patch

import pytest

from api.services.csv_mapper import (
    TARGET_FIELDS,
    apply_mapping,
    build_mapping_prompt,
    extract_domain,
    normalize_enum,
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

    def test_unknown_value_passthrough(self):
        assert normalize_enum("seniority_level", "Unknown Role") == "Unknown Role"

    def test_empty(self):
        assert normalize_enum("seniority_level", "") == ""
        assert normalize_enum("seniority_level", None) is None

    def test_whitespace_stripping(self):
        assert normalize_enum("seniority_level", "  VP  ") == "vp"


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
        row = {"Name": "John Doe", "Position": "CEO", "Company": "Acme"}
        mapping = {
            "mappings": [
                {"csv_header": "Name", "target": "contact.full_name", "confidence": 0.9, "transform": None},
                {"csv_header": "Position", "target": "contact.job_title", "confidence": 0.8, "transform": None},
                {"csv_header": "Company", "target": "company.name", "confidence": 0.9, "transform": None},
            ],
            "combine_columns": [],
        }
        result = apply_mapping(row, mapping)
        assert result["contact"]["full_name"] == "John Doe"
        assert result["contact"]["job_title"] == "CEO"
        assert result["company"]["name"] == "Acme"

    def test_extract_domain_transform(self):
        row = {"Website": "https://www.acme.com/about"}
        mapping = {
            "mappings": [
                {"csv_header": "Website", "target": "company.domain", "confidence": 0.9, "transform": "extract_domain"},
            ],
            "combine_columns": [],
        }
        result = apply_mapping(row, mapping)
        assert result["company"]["domain"] == "acme.com"

    def test_normalize_enum_transform(self):
        row = {"Level": "C-Level"}
        mapping = {
            "mappings": [
                {"csv_header": "Level", "target": "contact.seniority_level", "confidence": 0.8, "transform": "normalize_enum"},
            ],
            "combine_columns": [],
        }
        result = apply_mapping(row, mapping)
        assert result["contact"]["seniority_level"] == "c_level"

    def test_combine_columns(self):
        row = {"First": "John", "Last": "Doe", "Email": "j@test.com"}
        mapping = {
            "mappings": [
                {"csv_header": "First", "target": "contact.full_name", "confidence": 0.9, "transform": "combine_first_last"},
                {"csv_header": "Last", "target": "contact.full_name", "confidence": 0.9, "transform": None},
                {"csv_header": "Email", "target": "contact.email_address", "confidence": 0.9, "transform": None},
            ],
            "combine_columns": [
                {"sources": ["First", "Last"], "target": "contact.full_name", "separator": " "},
            ],
        }
        result = apply_mapping(row, mapping)
        assert result["contact"]["full_name"] == "John Doe"
        assert result["contact"]["email_address"] == "j@test.com"

    def test_unmapped_columns_ignored(self):
        row = {"Name": "John", "Internal ID": "12345"}
        mapping = {
            "mappings": [
                {"csv_header": "Name", "target": "contact.full_name", "confidence": 0.9, "transform": None},
                {"csv_header": "Internal ID", "target": None, "confidence": 0, "transform": None},
            ],
            "combine_columns": [],
        }
        result = apply_mapping(row, mapping)
        assert result["contact"]["full_name"] == "John"
        assert "Internal ID" not in result["contact"]
        assert "Internal ID" not in result["company"]

    def test_empty_values_skipped(self):
        row = {"Name": "John", "Email": ""}
        mapping = {
            "mappings": [
                {"csv_header": "Name", "target": "contact.full_name", "confidence": 0.9, "transform": None},
                {"csv_header": "Email", "target": "contact.email_address", "confidence": 0.9, "transform": None},
            ],
            "combine_columns": [],
        }
        result = apply_mapping(row, mapping)
        assert result["contact"]["full_name"] == "John"
        assert "email_address" not in result["contact"]


class TestCallClaudeForMapping:
    def test_successful_call(self):
        """Test that call_claude_for_mapping parses Claude's response."""
        import os
        os.environ["ANTHROPIC_API_KEY"] = "test-key"

        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "mappings": [
                {"csv_header": "Name", "target": "contact.full_name", "confidence": 0.95, "transform": None},
            ],
            "warnings": [],
            "combine_columns": [],
        })

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
        assert result["mappings"][0]["target"] == "contact.full_name"
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
        mock_response.content[0].text = '```json\n{"mappings": [], "warnings": [], "combine_columns": []}\n```'
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
                {"csv_header": "Name", "target": "contact.full_name", "confidence": 0.9, "transform": None},
                {"csv_header": "Alt Email", "target": "contact.custom.email_secondary", "confidence": 0.8, "transform": None},
            ],
            "combine_columns": [],
        }
        result = apply_mapping(row, mapping)
        assert result["contact"]["full_name"] == "John"
        assert result["contact"]["_custom_fields"]["email_secondary"] == "alt@test.com"

    def test_custom_company_field(self):
        row = {"Company": "Acme", "Tax ID": "DE123456"}
        mapping = {
            "mappings": [
                {"csv_header": "Company", "target": "company.name", "confidence": 0.9, "transform": None},
                {"csv_header": "Tax ID", "target": "company.custom.tax_id", "confidence": 0.8, "transform": None},
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
                {"csv_header": "Name", "target": "contact.full_name", "confidence": 0.9, "transform": None},
                {"csv_header": "Notes", "target": "contact.custom.internal_notes", "confidence": 0.7, "transform": None},
                {"csv_header": "Source ID", "target": "contact.custom.source_id", "confidence": 0.7, "transform": None},
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
                {"csv_header": "Name", "target": "contact.full_name", "confidence": 0.9, "transform": None},
                {"csv_header": "Notes", "target": "contact.custom.notes", "confidence": 0.7, "transform": None},
            ],
            "combine_columns": [],
        }
        result = apply_mapping(row, mapping)
        assert "_custom_fields" not in result["contact"]

    def test_mixed_standard_and_custom(self):
        row = {"Name": "Jane", "Email": "jane@test.com", "Priority": "High"}
        mapping = {
            "mappings": [
                {"csv_header": "Name", "target": "contact.full_name", "confidence": 0.9, "transform": None},
                {"csv_header": "Email", "target": "contact.email_address", "confidence": 0.9, "transform": None},
                {"csv_header": "Priority", "target": "contact.custom.priority", "confidence": 0.7, "transform": None},
            ],
            "combine_columns": [],
        }
        result = apply_mapping(row, mapping)
        assert result["contact"]["full_name"] == "Jane"
        assert result["contact"]["email_address"] == "jane@test.com"
        assert result["contact"]["_custom_fields"]["priority"] == "High"


class TestTargetFields:
    def test_contact_fields_present(self):
        assert "full_name" in TARGET_FIELDS["contact"]
        assert "email_address" in TARGET_FIELDS["contact"]
        assert "linkedin_url" in TARGET_FIELDS["contact"]

    def test_company_fields_present(self):
        assert "name" in TARGET_FIELDS["company"]
        assert "domain" in TARGET_FIELDS["company"]
        assert "industry" in TARGET_FIELDS["company"]
