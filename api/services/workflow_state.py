"""Workflow state computation — determines the user's position in the GTM flow.

The state is COMPUTED from actual data (strategy docs, contacts, enrichments,
messages, campaigns), not stored. Called by the onboarding-status endpoint.

Phase order (each phase implies all previous are completed):
  no_strategy -> strategy_draft -> strategy_ready -> contacts_imported ->
  enrichment_running -> enrichment_done -> qualified_reviewed ->
  messages_generated -> messages_approved -> campaign_created -> campaign_launched
"""

import json
import logging

from ..models import (
    Campaign,
    PipelineRun,
    StrategyDocument,
    db,
)


def _parse_jsonb(val):
    """Parse a JSONB value that might be a string (SQLite compat)."""
    if val is None:
        return {}
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


logger = logging.getLogger(__name__)

# Ordered list of phases — index determines precedence
WORKFLOW_PHASES = [
    "no_strategy",
    "strategy_draft",
    "strategy_ready",
    "contacts_imported",
    "enrichment_running",
    "enrichment_done",
    "qualified_reviewed",
    "messages_generated",
    "messages_approved",
    "campaign_created",
    "campaign_launched",
]

# Human-readable labels for each phase
PHASE_LABELS = {
    "no_strategy": "No Strategy",
    "strategy_draft": "Strategy Draft",
    "strategy_ready": "Strategy Ready",
    "contacts_imported": "Contacts Imported",
    "enrichment_running": "Enrichment Running",
    "enrichment_done": "Enrichment Complete",
    "qualified_reviewed": "Contacts Qualified",
    "messages_generated": "Messages Generated",
    "messages_approved": "Messages Approved",
    "campaign_created": "Campaign Created",
    "campaign_launched": "Campaign Launched",
}

# What action to suggest for each phase
PHASE_NEXT_ACTIONS = {
    "no_strategy": {
        "action": "create_strategy",
        "label": "Create your GTM strategy",
        "route": "/playbook/strategy",
    },
    "strategy_draft": {
        "action": "extract_icp",
        "label": "Extract ICP from your strategy",
        "route": "/playbook/strategy",
    },
    "strategy_ready": {
        "action": "import_contacts",
        "label": "Import your first contacts",
        "route": "/import",
    },
    "contacts_imported": {
        "action": "run_enrichment",
        "label": "Enrich your contacts",
        "route": "/enrich",
    },
    "enrichment_running": {
        "action": "wait_enrichment",
        "label": "Enrichment is running...",
        "route": "/enrich",
    },
    "enrichment_done": {
        "action": "select_contacts",
        "label": "Review and select qualified contacts",
        "route": "/playbook/contacts",
    },
    "qualified_reviewed": {
        "action": "generate_messages",
        "label": "Generate outreach messages",
        "route": "/playbook/messages",
    },
    "messages_generated": {
        "action": "review_messages",
        "label": "Review and approve messages",
        "route": "/messages",
    },
    "messages_approved": {
        "action": "create_campaign",
        "label": "Create your outreach campaign",
        "route": "/playbook/campaign",
    },
    "campaign_created": {
        "action": "launch_campaign",
        "label": "Launch your campaign",
        "route": "/campaigns",
    },
    "campaign_launched": {
        "action": "monitor_results",
        "label": "Monitor campaign results",
        "route": "/campaigns",
    },
}


def compute_workflow_state(tenant_id):
    """Compute the current workflow phase from actual data.

    Returns a dict with:
      - current_phase: str
      - completed_phases: list[str]
      - next_action: dict with action, label, route
      - context: dict with counts and metadata per phase
    """
    tid = str(tenant_id)
    context = {}

    # --- Strategy Document ---
    doc = StrategyDocument.query.filter_by(tenant_id=tid).first()
    has_content = bool(doc and doc.content and doc.content.strip())
    extracted = _parse_jsonb(doc.extracted_data) if doc else {}
    has_icp = bool(extracted.get("icp"))

    context["strategy"] = {
        "has_document": doc is not None,
        "has_content": has_content,
        "has_icp": has_icp,
        "phase": doc.phase if doc else None,
    }

    if not has_content:
        return _build_result("no_strategy", context)

    if not has_icp:
        return _build_result("strategy_draft", context)

    # --- Contacts ---
    contact_count = (
        db.session.execute(
            db.text("SELECT COUNT(*) FROM contacts WHERE tenant_id = :t"),
            {"t": tid},
        ).scalar()
        or 0
    )
    context["contacts"] = {"total": contact_count}

    if contact_count == 0:
        return _build_result("strategy_ready", context)

    # --- Enrichment ---
    running_pipeline = PipelineRun.query.filter_by(
        tenant_id=tid, status="running"
    ).first()
    enriched_contacts = (
        db.session.execute(
            db.text(
                "SELECT COUNT(*) FROM contacts WHERE tenant_id = :t AND processed_enrich = true"
            ),
            {"t": tid},
        ).scalar()
        or 0
    )
    completed_runs = (
        PipelineRun.query.filter_by(tenant_id=tid, status="completed")
        .order_by(PipelineRun.completed_at.desc())
        .first()
    )

    context["enrichment"] = {
        "is_running": running_pipeline is not None,
        "enriched_contacts": enriched_contacts,
        "has_completed_run": completed_runs is not None,
        "last_run_id": str(completed_runs.id) if completed_runs else None,
    }

    if running_pipeline and enriched_contacts == 0:
        return _build_result("enrichment_running", context)

    if contact_count > 0 and enriched_contacts == 0 and not running_pipeline:
        return _build_result("contacts_imported", context)

    # --- Qualified / Selected ---
    selections = _parse_jsonb(doc.playbook_selections) if doc else {}
    selected_ids = selections.get("contacts", {}).get("selected_ids", [])

    context["qualification"] = {
        "enriched_contacts": enriched_contacts,
        "selected_contacts": len(selected_ids),
    }

    if not selected_ids:
        # Enrichment done (or running with some enriched) but no selection yet
        if running_pipeline:
            return _build_result("enrichment_running", context)
        return _build_result("enrichment_done", context)

    # --- Messages ---
    message_counts = {}
    if selected_ids:
        # Use IN(...) with inline IDs — works with both PG and SQLite
        safe_ids = [sid for sid in selected_ids[:500] if isinstance(sid, str)]
        if safe_ids:
            placeholders = ", ".join(f"'{sid}'" for sid in safe_ids)
            msg_rows = db.session.execute(
                db.text(
                    f"SELECT m.status, COUNT(*) FROM messages m"
                    f" WHERE m.tenant_id = :t"
                    f" AND m.contact_id IN ({placeholders})"
                    f" GROUP BY m.status"
                ),
                {"t": tid},
            ).fetchall()
            for row in msg_rows:
                if row[0]:
                    message_counts[row[0]] = row[1]

    total_messages = sum(message_counts.values())
    approved_messages = message_counts.get("approved", 0)

    context["messages"] = {
        "total": total_messages,
        "by_status": message_counts,
        "approved": approved_messages,
    }

    if total_messages == 0:
        return _build_result("qualified_reviewed", context)

    if approved_messages == 0:
        return _build_result("messages_generated", context)

    # --- Campaign ---
    campaign = (
        Campaign.query.filter_by(tenant_id=tid)
        .order_by(Campaign.created_at.desc())
        .first()
    )

    context["campaign"] = {
        "exists": campaign is not None,
        "status": campaign.status if campaign else None,
        "name": campaign.name if campaign else None,
    }

    if not campaign:
        return _build_result("messages_approved", context)

    if campaign.status == "draft":
        return _build_result("campaign_created", context)

    return _build_result("campaign_launched", context)


def _build_result(current_phase, context):
    """Build the standard workflow state response dict."""
    phase_idx = WORKFLOW_PHASES.index(current_phase)
    completed = WORKFLOW_PHASES[:phase_idx]
    next_action = PHASE_NEXT_ACTIONS.get(current_phase, {})

    return {
        "current_phase": current_phase,
        "current_phase_label": PHASE_LABELS.get(current_phase, current_phase),
        "completed_phases": completed,
        "total_phases": len(WORKFLOW_PHASES),
        "progress_pct": round(phase_idx / (len(WORKFLOW_PHASES) - 1) * 100)
        if len(WORKFLOW_PHASES) > 1
        else 0,
        "next_action": next_action,
        "context": context,
    }
