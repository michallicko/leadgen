"""Browser extension API routes for lead import, activity sync, and status."""

from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request

from ..auth import require_auth, resolve_tenant
from ..models import Activity, Company, Contact, Tag, db

extension_bp = Blueprint("extension", __name__)


@extension_bp.route("/api/extension/leads", methods=["POST"])
@require_auth
def upload_leads():
    """Import leads from browser extension (Sales Navigator extraction)."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    data = request.get_json()
    if not data or "leads" not in data:
        return jsonify({"error": "Missing 'leads' in request body"}), 400

    leads = data["leads"]
    source = data.get("source", "sales_navigator")
    tag_name = data.get("tag")
    user = g.current_user
    owner_id = user.owner_id

    created_contacts = 0
    created_companies = 0
    skipped_duplicates = 0

    # Resolve or create tag
    tag = None
    if tag_name:
        tag = Tag.query.filter_by(tenant_id=str(tenant_id), name=tag_name).first()
        if not tag:
            tag = Tag(tenant_id=str(tenant_id), name=tag_name)
            db.session.add(tag)
            db.session.flush()

    for lead in leads:
        linkedin_url = (lead.get("linkedin_url") or "").strip()

        # Dedup by LinkedIn URL
        if linkedin_url:
            existing = Contact.query.filter_by(
                tenant_id=str(tenant_id), linkedin_url=linkedin_url
            ).first()
            if existing:
                skipped_duplicates += 1
                continue

        # Find or create company
        company = None
        company_name = (lead.get("company_name") or "").strip()
        if company_name:
            company = Company.query.filter(
                Company.tenant_id == str(tenant_id),
                db.func.lower(Company.name) == company_name.lower(),
            ).first()
            if not company:
                company = Company(
                    tenant_id=str(tenant_id),
                    name=company_name,
                    domain=lead.get("company_domain"),
                    industry=lead.get("industry"),
                    company_size=lead.get("company_size"),
                    revenue_range=lead.get("revenue_range"),
                    status="new",
                    owner_id=owner_id,
                )
                db.session.add(company)
                db.session.flush()
                created_companies += 1

        # Parse name
        full_name = (lead.get("name") or "").strip()
        parts = full_name.split(None, 1)
        first_name = parts[0] if parts else ""
        last_name = parts[1] if len(parts) > 1 else ""

        # Create contact
        contact = Contact(
            tenant_id=str(tenant_id),
            first_name=first_name,
            last_name=last_name,
            job_title=lead.get("job_title"),
            linkedin_url=linkedin_url or None,
            company_id=company.id if company else None,
            owner_id=owner_id,
            tag_id=tag.id if tag else None,
            import_source=source,
            is_stub=False,
        )
        db.session.add(contact)
        db.session.flush()
        created_contacts += 1

    db.session.commit()

    return jsonify(
        {
            "created_contacts": created_contacts,
            "created_companies": created_companies,
            "skipped_duplicates": skipped_duplicates,
        }
    )


@extension_bp.route("/api/extension/activities", methods=["POST"])
@require_auth
def upload_activities():
    """Sync activity events from browser extension."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    data = request.get_json()
    if not data or "events" not in data:
        return jsonify({"error": "Missing 'events' in request body"}), 400

    events = data["events"]
    user = g.current_user
    owner_id = user.owner_id

    created = 0
    skipped_duplicates = 0

    for event in events:
        external_id = event.get("external_id")

        # Dedup by external_id within tenant
        if external_id:
            existing = Activity.query.filter_by(
                tenant_id=str(tenant_id), external_id=external_id
            ).first()
            if existing:
                skipped_duplicates += 1
                continue

        # Resolve contact by LinkedIn URL
        contact_id = None
        linkedin_url = (event.get("contact_linkedin_url") or "").strip()
        if linkedin_url:
            contact = Contact.query.filter_by(
                tenant_id=str(tenant_id), linkedin_url=linkedin_url
            ).first()
            if not contact:
                # Create stub contact
                payload = event.get("payload", {})
                contact_name = (payload.get("contact_name") or "").strip()
                parts = contact_name.split(None, 1)
                contact = Contact(
                    tenant_id=str(tenant_id),
                    first_name=parts[0] if parts else "Unknown",
                    last_name=parts[1] if len(parts) > 1 else "",
                    linkedin_url=linkedin_url,
                    is_stub=True,
                    import_source="activity_stub",
                    owner_id=owner_id,
                )
                db.session.add(contact)
                db.session.flush()
            contact_id = contact.id

        # Parse timestamp
        ts = event.get("timestamp")
        timestamp = None
        if ts:
            try:
                timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                timestamp = datetime.now(timezone.utc)

        # Extract display fields from payload
        payload = event.get("payload", {})

        activity = Activity(
            tenant_id=str(tenant_id),
            contact_id=contact_id,
            owner_id=owner_id,
            event_type=event.get("event_type", "event"),
            activity_name=payload.get("contact_name", ""),
            activity_detail=payload.get("message", ""),
            source="linkedin_extension",
            external_id=external_id,
            timestamp=timestamp,
            payload=payload,
        )
        db.session.add(activity)
        created += 1

    db.session.commit()

    return jsonify({"created": created, "skipped_duplicates": skipped_duplicates})


@extension_bp.route("/api/extension/status", methods=["GET"])
@require_auth
def extension_status():
    """Get extension connection status and sync stats for current user."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    user = g.current_user
    owner_id = user.owner_id

    # Count leads imported via extension (have import_source, not stubs)
    lead_query = db.session.query(
        db.func.count(Contact.id),
        db.func.max(Contact.created_at),
    ).filter(
        Contact.tenant_id == str(tenant_id),
        Contact.import_source.isnot(None),
        Contact.is_stub.is_(False),
    )
    if owner_id:
        lead_query = lead_query.filter(Contact.owner_id == owner_id)
    lead_result = lead_query.first()
    lead_count = lead_result[0] or 0
    last_lead_sync = lead_result[1]

    # Count activities synced
    activity_query = db.session.query(
        db.func.count(Activity.id),
        db.func.max(Activity.created_at),
    ).filter(
        Activity.tenant_id == str(tenant_id),
        Activity.source == "linkedin_extension",
    )
    if owner_id:
        activity_query = activity_query.filter(Activity.owner_id == owner_id)
    activity_result = activity_query.first()
    activity_count = activity_result[0] or 0
    last_activity_sync = activity_result[1]

    connected = lead_count > 0 or activity_count > 0

    return jsonify(
        {
            "connected": connected,
            "last_lead_sync": last_lead_sync.isoformat() if last_lead_sync else None,
            "last_activity_sync": (
                last_activity_sync.isoformat() if last_activity_sync else None
            ),
            "total_leads_imported": lead_count,
            "total_activities_synced": activity_count,
        }
    )
