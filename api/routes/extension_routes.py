"""Browser extension API routes for lead import, activity sync, and status."""
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request

from ..auth import require_auth, resolve_tenant
from ..models import Activity, Company, Contact, Owner, Tag, db

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
