"""Unit tests for fuzzy enum mapper."""

import pytest

from api.services.enum_mapper import map_enum_value, ENUM_CONFIGS


class TestOwnershipTypeMapping:
    """Test ownership_type enum fuzzy mapping."""

    def test_valid_value_passthrough(self):
        assert map_enum_value("ownership_type", "bootstrapped") == "bootstrapped"

    def test_valid_value_case_insensitive(self):
        assert map_enum_value("ownership_type", "VC_Backed") == "vc_backed"

    def test_private_maps_to_bootstrapped(self):
        assert map_enum_value("ownership_type", "Private") == "bootstrapped"

    def test_privately_held_maps_to_bootstrapped(self):
        assert map_enum_value("ownership_type", "Privately held") == "bootstrapped"

    def test_government_maps_to_state_owned(self):
        assert map_enum_value("ownership_type", "Government") == "state_owned"

    def test_government_owned_maps_to_state_owned(self):
        assert map_enum_value("ownership_type", "Government-owned") == "state_owned"

    def test_non_profit_maps_to_other(self):
        assert map_enum_value("ownership_type", "Non-profit") == "other"

    def test_publicly_traded_maps_to_public(self):
        assert map_enum_value("ownership_type", "Publicly traded") == "public"

    def test_listed_maps_to_public(self):
        assert map_enum_value("ownership_type", "Listed") == "public"

    def test_venture_backed_maps_to_vc(self):
        assert map_enum_value("ownership_type", "Venture-backed") == "vc_backed"

    def test_pe_owned_maps_to_pe_backed(self):
        assert map_enum_value("ownership_type", "PE-owned") == "pe_backed"

    def test_private_equity_maps_to_pe_backed(self):
        assert map_enum_value("ownership_type", "Private equity") == "pe_backed"

    def test_cooperative_maps_to_other(self):
        assert map_enum_value("ownership_type", "Cooperative") == "other"

    def test_unknown_returns_none(self):
        assert map_enum_value("ownership_type", "xyzzy") is None

    def test_none_input(self):
        assert map_enum_value("ownership_type", None) is None

    def test_empty_string(self):
        assert map_enum_value("ownership_type", "") is None


class TestGeoRegionMapping:
    """Test geo_region enum fuzzy mapping."""

    def test_valid_value_passthrough(self):
        assert map_enum_value("geo_region", "dach") == "dach"

    def test_valid_uk_ireland(self):
        assert map_enum_value("geo_region", "uk_ireland") == "uk_ireland"

    def test_uk_ie_maps_to_uk_ireland(self):
        assert map_enum_value("geo_region", "uk_ie") == "uk_ireland"

    def test_uk_maps_to_uk_ireland(self):
        assert map_enum_value("geo_region", "uk") == "uk_ireland"

    def test_ireland_maps_to_uk_ireland(self):
        assert map_enum_value("geo_region", "ireland") == "uk_ireland"

    def test_north_america_maps_to_us(self):
        assert map_enum_value("geo_region", "north_america") == "us"

    def test_usa_maps_to_us(self):
        assert map_enum_value("geo_region", "usa") == "us"

    def test_united_states_maps_to_us(self):
        assert map_enum_value("geo_region", "united states") == "us"

    def test_germany_maps_to_dach(self):
        assert map_enum_value("geo_region", "germany") == "dach"

    def test_czech_maps_to_cee(self):
        assert map_enum_value("geo_region", "czech") == "cee"

    def test_france_maps_to_southern_europe(self):
        assert map_enum_value("geo_region", "france") == "southern_europe"

    def test_sweden_maps_to_nordics(self):
        assert map_enum_value("geo_region", "sweden") == "nordics"

    def test_netherlands_maps_to_benelux(self):
        assert map_enum_value("geo_region", "netherlands") == "benelux"

    def test_unknown_returns_none(self):
        assert map_enum_value("geo_region", "mars") is None


class TestIndustryMapping:
    """Test industry enum fuzzy mapping."""

    def test_valid_value_passthrough(self):
        assert map_enum_value("industry", "software_saas") == "software_saas"

    def test_arts_maps_to_creative_services(self):
        assert map_enum_value("industry", "arts") == "creative_services"

    def test_arts_entertainment_maps_to_creative_services(self):
        assert map_enum_value("industry", "arts & entertainment") == "creative_services"

    def test_events_maps_to_creative_services(self):
        assert map_enum_value("industry", "events") == "creative_services"

    def test_culture_maps_to_creative_services(self):
        assert map_enum_value("industry", "culture") == "creative_services"

    def test_performing_arts_maps_to_creative_services(self):
        assert map_enum_value("industry", "performing arts") == "creative_services"

    def test_music_maps_to_creative_services(self):
        assert map_enum_value("industry", "music") == "creative_services"

    def test_advertising_maps_to_creative_services(self):
        assert map_enum_value("industry", "advertising") == "creative_services"

    def test_digital_media_maps_to_creative_services(self):
        assert map_enum_value("industry", "digital media") == "creative_services"

    def test_unknown_returns_none(self):
        assert map_enum_value("industry", "xyzzy") is None

    def test_case_insensitive(self):
        assert map_enum_value("industry", "Healthcare") == "healthcare"


class TestBusinessTypeMapping:
    """Test business_type enum fuzzy mapping."""

    def test_valid_passthrough(self):
        assert map_enum_value("business_type", "saas") == "saas"

    def test_new_values_passthrough(self):
        assert map_enum_value("business_type", "product_company") == "product_company"
        assert map_enum_value("business_type", "service_company") == "service_company"
        assert map_enum_value("business_type", "hybrid") == "hybrid"

    def test_software_maps_to_saas(self):
        assert map_enum_value("business_type", "software") == "saas"

    def test_software_company_maps_to_product_company(self):
        assert map_enum_value("business_type", "software company") == "product_company"

    def test_consulting_maps_to_service_company(self):
        assert map_enum_value("business_type", "consulting") == "service_company"

    def test_service_provider_synonym_maps_to_service_company(self):
        assert map_enum_value("business_type", "service provider") == "service_company"

    def test_legacy_service_provider_passthrough(self):
        # Old data with exact "service_provider" still passes through as valid
        assert map_enum_value("business_type", "service_provider") == "service_company"

    def test_wholesale_maps_to_distributor(self):
        assert map_enum_value("business_type", "wholesale") == "distributor"

    def test_mixed_maps_to_hybrid(self):
        assert map_enum_value("business_type", "mixed") == "hybrid"


class TestCompanySizeMapping:
    """Test company_size enum fuzzy mapping."""

    def test_new_values_passthrough(self):
        assert map_enum_value("company_size", "small") == "small"
        assert map_enum_value("company_size", "medium") == "medium"
        assert map_enum_value("company_size", "micro") == "micro"
        assert map_enum_value("company_size", "mid_market") == "mid_market"
        assert map_enum_value("company_size", "enterprise") == "enterprise"

    def test_startup_maps_to_small(self):
        assert map_enum_value("company_size", "startup") == "small"

    def test_smb_maps_to_medium(self):
        assert map_enum_value("company_size", "smb") == "medium"

    def test_large_maps_to_enterprise(self):
        assert map_enum_value("company_size", "large") == "enterprise"

    def test_midsize_maps_to_medium(self):
        assert map_enum_value("company_size", "midsize") == "medium"

    def test_unknown_returns_none(self):
        assert map_enum_value("company_size", "xyzzy") is None


class TestIndustryCategoryMapping:
    """Test industry_category enum fuzzy mapping."""

    def test_valid_values_passthrough(self):
        assert map_enum_value("industry_category", "technology") == "technology"
        assert map_enum_value("industry_category", "services") == "services"
        assert map_enum_value("industry_category", "finance") == "finance"

    def test_tech_synonym(self):
        assert map_enum_value("industry_category", "tech") == "technology"

    def test_consulting_maps_to_services(self):
        assert map_enum_value("industry_category", "consulting") == "services"

    def test_healthcare_maps(self):
        assert map_enum_value("industry_category", "healthcare") == "healthcare_life_sci"

    def test_unknown_returns_none(self):
        assert map_enum_value("industry_category", "xyzzy") is None


class TestUnknownFieldName:
    """Test behavior with unknown enum field names."""

    def test_unknown_field_returns_none(self):
        assert map_enum_value("nonexistent_field", "value") is None


class TestEnumConfigsComplete:
    """Verify all enum configs have valid_values and synonyms."""

    def test_all_configs_have_valid_values(self):
        for field, config in ENUM_CONFIGS.items():
            assert "valid_values" in config, f"{field} missing valid_values"
            assert len(config["valid_values"]) > 0, f"{field} has empty valid_values"

    def test_all_synonyms_map_to_valid_values(self):
        for field, config in ENUM_CONFIGS.items():
            valid = config["valid_values"]
            for synonym, target in config.get("synonyms", {}).items():
                assert target in valid, (
                    f"{field}: synonym '{synonym}' maps to '{target}' "
                    f"which is not in valid_values"
                )
