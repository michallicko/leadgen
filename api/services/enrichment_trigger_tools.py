"""Enrichment trigger tools for AI chat.

Provides two tools:
- estimate_enrichment_cost: Computes cost estimate for enriching contacts
  in a tag, showing per-stage breakdown and budget status.
- start_enrichment: Triggers the enrichment DAG pipeline after user approval.

These tools enable the AI to proactively suggest enrichment with cost
transparency, and only start it after the user explicitly approves.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import text

from ..models import PipelineRun, StageRun, db
from .budget import get_budget_status
from .pipeline_engine import (
    _LEGACY_STAGE_ALIASES,
    count_eligible,
    start_pipeline_threads,
)
from .tool_registry import ToolContext, ToolDefinition

logger = logging.getLogger(__name__)

# Default enrichment stages for the auto-start flow
DEFAULT_STAGES = ["l1", "l2", "person"]

# Static cost defaults (USD per item) — same as enrich_routes
STATIC_COST_DEFAULTS = {
    "l1": 0.02,
    "l2": 0.08,
    "signals": 0.05,
    "registry": 0.00,
    "news": 0.04,
    "person": 0.04,
    "social": 0.03,
    "career": 0.03,
    "contact_details": 0.01,
    "qc": 0.00,
}

# Credits per USD (1 credit = $0.001)
CREDITS_PER_USD = 1000


def _resolve_tag(tenant_id, tag_name):
    """Look up tag by name, return tag_id or None."""
    row = db.session.execute(
        text("SELECT id FROM tags WHERE tenant_id = :t AND name = :n"),
        {"t": str(tenant_id), "n": tag_name},
    ).fetchone()
    return row[0] if row else None


def _get_tenant_tags(tenant_id):
    """Get all tags for a tenant with company counts."""
    rows = db.session.execute(
        text("""
            SELECT t.id, t.name,
                   (SELECT COUNT(*) FROM companies c WHERE c.tag_id = t.id) as company_count
            FROM tags t
            WHERE t.tenant_id = :t
            ORDER BY company_count DESC
        """),
        {"t": str(tenant_id)},
    ).fetchall()
    return [
        {"id": row[0], "name": row[1], "company_count": row[2]}
        for row in rows
    ]


def _get_cost_per_item(tenant_id, stage):
    """Get average cost per item from historical stage_runs."""
    row = db.session.execute(
        text("""
            SELECT AVG(cost_usd / NULLIF(done, 0)), COUNT(*)
            FROM stage_runs
            WHERE tenant_id = :t AND stage = :s
              AND status = 'completed' AND done > 0 AND cost_usd > 0
        """),
        {"t": str(tenant_id), "s": stage},
    ).fetchone()
    if row and row[0] is not None and row[1] >= 5:
        return round(float(row[0]), 4)
    return STATIC_COST_DEFAULTS.get(stage, 0.05)


# ---------------------------------------------------------------------------
# Tool: estimate_enrichment_cost
# ---------------------------------------------------------------------------


def estimate_enrichment_cost(args: dict, ctx: ToolContext) -> dict:
    """Estimate enrichment cost for a tag's companies.

    Returns per-stage breakdown with eligible counts, costs in both USD
    and credits, plus budget status.
    """
    tag_name = args.get("tag_name", "")
    stages = args.get("stages") or DEFAULT_STAGES

    # Resolve legacy stage names
    stages = [_LEGACY_STAGE_ALIASES.get(s, s) for s in stages]

    # If no tag specified, list available tags
    if not tag_name:
        tags = _get_tenant_tags(ctx.tenant_id)
        if not tags:
            return {
                "error": "No tags found. Import contacts first.",
                "available_tags": [],
            }
        return {
            "error": "Please specify a tag_name.",
            "available_tags": [
                {"name": t["name"], "companies": t["company_count"]}
                for t in tags
            ],
        }

    tag_id = _resolve_tag(ctx.tenant_id, tag_name)
    if not tag_id:
        tags = _get_tenant_tags(ctx.tenant_id)
        return {
            "error": "Tag '{}' not found.".format(tag_name),
            "available_tags": [
                {"name": t["name"], "companies": t["company_count"]}
                for t in tags
            ],
        }

    # Check if a pipeline is already running
    existing = db.session.execute(
        text("""
            SELECT id, status FROM pipeline_runs
            WHERE tenant_id = :t AND tag_id = :b
              AND status IN ('running', 'stopping')
            LIMIT 1
        """),
        {"t": str(ctx.tenant_id), "b": str(tag_id)},
    ).fetchone()
    if existing:
        return {
            "error": "A pipeline is already running for this tag.",
            "pipeline_run_id": str(existing[0]),
            "status": existing[1],
        }

    # Compute per-stage estimates
    stage_estimates = []
    total_cost_usd = 0.0
    total_eligible = 0

    for stage in stages:
        eligible = count_eligible(ctx.tenant_id, tag_id, stage, None, [])
        cost_per_item = _get_cost_per_item(ctx.tenant_id, stage)
        stage_cost = round(eligible * cost_per_item, 2)
        total_cost_usd += stage_cost
        total_eligible += eligible

        stage_estimates.append({
            "stage": stage,
            "eligible_count": eligible,
            "cost_per_item_usd": cost_per_item,
            "cost_per_item_credits": int(cost_per_item * CREDITS_PER_USD),
            "total_cost_usd": stage_cost,
            "total_cost_credits": int(stage_cost * CREDITS_PER_USD),
        })

    total_cost_credits = int(total_cost_usd * CREDITS_PER_USD)

    # Get budget status
    budget = get_budget_status(ctx.tenant_id)
    budget_info = None
    can_afford = True
    if budget:
        remaining = budget.get("remaining_credits", 0)
        can_afford = remaining >= total_cost_credits
        budget_info = {
            "total_budget": budget.get("total_budget", 0),
            "used_credits": budget.get("used_credits", 0),
            "remaining_credits": remaining,
            "can_afford": can_afford,
            "shortfall_credits": max(0, total_cost_credits - remaining),
        }

    return {
        "tag_name": tag_name,
        "stages": stage_estimates,
        "total_eligible": total_eligible,
        "total_cost_usd": round(total_cost_usd, 2),
        "total_cost_credits": total_cost_credits,
        "budget": budget_info,
        "can_start": can_afford and total_eligible > 0,
        "summary": (
            "{} companies eligible across {} stages. "
            "Estimated cost: {} credits (~${:.2f} USD).{}".format(
                total_eligible,
                len(stages),
                total_cost_credits,
                total_cost_usd,
                " Budget sufficient." if can_afford
                else " WARNING: Insufficient budget.",
            )
        ),
    }


# ---------------------------------------------------------------------------
# Tool: start_enrichment
# ---------------------------------------------------------------------------


def start_enrichment(args: dict, ctx: ToolContext) -> dict:
    """Start the enrichment pipeline for a tag after user approval.

    This should ONLY be called after showing the cost estimate to the user
    and receiving their explicit approval.
    """
    tag_name = args.get("tag_name", "")
    stages = args.get("stages") or DEFAULT_STAGES
    confirmed = args.get("confirmed", False)

    if not tag_name:
        return {"error": "tag_name is required."}

    if not confirmed:
        return {
            "error": "User confirmation required. Show the cost estimate "
            "first and ask the user to approve before starting enrichment.",
            "action_needed": "confirm",
        }

    # Resolve legacy stage names
    stages = [_LEGACY_STAGE_ALIASES.get(s, s) for s in stages]

    tag_id = _resolve_tag(ctx.tenant_id, tag_name)
    if not tag_id:
        return {"error": "Tag '{}' not found.".format(tag_name)}

    # Check no pipeline already running
    existing = db.session.execute(
        text("""
            SELECT id FROM pipeline_runs
            WHERE tenant_id = :t AND tag_id = :b
              AND status IN ('running', 'stopping')
            LIMIT 1
        """),
        {"t": str(ctx.tenant_id), "b": str(tag_id)},
    ).fetchone()
    if existing:
        return {
            "error": "A pipeline is already running for this tag.",
            "pipeline_run_id": str(existing[0]),
        }

    # Create pipeline_run
    pipeline_run = PipelineRun(
        tenant_id=str(ctx.tenant_id),
        tag_id=str(tag_id),
        owner_id=None,
        status="running",
        config="{}",
    )
    db.session.add(pipeline_run)
    db.session.flush()
    pipeline_run_id = str(pipeline_run.id)

    # Create stage_run records
    stage_run_ids = {}
    for stage in stages:
        stage_config = {"pipeline_run_id": pipeline_run_id}
        sr = StageRun(
            tenant_id=str(ctx.tenant_id),
            tag_id=str(tag_id),
            owner_id=None,
            stage=stage,
            status="pending",
            total=0,
            config=json.dumps(stage_config),
        )
        db.session.add(sr)
        db.session.flush()
        stage_run_ids[stage] = str(sr.id)

    pipeline_run.stages = json.dumps(stage_run_ids)
    db.session.commit()

    # Need to import current_app for thread spawning
    from flask import current_app
    app = current_app._get_current_object()

    # Spawn threads
    start_pipeline_threads(
        app,
        pipeline_run_id,
        stages,
        ctx.tenant_id,
        tag_id,
        owner_id=None,
        tier_filter=[],
        stage_run_ids=stage_run_ids,
    )

    return {
        "pipeline_run_id": pipeline_run_id,
        "stage_run_ids": stage_run_ids,
        "stages": stages,
        "summary": (
            "Enrichment pipeline started for tag '{}'. "
            "Running stages: {}. Track progress on the Enrich page.".format(
                tag_name, ", ".join(stages)
            )
        ),
    }


# ---------------------------------------------------------------------------
# Tool definitions for registry
# ---------------------------------------------------------------------------

ENRICHMENT_TRIGGER_TOOLS = [
    ToolDefinition(
        name="estimate_enrichment_cost",
        description=(
            "Estimate the cost of enriching contacts in a tag before starting. "
            "Returns per-stage breakdown (L1, L2, person) with eligible company "
            "counts, cost in credits and USD, and budget status. Use this BEFORE "
            "starting enrichment to show the user what it will cost. "
            "If no tag_name is provided, lists available tags."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "tag_name": {
                    "type": "string",
                    "description": (
                        "Name of the tag/batch to estimate enrichment for. "
                        "If omitted, returns a list of available tags."
                    ),
                },
                "stages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Enrichment stages to include. Default: ['l1', 'l2', 'person']. "
                        "Available: l1, l2, signals, registry, news, person, social, "
                        "career, contact_details, qc."
                    ),
                },
            },
            "required": [],
        },
        handler=estimate_enrichment_cost,
    ),
    ToolDefinition(
        name="start_enrichment",
        description=(
            "Start the enrichment pipeline for a tag. IMPORTANT: You MUST first "
            "call estimate_enrichment_cost and show the user the cost breakdown. "
            "Only call start_enrichment AFTER the user explicitly approves. "
            "Never auto-start enrichment without user confirmation."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "tag_name": {
                    "type": "string",
                    "description": "Name of the tag/batch to enrich.",
                },
                "stages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Enrichment stages to run. Default: ['l1', 'l2', 'person']."
                    ),
                },
                "confirmed": {
                    "type": "boolean",
                    "description": (
                        "Must be true to start. Set to true ONLY after the user "
                        "has seen the cost estimate and explicitly approved."
                    ),
                },
            },
            "required": ["tag_name", "confirmed"],
        },
        handler=start_enrichment,
    ),
]
