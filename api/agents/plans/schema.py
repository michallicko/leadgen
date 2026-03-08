"""Plan schema — configuration objects consumed by the deterministic planner."""

from dataclasses import dataclass, field


@dataclass
class PlanTrigger:
    """Determines when a plan activates."""

    page: str  # page_context value (playbook, contacts, etc.) or "*" for wildcard
    conditions: list[str] = field(default_factory=list)


@dataclass
class ResearchRequirements:
    """How the agent should approach external research."""

    primary_source: str = ""  # Jinja2 template e.g. "{{domain}}"
    cross_check_policy: str = "website_authoritative_with_consensus_override"


@dataclass
class ScoringCriterion:
    """A single scoring section with weight and criteria labels."""

    weight: float = 1.0
    criteria: list[str] = field(default_factory=list)


@dataclass
class ScoringRubric:
    """Quality scoring configuration for strategy sections."""

    sections: dict[str, ScoringCriterion] = field(default_factory=dict)
    thresholds: dict[str, float] = field(default_factory=dict)


@dataclass
class DiscoveryQuestion:
    """A discovery question template for the agent to ask when conditions are met."""

    category: str
    when: str  # condition description
    examples: list[str] = field(default_factory=list)


@dataclass
class Plan:
    """
    A plan is a YAML configuration object that tells the deterministic planner
    how the agent should behave in a given page context.

    Plans are NOT subgraphs — they're config consumed by the planner (BL-1009).
    """

    id: str
    name: str
    trigger: PlanTrigger
    persona: str = ""
    system_prompt_template: str = ""
    tools: list[str] = field(default_factory=list)
    research_requirements: ResearchRequirements = field(
        default_factory=ResearchRequirements
    )
    scoring_rubric: ScoringRubric = field(default_factory=ScoringRubric)
    discovery_questions: list[DiscoveryQuestion] = field(default_factory=list)
    phases: list[str] = field(default_factory=list)
