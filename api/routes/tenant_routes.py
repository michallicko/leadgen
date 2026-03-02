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
    campaigns) and suggests the most logical next action. Returns a list of
    suggestion objects with icon, summary, action label, and navigation target.
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
    )

    return jsonify({"suggestions": suggestions})


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
):
    """Build ordered list of workflow suggestions based on namespace state."""
    suggestions = []

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
                "priority": 1,
            }
        )
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
                "priority": 1,
            }
        )
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
                "priority": 1,
            }
        )
        return suggestions

    # Phase 4: Contacts exist but not enriched
    unenriched = company_count - enriched_count
    if contact_count > 0 and enriched_count == 0:
        suggestions.append(
            {
                "id": "start-enrichment",
                "icon": "enrich",
                "summary": f"{contact_count} contacts imported ({company_count} companies)",
                "detail": (
                    "Run enrichment to gather company intel, tech stack, "
                    "and AI opportunities for personalized outreach."
                ),
                "action_label": "Start Enrichment",
                "action_path": "/enrich",
                "priority": 1,
            }
        )
    elif unenriched > 0 and enriched_count > 0:
        suggestions.append(
            {
                "id": "continue-enrichment",
                "icon": "enrich",
                "summary": f"{enriched_count}/{company_count} companies enriched",
                "detail": (
                    f"{unenriched} companies still need enrichment. "
                    "Continue to get full coverage for your outreach."
                ),
                "action_label": "Continue Enrichment",
                "action_path": "/enrich",
                "priority": 2,
            }
        )

    # Phase 5: Enriched but no campaign
    if enriched_count > 0 and campaign_count == 0:
        suggestions.append(
            {
                "id": "create-campaign",
                "icon": "campaign",
                "summary": f"{enriched_count} companies enriched — ready for outreach",
                "detail": (
                    "Create a campaign to generate personalized messages "
                    "using your strategy and enrichment data."
                ),
                "action_label": "Create Campaign",
                "action_path": "/campaigns",
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
                    "summary": f"{draft_count} draft messages ready for review",
                    "detail": (
                        "Review and approve your outreach messages before "
                        "sending them to prospects."
                    ),
                    "action_label": "Review Messages",
                    "action_path": "/messages",
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
                "priority": 3,
            }
        )

    # Sort by priority (lower = more important)
    suggestions.sort(key=lambda s: s["priority"])

    return suggestions
