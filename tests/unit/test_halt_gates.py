"""Tests for halt gates module — gate evaluation, config, and event formatting."""

import json

from api.agents.halt_gates import (
    GateType,
    HaltFrequency,
    HaltGate,
    HaltGateConfig,
    HaltGateOption,
    HaltGateResponse,
    direction_gate,
    resource_gate,
    review_gate,
    scope_gate,
    should_halt,
)


class TestHaltGateConfig:
    """Test HaltGateConfig.from_preferences()."""

    def test_default_config(self):
        config = HaltGateConfig.from_preferences(None)
        assert config.frequency == HaltFrequency.ALWAYS
        assert config.disabled_types == []

    def test_empty_preferences(self):
        config = HaltGateConfig.from_preferences({})
        assert config.frequency == HaltFrequency.ALWAYS

    def test_custom_frequency(self):
        prefs = {"halt_gates": {"frequency": "major_only"}}
        config = HaltGateConfig.from_preferences(prefs)
        assert config.frequency == HaltFrequency.MAJOR_ONLY

    def test_autonomous_frequency(self):
        prefs = {"halt_gates": {"frequency": "autonomous"}}
        config = HaltGateConfig.from_preferences(prefs)
        assert config.frequency == HaltFrequency.AUTONOMOUS

    def test_invalid_frequency_defaults_to_always(self):
        prefs = {"halt_gates": {"frequency": "invalid_value"}}
        config = HaltGateConfig.from_preferences(prefs)
        assert config.frequency == HaltFrequency.ALWAYS

    def test_disabled_types(self):
        prefs = {"halt_gates": {"disabled_types": ["assumption", "review"]}}
        config = HaltGateConfig.from_preferences(prefs)
        assert GateType.ASSUMPTION in config.disabled_types
        assert GateType.REVIEW in config.disabled_types

    def test_invalid_disabled_types_ignored(self):
        prefs = {"halt_gates": {"disabled_types": ["invalid", "scope"]}}
        config = HaltGateConfig.from_preferences(prefs)
        assert len(config.disabled_types) == 1
        assert GateType.SCOPE in config.disabled_types


class TestShouldHalt:
    """Test should_halt() gate evaluation logic."""

    def _make_gate(self, gate_type: GateType) -> HaltGate:
        return HaltGate(
            gate_type=gate_type,
            question="Test question?",
            options=[HaltGateOption(label="Yes", value="yes")],
            context="Test context",
        )

    def test_always_halts_for_all_types(self):
        config = HaltGateConfig(frequency=HaltFrequency.ALWAYS)
        for gate_type in GateType:
            gate = self._make_gate(gate_type)
            assert should_halt(gate, config) is True

    def test_autonomous_never_halts(self):
        config = HaltGateConfig(frequency=HaltFrequency.AUTONOMOUS)
        for gate_type in GateType:
            gate = self._make_gate(gate_type)
            assert should_halt(gate, config) is False

    def test_major_only_halts_for_scope(self):
        config = HaltGateConfig(frequency=HaltFrequency.MAJOR_ONLY)
        gate = self._make_gate(GateType.SCOPE)
        assert should_halt(gate, config) is True

    def test_major_only_halts_for_direction(self):
        config = HaltGateConfig(frequency=HaltFrequency.MAJOR_ONLY)
        gate = self._make_gate(GateType.DIRECTION)
        assert should_halt(gate, config) is True

    def test_major_only_halts_for_resource(self):
        config = HaltGateConfig(frequency=HaltFrequency.MAJOR_ONLY)
        gate = self._make_gate(GateType.RESOURCE)
        assert should_halt(gate, config) is True

    def test_major_only_skips_assumption(self):
        config = HaltGateConfig(frequency=HaltFrequency.MAJOR_ONLY)
        gate = self._make_gate(GateType.ASSUMPTION)
        assert should_halt(gate, config) is False

    def test_major_only_skips_review(self):
        config = HaltGateConfig(frequency=HaltFrequency.MAJOR_ONLY)
        gate = self._make_gate(GateType.REVIEW)
        assert should_halt(gate, config) is False

    def test_disabled_type_skipped_in_always_mode(self):
        config = HaltGateConfig(
            frequency=HaltFrequency.ALWAYS,
            disabled_types=[GateType.SCOPE],
        )
        gate = self._make_gate(GateType.SCOPE)
        assert should_halt(gate, config) is False

    def test_non_disabled_type_still_halts(self):
        config = HaltGateConfig(
            frequency=HaltFrequency.ALWAYS,
            disabled_types=[GateType.SCOPE],
        )
        gate = self._make_gate(GateType.DIRECTION)
        assert should_halt(gate, config) is True


class TestHaltGateSerialization:
    """Test HaltGate.to_dict() serialization."""

    def test_basic_serialization(self):
        gate = HaltGate(
            gate_type=GateType.SCOPE,
            question="Which product?",
            options=[
                HaltGateOption(
                    label="Product A", value="a", description="The main product"
                ),
                HaltGateOption(label="Product B", value="b"),
            ],
            context="Company has multiple products",
            gate_id="test-gate-id",
        )

        result = gate.to_dict()

        assert result["gateId"] == "test-gate-id"
        assert result["gateType"] == "scope"
        assert result["question"] == "Which product?"
        assert result["context"] == "Company has multiple products"
        assert len(result["options"]) == 2
        assert result["options"][0]["label"] == "Product A"
        assert result["options"][0]["value"] == "a"
        assert result["options"][0]["description"] == "The main product"
        assert result["options"][1]["description"] == ""

    def test_resource_gate_metadata(self):
        gate = resource_gate(
            question="Proceed with enrichment?",
            estimated_tokens=5000,
            estimated_cost_usd="0.05",
            context="About to enrich 50 contacts",
        )

        result = gate.to_dict()

        assert result["gateType"] == "resource"
        assert result["metadata"]["estimatedTokens"] == 5000
        assert result["metadata"]["estimatedCostUsd"] == "0.05"

    def test_serialization_is_json_safe(self):
        gate = scope_gate(
            question="Focus area?",
            options=[
                {"label": "Option A", "value": "a"},
                {"label": "Option B", "value": "b"},
            ],
            context="Multiple scopes found",
        )

        # Should serialize to valid JSON without errors
        result = json.dumps(gate.to_dict())
        assert isinstance(result, str)


class TestGateFactories:
    """Test convenience factory functions."""

    def test_scope_gate(self):
        gate = scope_gate(
            question="Which product line?",
            options=[{"label": "All", "value": "all"}],
            context="Found 3 products",
        )
        assert gate.gate_type == GateType.SCOPE
        assert gate.question == "Which product line?"
        assert len(gate.options) == 1

    def test_direction_gate(self):
        gate = direction_gate(
            question="Broad or narrow?",
            options=[
                {"label": "Broad", "value": "broad"},
                {"label": "Narrow", "value": "narrow"},
            ],
            context="Two ICP segments found",
        )
        assert gate.gate_type == GateType.DIRECTION
        assert len(gate.options) == 2

    def test_review_gate_default_options(self):
        gate = review_gate(
            question="Strategy draft ready?",
            context="All sections complete",
        )
        assert gate.gate_type == GateType.REVIEW
        assert len(gate.options) == 3
        values = [o.value for o in gate.options]
        assert "approve" in values
        assert "adjust" in values
        assert "review_full" in values

    def test_review_gate_custom_options(self):
        gate = review_gate(
            question="How does this look?",
            context="Draft complete",
            options=[{"label": "Great", "value": "approve"}],
        )
        assert len(gate.options) == 1

    def test_resource_gate(self):
        gate = resource_gate(
            question="Enrich contacts?",
            estimated_tokens=10000,
            estimated_cost_usd="0.10",
            context="Will call external APIs",
        )
        assert gate.gate_type == GateType.RESOURCE
        assert gate.metadata["estimatedTokens"] == 10000
        values = [o.value for o in gate.options]
        assert "approve" in values
        assert "skip" in values
        assert "cancel" in values

    def test_gate_id_auto_generated(self):
        gate1 = scope_gate("Q1", [{"label": "A", "value": "a"}], "ctx")
        gate2 = scope_gate("Q2", [{"label": "B", "value": "b"}], "ctx")
        assert gate1.gate_id != gate2.gate_id
        assert len(gate1.gate_id) > 0


class TestHaltGateResponse:
    """Test HaltGateResponse dataclass."""

    def test_basic_response(self):
        resp = HaltGateResponse(gate_id="g1", choice="approve")
        assert resp.gate_id == "g1"
        assert resp.choice == "approve"
        assert resp.custom_input is None

    def test_response_with_custom_input(self):
        resp = HaltGateResponse(gate_id="g1", choice="custom", custom_input="My idea")
        assert resp.custom_input == "My idea"
