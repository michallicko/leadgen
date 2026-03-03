import json
import re
import secrets

from flask import Blueprint, g, jsonify, request

from ..auth import hash_password, require_auth, require_role, resolve_tenant
from ..models import (
    Campaign,
    Company,
    CompanyEnrichmentL1,
    Contact,
    Message,
    PipelineRun,
    StageRun,
    StrategyDocument,
    Tenant,
    User,
    UserTenantRole,
    db,
)
from ..services.workflow_state import compute_workflow_state

tenants_bp = Blueprint("tenants", __name__, url_prefix="/api/tenants")

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*$")


def _parse_settings(tenant):
    """Parse tenant settings, handling SQLite text or PG JSONB."""
    settings = tenant.settings
    if isinstance(settings, str):
        settings = json.loads(settings) if settings else {}
    return settings or {}


def _has_tenant_access(user, tenant_id):
    """Check if user is super_admin or has a role on the given tenant."""
    if user.is_super_admin:
        return True
    return any(r.tenant_id == tenant_id for r in user.roles)


def _is_tenant_admin(user, tenant_id):
    """Check if user is super_admin or admin on the given tenant."""
    if user.is_super_admin:
        return True
    return any(r.tenant_id == tenant_id and r.role == "admin" for r in user.roles)


@tenants_bp.route("", methods=["GET"])
@require_auth
def list_tenants():
    user = g.current_user

    if user.is_super_admin:
        tenants = Tenant.query.order_by(Tenant.created_at.desc()).all()
    else:
        tenant_ids = [r.tenant_id for r in user.roles]
        tenants = (
            Tenant.query.filter(Tenant.id.in_(tenant_ids))
            .order_by(Tenant.created_at.desc())
            .all()
        )

    return jsonify([t.to_dict() for t in tenants])


@tenants_bp.route("", methods=["POST"])
@require_role("admin")
def create_tenant():
    user = g.current_user
    if not user.is_super_admin:
        return jsonify({"error": "Only super admins can create namespaces"}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body required"}), 400

    name = (data.get("name") or "").strip()
    slug = (data.get("slug") or "").strip().lower()
    domain = (data.get("domain") or "").strip() or None
    admin_email = (data.get("admin_email") or "").strip().lower() or None

    if not name or not slug:
        return jsonify({"error": "name and slug required"}), 400

    if len(slug) < 2 or not SLUG_RE.match(slug):
        return jsonify(
            {"error": "Slug must be 2+ chars, lowercase alphanumeric and hyphens only"}
        ), 400

    if Tenant.query.filter_by(slug=slug).first():
        return jsonify({"error": "Slug already taken"}), 409

    tenant = Tenant(
        name=name, slug=slug, domain=domain, settings=data.get("settings", {})
    )
    db.session.add(tenant)
    db.session.flush()

    result = tenant.to_dict()
    temp_password = None

    if admin_email:
        existing_user = User.query.filter_by(email=admin_email).first()
        if existing_user:
            utr = UserTenantRole(
                user_id=existing_user.id,
                tenant_id=tenant.id,
                role="admin",
                granted_by=user.id,
            )
            db.session.add(utr)
        else:
            temp_password = secrets.token_urlsafe(12)
            new_user = User(
                email=admin_email,
                password_hash=hash_password(temp_password),
                display_name=admin_email.split("@")[0],
            )
            db.session.add(new_user)
            db.session.flush()
            utr = UserTenantRole(
                user_id=new_user.id,
                tenant_id=tenant.id,
                role="admin",
                granted_by=user.id,
            )
            db.session.add(utr)

    db.session.commit()

    if temp_password:
        result["temp_password"] = temp_password

    return jsonify(result), 201


@tenants_bp.route("/<tenant_id>", methods=["GET"])
@require_auth
def get_tenant(tenant_id):
    tenant = db.session.get(Tenant, tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404

    if not _has_tenant_access(g.current_user, tenant_id):
        return jsonify({"error": "Insufficient permissions"}), 403

    return jsonify(tenant.to_dict())


@tenants_bp.route("/<tenant_id>", methods=["PUT"])
@require_role("admin")
def update_tenant(tenant_id):
    if not g.current_user.is_super_admin:
        return jsonify({"error": "Only super admins can update namespaces"}), 403

    tenant = db.session.get(Tenant, tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body required"}), 400

    if "name" in data:
        tenant.name = data["name"]
    if "domain" in data:
        tenant.domain = data["domain"] or None
    if "settings" in data:
        tenant.settings = data["settings"]
    if "is_active" in data:
        tenant.is_active = bool(data["is_active"])

    db.session.commit()
    return jsonify(tenant.to_dict())


@tenants_bp.route("/<tenant_id>", methods=["DELETE"])
@require_role("admin")
def deactivate_tenant(tenant_id):
    if not g.current_user.is_super_admin:
        return jsonify({"error": "Only super admins can deactivate namespaces"}), 403

    tenant = db.session.get(Tenant, tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404

    tenant.is_active = False
    db.session.commit()
    return jsonify({"ok": True, "message": "Namespace deactivated"})


@tenants_bp.route("/<tenant_id>/settings", methods=["PATCH"])
@require_role("admin")
def patch_tenant_settings(tenant_id):
    """Merge-patch tenant settings (e.g. language, enrichment_language, onboarding)."""
    from ..services.language import VALID_LANGUAGE_CODES

    if not _is_tenant_admin(g.current_user, tenant_id):
        return jsonify({"error": "Insufficient permissions"}), 403

    tenant = db.session.get(Tenant, tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body required"}), 400

    # Validate language fields
    for key in ("language", "enrichment_language"):
        if key in data:
            val = data[key]
            if val is not None and val not in VALID_LANGUAGE_CODES:
                return jsonify({"error": f"Invalid {key}: {val}"}), 400

    # Allowed settings keys for merge-patch
    ALLOWED_KEYS = (
        "language",
        "enrichment_language",
        "onboarding_path",
        "checklist_dismissed",
    )

    # Merge-patch: update existing settings dict
    current = _parse_settings(tenant)
    for key in ALLOWED_KEYS:
        if key in data:
            if data[key] is None:
                current.pop(key, None)
            else:
                current[key] = data[key]

    tenant.settings = current
    db.session.commit()
    return jsonify(tenant.to_dict())


@tenants_bp.route("/<tenant_id>/users", methods=["GET"])
@require_auth
def list_tenant_users(tenant_id):
    tenant = db.session.get(Tenant, tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404

    if not _is_tenant_admin(g.current_user, tenant_id):
        return jsonify({"error": "Insufficient permissions"}), 403

    roles = (
        UserTenantRole.query.filter_by(tenant_id=tenant_id)
        .join(User, UserTenantRole.user_id == User.id)
        .order_by(User.display_name)
        .all()
    )

    result = []
    for r in roles:
        u = r.user
        result.append(
            {
                "id": str(u.id),
                "email": u.email,
                "display_name": u.display_name,
                "is_active": u.is_active,
                "role": r.role,
                "granted_at": r.granted_at.isoformat() if r.granted_at else None,
            }
        )

    return jsonify(result)


@tenants_bp.route("/onboarding-status", methods=["GET"])
@require_auth
def get_onboarding_status():
    """Return data counts and onboarding settings for the current namespace.

    Used by the frontend to decide whether to show the entry signpost,
    context-aware empty states, and the progress checklist.
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    tenant = db.session.get(Tenant, tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404

    # Count entities
    contact_count = Contact.query.filter_by(tenant_id=tenant_id).count()
    campaign_count = Campaign.query.filter_by(tenant_id=tenant_id).count()

    # Check if a strategy document exists with content
    strategy_doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    has_strategy = bool(
        strategy_doc and strategy_doc.content and strategy_doc.content.strip()
    )

    settings = _parse_settings(tenant)

    # Compute workflow state from actual data (BL-144)
    workflow = compute_workflow_state(tenant_id)

    return jsonify(
        {
            "contact_count": contact_count,
            "campaign_count": campaign_count,
            "has_strategy": has_strategy,
            "onboarding_path": settings.get("onboarding_path"),
            "checklist_dismissed": settings.get("checklist_dismissed", False),
            # Workflow state (BL-144)
            "workflow_phase": workflow["current_phase"],
            "workflow_phase_label": workflow["current_phase_label"],
            "completed_phases": workflow["completed_phases"],
            "progress_pct": workflow["progress_pct"],
            "next_action": workflow["next_action"],
            "workflow_context": workflow["context"],
        }
    )


VALID_ONBOARDING_PATHS = {"strategy", "import", "templates"}


@tenants_bp.route("/onboarding-settings", methods=["PATCH"])
@require_auth
def patch_onboarding_settings():
    """Update onboarding-specific settings for the current namespace.

    Any authenticated user with namespace access can update these.
    Only allows onboarding_path and checklist_dismissed keys.
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    if not _has_tenant_access(g.current_user, tenant_id):
        return jsonify({"error": "Insufficient permissions"}), 403

    tenant = db.session.get(Tenant, tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body required"}), 400

    current = _parse_settings(tenant)

    if "onboarding_path" in data:
        val = data["onboarding_path"]
        if val is not None and val not in VALID_ONBOARDING_PATHS:
            return jsonify({"error": f"Invalid onboarding_path: {val}"}), 400
        if val is None:
            current.pop("onboarding_path", None)
        else:
            current["onboarding_path"] = val

    if "checklist_dismissed" in data:
        val = data["checklist_dismissed"]
        if not isinstance(val, bool):
            return jsonify({"error": "checklist_dismissed must be a boolean"}), 400
        current["checklist_dismissed"] = val

    tenant.settings = current
    db.session.commit()
    return jsonify(
        {
            "onboarding_path": current.get("onboarding_path"),
            "checklist_dismissed": current.get("checklist_dismissed", False),
        }
    )


@tenants_bp.route("/workflow-suggestions", methods=["GET"])
@require_auth
def get_workflow_suggestions():
    """Return proactive next-step suggestions based on namespace workflow state.

    Inspects what the user has done (strategy, contacts, enrichment, messages,
    campaigns) and suggests the most logical next action. Also detects recent
    events (enrichment completion, message generation) and returns event-driven
    nudges with higher priority. BL-135 + BL-169.

    Returns:
        suggestions: list of suggestion objects with icon, summary, action label,
            navigation target, nudge_type, and optional action_type for auto-nav.
        nudge_count: number of event-driven nudges (for notification badge).
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    # Gather namespace state
    strategy_doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    has_strategy = bool(
        strategy_doc and strategy_doc.content and strategy_doc.content.strip()
    )
    has_extracted = bool(
        strategy_doc
        and strategy_doc.extracted_data
        and isinstance(strategy_doc.extracted_data, dict)
        and any(strategy_doc.extracted_data.values())
    )
    current_phase = strategy_doc.phase if strategy_doc else "strategy"

    contact_count = Contact.query.filter_by(tenant_id=tenant_id).count()
    company_count = Company.query.filter_by(tenant_id=tenant_id).count()

    # Count enriched companies (have L1 data)
    enriched_count = (
        db.session.query(CompanyEnrichmentL1.company_id)
        .join(Company, Company.id == CompanyEnrichmentL1.company_id)
        .filter(Company.tenant_id == tenant_id)
        .count()
    )

    message_count = Message.query.filter_by(tenant_id=tenant_id).count()
    campaign_count = Campaign.query.filter_by(tenant_id=tenant_id).count()

    # Active campaigns (status = generating or review or active)
    active_campaigns = Campaign.query.filter(
        Campaign.tenant_id == tenant_id,
        Campaign.status.in_(["generating", "review", "active"]),
    ).count()

    # Event detection for nudges (BL-169)
    event_context = _detect_workflow_events(tenant_id)

    suggestions = _build_workflow_suggestions(
        tenant_id=tenant_id,
        has_strategy=has_strategy,
        has_extracted=has_extracted,
        current_phase=current_phase,
        contact_count=contact_count,
        company_count=company_count,
        enriched_count=enriched_count,
        message_count=message_count,
        campaign_count=campaign_count,
        active_campaigns=active_campaigns,
        event_context=event_context,
    )

    # Count event-driven nudges for notification badge
    nudge_count = sum(1 for s in suggestions if s.get("nudge_type") == "event")

    return jsonify({"suggestions": suggestions, "nudge_count": nudge_count})


def _detect_workflow_events(tenant_id):
    """Detect recent workflow events for event-driven nudges (BL-169).

    Returns a dict with event flags and context data for nudge generation.
    """
    from datetime import datetime, timedelta, timezone

    # Look back 24 hours for recent events
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    events = {
        "enrichment_just_completed": False,
        "enrichment_running": False,
        "messages_just_generated": False,
        "triage_completed": False,
        "triage_passed": 0,
        "triage_disqualified": 0,
        "l2_completed_count": 0,
        "person_completed_count": 0,
        "recent_pipeline": None,
    }

    # Check for recently completed pipeline runs
    recent_pipeline = (
        PipelineRun.query.filter(
            PipelineRun.tenant_id == tenant_id,
            PipelineRun.status == "completed",
            PipelineRun.completed_at >= cutoff,
        )
        .order_by(PipelineRun.completed_at.desc())
        .first()
    )

    if recent_pipeline:
        events["enrichment_just_completed"] = True
        events["recent_pipeline"] = {
            "l1_done": recent_pipeline.l1_done or 0,
            "l2_done": recent_pipeline.l2_done or 0,
            "person_done": recent_pipeline.person_done or 0,
            "total_companies": recent_pipeline.total_companies or 0,
            "completed_at": (
                recent_pipeline.completed_at.isoformat()
                if recent_pipeline.completed_at
                else None
            ),
        }

    # Check for running pipeline
    running_pipeline = PipelineRun.query.filter_by(
        tenant_id=tenant_id, status="running"
    ).first()
    if running_pipeline:
        events["enrichment_running"] = True

    # Check for recently completed stage runs (triage, L2, person)
    recent_stages = (
        StageRun.query.filter(
            StageRun.tenant_id == tenant_id,
            StageRun.status == "completed",
            StageRun.completed_at >= cutoff,
        )
        .all()
    )

    for stage in recent_stages:
        if stage.stage == "triage":
            events["triage_completed"] = True
        elif stage.stage == "l2_deep_research":
            events["l2_completed_count"] += stage.done or 0
        elif stage.stage == "person":
            events["person_completed_count"] += stage.done or 0

    # Count triage results (passed vs disqualified) from company statuses
    if events["triage_completed"]:
        events["triage_passed"] = Company.query.filter(
            Company.tenant_id == tenant_id,
            Company.status == "triage_passed",
        ).count()
        events["triage_disqualified"] = Company.query.filter(
            Company.tenant_id == tenant_id,
            Company.status == "triage_disqualified",
        ).count()

    # Check for recently generated messages
    recent_messages = Message.query.filter(
        Message.tenant_id == tenant_id,
        Message.status == "draft",
        Message.created_at >= cutoff,
    ).count()
    if recent_messages > 0:
        events["messages_just_generated"] = True
        events["recent_message_count"] = recent_messages

    return events


def _build_workflow_suggestions(
    *,
    tenant_id,
    has_strategy,
    has_extracted,
    current_phase,
    contact_count,
    company_count,
    enriched_count,
    message_count,
    campaign_count,
    active_campaigns,
    event_context=None,
):
    """Build ordered list of workflow suggestions based on namespace state.

    Includes event-driven nudges (BL-169) when recent events are detected.
    Each suggestion now includes:
    - nudge_type: "step" (normal workflow) or "event" (triggered by a recent event)
    - action_type: "navigate" (default) or "navigate_and_act" (auto-navigate + start action)
    """
    suggestions = []
    events = event_context or {}

    # -----------------------------------------------------------------------
    # Event-driven nudges (BL-169) — highest priority, inserted first
    # -----------------------------------------------------------------------

    # Nudge: Triage just completed
    if events.get("triage_completed"):
        passed = events.get("triage_passed", 0)
        disqualified = events.get("triage_disqualified", 0)
        if passed > 0:
            suggestions.append(
                {
                    "id": "nudge-triage-complete",
                    "icon": "enrich",
                    "summary": "Triage complete: {} passed, {} disqualified".format(
                        passed, disqualified
                    ),
                    "detail": (
                        "Ready for deep enrichment on the {} qualified companies?".format(
                            passed
                        )
                    ),
                    "action_label": "Run Deep Enrichment",
                    "action_path": "/enrich",
                    "action_type": "navigate",
                    "nudge_type": "event",
                    "priority": 0,
                }
            )

    # Nudge: Enrichment just completed
    if events.get("enrichment_just_completed"):
        pipeline = events.get("recent_pipeline", {})
        l2_done = pipeline.get("l2_done", 0)
        person_done = pipeline.get("person_done", 0)

        summary_parts = []
        if l2_done > 0:
            summary_parts.append("{} companies deep-enriched".format(l2_done))
        if person_done > 0:
            summary_parts.append("{} contacts enriched".format(person_done))

        if summary_parts:
            suggestions.append(
                {
                    "id": "nudge-enrichment-complete",
                    "icon": "enrich",
                    "summary": "Enrichment complete: {}".format(
                        ", ".join(summary_parts)
                    ),
                    "detail": (
                        "Review enrichment results and refine your "
                        "strategy with new insights, or proceed to messaging."
                    ),
                    "action_label": "Review Results",
                    "action_path": "/enrich",
                    "action_type": "navigate",
                    "nudge_type": "event",
                    "priority": 0,
                }
            )

    # Nudge: L2 stage completed (without full pipeline complete)
    if (
        events.get("l2_completed_count", 0) > 0
        and not events.get("enrichment_just_completed")
    ):
        suggestions.append(
            {
                "id": "nudge-l2-complete",
                "icon": "enrich",
                "summary": "Deep research done for {} companies".format(
                    events["l2_completed_count"]
                ),
                "detail": (
                    "L2 enrichment revealed competitor intel, AI opportunities, "
                    "and pain points. Review the data or proceed to person enrichment."
                ),
                "action_label": "View Enriched Companies",
                "action_path": "/companies",
                "action_type": "navigate",
                "nudge_type": "event",
                "priority": 0,
            }
        )

    # Nudge: Person enrichment stage completed
    if (
        events.get("person_completed_count", 0) > 0
        and not events.get("enrichment_just_completed")
    ):
        suggestions.append(
            {
                "id": "nudge-person-complete",
                "icon": "contacts",
                "summary": "{} contacts enriched with person intel".format(
                    events["person_completed_count"]
                ),
                "detail": (
                    "Person profiles are ready. You can now generate "
                    "personalized outreach messages."
                ),
                "action_label": "View Contacts",
                "action_path": "/contacts",
                "action_type": "navigate",
                "nudge_type": "event",
                "priority": 0,
            }
        )

    # Nudge: Messages just generated
    if events.get("messages_just_generated"):
        count = events.get("recent_message_count", 0)
        suggestions.append(
            {
                "id": "nudge-messages-ready",
                "icon": "messages",
                "summary": "{} new messages ready for review".format(count),
                "detail": (
                    "The AI has generated outreach messages. "
                    "Review and approve them before sending."
                ),
                "action_label": "Review Messages",
                "action_path": "/messages",
                "action_type": "navigate",
                "nudge_type": "event",
                "priority": 0,
            }
        )

    # -----------------------------------------------------------------------
    # Regular workflow suggestions (original BL-135 logic)
    # -----------------------------------------------------------------------

    # Phase 1: No strategy yet
    if not has_strategy:
        suggestions.append(
            {
                "id": "create-strategy",
                "icon": "strategy",
                "summary": "Start by defining your GTM strategy",
                "detail": (
                    "The AI strategist will help you build an ICP, "
                    "value proposition, and messaging framework."
                ),
                "action_label": "Open Playbook",
                "action_path": "/playbook",
                "action_type": "navigate",
                "nudge_type": "step",
                "priority": 1,
            }
        )
        suggestions.sort(key=lambda s: s["priority"])
        return suggestions

    # Phase 2: Strategy exists but no extracted data (ICP etc.)
    if has_strategy and not has_extracted:
        suggestions.append(
            {
                "id": "extract-strategy",
                "icon": "strategy",
                "summary": "Your strategy needs structured data extraction",
                "detail": (
                    "Ask the AI to extract your ICP, personas, and "
                    "messaging angles from your strategy document."
                ),
                "action_label": "Refine Strategy",
                "action_path": "/playbook",
                "action_type": "navigate",
                "nudge_type": "step",
                "priority": 1,
            }
        )
        suggestions.sort(key=lambda s: s["priority"])
        return suggestions

    # Phase 3: Strategy extracted but no contacts
    if contact_count == 0:
        suggestions.append(
            {
                "id": "import-contacts",
                "icon": "contacts",
                "summary": "Import your first contacts",
                "detail": (
                    "Upload a CSV or connect your CRM to bring in "
                    "contacts that match your ICP."
                ),
                "action_label": "Import Contacts",
                "action_path": "/import",
                "action_type": "navigate",
                "nudge_type": "step",
                "priority": 1,
            }
        )
        suggestions.sort(key=lambda s: s["priority"])
        return suggestions

    # Phase 4: Contacts exist but not enriched
    unenriched = company_count - enriched_count
    if contact_count > 0 and enriched_count == 0:
        suggestions.append(
            {
                "id": "start-enrichment",
                "icon": "enrich",
                "summary": "{} contacts imported ({} companies)".format(
                    contact_count, company_count
                ),
                "detail": (
                    "Run enrichment to gather company intel, tech stack, "
                    "and AI opportunities for personalized outreach."
                ),
                "action_label": "Start Enrichment",
                "action_path": "/enrich",
                "action_type": "navigate",
                "nudge_type": "step",
                "priority": 1,
            }
        )
    elif unenriched > 0 and enriched_count > 0:
        suggestions.append(
            {
                "id": "continue-enrichment",
                "icon": "enrich",
                "summary": "{}/{} companies enriched".format(
                    enriched_count, company_count
                ),
                "detail": (
                    "{} companies still need enrichment. "
                    "Continue to get full coverage for your outreach.".format(
                        unenriched
                    )
                ),
                "action_label": "Continue Enrichment",
                "action_path": "/enrich",
                "action_type": "navigate",
                "nudge_type": "step",
                "priority": 2,
            }
        )

    # Phase 5: Enriched but no campaign
    if enriched_count > 0 and campaign_count == 0:
        suggestions.append(
            {
                "id": "create-campaign",
                "icon": "campaign",
                "summary": "{} companies enriched — ready for outreach".format(
                    enriched_count
                ),
                "detail": (
                    "Create a campaign to generate personalized messages "
                    "using your strategy and enrichment data."
                ),
                "action_label": "Create Campaign",
                "action_path": "/campaigns",
                "action_type": "navigate",
                "nudge_type": "step",
                "priority": 1,
            }
        )

    # Phase 6: Campaign exists but no messages
    if campaign_count > 0 and message_count == 0 and active_campaigns == 0:
        suggestions.append(
            {
                "id": "generate-messages",
                "icon": "messages",
                "summary": "Campaign created — generate your outreach messages",
                "detail": (
                    "The AI will write personalized messages for each "
                    "contact using your strategy and enrichment data."
                ),
                "action_label": "View Campaigns",
                "action_path": "/campaigns",
                "action_type": "navigate",
                "nudge_type": "step",
                "priority": 1,
            }
        )

    # Phase 7: Messages generated — review them
    if message_count > 0:
        draft_count = Message.query.filter_by(
            tenant_id=tenant_id, status="draft"
        ).count()
        if draft_count > 0:
            suggestions.append(
                {
                    "id": "review-messages",
                    "icon": "messages",
                    "summary": "{} draft messages ready for review".format(draft_count),
                    "detail": (
                        "Review and approve your outreach messages before "
                        "sending them to prospects."
                    ),
                    "action_label": "Review Messages",
                    "action_path": "/messages",
                    "action_type": "navigate",
                    "nudge_type": "step",
                    "priority": 1,
                }
            )

    # Always suggest strategy refinement if we have data to learn from
    if enriched_count > 0 and has_strategy:
        suggestions.append(
            {
                "id": "refine-strategy",
                "icon": "strategy",
                "summary": "Refine your strategy with enrichment insights",
                "detail": (
                    "The AI can analyze your enriched companies to identify "
                    "patterns and sharpen your ICP and messaging."
                ),
                "action_label": "Open Playbook",
                "action_path": "/playbook",
                "action_type": "navigate",
                "nudge_type": "step",
                "priority": 3,
            }
        )

    # Sort by priority (lower = more important)
    suggestions.sort(key=lambda s: s["priority"])

    return suggestions


# ---------------------------------------------------------------------------
# Phase Transition Detection (BL-170)
# ---------------------------------------------------------------------------

@tenants_bp.route("/phase-transition", methods=["GET"])
@require_auth
def get_phase_transition():
    """Check if the user's current workflow phase is complete and suggest advancement.

    Returns transition info: whether a transition is available, what the
    current and next phases are, and a CTA for the user. BL-170.
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    workflow = compute_workflow_state(tenant_id)
    current_phase = workflow["current_phase"]
    next_action = workflow.get("next_action", {})
    context = workflow.get("context", {})

    transition = _detect_phase_transition(current_phase, next_action, context)

    return jsonify({
        "current_phase": current_phase,
        "current_phase_label": workflow["current_phase_label"],
        "progress_pct": workflow["progress_pct"],
        "transition": transition,
    })


def _detect_phase_transition(current_phase, next_action, context):
    """Detect if a phase transition is ready and build the transition object.

    Returns a dict with:
    - ready: bool — whether the phase is complete and transition is available
    - next_phase_label: str — human label for the next phase
    - cta_label: str — call-to-action text for the button
    - cta_path: str — navigation path for the CTA
    - message: str — descriptive message about what was completed
    """
    from ..services.workflow_state import PHASE_LABELS, WORKFLOW_PHASES

    # Phases where we detect completion and suggest transition
    TRANSITION_TRIGGERS = {
        "strategy_ready": {
            "check": lambda ctx: True,  # Strategy is ready = contacts phase
            "message": "Your strategy is ready with ICP and personas extracted.",
            "cta_label": "Import Contacts",
            "cta_path": "/import",
        },
        "contacts_imported": {
            "check": lambda ctx: ctx.get("contacts", {}).get("total", 0) > 0,
            "message": "Contacts imported successfully.",
            "cta_label": "Start Enrichment",
            "cta_path": "/enrich",
        },
        "enrichment_done": {
            "check": lambda ctx: (
                ctx.get("enrichment", {}).get("enriched_contacts", 0) > 0
                and not ctx.get("enrichment", {}).get("is_running")
            ),
            "message": "Enrichment complete. Review and select qualified contacts.",
            "cta_label": "Select Contacts",
            "cta_path": "/playbook/contacts",
        },
        "qualified_reviewed": {
            "check": lambda ctx: (
                ctx.get("qualification", {}).get("selected_contacts", 0) > 0
            ),
            "message": "Contacts selected and qualified.",
            "cta_label": "Generate Messages",
            "cta_path": "/playbook/messages",
        },
        "messages_generated": {
            "check": lambda ctx: (
                ctx.get("messages", {}).get("total", 0) > 0
            ),
            "message": "Messages generated. Review and approve them.",
            "cta_label": "Review Messages",
            "cta_path": "/messages",
        },
        "messages_approved": {
            "check": lambda ctx: (
                ctx.get("messages", {}).get("approved", 0) > 0
            ),
            "message": "Messages approved and ready for campaign.",
            "cta_label": "Create Campaign",
            "cta_path": "/campaigns",
        },
        "campaign_created": {
            "check": lambda ctx: (
                ctx.get("campaign", {}).get("exists", False)
            ),
            "message": "Campaign created. Ready to launch.",
            "cta_label": "Launch Campaign",
            "cta_path": "/campaigns",
        },
    }

    trigger = TRANSITION_TRIGGERS.get(current_phase)
    if not trigger:
        return {"ready": False}

    if not trigger["check"](context):
        return {"ready": False}

    # Find next phase
    try:
        phase_idx = WORKFLOW_PHASES.index(current_phase)
        next_phase = WORKFLOW_PHASES[phase_idx + 1] if phase_idx + 1 < len(WORKFLOW_PHASES) else None
    except (ValueError, IndexError):
        next_phase = None

    next_label = PHASE_LABELS.get(next_phase, "") if next_phase else ""

    return {
        "ready": True,
        "next_phase": next_phase,
        "next_phase_label": next_label,
        "cta_label": trigger["cta_label"],
        "cta_path": trigger["cta_path"],
        "message": trigger["message"],
    }
