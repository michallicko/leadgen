"""Tests for the enrichment DAG stage registry."""
import pytest


class TestGetStage:
    def test_existing_stage(self):
        from api.services.stage_registry import get_stage

        result = get_stage("l1")
        assert result is not None
        assert result["code"] == "l1"
        assert result["entity_type"] == "company"
        assert result["display_name"] == "L1 Company Profile"
        assert result["hard_deps"] == []

    def test_nonexistent_stage(self):
        from api.services.stage_registry import get_stage

        assert get_stage("nonexistent") is None

    def test_all_stages_have_required_keys(self):
        from api.services.stage_registry import get_all_stages

        required_keys = {
            "code", "entity_type", "hard_deps", "soft_deps",
            "execution_mode", "display_name", "cost_default_usd", "country_gate",
        }
        for stage in get_all_stages():
            missing = required_keys - set(stage.keys())
            assert not missing, f"Stage {stage['code']} missing keys: {missing}"


class TestGetStagesForEntityType:
    def test_company_stages(self):
        from api.services.stage_registry import get_stages_for_entity_type

        company_stages = get_stages_for_entity_type("company")
        codes = {s["code"] for s in company_stages}
        assert "l1" in codes
        assert "l2" in codes
        assert "registry" in codes
        assert "news" in codes
        assert "qc" in codes
        assert "person" not in codes

    def test_contact_stages(self):
        from api.services.stage_registry import get_stages_for_entity_type

        contact_stages = get_stages_for_entity_type("contact")
        codes = {s["code"] for s in contact_stages}
        assert "person" in codes
        assert "social" in codes
        assert "career" in codes
        assert "contact_details" in codes
        assert "generate" not in codes
        assert "l1" not in codes


class TestTopoSort:
    def test_single_stage(self):
        from api.services.stage_registry import topo_sort

        assert topo_sort(["l1"]) == ["l1"]

    def test_linear_chain(self):
        from api.services.stage_registry import topo_sort

        result = topo_sort(["l1", "l2"])
        assert result.index("l1") < result.index("l2")

    def test_full_pipeline(self):
        from api.services.stage_registry import topo_sort

        stages = ["l1", "l2", "person", "registry"]
        result = topo_sort(stages)
        assert result.index("l1") < result.index("l2")
        assert result.index("l1") < result.index("person")
        assert result.index("l1") < result.index("registry")

    def test_parallel_after_l1(self):
        """L2, signals, and registry are all after L1 but parallel to each other."""
        from api.services.stage_registry import topo_sort

        stages = ["l1", "l2", "signals", "registry"]
        result = topo_sort(stages)
        assert result[0] == "l1"
        # L2, signals, registry can be in any order as long as after L1
        assert set(result[1:]) == {"l2", "signals", "registry"}

    def test_soft_deps_on_by_default(self):
        """Person has soft dep on L2 — should come after L2 when enabled."""
        from api.services.stage_registry import topo_sort

        stages = ["l1", "l2", "person"]
        result = topo_sort(stages)
        assert result.index("l1") < result.index("l2")
        assert result.index("l2") < result.index("person")

    def test_soft_deps_off(self):
        """With soft deps off, person only needs l1 (hard dep)."""
        from api.services.stage_registry import topo_sort

        stages = ["l1", "l2", "person"]
        result = topo_sort(stages, soft_deps_enabled={"person": False})
        assert result.index("l1") < result.index("person")
        # l2 and person are independent — person doesn't need to wait for l2

    def test_qc_terminal_depends_on_all(self):
        """QC (terminal) should come after all other enabled stages."""
        from api.services.stage_registry import topo_sort

        stages = ["l1", "l2", "registry", "qc"]
        result = topo_sort(stages)
        assert result[-1] == "qc"

    def test_unknown_stage_raises(self):
        from api.services.stage_registry import topo_sort

        with pytest.raises(ValueError, match="Unknown stage"):
            topo_sort(["l1", "bogus"])

    def test_empty_list(self):
        from api.services.stage_registry import topo_sort

        assert topo_sort([]) == []

    def test_missing_dep_not_in_codes(self):
        """If a hard dep isn't in the stage list, it's ignored (not enforced)."""
        from api.services.stage_registry import topo_sort

        # l2 depends on l1, but l1 not in the list — should still work
        result = topo_sort(["l2"])
        assert result == ["l2"]


class TestResolveDeps:
    def test_no_deps(self):
        from api.services.stage_registry import resolve_deps

        assert resolve_deps("l1") == []

    def test_hard_deps_only(self):
        from api.services.stage_registry import resolve_deps

        deps = resolve_deps("l2")
        assert deps == ["l1"]

    def test_hard_plus_soft_deps_default(self):
        from api.services.stage_registry import resolve_deps

        deps = resolve_deps("person")
        assert "l1" in deps
        assert "l2" in deps
        assert "signals" in deps

    def test_soft_deps_disabled(self):
        from api.services.stage_registry import resolve_deps

        deps = resolve_deps("person", soft_deps_enabled={"person": False})
        assert deps == ["l1"]

    def test_unknown_stage(self):
        from api.services.stage_registry import resolve_deps

        assert resolve_deps("nonexistent") == []


class TestEstimateCost:
    def test_single_stage(self):
        from api.services.stage_registry import estimate_cost

        cost = estimate_cost(["l1"], 100)
        assert cost == 2.0  # 0.02 * 100

    def test_multiple_stages(self):
        from api.services.stage_registry import estimate_cost

        cost = estimate_cost(["l1", "l2"], 100)
        assert cost == 10.0  # (0.02 + 0.08) * 100

    def test_free_stages(self):
        from api.services.stage_registry import estimate_cost

        cost = estimate_cost(["registry"], 100)
        assert cost == 0.0


class TestCountryGate:
    def test_registry_has_country_gate(self):
        from api.services.stage_registry import get_stage

        stage = get_stage("registry")
        assert stage["country_gate"] is not None
        assert "countries" in stage["country_gate"]
        assert "tlds" in stage["country_gate"]
        # Unified gate covers all 4 countries
        countries = stage["country_gate"]["countries"]
        assert "CZ" in countries
        assert "NO" in countries
        assert "FI" in countries
        assert "FR" in countries
        tlds = stage["country_gate"]["tlds"]
        assert ".cz" in tlds
        assert ".no" in tlds
        assert ".fi" in tlds
        assert ".fr" in tlds

    def test_non_registry_stages_no_gate(self):
        from api.services.stage_registry import get_stage

        for code in ["l1", "l2", "signals", "news", "person", "social", "career", "contact_details", "qc"]:
            stage = get_stage(code)
            assert stage["country_gate"] is None, f"{code} should not have country_gate"


class TestStageFields:
    def test_stage_fields_has_entries(self):
        from api.services.stage_registry import STAGE_FIELDS

        assert len(STAGE_FIELDS) > 0

    def test_stage_fields_covers_registry_stages(self):
        from api.services.stage_registry import STAGE_FIELDS, STAGE_REGISTRY

        for code in STAGE_REGISTRY:
            assert code in STAGE_FIELDS, f"STAGE_FIELDS missing entry for {code}"

    def test_every_field_has_required_keys(self):
        from api.services.stage_registry import STAGE_FIELDS

        required = {"key", "label", "type", "table"}
        for stage, fields in STAGE_FIELDS.items():
            for field in fields:
                missing = required - set(field.keys())
                assert not missing, f"{stage}.{field.get('key', '?')} missing: {missing}"

    def test_field_types_are_valid(self):
        from api.services.stage_registry import STAGE_FIELDS, VALID_FIELD_TYPES

        for stage, fields in STAGE_FIELDS.items():
            for field in fields:
                assert field["type"] in VALID_FIELD_TYPES, (
                    f"{stage}.{field['key']} has invalid type '{field['type']}'"
                )

    def test_field_keys_are_snake_case(self):
        import re
        from api.services.stage_registry import STAGE_FIELDS

        pattern = re.compile(r"^[a-z][a-z0-9_]*$")
        for stage, fields in STAGE_FIELDS.items():
            for field in fields:
                assert pattern.match(field["key"]), (
                    f"{stage}.{field['key']} is not snake_case"
                )

    def test_field_counts(self):
        """Verify expected field counts per stage to catch accidental drops."""
        from api.services.stage_registry import STAGE_FIELDS

        expected_min = {
            "l1": 14,
            "l2": 21,
            "registry": 23,
            "signals": 5,
            "news": 5,
            "person": 17,
            "social": 5,
            "career": 4,
            "contact_details": 4,
            "qc": 2,
        }
        for stage, min_count in expected_min.items():
            actual = len(STAGE_FIELDS[stage])
            assert actual >= min_count, (
                f"{stage}: expected >= {min_count} fields, got {actual}"
            )


class TestGetStageLabels:
    def test_returns_list_of_strings(self):
        from api.services.stage_registry import get_stage_labels

        labels = get_stage_labels("l1")
        assert isinstance(labels, list)
        assert all(isinstance(lbl, str) for lbl in labels)

    def test_backward_compat_l1(self):
        from api.services.stage_registry import get_stage_labels

        labels = get_stage_labels("l1")
        assert "Industry" in labels
        assert "Summary" in labels
        assert "Triage Score" in labels

    def test_backward_compat_registry(self):
        from api.services.stage_registry import get_stage_labels

        labels = get_stage_labels("registry")
        assert "Official Name" in labels
        assert "Insolvency" in labels
        assert "Credibility Score" in labels

    def test_unknown_stage_returns_empty(self):
        from api.services.stage_registry import get_stage_labels

        assert get_stage_labels("nonexistent") == []


class TestGetStageFieldDefs:
    def test_returns_list_of_dicts(self):
        from api.services.stage_registry import get_stage_field_defs

        defs = get_stage_field_defs("l2")
        assert isinstance(defs, list)
        assert all(isinstance(d, dict) for d in defs)
        assert defs[0]["key"] == "company_intel"

    def test_unknown_stage_returns_empty(self):
        from api.services.stage_registry import get_stage_field_defs

        assert get_stage_field_defs("nonexistent") == []

    def test_person_spans_multiple_tables(self):
        from api.services.stage_registry import get_stage_field_defs

        tables = {f["table"] for f in get_stage_field_defs("person")}
        assert "contacts" in tables
        assert "contact_enrichment" in tables
