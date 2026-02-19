import json
import math

from flask import Blueprint, jsonify, request

from ..auth import require_auth, require_role, resolve_tenant
from ..display import (
    display_contact_source,
    display_department,
    display_icp_fit,
    display_language,
    display_relationship_status,
    display_seniority,
    display_status,
    display_tier,
)
from ..models import db

contacts_bp = Blueprint("contacts", __name__)


def _add_multi_filter(where, params, param_name, column, request_obj):
    """Add a multi-value include/exclude filter to the WHERE clause."""
    raw = request_obj.args.get(param_name, "").strip()
    if not raw:
        return
    values = [v.strip() for v in raw.split(",") if v.strip()]
    if not values:
        return
    exclude = request_obj.args.get(f"{param_name}_exclude", "").strip().lower() == "true"
    placeholders = ", ".join(f":{param_name}_{i}" for i in range(len(values)))
    for i, v in enumerate(values):
        params[f"{param_name}_{i}"] = v
    if exclude:
        where.append(f"({column} IS NULL OR {column} NOT IN ({placeholders}))")
    else:
        where.append(f"{column} IN ({placeholders})")


def _iso(v):
    """Safely convert a datetime or string to ISO format."""
    if v is None:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def _parse_jsonb(v):
    """Parse a JSONB value that may be a string (SQLite) or dict (Postgres)."""
    if v is None:
        return {}
    if isinstance(v, str):
        return json.loads(v) if v else {}
    return v

ALLOWED_SORT = {
    "last_name", "first_name", "job_title", "email_address", "contact_score",
    "icp_fit", "message_status", "created_at",
}


@contacts_bp.route("/api/contacts", methods=["GET"])
@require_auth
def list_contacts():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    page = max(1, request.args.get("page", 1, type=int))
    page_size = min(100, max(1, request.args.get("page_size", 25, type=int)))
    search = request.args.get("search", "").strip()
    tag_name = request.args.get("tag_name", "").strip()
    owner_name = request.args.get("owner_name", "").strip()
    icp_fit = request.args.get("icp_fit", "").strip()
    message_status = request.args.get("message_status", "").strip()
    company_id = request.args.get("company_id", "").strip()
    sort = request.args.get("sort", "last_name").strip()
    sort_dir = request.args.get("sort_dir", "asc").strip().lower()

    if sort not in ALLOWED_SORT:
        sort = "last_name"
    if sort_dir not in ("asc", "desc"):
        sort_dir = "asc"

    where = ["ct.tenant_id = :tenant_id"]
    params = {"tenant_id": tenant_id}

    if search:
        where.append(
            "(LOWER(ct.first_name) LIKE LOWER(:search) OR LOWER(ct.last_name) LIKE LOWER(:search)"
            " OR LOWER(ct.email_address) LIKE LOWER(:search)"
            " OR LOWER(ct.job_title) LIKE LOWER(:search))"
        )
        params["search"] = f"%{search}%"
    if tag_name:
        where.append("""EXISTS (
            SELECT 1 FROM contact_tag_assignments cta
            JOIN tags bt ON bt.id = cta.tag_id
            WHERE cta.contact_id = ct.id AND bt.name = :tag_name
        )""")
        params["tag_name"] = tag_name
    if owner_name:
        where.append("o.name = :owner_name")
        params["owner_name"] = owner_name
    if icp_fit:
        where.append("ct.icp_fit = :icp_fit")
        params["icp_fit"] = icp_fit
    if message_status:
        where.append("ct.message_status = :message_status")
        params["message_status"] = message_status
    if company_id:
        where.append("ct.company_id = :company_id")
        params["company_id"] = company_id

    # Custom field filters: cf_{key}=value
    cf_idx = 0
    for param_key, param_val in request.args.items():
        if param_key.startswith("cf_") and param_val.strip():
            field_key = param_key[3:]
            # Use json_extract for SQLite compat, ->> for Postgres
            dialect = db.engine.dialect.name
            if dialect == "sqlite":
                where.append(f"json_extract(ct.custom_fields, '$.{field_key}') = :cf_val_{cf_idx}")
            else:
                where.append(f"ct.custom_fields ->> :cf_key_{cf_idx} = :cf_val_{cf_idx}")
                params[f"cf_key_{cf_idx}"] = field_key
            params[f"cf_val_{cf_idx}"] = param_val.strip()
            cf_idx += 1

    # --- Multi-value ICP filters ---
    _add_multi_filter(where, params, "industry", "co.industry", request)
    _add_multi_filter(where, params, "company_size", "co.company_size", request)
    _add_multi_filter(where, params, "geo_region", "co.geo_region", request)
    _add_multi_filter(where, params, "revenue_range", "co.revenue_range", request)
    _add_multi_filter(where, params, "seniority_level", "ct.seniority_level", request)
    _add_multi_filter(where, params, "department", "ct.department", request)
    _add_multi_filter(where, params, "linkedin_activity", "ct.linkedin_activity_level", request)

    # Job titles filter (ILIKE match)
    job_titles_raw = request.args.get("job_titles", "").strip()
    if job_titles_raw:
        titles = [t.strip() for t in job_titles_raw.split(",") if t.strip()]
        if titles:
            job_exclude = request.args.get("job_titles_exclude", "").strip().lower() == "true"
            title_clauses = []
            for i, t in enumerate(titles):
                params[f"jt_{i}"] = f"%{t}%"
                title_clauses.append(f"LOWER(ct.job_title) LIKE LOWER(:jt_{i})")
            combined = " OR ".join(title_clauses)
            if job_exclude:
                where.append(f"(ct.job_title IS NULL OR NOT ({combined}))")
            else:
                where.append(f"({combined})")

    # Campaign exclusion
    exclude_campaign_id = request.args.get("exclude_campaign_id", "").strip()

    where_clause = " AND ".join(where)

    # Build JOINs - always join companies for potential company filters
    joins = """
        LEFT JOIN companies co ON ct.company_id = co.id
        LEFT JOIN owners o ON ct.owner_id = o.id
    """

    # Campaign exclusion join
    if exclude_campaign_id:
        joins += """
        LEFT JOIN campaign_contacts cc
            ON cc.contact_id = ct.id AND cc.campaign_id = :excl_campaign_id
        """
        where.append("cc.id IS NULL")
        params["excl_campaign_id"] = exclude_campaign_id
        where_clause = " AND ".join(where)

    # Count
    total = db.session.execute(
        db.text(f"""
            SELECT COUNT(*)
            FROM contacts ct
            {joins}
            WHERE {where_clause}
        """),
        params,
    ).scalar() or 0

    pages = max(1, math.ceil(total / page_size))
    offset = (page - 1) * page_size

    order = f"ct.{sort} {'ASC' if sort_dir == 'asc' else 'DESC'} NULLS LAST"

    rows = db.session.execute(
        db.text(f"""
            SELECT
                ct.id, ct.first_name, ct.last_name, ct.job_title,
                co.id AS company_id, co.name AS company_name,
                ct.email_address, ct.contact_score, ct.icp_fit,
                ct.message_status,
                o.name AS owner_name
            FROM contacts ct
            {joins}
            WHERE {where_clause}
            ORDER BY {order}
            LIMIT :limit OFFSET :offset
        """),
        {**params, "limit": page_size, "offset": offset},
    ).fetchall()

    # Collect contact IDs for batch tag lookup
    contact_ids = [str(r[0]) for r in rows]
    tag_map: dict[str, list[str]] = {cid: [] for cid in contact_ids}
    if contact_ids:
        # Use IN clause with positional params for SQLite compat
        placeholders = ", ".join(f":cid_{i}" for i in range(len(contact_ids)))
        tag_params = {f"cid_{i}": cid for i, cid in enumerate(contact_ids)}
        tag_rows = db.session.execute(
            db.text(f"""
                SELECT cta.contact_id, t.name
                FROM contact_tag_assignments cta
                JOIN tags t ON t.id = cta.tag_id
                WHERE cta.contact_id IN ({placeholders})
                ORDER BY t.name
            """),
            tag_params,
        ).fetchall()
        for tr in tag_rows:
            tag_map.setdefault(str(tr[0]), []).append(tr[1])

    contacts = []
    for r in rows:
        cid = str(r[0])
        first = r[1] or ""
        last = r[2] or ""
        full_name = (first + " " + last).strip() if last else first
        tag_names = tag_map.get(cid, [])
        contacts.append({
            "id": cid,
            "full_name": full_name,
            "first_name": first,
            "last_name": last,
            "job_title": r[3],
            "company_id": str(r[4]) if r[4] else None,
            "company_name": r[5],
            "email_address": r[6],
            "contact_score": r[7],
            "icp_fit": display_icp_fit(r[8]),
            "message_status": r[9],
            "owner_name": r[10],
            "tag_name": tag_names[0] if tag_names else None,
            "tag_names": tag_names,
        })

    return jsonify({
        "contacts": contacts,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    })


@contacts_bp.route("/api/contacts/<contact_id>", methods=["GET"])
@require_auth
def get_contact(contact_id):
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    row = db.session.execute(
        db.text("""
            SELECT
                ct.id, ct.first_name, ct.last_name, ct.job_title,
                ct.email_address, ct.linkedin_url, ct.phone_number,
                ct.profile_photo_url,
                ct.seniority_level, ct.department,
                ct.location_city, ct.location_country,
                ct.icp_fit, ct.relationship_status,
                ct.contact_source, ct.language, ct.message_status,
                ct.ai_champion, ct.ai_champion_score,
                ct.authority_score, ct.contact_score,
                ct.enrichment_cost_usd, ct.processed_enrich,
                ct.email_lookup, ct.duplicity_check,
                ct.duplicity_conflict, ct.duplicity_detail,
                ct.notes, ct.error, ct.custom_fields,
                ct.created_at, ct.updated_at,
                ct.last_enriched_at, ct.employment_status,
                ct.employment_verified_at,
                co.id AS company_id, co.name AS company_name,
                co.domain AS company_domain, co.status AS company_status,
                co.tier AS company_tier,
                o.name AS owner_name, b.name AS tag_name
            FROM contacts ct
            LEFT JOIN companies co ON ct.company_id = co.id
            LEFT JOIN owners o ON ct.owner_id = o.id
            LEFT JOIN tags b ON ct.tag_id = b.id
            WHERE ct.id = :id AND ct.tenant_id = :tenant_id
        """),
        {"id": contact_id, "tenant_id": tenant_id},
    ).fetchone()

    if not row:
        return jsonify({"error": "Contact not found"}), 404

    first = row[1] or ""
    last = row[2] or ""
    contact = {
        "id": str(row[0]),
        "first_name": first,
        "last_name": last,
        "full_name": (first + " " + last).strip() if last else first,
        "job_title": row[3],
        "email_address": row[4],
        "linkedin_url": row[5],
        "phone_number": row[6],
        "profile_photo_url": row[7],
        "seniority_level": display_seniority(row[8]),
        "department": display_department(row[9]),
        "location_city": row[10],
        "location_country": row[11],
        "icp_fit": display_icp_fit(row[12]),
        "relationship_status": display_relationship_status(row[13]),
        "contact_source": display_contact_source(row[14]),
        "language": display_language(row[15]),
        "message_status": row[16],
        "ai_champion": row[17],
        "ai_champion_score": row[18],
        "authority_score": row[19],
        "contact_score": row[20],
        "enrichment_cost_usd": float(row[21]) if row[21] is not None else None,
        "processed_enrich": row[22],
        "email_lookup": row[23],
        "duplicity_check": row[24],
        "duplicity_conflict": row[25],
        "duplicity_detail": row[26],
        "notes": row[27],
        "error": row[28],
        "custom_fields": _parse_jsonb(row[29]),
        "created_at": _iso(row[30]),
        "updated_at": _iso(row[31]),
        "last_enriched_at": _iso(row[32]),
        "employment_status": row[33],
        "employment_verified_at": _iso(row[34]),
        "company": {
            "id": str(row[35]),
            "name": row[36],
            "domain": row[37],
            "status": display_status(row[38]),
            "tier": display_tier(row[39]),
        } if row[35] else None,
        "owner_name": row[40],
        "tag_name": row[41],
    }

    # Stage completions (DAG tracking)
    sc_rows = db.session.execute(
        db.text("""
            SELECT stage, status, completed_at, cost_usd, error
            FROM entity_stage_completions
            WHERE entity_type = 'contact' AND entity_id = :id
            ORDER BY completed_at NULLS LAST
        """),
        {"id": contact_id},
    ).fetchall()
    contact["stage_completions"] = [{
        "stage": r[0],
        "status": r[1],
        "completed_at": _iso(r[2]),
        "cost_usd": float(r[3]) if r[3] is not None else None,
        "error": r[4],
    } for r in sc_rows]

    # Contact enrichment
    enrich_row = db.session.execute(
        db.text("""
            SELECT person_summary, linkedin_profile_summary,
                   relationship_synthesis,
                   ai_champion, ai_champion_score, authority_score,
                   career_trajectory, previous_companies,
                   speaking_engagements, publications,
                   twitter_handle, github_username,
                   enriched_at, enrichment_cost_usd
            FROM contact_enrichment
            WHERE contact_id = :id
        """),
        {"id": contact_id},
    ).fetchone()

    if enrich_row:
        contact["enrichment"] = {
            "person_summary": enrich_row[0],
            "linkedin_profile_summary": enrich_row[1],
            "relationship_synthesis": enrich_row[2],
            "ai_champion": enrich_row[3],
            "ai_champion_score": enrich_row[4],
            "authority_score": enrich_row[5],
            "career_trajectory": enrich_row[6],
            "previous_companies": _parse_jsonb(enrich_row[7]),
            "speaking_engagements": enrich_row[8],
            "publications": enrich_row[9],
            "twitter_handle": enrich_row[10],
            "github_username": enrich_row[11],
            "enriched_at": _iso(enrich_row[12]),
            "enrichment_cost_usd": float(enrich_row[13]) if enrich_row[13] is not None else None,
        }
    else:
        contact["enrichment"] = None

    # Messages
    msg_rows = db.session.execute(
        db.text("""
            SELECT m.id, m.channel, m.sequence_step, m.variant,
                   m.subject, m.status, m.tone
            FROM messages m
            WHERE m.contact_id = :id
            ORDER BY m.sequence_step, m.variant
        """),
        {"id": contact_id},
    ).fetchall()
    contact["messages"] = [{
        "id": str(r[0]),
        "channel": r[1],
        "sequence_step": r[2],
        "variant": (r[3] or "a").upper(),
        "subject": r[4],
        "status": r[5],
        "tone": r[6],
    } for r in msg_rows]

    return jsonify(contact)


@contacts_bp.route("/api/contacts/<contact_id>", methods=["PATCH"])
@require_role("editor")
def update_contact(contact_id):
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    body = request.get_json(silent=True) or {}
    allowed = {
        "notes", "icp_fit", "message_status", "relationship_status",
        "seniority_level", "department", "contact_source", "language",
    }
    fields = {k: v for k, v in body.items() if k in allowed}
    custom_fields_update = body.get("custom_fields")

    if not fields and not custom_fields_update:
        return jsonify({"error": "No valid fields to update"}), 400

    row = db.session.execute(
        db.text("SELECT id, custom_fields FROM contacts WHERE id = :id AND tenant_id = :t"),
        {"id": contact_id, "t": tenant_id},
    ).fetchone()
    if not row:
        return jsonify({"error": "Contact not found"}), 404

    set_parts = []
    params = {"id": contact_id}
    for k, v in fields.items():
        set_parts.append(f"{k} = :{k}")
        params[k] = v

    if custom_fields_update and isinstance(custom_fields_update, dict):
        existing_cf = _parse_jsonb(row[1])
        existing_cf.update(custom_fields_update)
        set_parts.append("custom_fields = :custom_fields")
        params["custom_fields"] = json.dumps(existing_cf)

    db.session.execute(
        db.text(f"UPDATE contacts SET {', '.join(set_parts)} WHERE id = :id"),
        params,
    )
    db.session.commit()

    return jsonify({"ok": True})


@contacts_bp.route("/api/contacts/filter-counts", methods=["POST"])
@require_auth
def filter_counts():
    """Return faceted counts for all filterable fields.

    Each field's counts are computed with all OTHER active filters applied
    (standard faceted search pattern).
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    body = request.get_json(silent=True) or {}
    filters = body.get("filters", {})
    search = body.get("search", "").strip()
    tag_name = body.get("tag_name", "").strip()
    owner_name = body.get("owner_name", "").strip()
    exclude_campaign_id = body.get("exclude_campaign_id", "").strip() if body.get("exclude_campaign_id") else ""

    # Define all facet fields with their column references
    FACET_FIELDS = {
        "industry": "co.industry",
        "company_size": "co.company_size",
        "geo_region": "co.geo_region",
        "revenue_range": "co.revenue_range",
        "seniority_level": "ct.seniority_level",
        "department": "ct.department",
        "linkedin_activity": "ct.linkedin_activity_level",
    }

    def _build_base_where(params, exclude_facet=None):
        """Build WHERE clause applying all filters EXCEPT exclude_facet."""
        where = ["ct.tenant_id = :tenant_id"]
        params["tenant_id"] = tenant_id

        if search:
            where.append(
                "(LOWER(ct.first_name) LIKE LOWER(:search) OR LOWER(ct.last_name) LIKE LOWER(:search)"
                " OR LOWER(ct.email_address) LIKE LOWER(:search)"
                " OR LOWER(ct.job_title) LIKE LOWER(:search))"
            )
            params["search"] = f"%{search}%"
        if tag_name:
            where.append("""EXISTS (
                SELECT 1 FROM contact_tag_assignments cta
                JOIN tags bt ON bt.id = cta.tag_id
                WHERE cta.contact_id = ct.id AND bt.name = :tag_name
            )""")
            params["tag_name"] = tag_name
        if owner_name:
            where.append("o.name = :owner_name")
            params["owner_name"] = owner_name

        # Apply all multi-value filters EXCEPT the one being faceted
        for field_key, column in FACET_FIELDS.items():
            if field_key == exclude_facet:
                continue
            f = filters.get(field_key, {})
            values = f.get("values", []) if isinstance(f, dict) else []
            if not values:
                continue
            exclude = f.get("exclude", False) if isinstance(f, dict) else False
            placeholders = ", ".join(f":{field_key}_{i}" for i in range(len(values)))
            for i, v in enumerate(values):
                params[f"{field_key}_{i}"] = v
            if exclude:
                where.append(f"({column} IS NULL OR {column} NOT IN ({placeholders}))")
            else:
                where.append(f"{column} IN ({placeholders})")

        return " AND ".join(where)

    joins = """
        LEFT JOIN companies co ON ct.company_id = co.id
        LEFT JOIN owners o ON ct.owner_id = o.id
    """
    if exclude_campaign_id:
        joins += """
        LEFT JOIN campaign_contacts cc
            ON cc.contact_id = ct.id AND cc.campaign_id = :excl_campaign_id
        """

    facets = {}
    for field_key, column in FACET_FIELDS.items():
        params = {}
        where_clause = _build_base_where(params, exclude_facet=field_key)
        if exclude_campaign_id:
            params["excl_campaign_id"] = exclude_campaign_id
            extra_where = " AND cc.id IS NULL"
        else:
            extra_where = ""

        rows = db.session.execute(
            db.text(f"""
                SELECT {column} AS val, COUNT(*) AS cnt
                FROM contacts ct
                {joins}
                WHERE {where_clause}{extra_where}
                  AND {column} IS NOT NULL
                GROUP BY {column}
                ORDER BY cnt DESC
            """),
            params,
        ).fetchall()
        facets[field_key] = [{"value": r[0], "count": r[1]} for r in rows]

    # Total count with ALL filters applied
    total_params = {}
    total_where = _build_base_where(total_params)
    if exclude_campaign_id:
        total_params["excl_campaign_id"] = exclude_campaign_id
        extra_where = " AND cc.id IS NULL"
    else:
        extra_where = ""

    total = db.session.execute(
        db.text(f"""
            SELECT COUNT(*)
            FROM contacts ct
            {joins}
            WHERE {total_where}{extra_where}
        """),
        total_params,
    ).scalar() or 0

    return jsonify({"total": total, "facets": facets})


@contacts_bp.route("/api/contacts/job-titles", methods=["GET"])
@require_auth
def job_title_suggestions():
    """Return distinct job titles matching a query, with counts."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    q = request.args.get("q", "").strip()
    limit = min(50, max(1, request.args.get("limit", 20, type=int)))

    if len(q) < 2:
        return jsonify({"titles": []})

    rows = db.session.execute(
        db.text("""
            SELECT ct.job_title, COUNT(*) AS cnt
            FROM contacts ct
            WHERE ct.tenant_id = :tenant_id
              AND ct.job_title IS NOT NULL
              AND LOWER(ct.job_title) LIKE LOWER(:q)
            GROUP BY ct.job_title
            ORDER BY cnt DESC
            LIMIT :limit
        """),
        {"tenant_id": tenant_id, "q": f"%{q}%", "limit": limit},
    ).fetchall()

    return jsonify({
        "titles": [{"title": r[0], "count": r[1]} for r in rows]
    })
