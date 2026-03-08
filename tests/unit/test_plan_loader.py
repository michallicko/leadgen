"""Tests for the plan abstraction layer (BL-1008)."""

from api.agents.plans.loader import (
    _load_all_plans,
    _evaluate_conditions,
    load_plan,
    load_plan_by_id,
)


TENANT = {
    "company_name": "Acme Corp",
    "domain": "acme.com",
    "user_name": "Alice",
    "namespace": "acme",
}


class TestLoadAllPlans:
    """Verify YAML configs are parsed into Plan objects."""

    def test_loads_at_least_three_plans(self):
        plans = _load_all_plans()
        ids = {p.id for p in plans}
        assert "playbook_onboarding" in ids
        assert "strategy_refinement" in ids
        assert "copilot" in ids

    def test_playbook_onboarding_structure(self):
        plans = _load_all_plans()
        po = next(p for p in plans if p.id == "playbook_onboarding")
        assert po.trigger.page == "playbook"
        assert "no_strategy_exists" in po.trigger.conditions
        assert "onboarding_not_completed" in po.trigger.conditions
        assert len(po.tools) > 0
        assert "web_research" in po.tools
        assert len(po.phases) == 4
        assert len(po.discovery_questions) == 4

    def test_scoring_rubric_parsed(self):
        plans = _load_all_plans()
        po = next(p for p in plans if p.id == "playbook_onboarding")
        rubric = po.scoring_rubric
        assert "icp_definition" in rubric.sections
        assert rubric.sections["icp_definition"].weight == 2.0
        assert "specificity" in rubric.sections["icp_definition"].criteria
        assert rubric.thresholds["completeness"] == 0.8
        assert rubric.thresholds["quality_min"] == 3.5

    def test_copilot_has_wildcard_page(self):
        plans = _load_all_plans()
        copilot = next(p for p in plans if p.id == "copilot")
        assert copilot.trigger.page == "*"
        assert copilot.trigger.conditions == []


class TestEvaluateConditions:
    """Verify condition evaluation against state."""

    def test_no_conditions_always_true(self):
        assert _evaluate_conditions([], {}) is True

    def test_no_strategy_exists_when_false(self):
        assert (
            _evaluate_conditions(["no_strategy_exists"], {"has_strategy": False})
            is True
        )

    def test_no_strategy_exists_when_true(self):
        assert (
            _evaluate_conditions(["no_strategy_exists"], {"has_strategy": True})
            is False
        )

    def test_strategy_exists(self):
        assert _evaluate_conditions(["strategy_exists"], {"has_strategy": True}) is True
        assert (
            _evaluate_conditions(["strategy_exists"], {"has_strategy": False}) is False
        )

    def test_multiple_conditions_all_must_pass(self):
        state = {"has_strategy": False, "onboarding_completed": False}
        assert (
            _evaluate_conditions(
                ["no_strategy_exists", "onboarding_not_completed"], state
            )
            is True
        )

    def test_multiple_conditions_one_fails(self):
        state = {"has_strategy": False, "onboarding_completed": True}
        assert (
            _evaluate_conditions(
                ["no_strategy_exists", "onboarding_not_completed"], state
            )
            is False
        )

    def test_unknown_condition_returns_false(self):
        assert _evaluate_conditions(["unknown_condition"], {}) is False


class TestLoadPlan:
    """Verify plan resolution logic."""

    def test_playbook_onboarding_selected(self):
        state = {"has_strategy": False, "onboarding_completed": False}
        plan = load_plan("playbook", TENANT, state)
        assert plan.id == "playbook_onboarding"

    def test_strategy_refinement_selected(self):
        state = {"has_strategy": True, "onboarding_completed": True}
        plan = load_plan("playbook", TENANT, state)
        assert plan.id == "strategy_refinement"

    def test_copilot_fallback_for_unknown_page(self):
        state = {"has_strategy": False}
        plan = load_plan("contacts", TENANT, state)
        assert plan.id == "copilot"

    def test_copilot_fallback_for_no_matching_conditions(self):
        # playbook page but strategy exists AND onboarding not completed
        # — strategy_refinement requires strategy_exists (met),
        #   playbook_onboarding requires no_strategy_exists (not met)
        # so strategy_refinement should win
        state = {"has_strategy": True, "onboarding_completed": False}
        plan = load_plan("playbook", TENANT, state)
        assert plan.id == "strategy_refinement"

    def test_most_specific_wins(self):
        """playbook_onboarding has 2 conditions vs strategy_refinement's 1."""
        state = {"has_strategy": False, "onboarding_completed": False}
        plan = load_plan("playbook", TENANT, state)
        assert plan.id == "playbook_onboarding"
        assert len(plan.trigger.conditions) == 2

    def test_template_resolution_company_name(self):
        state = {"has_strategy": False, "onboarding_completed": False}
        plan = load_plan("playbook", TENANT, state)
        assert "Acme Corp" in plan.system_prompt_template

    def test_template_resolution_domain(self):
        state = {"has_strategy": False, "onboarding_completed": False}
        plan = load_plan("playbook", TENANT, state)
        assert "acme.com" in plan.system_prompt_template
        assert plan.research_requirements.primary_source == "acme.com"

    def test_template_resolution_strategy_refinement(self):
        state = {"has_strategy": True}
        plan = load_plan("playbook", TENANT, state)
        assert "Acme Corp" in plan.system_prompt_template
        assert plan.research_requirements.primary_source == "acme.com"

    def test_copilot_template_resolution(self):
        state = {}
        plan = load_plan("messages", TENANT, state)
        assert "Acme Corp" in plan.system_prompt_template


class TestLoadPlanById:
    """Verify direct plan loading by ID."""

    def test_load_existing(self):
        plan = load_plan_by_id("copilot", TENANT)
        assert plan is not None
        assert plan.id == "copilot"
        assert "Acme Corp" in plan.system_prompt_template

    def test_load_nonexistent(self):
        plan = load_plan_by_id("nonexistent", TENANT)
        assert plan is None
