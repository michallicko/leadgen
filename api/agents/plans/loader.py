"""Plan loader — resolves the active plan from YAML configs based on context."""

from __future__ import annotations

from pathlib import Path

import yaml
from jinja2 import Template

from api.agents.plans.schema import (
    DiscoveryQuestion,
    Plan,
    PlanTrigger,
    ResearchRequirements,
    ScoringCriterion,
    ScoringRubric,
)

CONFIGS_DIR = Path(__file__).parent / "configs"

# Maps condition strings to evaluator functions against state dict.
CONDITION_EVALUATORS: dict[str, callable] = {
    "no_strategy_exists": lambda state: not state.get("has_strategy", False),
    "onboarding_not_completed": lambda state: (
        not state.get("onboarding_completed", False)
    ),
    "strategy_exists": lambda state: bool(state.get("has_strategy", False)),
}


def _parse_trigger(raw: dict) -> PlanTrigger:
    return PlanTrigger(
        page=raw.get("page", "*"),
        conditions=raw.get("conditions", []),
    )


def _parse_scoring_rubric(raw: dict | None) -> ScoringRubric:
    if not raw:
        return ScoringRubric()
    sections = {}
    for name, section_data in (raw.get("sections") or {}).items():
        if isinstance(section_data, dict):
            sections[name] = ScoringCriterion(
                weight=section_data.get("weight", 1.0),
                criteria=section_data.get("criteria", []),
            )
    thresholds = raw.get("thresholds") or {}
    return ScoringRubric(sections=sections, thresholds=thresholds)


def _parse_discovery_questions(raw: list | None) -> list[DiscoveryQuestion]:
    if not raw:
        return []
    return [
        DiscoveryQuestion(
            category=q.get("category", ""),
            when=q.get("when", ""),
            examples=q.get("examples", []),
        )
        for q in raw
    ]


def _parse_plan(data: dict) -> Plan:
    """Parse a raw YAML dict into a Plan dataclass."""
    rr = data.get("research_requirements") or {}
    return Plan(
        id=data["id"],
        name=data["name"],
        trigger=_parse_trigger(data.get("trigger", {})),
        persona=data.get("persona", ""),
        system_prompt_template=data.get("system_prompt_template", ""),
        tools=data.get("tools", []),
        research_requirements=ResearchRequirements(
            primary_source=rr.get("primary_source", ""),
            cross_check_policy=rr.get(
                "cross_check_policy",
                "website_authoritative_with_consensus_override",
            ),
        ),
        scoring_rubric=_parse_scoring_rubric(data.get("scoring_rubric")),
        discovery_questions=_parse_discovery_questions(data.get("discovery_questions")),
        phases=data.get("phases", []),
    )


def _load_all_plans() -> list[Plan]:
    """Load and parse all YAML plan configs from the configs directory."""
    plans: list[Plan] = []
    if not CONFIGS_DIR.is_dir():
        return plans
    for filepath in sorted(CONFIGS_DIR.glob("*.yaml")):
        with open(filepath) as f:
            data = yaml.safe_load(f)
        if data:
            plans.append(_parse_plan(data))
    return plans


def _evaluate_conditions(conditions: list[str], state: dict) -> bool:
    """Return True if ALL conditions are satisfied against state."""
    for condition in conditions:
        evaluator = CONDITION_EVALUATORS.get(condition)
        if evaluator is None:
            # Unknown condition — treat as not met
            return False
        if not evaluator(state):
            return False
    return True


def _resolve_templates(plan: Plan, tenant_context: dict) -> Plan:
    """Resolve Jinja2 template variables in plan fields using tenant_context."""
    if plan.system_prompt_template:
        plan.system_prompt_template = Template(plan.system_prompt_template).render(
            **tenant_context
        )

    if plan.research_requirements.primary_source:
        plan.research_requirements.primary_source = Template(
            plan.research_requirements.primary_source
        ).render(**tenant_context)

    return plan


def load_plan(page_context: str, tenant_context: dict, state: dict) -> Plan:
    """
    Resolve which plan to activate based on page_context + conditions.

    Args:
        page_context: Current page (playbook, contacts, messages, etc.)
        tenant_context: Dict with company_name, domain, user_name, namespace
        state: Current state dict (has_strategy, onboarding_completed, etc.)

    Returns:
        Resolved Plan with Jinja2 templates filled in.
    """
    all_plans = _load_all_plans()

    # Filter candidates: page must match exactly or be wildcard
    candidates: list[Plan] = []
    for plan in all_plans:
        page_matches = plan.trigger.page == page_context or plan.trigger.page == "*"
        if not page_matches:
            continue
        if not _evaluate_conditions(plan.trigger.conditions, state):
            continue
        candidates.append(plan)

    if not candidates:
        # Fall back to copilot if nothing matches at all
        # (copilot has page="*" and no conditions, so it should always match,
        # but handle the edge case where configs are missing)
        return _resolve_templates(
            Plan(
                id="copilot",
                name="Copilot",
                trigger=PlanTrigger(page="*"),
                persona="Helpful assistant.",
                system_prompt_template="You are a helpful assistant for "
                "{{company_name}}'s leadgen platform.",
                tools=["navigate_suggestion", "data_lookup"],
                phases=["respond"],
            ),
            tenant_context,
        )

    # Prefer the most specific plan: more conditions = higher priority.
    # Among plans with equal conditions, prefer exact page match over wildcard.
    def _specificity(p: Plan) -> tuple[int, int]:
        page_exact = 1 if p.trigger.page != "*" else 0
        return (len(p.trigger.conditions), page_exact)

    candidates.sort(key=_specificity, reverse=True)
    best = candidates[0]

    return _resolve_templates(best, tenant_context)


def load_plan_by_id(plan_id: str, tenant_context: dict) -> Plan | None:
    """Load a specific plan by its ID, useful for testing and direct access."""
    for plan in _load_all_plans():
        if plan.id == plan_id:
            return _resolve_templates(plan, tenant_context)
    return None
