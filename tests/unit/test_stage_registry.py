"""Unit tests for stage registry boost configuration."""

import pytest

from api.services.stage_registry import (
    STAGE_REGISTRY,
    BOOST_MODELS,
    ANTHROPIC_BOOST,
    get_model_for_stage,
    get_stage,
    topo_sort,
)


class TestBoostModelsDefined:
    """Test that BOOST_MODELS is properly defined for all enrichment stages."""

    def test_boost_models_has_entries(self):
        assert len(BOOST_MODELS) > 0

    def test_l1_has_boost_config(self):
        assert "l1" in BOOST_MODELS
        cfg = BOOST_MODELS["l1"]
        assert "standard" in cfg
        assert "boost" in cfg
        assert "cost_boost" in cfg

    def test_l2_has_boost_config(self):
        assert "l2" in BOOST_MODELS
        assert BOOST_MODELS["l2"]["boost"] == "sonar-reasoning-pro"

    def test_person_has_boost_config(self):
        assert "person" in BOOST_MODELS

    def test_all_boost_entries_have_required_keys(self):
        for stage, cfg in BOOST_MODELS.items():
            assert "standard" in cfg, "{} missing 'standard'".format(stage)
            assert "boost" in cfg, "{} missing 'boost'".format(stage)
            assert "cost_boost" in cfg, "{} missing 'cost_boost'".format(stage)

    def test_boost_cost_higher_than_zero(self):
        for stage, cfg in BOOST_MODELS.items():
            assert cfg["cost_boost"] > 0, "{} boost cost should be > 0".format(stage)


class TestBoostCostOverride:
    """Test that boost costs override default stage costs."""

    def test_l1_boost_cost_higher_than_default(self):
        l1_stage = STAGE_REGISTRY["l1"]
        l1_boost = BOOST_MODELS["l1"]
        assert l1_boost["cost_boost"] > l1_stage["cost_default_usd"]

    def test_l2_boost_cost_higher_than_default(self):
        l2_stage = STAGE_REGISTRY["l2"]
        l2_boost = BOOST_MODELS["l2"]
        assert l2_boost["cost_boost"] > l2_stage["cost_default_usd"]


class TestGetModelForStage:
    """Test the get_model_for_stage() helper function."""

    def test_standard_model_for_l1(self):
        model = get_model_for_stage("l1", boost=False)
        assert model == BOOST_MODELS["l1"]["standard"]

    def test_boost_model_for_l1(self):
        model = get_model_for_stage("l1", boost=True)
        assert model == BOOST_MODELS["l1"]["boost"]

    def test_standard_model_for_l2(self):
        model = get_model_for_stage("l2", boost=False)
        assert model == BOOST_MODELS["l2"]["standard"]

    def test_boost_model_for_l2(self):
        model = get_model_for_stage("l2", boost=True)
        assert model == "sonar-reasoning-pro"

    def test_unknown_stage_returns_sonar_default(self):
        model = get_model_for_stage("nonexistent", boost=False)
        assert model == "sonar"

    def test_unknown_stage_boost_returns_sonar_pro(self):
        model = get_model_for_stage("nonexistent", boost=True)
        assert model == "sonar-pro"

    def test_provider_perplexity_default(self):
        model = get_model_for_stage("l1", boost=False, provider="perplexity")
        assert model == BOOST_MODELS["l1"]["standard"]

    def test_provider_anthropic_standard(self):
        model = get_model_for_stage("l2", boost=False, provider="anthropic")
        assert model == ANTHROPIC_BOOST["standard"]

    def test_provider_anthropic_boost(self):
        model = get_model_for_stage("l2", boost=True, provider="anthropic")
        assert model == ANTHROPIC_BOOST["boost"]


class TestAnthropicBoost:
    """Test ANTHROPIC_BOOST configuration."""

    def test_has_standard_and_boost(self):
        assert "standard" in ANTHROPIC_BOOST
        assert "boost" in ANTHROPIC_BOOST

    def test_standard_is_haiku(self):
        assert "haiku" in ANTHROPIC_BOOST["standard"]

    def test_boost_is_sonnet(self):
        assert "sonnet" in ANTHROPIC_BOOST["boost"]


class TestTriageInRegistry:
    """Test that triage stage is properly registered."""

    def test_triage_exists_in_registry(self):
        assert "triage" in STAGE_REGISTRY

    def test_triage_is_gate(self):
        assert STAGE_REGISTRY["triage"].get("is_gate") is True

    def test_triage_depends_on_l1(self):
        assert "l1" in STAGE_REGISTRY["triage"]["hard_deps"]

    def test_triage_is_company_type(self):
        assert STAGE_REGISTRY["triage"]["entity_type"] == "company"

    def test_triage_zero_cost(self):
        assert STAGE_REGISTRY["triage"]["cost_default_usd"] == 0.0

    def test_triage_in_topo_sort(self):
        """Triage should come after l1 in topological order."""
        order = topo_sort(["l1", "triage", "l2"])
        assert order.index("l1") < order.index("triage")
        assert order.index("triage") < order.index("l2")
