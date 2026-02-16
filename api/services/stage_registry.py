"""Stage registry: configurable DAG of enrichment stages.

Defines each stage's dependencies, entity type, execution mode, and
country gates. Provides utility functions for topological sorting and
stage lookup used by the DAG executor and eligibility builder.
"""

from collections import deque
from typing import Dict, List, Optional

STAGE_REGISTRY = {
    "l1": {
        "entity_type": "company",
        "hard_deps": [],
        "soft_deps": [],
        "execution_mode": "native",
        "display_name": "L1 Company Profile",
        "cost_default_usd": 0.02,
        "country_gate": None,
    },
    "l2": {
        "entity_type": "company",
        "hard_deps": ["l1"],
        "soft_deps": [],
        "execution_mode": "webhook",
        "display_name": "L2 Deep Research",
        "cost_default_usd": 0.08,
        "country_gate": None,
    },
    "signals": {
        "entity_type": "company",
        "hard_deps": ["l1"],
        "soft_deps": [],
        "execution_mode": "native",
        "display_name": "Strategic Signals",
        "cost_default_usd": 0.05,
        "country_gate": None,
    },
    "registry": {
        "entity_type": "company",
        "hard_deps": ["l1"],
        "soft_deps": [],
        "execution_mode": "native",
        "display_name": "Legal & Registry",
        "cost_default_usd": 0.00,
        "country_gate": {
            "countries": ["CZ", "Czech Republic", "Czechia",
                          "NO", "Norway", "Norge",
                          "FI", "Finland", "Suomi",
                          "FR", "France"],
            "tlds": [".cz", ".no", ".fi", ".fr"],
        },
    },
    "news": {
        "entity_type": "company",
        "hard_deps": ["l1"],
        "soft_deps": [],
        "execution_mode": "native",
        "display_name": "News & PR",
        "cost_default_usd": 0.04,
        "country_gate": None,
    },
    "person": {
        "entity_type": "contact",
        "hard_deps": ["l1"],
        "soft_deps": ["l2", "signals"],
        "execution_mode": "webhook",
        "display_name": "Role & Employment",
        "cost_default_usd": 0.04,
        "country_gate": None,
    },
    "social": {
        "entity_type": "contact",
        "hard_deps": ["l1"],
        "soft_deps": ["l2", "signals"],
        "execution_mode": "native",
        "display_name": "Social & Online",
        "cost_default_usd": 0.03,
        "country_gate": None,
    },
    "career": {
        "entity_type": "contact",
        "hard_deps": ["l1"],
        "soft_deps": ["l2"],
        "execution_mode": "native",
        "display_name": "Career History",
        "cost_default_usd": 0.03,
        "country_gate": None,
    },
    "contact_details": {
        "entity_type": "contact",
        "hard_deps": ["l1"],
        "soft_deps": [],
        "execution_mode": "native",
        "display_name": "Contact Details",
        "cost_default_usd": 0.01,
        "country_gate": None,
    },
    "qc": {
        "entity_type": "company",
        "hard_deps": [],
        "soft_deps": [],
        "execution_mode": "native",
        "display_name": "Quality Check",
        "cost_default_usd": 0.00,
        "country_gate": None,
        "is_terminal": True,
    },
}

STAGE_FIELDS = {
    "l1": ["Industry", "Business Model", "Revenue", "Employees", "Summary", "Triage Score"],
    "l2": ["Company Intel", "News", "AI Opportunities", "Tech Stack", "Pain Hypothesis"],
    "registry": ["Official Name", "Legal Form", "Registration Status", "Credibility Score", "Insolvency"],
    "signals": ["Funding", "M&A Activity", "Hiring Patterns", "Growth Indicators"],
    "news": ["Media Mentions", "Press Releases", "Sentiment", "Thought Leadership"],
    "person": ["Current Title", "Reporting Structure", "Tenure", "Employment Status"],
    "social": ["LinkedIn Profile", "Twitter/X", "Speaking Engagements", "Publications"],
    "career": ["Previous Roles", "Career Trajectory", "Industry Experience"],
    "contact_details": ["Email Status", "Phone", "Alternative Contacts"],
    "qc": ["Quality Flags", "Data Completeness"],
}


def get_stage(code: str) -> Optional[dict]:
    """Look up a stage by its code. Returns None if not found."""
    entry = STAGE_REGISTRY.get(code)
    if entry is None:
        return None
    return {"code": code, **entry}


def get_all_stages() -> List[dict]:
    """Return all stages with their codes."""
    return [{"code": k, **v} for k, v in STAGE_REGISTRY.items()]


def get_stages_for_entity_type(entity_type: str) -> List[dict]:
    """Return stages that operate on a given entity type ('company' or 'contact')."""
    return [
        {"code": k, **v}
        for k, v in STAGE_REGISTRY.items()
        if v["entity_type"] == entity_type
    ]


def topo_sort(stage_codes: List[str], soft_deps_enabled: Optional[Dict[str, bool]] = None) -> List[str]:
    """Topological sort of stage codes respecting hard + activated soft dependencies.

    Args:
        stage_codes: list of stage codes to sort (subset of STAGE_REGISTRY keys)
        soft_deps_enabled: dict of stage_code -> bool for soft deps. If None, all soft deps ON.

    Returns:
        Sorted list of stage codes (dependencies first).

    Raises:
        ValueError: if a cycle is detected or unknown stages are referenced.
    """
    if soft_deps_enabled is None:
        soft_deps_enabled = {}

    codes_set = set(stage_codes)

    # Build adjacency: dep -> [dependents]
    in_degree = {code: 0 for code in codes_set}
    graph = {code: [] for code in codes_set}

    for code in codes_set:
        entry = STAGE_REGISTRY.get(code)
        if entry is None:
            raise ValueError(f"Unknown stage: {code}")

        # Hard deps
        for dep in entry["hard_deps"]:
            if dep in codes_set:
                graph[dep].append(code)
                in_degree[code] += 1

        # Soft deps (only if enabled)
        for dep in entry.get("soft_deps", []):
            enabled = soft_deps_enabled.get(code, True)  # default ON
            if enabled and dep in codes_set:
                graph[dep].append(code)
                in_degree[code] += 1

        # Terminal stages (QC): depend on all other enabled stages
        if entry.get("is_terminal"):
            for other in codes_set:
                if other != code and other not in entry["hard_deps"]:
                    # Don't double-count if already a hard dep
                    graph[other].append(code)
                    in_degree[code] += 1

    # Kahn's algorithm
    queue = deque(code for code, deg in in_degree.items() if deg == 0)
    result = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(codes_set):
        raise ValueError("Cycle detected in stage dependency graph")

    return result


def resolve_deps(stage_code: str, soft_deps_enabled: Optional[Dict[str, bool]] = None) -> List[str]:
    """Return the effective dependency list for a stage (hard + activated soft).

    Args:
        stage_code: the stage to resolve dependencies for
        soft_deps_enabled: dict of stage_code -> bool. If None, all soft deps ON.

    Returns:
        List of stage codes this stage depends on.
    """
    if soft_deps_enabled is None:
        soft_deps_enabled = {}

    entry = STAGE_REGISTRY.get(stage_code)
    if entry is None:
        return []

    deps = list(entry["hard_deps"])

    enabled = soft_deps_enabled.get(stage_code, True)
    if enabled:
        deps.extend(entry.get("soft_deps", []))

    return deps


def estimate_cost(stage_codes: List[str], entity_count: int) -> float:
    """Estimate total cost for running stages on N entities."""
    total = 0.0
    for code in stage_codes:
        entry = STAGE_REGISTRY.get(code)
        if entry:
            total += entry["cost_default_usd"] * entity_count
    return round(total, 4)
