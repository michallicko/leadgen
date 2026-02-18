"""Unit tests for field quality schema."""

import pytest

from api.services.field_schema import (
    BUSINESS_TYPE_VALUES,
    COMPANY_SIZE_LEGACY,
    COMPANY_SIZE_VALUES,
    INDUSTRY_CATEGORY_VALUES,
    REVENUE_RANGE_VALUES,
    employees_to_size,
    get_prompt_instructions,
    industry_to_category,
    revenue_to_range,
)


class TestEmployeesToSize:
    """Test headcount → company_size bucketing."""

    def test_none_returns_none(self):
        assert employees_to_size(None) is None

    def test_1_employee_micro(self):
        assert employees_to_size(1) == "micro"

    def test_9_employees_micro(self):
        assert employees_to_size(9) == "micro"

    def test_10_employees_small(self):
        assert employees_to_size(10) == "small"

    def test_49_employees_small(self):
        assert employees_to_size(49) == "small"

    def test_50_employees_medium(self):
        assert employees_to_size(50) == "medium"

    def test_199_employees_medium(self):
        assert employees_to_size(199) == "medium"

    def test_200_employees_mid_market(self):
        assert employees_to_size(200) == "mid_market"

    def test_999_employees_mid_market(self):
        assert employees_to_size(999) == "mid_market"

    def test_1000_employees_enterprise(self):
        assert employees_to_size(1000) == "enterprise"

    def test_50000_employees_enterprise(self):
        assert employees_to_size(50000) == "enterprise"


class TestRevenueToRange:
    """Test revenue EUR millions → revenue_range bucketing."""

    def test_none_returns_none(self):
        assert revenue_to_range(None) is None

    def test_0_5m_micro(self):
        assert revenue_to_range(0.5) == "micro"

    def test_1m_small(self):
        assert revenue_to_range(1) == "small"

    def test_9m_small(self):
        assert revenue_to_range(9) == "small"

    def test_10m_medium(self):
        assert revenue_to_range(10) == "medium"

    def test_49m_medium(self):
        assert revenue_to_range(49) == "medium"

    def test_50m_mid_market(self):
        assert revenue_to_range(50) == "mid_market"

    def test_199m_mid_market(self):
        assert revenue_to_range(199) == "mid_market"

    def test_200m_enterprise(self):
        assert revenue_to_range(200) == "enterprise"

    def test_5000m_enterprise(self):
        assert revenue_to_range(5000) == "enterprise"


class TestIndustryToCategory:
    """Test industry → industry_category derivation."""

    def test_none_returns_none(self):
        assert industry_to_category(None) is None

    def test_empty_returns_none(self):
        assert industry_to_category("") is None

    def test_software_saas_is_technology(self):
        assert industry_to_category("software_saas") == "technology"

    def test_it_is_technology(self):
        assert industry_to_category("it") == "technology"

    def test_professional_services_is_services(self):
        assert industry_to_category("professional_services") == "services"

    def test_creative_services_is_services(self):
        assert industry_to_category("creative_services") == "services"

    def test_financial_services_is_finance(self):
        assert industry_to_category("financial_services") == "finance"

    def test_healthcare_is_healthcare_life_sci(self):
        assert industry_to_category("healthcare") == "healthcare_life_sci"

    def test_pharma_biotech_is_healthcare_life_sci(self):
        assert industry_to_category("pharma_biotech") == "healthcare_life_sci"

    def test_manufacturing_is_industrial(self):
        assert industry_to_category("manufacturing") == "industrial"

    def test_automotive_is_industrial(self):
        assert industry_to_category("automotive") == "industrial"

    def test_retail_is_consumer(self):
        assert industry_to_category("retail") == "consumer"

    def test_hospitality_is_consumer(self):
        assert industry_to_category("hospitality") == "consumer"

    def test_telecom_is_infrastructure(self):
        assert industry_to_category("telecom") == "infrastructure"

    def test_agriculture_is_primary_sector(self):
        assert industry_to_category("agriculture") == "primary_sector"

    def test_education_is_public_education(self):
        assert industry_to_category("education") == "public_education"

    def test_other_returns_none(self):
        assert industry_to_category("other") is None

    def test_unknown_returns_none(self):
        assert industry_to_category("xyzzy") is None


class TestAllIndustriesCovered:
    """Verify every industry in INDUSTRY_CATEGORY_VALUES maps back correctly."""

    def test_all_industries_map_to_their_category(self):
        for cat, meta in INDUSTRY_CATEGORY_VALUES.items():
            for ind in meta["industries"]:
                assert industry_to_category(ind) == cat, (
                    f"industry '{ind}' should map to '{cat}'"
                )


class TestGetPromptInstructions:
    """Test prompt instruction generation."""

    def test_l1_has_business_type(self):
        instructions = get_prompt_instructions("l1")
        assert "business_type" in instructions
        assert "product_company" in instructions["business_type"]

    def test_l1_has_industry(self):
        instructions = get_prompt_instructions("l1")
        assert "industry" in instructions

    def test_unknown_stage_returns_empty(self):
        assert get_prompt_instructions("nonexistent") == {}


class TestSchemaCompleteness:
    """Verify schema constants are internally consistent."""

    def test_company_size_legacy_maps_to_valid_values(self):
        for legacy, target in COMPANY_SIZE_LEGACY.items():
            assert target in COMPANY_SIZE_VALUES, (
                f"legacy '{legacy}' maps to '{target}' not in COMPANY_SIZE_VALUES"
            )

    def test_company_size_values_non_empty(self):
        assert len(COMPANY_SIZE_VALUES) >= 5

    def test_revenue_range_values_non_empty(self):
        assert len(REVENUE_RANGE_VALUES) >= 5

    def test_business_type_values_non_empty(self):
        assert len(BUSINESS_TYPE_VALUES) >= 7

    def test_industry_category_covers_major_industries(self):
        all_industries = set()
        for meta in INDUSTRY_CATEGORY_VALUES.values():
            all_industries.update(meta["industries"])
        # At least 20 industries covered
        assert len(all_industries) >= 20
