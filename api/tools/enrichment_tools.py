"""Enrichment tool wrappers for the AI agent.

Provides tool definitions that bridge the agent tool registry to the
underlying enricher services. Each tool handles Flask app context and
returns structured results for agent consumption.

Tools:
- enrich_company_news: Run news & PR enrichment for a company
- enrich_company_signals: Run strategic signals enrichment for a company
- enrich_contact_social: Run social presence enrichment for a contact
- enrich_contact_career: Run career history enrichment for a contact
- enrich_contact_details: Run contact details enrichment for a contact
- check_enrichment_status: Check pipeline run progress
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import text

from ..models import db
from ..services.tool_registry import ToolContext, ToolDefinition

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


def _enrich_company_news(args: dict, ctx: ToolContext) -> dict:
    """Enrich a company with news & PR data."""
    company_id = args.get("company_id", "")
    if not company_id:
        return {"error": "company_id is required"}

    boost = args.get("boost", False)

    try:
        from ..services.news_enricher import enrich_news

        result = enrich_news(
            entity_id=company_id,
            tenant_id=ctx.tenant_id,
            boost=boost,
            user_id=ctx.user_id,
        )
        return result
    except Exception as exc:
        logger.exception("enrich_company_news failed: %s", exc)
        return {"error": str(exc), "enrichment_cost_credits": 0}


def _enrich_company_signals(args: dict, ctx: ToolContext) -> dict:
    """Enrich a company with strategic signals data."""
    company_id = args.get("company_id", "")
    if not company_id:
        return {"error": "company_id is required"}

    boost = args.get("boost", False)

    try:
        from ..services.signals_enricher import enrich_signals

        result = enrich_signals(
            entity_id=company_id,
            tenant_id=ctx.tenant_id,
            boost=boost,
            user_id=ctx.user_id,
        )
        return result
    except Exception as exc:
        logger.exception("enrich_company_signals failed: %s", exc)
        return {"error": str(exc), "enrichment_cost_credits": 0}


def _enrich_contact_social(args: dict, ctx: ToolContext) -> dict:
    """Enrich a contact with social & online presence data."""
    contact_id = args.get("contact_id", "")
    if not contact_id:
        return {"error": "contact_id is required"}

    boost = args.get("boost", False)

    try:
        from ..services.social_enricher import enrich_social

        result = enrich_social(
            entity_id=contact_id,
            tenant_id=ctx.tenant_id,
            boost=boost,
            user_id=ctx.user_id,
        )
        return result
    except Exception as exc:
        logger.exception("enrich_contact_social failed: %s", exc)
        return {"error": str(exc), "enrichment_cost_credits": 0}


def _enrich_contact_career(args: dict, ctx: ToolContext) -> dict:
    """Enrich a contact with career history data."""
    contact_id = args.get("contact_id", "")
    if not contact_id:
        return {"error": "contact_id is required"}

    boost = args.get("boost", False)

    try:
        from ..services.career_enricher import enrich_career

        result = enrich_career(
            entity_id=contact_id,
            tenant_id=ctx.tenant_id,
            boost=boost,
            user_id=ctx.user_id,
        )
        return result
    except Exception as exc:
        logger.exception("enrich_contact_career failed: %s", exc)
        return {"error": str(exc), "enrichment_cost_credits": 0}


def _enrich_contact_details_handler(args: dict, ctx: ToolContext) -> dict:
    """Enrich a contact with contact details (email, phone, etc.)."""
    contact_id = args.get("contact_id", "")
    if not contact_id:
        return {"error": "contact_id is required"}

    boost = args.get("boost", False)

    try:
        from ..services.contact_details_enricher import enrich_contact_details

        result = enrich_contact_details(
            entity_id=contact_id,
            tenant_id=ctx.tenant_id,
            boost=boost,
            user_id=ctx.user_id,
        )
        return result
    except Exception as exc:
        logger.exception("enrich_contact_details failed: %s", exc)
        return {"error": str(exc), "enrichment_cost_credits": 0}


def _check_enrichment_status(args: dict, ctx: ToolContext) -> dict:
    """Check the status of a pipeline run and its stages."""
    pipeline_run_id = args.get("pipeline_run_id", "")
    if not pipeline_run_id:
        return {"error": "pipeline_run_id is required"}

    # Look up the pipeline run
    pr_row = db.session.execute(
        text("""
            SELECT id, tenant_id, tag_id, status, stages,
                   started_at, completed_at
            FROM pipeline_runs
            WHERE id = :pid AND tenant_id = :tid
        """),
        {"pid": str(pipeline_run_id), "tid": str(ctx.tenant_id)},
    ).fetchone()

    if not pr_row:
        return {"error": "Pipeline run not found", "pipeline_run_id": pipeline_run_id}

    # Parse stages JSON to get stage_run_ids
    stages_json = pr_row[4] or "{}"
    try:
        stage_run_ids = (
            json.loads(stages_json) if isinstance(stages_json, str) else stages_json
        )
    except (json.JSONDecodeError, TypeError):
        stage_run_ids = {}

    # Get tag name
    tag_row = db.session.execute(
        text("SELECT name FROM tags WHERE id = :tid AND tenant_id = :tenant_id"),
        {"tid": str(pr_row[2]), "tenant_id": str(ctx.tenant_id)},
    ).fetchone()
    tag_name = tag_row[0] if tag_row else "unknown"

    # Fetch stage run details
    stage_details = []
    if stage_run_ids:
        sr_ids = list(stage_run_ids.values())
        placeholders = ", ".join(f":id{i}" for i in range(len(sr_ids)))
        params = {f"id{i}": str(sid) for i, sid in enumerate(sr_ids)}

        params["tenant_id"] = str(ctx.tenant_id)
        sr_rows = db.session.execute(
            text(f"""
                SELECT id, stage, status, total, done, failed, cost_usd,
                       started_at, completed_at, error
                FROM stage_runs
                WHERE id IN ({placeholders}) AND tenant_id = :tenant_id
                ORDER BY started_at
            """),
            params,
        ).fetchall()

        for sr in sr_rows:
            stage_details.append(
                {
                    "stage_run_id": str(sr[0]),
                    "stage": sr[1],
                    "status": sr[2],
                    "total": sr[3] or 0,
                    "done": sr[4] or 0,
                    "failed": sr[5] or 0,
                    "cost_credits": int(float(sr[6]) * 1000) if sr[6] else 0,
                    "error": sr[9],
                }
            )

    total_done = sum(s["done"] for s in stage_details)
    total_items = sum(s["total"] for s in stage_details)
    total_cost_credits = sum(s["cost_credits"] for s in stage_details)

    return {
        "pipeline_run_id": str(pr_row[0]),
        "tag_name": tag_name,
        "status": pr_row[3],
        "started_at": str(pr_row[5]) if pr_row[5] else None,
        "completed_at": str(pr_row[6]) if pr_row[6] else None,
        "stages": stage_details,
        "progress": {
            "total_items": total_items,
            "completed": total_done,
            "percentage": round(total_done / total_items * 100, 1)
            if total_items > 0
            else 0,
        },
        "total_cost_credits": total_cost_credits,
        "summary": "Pipeline '{}': {} — {}/{} items done ({:.1f}%). Cost: {} credits".format(
            tag_name,
            pr_row[3],
            total_done,
            total_items,
            round(total_done / total_items * 100, 1) if total_items > 0 else 0,
            total_cost_credits,
        ),
    }


# ---------------------------------------------------------------------------
# Tool definitions for registry
# ---------------------------------------------------------------------------

ENRICHMENT_AGENT_TOOLS = [
    ToolDefinition(
        name="enrich_company_news",
        description=(
            "Run news & PR enrichment for a single company. Researches recent "
            "news coverage, press releases, and media sentiment. Requires a "
            "company_id. Returns enrichment cost and any errors."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "company_id": {
                    "type": "string",
                    "description": "UUID of the company to enrich with news data.",
                },
                "boost": {
                    "type": "boolean",
                    "description": "Use higher-quality model (costs more). Default false.",
                },
            },
            "required": ["company_id"],
        },
        handler=_enrich_company_news,
    ),
    ToolDefinition(
        name="enrich_company_signals",
        description=(
            "Run strategic signals enrichment for a single company. Researches "
            "buying signals, hiring patterns, AI adoption, growth indicators. "
            "Requires a company_id. Returns enrichment cost and any errors."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "company_id": {
                    "type": "string",
                    "description": "UUID of the company to enrich with signals data.",
                },
                "boost": {
                    "type": "boolean",
                    "description": "Use higher-quality model (costs more). Default false.",
                },
            },
            "required": ["company_id"],
        },
        handler=_enrich_company_signals,
    ),
    ToolDefinition(
        name="enrich_contact_social",
        description=(
            "Run social & online presence enrichment for a single contact. "
            "Researches LinkedIn, Twitter, GitHub, speaking engagements, and "
            "publications. Requires a contact_id."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "contact_id": {
                    "type": "string",
                    "description": "UUID of the contact to enrich with social data.",
                },
                "boost": {
                    "type": "boolean",
                    "description": "Use higher-quality model (costs more). Default false.",
                },
            },
            "required": ["contact_id"],
        },
        handler=_enrich_contact_social,
    ),
    ToolDefinition(
        name="enrich_contact_career",
        description=(
            "Run career history enrichment for a single contact. Researches "
            "previous companies, role progression, industry experience. "
            "Requires a contact_id."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "contact_id": {
                    "type": "string",
                    "description": "UUID of the contact to enrich with career data.",
                },
                "boost": {
                    "type": "boolean",
                    "description": "Use higher-quality model (costs more). Default false.",
                },
            },
            "required": ["contact_id"],
        },
        handler=_enrich_contact_career,
    ),
    ToolDefinition(
        name="enrich_contact_details",
        description=(
            "Run contact details enrichment for a single contact. Researches "
            "email address, phone number, LinkedIn URL, and profile photo. "
            "Only fills in blank fields. Requires a contact_id."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "contact_id": {
                    "type": "string",
                    "description": "UUID of the contact to enrich with details.",
                },
                "boost": {
                    "type": "boolean",
                    "description": "Use higher-quality model (costs more). Default false.",
                },
            },
            "required": ["contact_id"],
        },
        handler=_enrich_contact_details_handler,
    ),
    ToolDefinition(
        name="check_enrichment_status",
        description=(
            "Check the status and progress of an enrichment pipeline run. "
            "Returns per-stage breakdown with items processed, failures, costs, "
            "and overall progress percentage. Use after starting enrichment."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "pipeline_run_id": {
                    "type": "string",
                    "description": "UUID of the pipeline run to check.",
                },
            },
            "required": ["pipeline_run_id"],
        },
        handler=_check_enrichment_status,
    ),
]
