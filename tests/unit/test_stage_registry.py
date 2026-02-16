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
        assert "qc" in codes
        assert "person" not in codes
        assert "generate" not in codes

    def test_contact_stages(self):
        from api.services.stage_registry import get_stages_for_entity_type

        contact_stages = get_stages_for_entity_type("contact")
        codes = {s["code"] for s in contact_stages}
        assert "person" in codes
        assert "generate" in codes
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

        stages = ["l1", "l2", "person", "generate"]
        result = topo_sort(stages)
        assert result.index("l1") < result.index("l2")
        assert result.index("l1") < result.index("person")
        assert result.index("person") < result.index("generate")

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

        for code in ["l1", "l2", "signals", "person", "generate", "qc"]:
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

    def test_l1_fields(self):
        from api.services.stage_registry import STAGE_FIELDS

        assert "Industry" in STAGE_FIELDS["l1"]
        assert "Summary" in STAGE_FIELDS["l1"]

    def test_registry_fields(self):
        from api.services.stage_registry import STAGE_FIELDS

        assert "Official Name" in STAGE_FIELDS["registry"]
        assert "Insolvency" in STAGE_FIELDS["registry"]
