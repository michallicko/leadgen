"""Playbook (GTM Strategy) API routes."""

import json
import logging
import math
import os
import re
import threading
import time

from flask import Blueprint, Response, jsonify, request

from ..auth import require_auth, resolve_tenant
from ..display import display_seniority
from ..models import (
    Company,
    CompanyEnrichmentL1,
    CompanyEnrichmentL2,
    CompanyEnrichmentProfile,
    CompanyEnrichmentSignals,
    CompanyEnrichmentMarket,
    PLAYBOOK_PHASES,
    PlaybookLog,
    StrategyDocument,
    StrategyChatMessage,
    StrategyVersion,
    Tenant,
    ToolExecution,
    db,
)
from ..services.agent_executor import execute_agent_turn
from ..services.anthropic_client import AnthropicClient
from ..services.llm_logger import log_llm_usage
from ..services.playbook_service import (
    build_extraction_prompt,
    build_messages,
    build_proactive_analysis_prompt,
    build_seeded_template,
    build_system_prompt,
)
from ..services.tool_registry import ToolContext, get_tools_for_api

logger = logging.getLogger(__name__)

playbook_bp = Blueprint("playbook", __name__)

_ALLOWED_PAGE_CONTEXTS = frozenset(
    {
        "contacts",
        "companies",
        "messages",
        "campaigns",
        "enrich",
        "import",
        "playbook",
    }
)


@playbook_bp.route("/api/playbook", methods=["GET"])
@require_auth
def get_playbook():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc:
        doc = StrategyDocument(tenant_id=tenant_id, status="draft")
        db.session.add(doc)
        db.session.commit()

    result = doc.to_dict()

    # Check for undoable AI edits
    has_ai_edits = (
        StrategyVersion.query.filter_by(
            document_id=doc.id, edit_source="ai_tool"
        ).first()
        is not None
    )
    result["has_ai_edits"] = has_ai_edits

    return jsonify(result), 200


@playbook_bp.route("/api/playbook", methods=["PUT"])
@require_auth
def update_playbook():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    data = request.get_json(silent=True) or {}

    content = data.get("content")
    status = data.get("status")
    objective = data.get("objective")

    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc:
        return jsonify({"error": "No strategy document found"}), 404

    if content is not None:
        doc.content = content
        doc.version = doc.version + 1
    doc.updated_by = getattr(request, "user_id", None)
    if status:
        doc.status = status
    if objective is not None:
        doc.objective = objective

    # Persist playbook selections (contacts, messages, etc.)
    playbook_selections = data.get("playbook_selections")
    if playbook_selections is not None and isinstance(playbook_selections, dict):
        existing = doc.playbook_selections or {}
        if isinstance(existing, str):
            try:
                existing = json.loads(existing)
            except (ValueError, TypeError):
                existing = {}
        existing.update(playbook_selections)
        doc.playbook_selections = existing

    db.session.commit()
    return jsonify(doc.to_dict()), 200


@playbook_bp.route("/api/playbook/undo", methods=["POST"])
@require_auth
def undo_ai_edit():
    """Undo the most recent AI edit(s) to the strategy document.

    Finds the most recent turn_id (batch of edits from one AI turn) and
    restores the document to the snapshot taken before the first edit of
    that turn.  If no turn_id is set, reverts to the most recent snapshot.

    The undo itself creates a snapshot (with edit_source='user_undo') so
    it can be un-undone.  After restoring, the AI-tool snapshots from the
    undone turn are deleted.
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc:
        return jsonify({"error": "No strategy document found"}), 404

    # Find the latest ai_tool snapshot for this document
    latest_snap = (
        StrategyVersion.query.filter_by(document_id=doc.id, edit_source="ai_tool")
        .order_by(StrategyVersion.created_at.desc())
        .first()
    )

    if not latest_snap:
        return jsonify({"error": "No AI edits to undo"}), 404

    # Batch undo: if the latest snapshot has a turn_id, find the
    # earliest snapshot from that turn to restore the state from
    # *before* the first tool call of the turn.
    if latest_snap.turn_id:
        restore_snap = (
            StrategyVersion.query.filter_by(
                document_id=doc.id,
                edit_source="ai_tool",
                turn_id=latest_snap.turn_id,
            )
            .order_by(StrategyVersion.created_at.asc())
            .first()
        )
    else:
        restore_snap = latest_snap

    # Save a snapshot of current state (so undo is undoable)
    from ..services.strategy_tools import _snapshot

    _snapshot(doc, edit_source="user_undo")

    restored_version = restore_snap.version

    # Restore content and extracted_data from the snapshot
    doc.content = restore_snap.content
    doc.extracted_data = restore_snap.extracted_data
    doc.version += 1
    doc.updated_by = getattr(request, "user_id", None)

    # Delete the ai_tool snapshots that were undone
    if latest_snap.turn_id:
        StrategyVersion.query.filter_by(
            document_id=doc.id,
            edit_source="ai_tool",
            turn_id=latest_snap.turn_id,
        ).delete()
    else:
        db.session.delete(latest_snap)

    db.session.commit()

    return jsonify(
        {
            "success": True,
            "restored_version": restored_version,
            "current_version": doc.version,
        }
    ), 200


@playbook_bp.route("/api/playbook/phase", methods=["PUT"])
@require_auth
def update_phase():
    """Advance or rewind the playbook phase.

    Forward transitions are gated:
      strategy -> contacts: requires non-empty extracted_data
      contacts -> messages: requires at least 1 selected contact
      messages -> campaign: requires at least 1 generated message

    Backward transitions are always allowed.
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    data = request.get_json(silent=True) or {}
    target_phase = data.get("phase")
    if target_phase not in PLAYBOOK_PHASES:
        return jsonify(
            {
                "error": "Invalid phase. Must be one of: {}".format(
                    ", ".join(PLAYBOOK_PHASES)
                )
            }
        ), 400

    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc:
        return jsonify({"error": "No strategy document found"}), 404

    current_idx = (
        PLAYBOOK_PHASES.index(doc.phase) if doc.phase in PLAYBOOK_PHASES else 0
    )
    target_idx = PLAYBOOK_PHASES.index(target_phase)

    # Forward transition validation
    if target_idx > current_idx:
        error = _validate_phase_transition(doc, doc.phase, target_phase)
        if error:
            return jsonify({"error": error, "current_phase": doc.phase}), 422

    doc.phase = target_phase
    db.session.commit()

    return jsonify(doc.to_dict()), 200


def _validate_phase_transition(doc, current_phase, target_phase):
    """Validate that a forward phase transition is allowed.

    Returns an error message string if blocked, or None if allowed.
    """
    if target_phase == "contacts":
        extracted = doc.extracted_data or {}
        if isinstance(extracted, str):
            import json as _json

            try:
                extracted = _json.loads(extracted)
            except (ValueError, TypeError):
                extracted = {}
        if not extracted.get("icp"):
            return (
                "Strategy must have extracted ICP data before moving to Contacts. "
                "Save and extract first."
            )
        return None

    if target_phase == "messages":
        selections = doc.playbook_selections or {}
        if isinstance(selections, str):
            import json as _json

            try:
                selections = _json.loads(selections)
            except (ValueError, TypeError):
                selections = {}
        contact_ids = selections.get("contacts", {}).get("selected_ids", [])
        if not contact_ids:
            return "Select at least one contact before moving to Messages."
        return None

    if target_phase == "campaign":
        selections = doc.playbook_selections or {}
        if isinstance(selections, str):
            import json as _json

            try:
                selections = _json.loads(selections)
            except (ValueError, TypeError):
                selections = {}
        contact_ids = selections.get("contacts", {}).get("selected_ids", [])
        if not contact_ids:
            return "No contacts selected."
        from ..models import Message

        msg_count = Message.query.filter(
            Message.tenant_id == doc.tenant_id,
            Message.contact_id.in_(contact_ids),
        ).count()
        if msg_count == 0:
            return (
                "Generate messages for selected contacts before launching a campaign."
            )
        return None

    return None


@playbook_bp.route("/api/playbook/extract", methods=["POST"])
@require_auth
def extract_strategy():
    """Extract structured data from the strategy document using an LLM."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc:
        return jsonify({"error": "No strategy document found"}), 404

    system_prompt, user_prompt = build_extraction_prompt(doc.content or "")

    client = _get_anthropic_client()
    user_id = getattr(request, "user_id", None)

    start_time = time.time()
    try:
        result = client.query(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=4096,
            temperature=0.1,
        )
        raw_text = result.content
    except Exception as e:
        logger.exception("LLM extraction error: %s", e)
        return jsonify({"error": "LLM extraction failed: {}".format(str(e))}), 502

    duration_ms = int((time.time() - start_time) * 1000)

    # Log LLM usage for strategy extraction
    log_llm_usage(
        tenant_id=tenant_id,
        operation="strategy_extraction",
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        provider="anthropic",
        user_id=user_id,
        duration_ms=duration_ms,
        metadata={"document_id": str(doc.id)},
    )

    # Strip markdown code fences if the LLM wraps the JSON
    stripped = re.sub(r"```(?:json)?\s*(.*?)\s*```", r"\1", raw_text, flags=re.DOTALL)

    try:
        extracted_data = json.loads(stripped)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("LLM returned invalid JSON: %s", raw_text[:200])
        db.session.commit()  # Commit the LLM usage log even on parse failure
        return jsonify(
            {
                "error": "Failed to parse extraction result as JSON",
                "detail": str(e),
            }
        ), 422

    doc.extracted_data = extracted_data
    db.session.commit()

    return jsonify(
        {
            "extracted_data": extracted_data,
            "version": doc.version,
        }
    ), 200


@playbook_bp.route("/api/playbook/contacts", methods=["GET"])
@require_auth
def playbook_contacts():
    """Return contacts filtered by the playbook's ICP criteria.

    Reads extracted_data.icp from the strategy document, maps ICP fields
    to contact query filters (reusing _map_icp_to_filters from
    icp_filter_tools), and returns a paginated contact list.

    Query params allow overriding individual filters and pagination:
        page (int, default 1), per_page (int, default 25, max 100)
        industries, seniority_levels, geo_regions, company_sizes (comma-sep)
        sort (str), sort_dir (asc|desc)
        search (str) — text search across name/email/title
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc:
        return jsonify({"error": "No strategy document found"}), 404

    # Read ICP from extracted_data
    extracted = doc.extracted_data or {}
    if isinstance(extracted, str):
        try:
            extracted = json.loads(extracted)
        except (ValueError, TypeError):
            extracted = {}

    icp = extracted.get("icp", {})
    if isinstance(icp, str):
        try:
            icp = json.loads(icp)
        except (ValueError, TypeError):
            icp = {}

    icp_source = bool(icp)

    # Merge top-level personas into icp if present
    top_personas = extracted.get("personas", [])
    icp_personas = icp.get("personas", []) if isinstance(icp, dict) else []
    if top_personas and not icp_personas and isinstance(icp, dict):
        icp["personas"] = top_personas

    # Map ICP to base filters
    from ..services.icp_filter_tools import _map_icp_to_filters

    base_filters = _map_icp_to_filters(icp) if icp else {}

    # Allow query param overrides (comma-separated lists)
    override_keys = ["industries", "seniority_levels", "geo_regions", "company_sizes"]
    for key in override_keys:
        raw = request.args.get(key, "").strip()
        if raw:
            base_filters[key] = [v.strip() for v in raw.split(",") if v.strip()]

    # Pagination
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(100, max(1, request.args.get("per_page", 25, type=int)))

    # Sort
    sort_field = request.args.get("sort", "last_name").strip()
    sort_dir = request.args.get("sort_dir", "asc").strip().lower()
    _SORT_ALLOWED = {
        "last_name", "first_name", "job_title", "seniority_level",
        "contact_score", "created_at",
    }
    if sort_field not in _SORT_ALLOWED:
        sort_field = "last_name"
    if sort_dir not in ("asc", "desc"):
        sort_dir = "asc"

    # Text search
    search = request.args.get("search", "").strip()

    # Build WHERE clause
    where = [
        "ct.tenant_id = :tenant_id",
        "(ct.is_disqualified = false OR ct.is_disqualified IS NULL)",
    ]
    params = {"tenant_id": tenant_id}

    if search:
        where.append(
            "(LOWER(ct.first_name) LIKE LOWER(:search)"
            " OR LOWER(ct.last_name) LIKE LOWER(:search)"
            " OR LOWER(ct.email_address) LIKE LOWER(:search)"
            " OR LOWER(ct.job_title) LIKE LOWER(:search))"
        )
        params["search"] = "%{}%".format(search)

    # Apply ICP-derived (or overridden) multi-value filters
    multi_map = {
        "industries": ("co.industry", "ind"),
        "seniority_levels": ("ct.seniority_level", "sen"),
        "geo_regions": ("co.geo_region", "geo"),
        "company_sizes": ("co.company_size", "csz"),
    }
    for key, (column, prefix) in multi_map.items():
        values = base_filters.get(key, [])
        if not values or not isinstance(values, list):
            continue
        phs = []
        for i, v in enumerate(values):
            pname = "{}_{}".format(prefix, i)
            params[pname] = v
            phs.append(":{}".format(pname))
        where.append("{} IN ({})".format(column, ", ".join(phs)))

    where_clause = " AND ".join(where)

    joins = """
        LEFT JOIN companies co ON ct.company_id = co.id
        LEFT JOIN owners o ON ct.owner_id = o.id
    """

    # Count total
    total = (
        db.session.execute(
            db.text(
                "SELECT COUNT(*) FROM contacts ct {} WHERE {}".format(
                    joins, where_clause
                )
            ),
            params,
        ).scalar()
        or 0
    )

    pages = max(1, math.ceil(total / per_page))
    offset = (page - 1) * per_page

    order = "ct.{} {} NULLS LAST".format(
        sort_field, "ASC" if sort_dir == "asc" else "DESC"
    )

    rows = db.session.execute(
        db.text(
            """
            SELECT
                ct.id, ct.first_name, ct.last_name, ct.job_title,
                co.id AS company_id, co.name AS company_name,
                ct.email_address, ct.seniority_level,
                ct.contact_score, ct.icp_fit,
                co.industry, co.company_size, co.status AS company_status
            FROM contacts ct
            {joins}
            WHERE {where}
            ORDER BY {order}
            LIMIT :limit OFFSET :offset
        """.format(
                joins=joins, where=where_clause, order=order
            )
        ),
        {**params, "limit": per_page, "offset": offset},
    ).fetchall()

    contacts = []
    for r in rows:
        contacts.append(
            {
                "id": str(r[0]),
                "first_name": r[1] or "",
                "last_name": r[2] or "",
                "full_name": (
                    ((r[1] or "") + " " + (r[2] or "")).strip() or r[1] or ""
                ),
                "job_title": r[3],
                "company_id": str(r[4]) if r[4] else None,
                "company_name": r[5],
                "email_address": r[6],
                "seniority_level": display_seniority(r[7]),
                "contact_score": r[8],
                "icp_fit": r[9],
                "industry": r[10],
                "company_size": r[11],
                "company_status": r[12],
            }
        )

    return jsonify(
        {
            "filters": {"applied_filters": base_filters},
            "contacts": contacts,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
            "icp_source": icp_source,
        }
    ), 200


@playbook_bp.route("/api/playbook/contacts/confirm", methods=["POST"])
@require_auth
def confirm_contact_selection():
    """Save selected contact IDs and advance phase to messages.

    Body: { "selected_ids": ["id1", "id2", ...] }
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc:
        return jsonify({"error": "No strategy document found"}), 404

    data = request.get_json(silent=True) or {}
    selected_ids = data.get("selected_ids", [])
    if not isinstance(selected_ids, list) or not selected_ids:
        return jsonify({"error": "selected_ids must be a non-empty list"}), 400

    # Validate that all IDs are actual contacts for this tenant
    valid_ids = [
        str(r[0])
        for r in db.session.execute(
            db.text(
                "SELECT id FROM contacts WHERE tenant_id = :t AND id IN ({})".format(
                    ", ".join(":cid_{}".format(i) for i in range(len(selected_ids)))
                )
            ),
            {
                "t": tenant_id,
                **{"cid_{}".format(i): cid for i, cid in enumerate(selected_ids)},
            },
        ).fetchall()
    ]

    if not valid_ids:
        return jsonify({"error": "No valid contacts found for the given IDs"}), 400

    # Save selections
    existing = doc.playbook_selections or {}
    if isinstance(existing, str):
        try:
            existing = json.loads(existing)
        except (ValueError, TypeError):
            existing = {}
    existing["contacts"] = {"selected_ids": valid_ids}
    doc.playbook_selections = existing

    # Advance phase to messages
    doc.phase = "messages"
    db.session.commit()

    return jsonify(
        {
            "success": True,
            "selected_count": len(valid_ids),
            "phase": doc.phase,
            "playbook_selections": doc.playbook_selections,
        }
    ), 200


def _get_or_create_document(tenant_id):
    """Return the tenant's strategy document, creating one if needed."""
    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc:
        doc = StrategyDocument(tenant_id=tenant_id, status="draft")
        db.session.add(doc)
        db.session.flush()
    return doc


# --- Company status mapping for research status ---
_COMPLETED_STATUSES = {"enriched_l2", "triage_passed", "triage_disqualified"}
_FAILED_STATUSES = {"enrichment_l2_failed", "enrichment_failed", "disqualified"}
_IN_PROGRESS_STATUSES = {"new", "enrichment_l1", "enrichment_l2"}


def _research_status_from_company(company):
    """Map a company's status to a research status string."""
    if not company or not company.status:
        return "not_started"
    status = company.status.lower().replace(" ", "_")
    if status in _COMPLETED_STATUSES:
        return "completed"
    if status in _FAILED_STATUSES:
        return "failed"
    if status in _IN_PROGRESS_STATUSES:
        return "in_progress"
    return "in_progress"


def _load_enrichment_data(company_id):
    """Load L1 and L2 enrichment records for a company.

    Returns a dict with company, profile, signals, market, and L1 data merged,
    or None if no enrichment data exists.
    """
    result = {}

    # Company-level fields populated by L1
    company = db.session.get(Company, company_id)
    if company:
        result["company"] = {
            "name": company.name,
            "domain": company.domain,
            "industry": company.industry,
            "industry_category": company.industry_category,
            "summary": company.summary,
            "company_size": company.company_size,
            "revenue_range": company.revenue_range,
            "hq_country": company.hq_country,
            "hq_city": company.hq_city,
            "tier": company.tier,
            "status": company.status,
        }

    l1 = db.session.get(CompanyEnrichmentL1, company_id)
    if l1:
        result["triage_notes"] = l1.triage_notes
        result["pre_score"] = float(l1.pre_score) if l1.pre_score else None
        result["confidence"] = float(l1.confidence) if l1.confidence else None

    l2 = db.session.get(CompanyEnrichmentL2, company_id)
    if l2:
        result["company_overview"] = l2.company_intel
        result["ai_opportunities"] = l2.ai_opportunities
        result["pain_hypothesis"] = l2.pain_hypothesis
        result["quick_wins"] = l2.quick_wins
        # Phase 1 (BL-054): Add high-value L2 fields for chat context
        result["pitch_framing"] = l2.pitch_framing
        result["revenue_trend"] = l2.revenue_trend
        result["industry_pain_points"] = l2.industry_pain_points
        result["relevant_case_study"] = l2.relevant_case_study
        result["enriched_at"] = l2.enriched_at.isoformat() if l2.enriched_at else None

    profile = db.session.get(CompanyEnrichmentProfile, company_id)
    if profile:
        result["company_intel"] = profile.company_intel
        result["key_products"] = profile.key_products
        result["customer_segments"] = profile.customer_segments
        result["competitors"] = profile.competitors
        result["tech_stack"] = profile.tech_stack
        result["leadership_team"] = profile.leadership_team
        result["certifications"] = profile.certifications

    signals = db.session.get(CompanyEnrichmentSignals, company_id)
    if signals:
        result["digital_initiatives"] = signals.digital_initiatives
        result["hiring_signals"] = signals.hiring_signals
        result["ai_adoption_level"] = signals.ai_adoption_level
        result["growth_indicators"] = signals.growth_indicators

    market = db.session.get(CompanyEnrichmentMarket, company_id)
    if market:
        result["recent_news"] = market.recent_news
        result["funding_history"] = market.funding_history

    return result if result else None


def _log_event(tenant_id, user_id, doc_id, event_type, payload=None):
    """Write a PlaybookLog entry."""
    log = PlaybookLog(
        tenant_id=tenant_id,
        user_id=user_id,
        doc_id=doc_id,
        event_type=event_type,
        payload=payload,
    )
    db.session.add(log)
    db.session.commit()


def _run_self_research(
    app, company_id, tenant_id, additional_domains=None, challenge_type=None
):
    """Run L1 + L2 enrichment in a background thread for self-company research.

    Args:
        additional_domains: Optional list of competitor/partner domains for
            lightweight web_search enrichment. The primary domain gets full
            L1+L2 enrichment; additional domains get stored as metadata.
        challenge_type: Optional string indicating the user's primary GTM
            challenge. Passed to build_seeded_template for adaptive sections.
    """
    with app.app_context():
        try:
            from api.services.l1_enricher import enrich_l1
            from api.services.l2_enricher import enrich_l2

            logger.info(
                "Starting self-research for company %s (additional_domains=%s)",
                company_id,
                additional_domains,
            )

            enrich_l1(company_id, tenant_id)

            # Update company name from L1 enrichment results
            company = db.session.get(Company, company_id)
            if company and company.is_self:
                l1 = db.session.get(CompanyEnrichmentL1, company_id)
                if l1 and l1.raw_response:
                    import json as _json

                    try:
                        raw = (
                            _json.loads(l1.raw_response)
                            if isinstance(l1.raw_response, str)
                            else l1.raw_response
                        )
                        l1_name = raw.get("company_name") or raw.get("name")
                        if l1_name and l1_name != company.name:
                            company.name = l1_name
                    except (ValueError, TypeError, AttributeError):
                        pass

            # After L1, auto-advance to triage_passed if still in early status
            _SKIP_STATUSES = {"triage_passed", "enriched_l2", "enrichment_l2_failed"}
            if company and company.status not in _SKIP_STATUSES:
                company.status = "triage_passed"
                db.session.commit()

            l2_result = enrich_l2(company_id, tenant_id)
            l2_failed = "error" in l2_result

            if l2_failed:
                logger.warning(
                    "Self-research L2 failed for company %s: %s",
                    company_id,
                    l2_result.get("error"),
                )

            # Seed the strategy document with whatever data we have
            # (L1 data if L2 failed, full data if L2 succeeded).
            # Start a clean session state since L2 failure may have
            # left the session dirty from rollbacks.
            try:
                db.session.rollback()
            except Exception:
                pass
            doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
            if doc and doc.version == 1:
                enrichment_data = _load_enrichment_data(company_id)
                if additional_domains and enrichment_data:
                    enrichment_data["additional_domains"] = additional_domains
                doc.content = build_seeded_template(
                    doc.objective, enrichment_data, challenge_type=challenge_type
                )
                doc.enrichment_id = company_id
                db.session.commit()
                logger.info(
                    "Seeded template for company %s (content length: %d, l2_failed: %s)",
                    company_id,
                    len(doc.content or ""),
                    l2_failed,
                )

            if not l2_failed:
                logger.info("Self-research completed for company %s", company_id)

            # Log research completion (skip if no valid user_id to avoid UUID error)
            doc = StrategyDocument.query.filter_by(enrichment_id=company_id).first()
            if doc and doc.updated_by:
                enrichment_data = _load_enrichment_data(company_id)
                _log_event(
                    tenant_id=tenant_id,
                    user_id=doc.updated_by,
                    doc_id=doc.id,
                    event_type="research_complete"
                    if not l2_failed
                    else "research_partial",
                    payload={
                        "company_id": str(company_id),
                        "enrichment_keys": list(enrichment_data.keys())
                        if enrichment_data
                        else [],
                        "l2_failed": l2_failed,
                    },
                )
        except Exception:
            logger.exception("Self-research failed for company %s", company_id)
            # Still try to seed template with whatever data we have
            try:
                db.session.rollback()  # Clear poisoned transaction
                doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
                if doc and doc.version == 1:
                    enrichment_data = _load_enrichment_data(company_id)
                    if enrichment_data:
                        doc.content = build_seeded_template(
                            doc.objective,
                            enrichment_data,
                            challenge_type=challenge_type,
                        )
                        db.session.commit()
            except Exception:
                logger.exception("Failed to seed template after research error")


@playbook_bp.route("/api/playbook/research", methods=["POST"])
@require_auth
def trigger_research():
    """Trigger research on the tenant's own company.

    Creates or finds a company record with is_self=True, saves the
    objective, and launches L1+L2 enrichment in a background thread.
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    data = request.get_json(silent=True) or {}
    objective = data.get("objective")
    challenge_type = data.get("challenge_type")

    # Support multi-domain format: {domains: [...], primary_domain: "..."}
    # Backward compat: {domain: "..."} treated as {domains: [domain]}
    domains = data.get("domains")
    primary_domain = data.get("primary_domain")
    if not domains:
        # Old format: single domain field
        legacy_domain = data.get("domain")
        if legacy_domain:
            domains = [legacy_domain]
            primary_domain = legacy_domain

    # Resolve primary domain
    domain = primary_domain or (domains[0] if domains else None)

    # Fall back to tenant's domain if none provided
    if not domain:
        tenant = db.session.get(Tenant, tenant_id)
        domain = tenant.domain if tenant else None

    if not domain:
        return jsonify(
            {"error": "Domain is required (provide in body or set on tenant)"}
        ), 400

    if not domains:
        domains = [domain]

    # Derive company name from domain (strip TLD, capitalize)
    # e.g., "notion.so" -> "Notion", "stripe.com" -> "Stripe"
    domain_parts = domain.split(".")
    company_name = domain_parts[0].capitalize() if domain_parts else domain

    # Find or create the self-company for this tenant
    company = Company.query.filter_by(tenant_id=tenant_id, is_self=True).first()

    if company:
        company.domain = domain
        company.name = company_name
        # Reset status for re-research
        company.status = "new"
    else:
        company = Company(
            tenant_id=tenant_id,
            name=company_name,
            domain=domain,
            is_self=True,
            status="new",
        )
        db.session.add(company)
        db.session.flush()

    # Link the strategy document to this company and save objective
    doc = _get_or_create_document(tenant_id)
    doc.enrichment_id = company.id
    if objective:
        doc.objective = objective
    db.session.commit()

    # Store additional domains as metadata for lightweight research
    additional_domains = [d for d in domains if d != domain]

    # Log research trigger
    user_id = getattr(request, "user_id", None)
    if user_id:
        _log_event(
            tenant_id=tenant_id,
            user_id=user_id,
            doc_id=doc.id,
            event_type="research_trigger",
            payload={
                "domain": domain,
                "domains": domains,
                "additional_domains": additional_domains,
                "objective": objective,
                "company_id": str(company.id),
            },
        )

    # Launch enrichment in background thread
    from flask import current_app

    app = current_app._get_current_object()
    t = threading.Thread(
        target=_run_self_research,
        args=(app, company.id, tenant_id),
        kwargs={
            "additional_domains": additional_domains,
            "challenge_type": challenge_type,
        },
        daemon=True,
        name="self-research-{}".format(company.id),
    )
    t.start()

    return jsonify(
        {
            "status": "triggered",
            "company_id": company.id,
            "domain": company.domain,
            "domains": domains,
            "challenge_type": challenge_type,
        }
    ), 200


@playbook_bp.route("/api/playbook/research", methods=["GET"])
@require_auth
def get_research_status():
    """Return the research/enrichment status for the tenant's strategy document."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc or not doc.enrichment_id:
        return jsonify({"status": "not_started"}), 200

    company = db.session.get(Company, doc.enrichment_id)
    if not company:
        return jsonify({"status": "not_started"}), 200

    status = _research_status_from_company(company)

    # Guard against race condition: enrichment may set company status to
    # "enriched_l2" before the template is seeded into the document.
    # Keep reporting "in_progress" until the document actually has content.
    if status == "completed":
        if not doc.content or len(doc.content.strip()) == 0:
            status = "in_progress"

    result = {
        "status": status,
        "company": {
            "id": company.id,
            "name": company.name,
            "domain": company.domain,
            "status": company.status,
            "tier": company.tier,
        },
    }

    # Include enrichment data when research is completed or failed (partial data)
    if result["status"] in ("completed", "failed"):
        enrichment_data = _load_enrichment_data(company.id)
        if enrichment_data:
            result["enrichment_data"] = enrichment_data

    return jsonify(result), 200


@playbook_bp.route("/api/playbook/chat", methods=["GET"])
@require_auth
def get_chat_history():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    limit = min(request.args.get("limit", 50, type=int), 200)

    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc:
        return jsonify({"messages": []}), 200

    # Thread-aware: find the latest thread_start marker and return
    # only messages from that point onward. If no marker exists,
    # return all messages (backward compatible).
    latest_thread_start = (
        StrategyChatMessage.query.filter_by(
            document_id=doc.id, tenant_id=tenant_id, thread_start=True
        )
        .order_by(StrategyChatMessage.created_at.desc())
        .first()
    )

    if latest_thread_start:
        # Use a subquery to get messages created at or after the marker.
        # We compare by created_at and also include the marker by id to
        # handle edge cases with timestamp precision across databases.
        messages = (
            StrategyChatMessage.query.filter(
                StrategyChatMessage.document_id == doc.id,
                StrategyChatMessage.tenant_id == tenant_id,
                db.or_(
                    StrategyChatMessage.id == latest_thread_start.id,
                    StrategyChatMessage.created_at > latest_thread_start.created_at,
                ),
            )
            .order_by(StrategyChatMessage.created_at.asc())
            .limit(limit)
            .all()
        )
    else:
        messages = (
            StrategyChatMessage.query.filter_by(document_id=doc.id, tenant_id=tenant_id)
            .order_by(StrategyChatMessage.created_at.asc())
            .limit(limit)
            .all()
        )

    return jsonify({"messages": [m.to_dict() for m in messages]}), 200


def _wants_streaming(req):
    """Check if the client wants an SSE streaming response."""
    accept = req.headers.get("Accept", "")
    if "text/event-stream" in accept:
        return True
    if req.args.get("stream", "").lower() in ("true", "1", "yes"):
        return True
    return False


def _get_anthropic_client():
    """Create an AnthropicClient with the API key from environment."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    return AnthropicClient(api_key=api_key)


@playbook_bp.route("/api/playbook/chat/new-thread", methods=["POST"])
@require_auth
def new_chat_thread():
    """Create a new conversation thread.

    Inserts a system-role marker message with thread_start=True.
    Old messages before this point are retained but not shown in the active thread.
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    doc = _get_or_create_document(tenant_id)
    user_id = getattr(request, "user_id", None)

    marker = StrategyChatMessage(
        tenant_id=tenant_id,
        document_id=doc.id,
        role="system",
        content="--- New conversation started ---",
        thread_start=True,
        created_by=user_id,
    )
    db.session.add(marker)
    db.session.commit()

    return jsonify(
        {
            "thread_id": marker.id,
            "created_at": marker.created_at.isoformat() if marker.created_at else None,
        }
    ), 201


@playbook_bp.route("/api/playbook/chat", methods=["POST"])
@require_auth
def post_chat_message():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    data = request.get_json(silent=True) or {}
    message_text = data.get("message")
    if not message_text:
        return jsonify({"error": "message is required"}), 400

    page_context = data.get("page_context")
    if page_context and page_context not in _ALLOWED_PAGE_CONTEXTS:
        page_context = None

    doc = _get_or_create_document(tenant_id)
    tenant = db.session.get(Tenant, tenant_id)
    user_id = getattr(request, "user_id", None)

    # Save the user message before any LLM work
    user_msg = StrategyChatMessage(
        tenant_id=tenant_id,
        document_id=doc.id,
        role="user",
        content=message_text,
        page_context=page_context,
        created_by=user_id,
    )
    db.session.add(user_msg)
    db.session.flush()

    # Log user chat event
    if user_id:
        _log_event(
            tenant_id=tenant_id,
            user_id=user_id,
            doc_id=doc.id,
            event_type="chat_user",
            payload={"message": message_text},
        )

    # Load chat history for context — thread-aware
    # Find latest thread_start marker to scope history
    latest_thread_start = (
        StrategyChatMessage.query.filter_by(
            document_id=doc.id, tenant_id=tenant_id, thread_start=True
        )
        .order_by(StrategyChatMessage.created_at.desc())
        .first()
    )

    if latest_thread_start:
        history = (
            StrategyChatMessage.query.filter(
                StrategyChatMessage.document_id == doc.id,
                StrategyChatMessage.tenant_id == tenant_id,
                StrategyChatMessage.id != user_msg.id,
                db.or_(
                    StrategyChatMessage.id == latest_thread_start.id,
                    StrategyChatMessage.created_at > latest_thread_start.created_at,
                ),
            )
            .order_by(StrategyChatMessage.created_at.asc())
            .all()
        )
    else:
        history = (
            StrategyChatMessage.query.filter_by(document_id=doc.id, tenant_id=tenant_id)
            .filter(StrategyChatMessage.id != user_msg.id)
            .order_by(StrategyChatMessage.created_at.asc())
            .all()
        )

    # Load enrichment data if research has been done
    enrichment_data = None
    if doc.enrichment_id:
        enrichment_data = _load_enrichment_data(doc.enrichment_id)
    else:
        # BL-054: Fallback — find self-company for the tenant
        self_company = Company.query.filter_by(
            tenant_id=tenant_id, is_self=True
        ).first()
        if self_company:
            doc.enrichment_id = self_company.id
            db.session.commit()
            enrichment_data = _load_enrichment_data(self_company.id)
            logger.info(
                "Self-company fallback: linked company %s to strategy doc %s",
                self_company.id,
                doc.id,
            )

    # Determine phase for system prompt (request param overrides doc phase)
    phase = data.get("phase") or doc.phase or "strategy"

    # Build prompt and messages
    system_prompt = build_system_prompt(
        tenant,
        doc,
        enrichment_data=enrichment_data,
        phase=phase,
        page_context=page_context,
    )
    messages = build_messages(history, message_text)

    client = _get_anthropic_client()

    if _wants_streaming(request):
        return _stream_response(
            client,
            system_prompt,
            messages,
            tenant_id,
            doc.id,
            user_msg,
            user_id,
        )
    else:
        return _sync_response(
            client,
            system_prompt,
            messages,
            tenant_id,
            doc.id,
            user_msg,
            user_id,
        )


def _stream_response(
    client, system_prompt, messages, tenant_id, doc_id, user_msg, user_id=None
):
    """Return an SSE streaming response with LLM chunks.

    If tools are registered, uses the agent executor (agentic loop with
    tool_start/tool_result events). Otherwise, falls back to simple
    stream_query for backward compatibility.

    DB operations (saving the assistant message) happen inside the generator
    using the app context, since the generator runs outside the request context.
    """
    # Capture the app for use inside the generator (runs outside request context)
    from flask import current_app

    app = current_app._get_current_object()

    # Check if any tools are registered
    tools = get_tools_for_api()

    if tools:
        return _stream_agent_response(
            client,
            system_prompt,
            messages,
            tools,
            tenant_id,
            doc_id,
            user_msg,
            user_id,
            app,
        )
    else:
        return _stream_simple_response(
            client,
            system_prompt,
            messages,
            tenant_id,
            doc_id,
            user_msg,
            user_id,
            app,
        )


def _stream_simple_response(
    client, system_prompt, messages, tenant_id, doc_id, user_msg, user_id, app
):
    """Backward-compatible simple streaming (no tools)."""
    start_time = time.time()

    def generate():
        full_text = []

        try:
            for chunk in client.stream_query(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=1024,
                temperature=0.4,
            ):
                full_text.append(chunk)
                yield "data: {}\n\n".format(
                    json.dumps({"type": "chunk", "text": chunk})
                )
        except Exception as e:
            logger.exception("LLM streaming error: %s", e)
            yield "data: {}\n\n".format(
                json.dumps({"type": "error", "message": str(e)})
            )
            return

        # Save the assistant message after streaming completes
        assistant_content = "".join(full_text)
        duration_ms = int((time.time() - start_time) * 1000)
        with app.app_context():
            assistant_msg = StrategyChatMessage(
                tenant_id=tenant_id,
                document_id=doc_id,
                role="assistant",
                content=assistant_content,
            )
            db.session.add(assistant_msg)

            # Log LLM usage from streaming token data
            usage = client.last_stream_usage
            log_llm_usage(
                tenant_id=tenant_id,
                operation="playbook_chat",
                model=usage.get("model", client.default_model),
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                provider="anthropic",
                user_id=user_id,
                duration_ms=duration_ms,
                metadata={
                    "document_id": str(doc_id),
                    "message_length": len(assistant_content),
                    "streaming": True,
                },
            )

            db.session.commit()
            msg_id = assistant_msg.id

            # Log assistant chat event
            if user_id:
                _log_event(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    doc_id=doc_id,
                    event_type="chat_assistant",
                    payload={"message": assistant_content[:500]},
                )

        yield "data: {}\n\n".format(json.dumps({"type": "done", "message_id": msg_id}))

    # Commit the user message before entering the generator
    db.session.commit()

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _stream_agent_response(
    client, system_prompt, messages, tools, tenant_id, doc_id, user_msg, user_id, app
):
    """Agent-mode streaming with tool-use loop.

    Uses execute_agent_turn() generator to handle tool calls. Yields SSE
    events for tool_start, tool_result, chunk, and done. Saves assistant
    message and tool execution records to the database.
    """
    import uuid as _uuid

    turn_id = str(_uuid.uuid4())

    tool_context = ToolContext(
        tenant_id=str(tenant_id),
        user_id=str(user_id) if user_id else None,
        document_id=str(doc_id) if doc_id else None,
        turn_id=turn_id,
    )

    def generate():
        full_text = []
        msg_id = None
        done_data = None

        try:
            for sse_event in execute_agent_turn(
                client=client,
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
                tool_context=tool_context,
                app=app,
            ):
                if sse_event.type == "chunk":
                    full_text.append(sse_event.data.get("text", ""))
                    yield "data: {}\n\n".format(
                        json.dumps(sse_event.data | {"type": "chunk"})
                    )

                elif sse_event.type == "tool_start":
                    yield "data: {}\n\n".format(
                        json.dumps(sse_event.data | {"type": "tool_start"})
                    )

                elif sse_event.type == "tool_result":
                    yield "data: {}\n\n".format(
                        json.dumps(sse_event.data | {"type": "tool_result"})
                    )

                elif sse_event.type == "done":
                    done_data = sse_event.data

        except Exception as e:
            logger.exception("Agent execution error: %s", e)
            yield "data: {}\n\n".format(
                json.dumps({"type": "error", "message": str(e)})
            )
            return

        # Save the assistant message after the agent turn completes
        assistant_content = "".join(full_text)
        with app.app_context():
            # Build metadata with tool call summary and cost totals
            extra = {}
            if done_data:
                extra = {
                    "tool_calls": done_data.get("tool_calls", []),
                    "llm_calls": len(done_data.get("tool_calls", [])) + 1,
                    "total_input_tokens": done_data.get("total_input_tokens", 0),
                    "total_output_tokens": done_data.get("total_output_tokens", 0),
                    "total_cost_usd": done_data.get("total_cost_usd", "0"),
                }

            assistant_msg = StrategyChatMessage(
                tenant_id=tenant_id,
                document_id=doc_id,
                role="assistant",
                content=assistant_content,
                extra=extra,
            )
            db.session.add(assistant_msg)
            db.session.flush()
            msg_id = assistant_msg.id

            # Log tool executions to the tool_executions table
            if done_data:
                for tc in done_data.get("tool_calls", []):
                    tool_exec = ToolExecution(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        document_id=doc_id,
                        chat_message_id=msg_id,
                        tool_name=tc.get("tool_name", ""),
                        input_args=tc.get("input_args", {}),
                        output_data=tc.get("output_data", {}),
                        is_error=tc.get("status") == "error",
                        error_message=tc.get("error_message"),
                        duration_ms=tc.get("duration_ms"),
                    )
                    db.session.add(tool_exec)

                # Log aggregated LLM usage
                log_llm_usage(
                    tenant_id=tenant_id,
                    operation="playbook_chat",
                    model=done_data.get("model", client.default_model),
                    input_tokens=done_data.get("total_input_tokens", 0),
                    output_tokens=done_data.get("total_output_tokens", 0),
                    user_id=user_id,
                    metadata={
                        "agent_turn": True,
                        "tool_calls": len(done_data.get("tool_calls", [])),
                    },
                )

            db.session.commit()

            # Log assistant chat event
            if user_id:
                _log_event(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    doc_id=doc_id,
                    event_type="chat_assistant",
                    payload={
                        "message": assistant_content[:500],
                        "tool_calls": done_data.get("tool_calls", [])
                        if done_data
                        else [],
                    },
                )

        # Emit done event with message_id, tool call summary, and
        # document_changed signal for frontend (WRITE + THINK features)
        done_payload = {"type": "done", "message_id": msg_id}
        if done_data and done_data.get("tool_calls"):
            done_payload["tool_calls"] = done_data["tool_calls"]

            # Check if any tool calls modified the strategy document
            strategy_edit_tools = {
                "update_strategy_section",
                "set_extracted_field",
                "append_to_section",
            }
            doc_changes = []
            for tc in done_data["tool_calls"]:
                tn = tc.get("tool_name", "")
                if tn in strategy_edit_tools and tc.get("status") == "success":
                    output = tc.get("output_data") or {}
                    if tn in ("update_strategy_section", "append_to_section"):
                        doc_changes.append(output.get("section", tn))
                    elif tn == "set_extracted_field":
                        doc_changes.append(
                            "data: {}".format(
                                (tc.get("input_args") or {}).get("path", "")
                            )
                        )

            if doc_changes:
                done_payload["document_changed"] = True
                if len(doc_changes) == 1:
                    done_payload["changes_summary"] = "Strategy updated: {}".format(
                        doc_changes[0]
                    )
                else:
                    done_payload["changes_summary"] = (
                        "Strategy updated: {} ({} changes)".format(
                            ", ".join(doc_changes), len(doc_changes)
                        )
                    )

        yield "data: {}\n\n".format(json.dumps(done_payload))

        # --- Proactive analysis follow-up ---
        # If strategy edits were made, generate a proactive analysis message
        # with context-aware suggestions. This appears as a second assistant
        # message in the conversation without user intervention.
        has_doc_changes = done_payload.get("document_changed", False)
        if has_doc_changes:
            try:
                with app.app_context():
                    # Load the freshly-updated strategy document
                    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
                    strategy_content = doc.content if doc else ""

                    # Load enrichment data for grounded suggestions
                    enrichment_data = None
                    if doc and doc.enrichment_id:
                        enrichment_data = _load_enrichment_data(doc.enrichment_id)

                    analysis_prompt = build_proactive_analysis_prompt(
                        strategy_content, enrichment_data
                    )

                # Signal the frontend that analysis is starting
                yield "data: {}\n\n".format(json.dumps({"type": "analysis_start"}))

                # Stream the analysis response (simple query, no tools)
                analysis_parts = []
                for chunk in client.stream_query(
                    messages=[{"role": "user", "content": analysis_prompt}],
                    system_prompt=system_prompt,
                    max_tokens=512,
                    temperature=0.4,
                ):
                    analysis_parts.append(chunk)
                    yield "data: {}\n\n".format(
                        json.dumps({"type": "analysis_chunk", "text": chunk})
                    )

                analysis_content = "".join(analysis_parts)

                # Save analysis as an assistant message
                analysis_msg_id = None
                with app.app_context():
                    analysis_msg = StrategyChatMessage(
                        tenant_id=tenant_id,
                        document_id=doc_id,
                        role="assistant",
                        content=analysis_content,
                        extra={"proactive_analysis": True},
                    )
                    db.session.add(analysis_msg)
                    db.session.flush()
                    analysis_msg_id = analysis_msg.id

                    # Log LLM usage for the analysis call
                    usage = client.last_stream_usage
                    log_llm_usage(
                        tenant_id=tenant_id,
                        operation="proactive_analysis",
                        model=usage.get("model", client.default_model),
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
                        provider="anthropic",
                        user_id=user_id,
                        metadata={
                            "document_id": str(doc_id),
                            "trigger": "strategy_edit",
                        },
                    )

                    db.session.commit()

                # Extract suggestion chips from the analysis text.
                # Look for numbered lines (e.g., "1. ...", "2. ...") and
                # extract a short actionable phrase from each.
                suggestions = _extract_suggestion_chips(analysis_content)

                yield "data: {}\n\n".format(
                    json.dumps(
                        {
                            "type": "analysis_done",
                            "message_id": analysis_msg_id,
                            "suggestions": suggestions,
                        }
                    )
                )

            except Exception as e:
                logger.warning("Proactive analysis failed (non-fatal): %s", e)
                # Non-fatal: the main response was already delivered

    # Commit the user message before entering the generator
    db.session.commit()

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _extract_suggestion_chips(analysis_text):
    """Extract short suggestion chips from a proactive analysis message.

    Looks for numbered lines (e.g. "1. Your ICP targets...Want me to...?")
    and extracts the question portion as a clickable chip. Falls back to
    the first sentence of each numbered line if no question is found.

    Args:
        analysis_text: The full analysis message text.

    Returns:
        list[str]: Up to 3 suggestion strings suitable for UI chips.
    """
    suggestions = []
    # Match numbered lines: "1. ...", "2. ...", etc.
    numbered = re.findall(r"^\d+[\.\)]\s*(.+)", analysis_text, re.MULTILINE)

    for line in numbered[:3]:
        # Try to extract a question (sentence ending with ?)
        questions = re.findall(r"([^.!?]*\?)", line)
        if questions:
            # Take the last question (usually the actionable one)
            chip = questions[-1].strip()
            # Clean up leading conjunctions
            for prefix in [
                "Want me to ",
                "Should I ",
                "Shall I ",
                "Would you like me to ",
            ]:
                if chip.startswith(prefix):
                    chip = "Yes, " + chip[0].lower() + chip[1:]
                    break
            suggestions.append(chip)
        else:
            # No question found -- use truncated line
            chip = line.strip()
            if len(chip) > 80:
                chip = chip[:77] + "..."
            suggestions.append(chip)

    return suggestions


def _sync_response(
    client, system_prompt, messages, tenant_id, doc_id, user_msg, user_id=None
):
    """Return a non-streaming JSON response with the full LLM reply.

    If tools are registered, consumes the agent executor loop collecting
    all events, then persists the assistant message and tool execution
    records. Otherwise, falls back to the simple stream_query path.
    """
    tools = get_tools_for_api()

    if tools:
        return _sync_agent_response(
            client,
            system_prompt,
            messages,
            tools,
            tenant_id,
            doc_id,
            user_msg,
            user_id,
        )

    # --- No-tools path (backward compatible) ---
    start_time = time.time()
    llm_error = False
    try:
        full_text = []
        for chunk in client.stream_query(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=1024,
            temperature=0.4,
        ):
            full_text.append(chunk)

        assistant_content = "".join(full_text)
    except Exception as e:
        logger.exception("LLM query error: %s", e)
        llm_error = True
        # Fall back to error message so the user message is still saved
        assistant_content = (
            "Sorry, I encountered an error generating a response. Please try again."
        )

    duration_ms = int((time.time() - start_time) * 1000)

    assistant_msg = StrategyChatMessage(
        tenant_id=tenant_id,
        document_id=doc_id,
        role="assistant",
        content=assistant_content,
    )
    db.session.add(assistant_msg)

    # Log LLM usage (skip if LLM call failed)
    if not llm_error:
        usage = client.last_stream_usage
        log_llm_usage(
            tenant_id=tenant_id,
            operation="playbook_chat",
            model=usage.get("model", client.default_model),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            provider="anthropic",
            user_id=user_id,
            duration_ms=duration_ms,
            metadata={
                "document_id": str(doc_id),
                "message_length": len(assistant_content),
                "streaming": False,
            },
        )

    db.session.commit()

    # Log assistant chat event
    if user_id:
        _log_event(
            tenant_id=tenant_id,
            user_id=user_id,
            doc_id=doc_id,
            event_type="chat_assistant",
            payload={"message": assistant_content[:500]},
        )

    return jsonify(
        {
            "user_message": user_msg.to_dict(),
            "assistant_message": assistant_msg.to_dict(),
        }
    ), 201


def _sync_agent_response(
    client,
    system_prompt,
    messages,
    tools,
    tenant_id,
    doc_id,
    user_msg,
    user_id,
):
    """Sync (non-streaming) response with agent tool-use loop.

    Collects all SSE events from execute_agent_turn(), persists the
    assistant message and tool execution records, and returns JSON.
    """
    import uuid as _uuid

    tool_context = ToolContext(
        tenant_id=str(tenant_id),
        user_id=str(user_id) if user_id else None,
        document_id=str(doc_id) if doc_id else None,
        turn_id=str(_uuid.uuid4()),
    )

    try:
        events = list(
            execute_agent_turn(
                client=client,
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
                tool_context=tool_context,
            )
        )
    except Exception as e:
        logger.exception("Agent sync execution error: %s", e)
        assistant_msg = StrategyChatMessage(
            tenant_id=tenant_id,
            document_id=doc_id,
            role="assistant",
            content="Sorry, I encountered an error generating a response. Please try again.",
        )
        db.session.add(assistant_msg)
        db.session.commit()
        return jsonify(
            {
                "user_message": user_msg.to_dict(),
                "assistant_message": assistant_msg.to_dict(),
            }
        ), 201

    text_parts = [e.data.get("text", "") for e in events if e.type == "chunk"]
    done_event = next((e for e in events if e.type == "done"), None)
    done_data = done_event.data if done_event else {}

    assistant_content = "".join(text_parts)

    # Build metadata with tool call summary and cost totals
    extra = {}
    if done_data:
        extra = {
            "tool_calls": done_data.get("tool_calls", []),
            "llm_calls": len(done_data.get("tool_calls", [])) + 1,
            "total_input_tokens": done_data.get("total_input_tokens", 0),
            "total_output_tokens": done_data.get("total_output_tokens", 0),
            "total_cost_usd": done_data.get("total_cost_usd", "0"),
        }

    assistant_msg = StrategyChatMessage(
        tenant_id=tenant_id,
        document_id=doc_id,
        role="assistant",
        content=assistant_content,
        extra=extra,
    )
    db.session.add(assistant_msg)
    db.session.flush()
    msg_id = assistant_msg.id

    # Log tool executions to the tool_executions table
    if done_data:
        for tc in done_data.get("tool_calls", []):
            tool_exec = ToolExecution(
                tenant_id=tenant_id,
                user_id=user_id,
                document_id=doc_id,
                chat_message_id=msg_id,
                tool_name=tc.get("tool_name", ""),
                input_args=tc.get("input_args", {}),
                output_data=tc.get("output_data", {}),
                is_error=tc.get("status") == "error",
                error_message=tc.get("error_message"),
                duration_ms=tc.get("duration_ms"),
            )
            db.session.add(tool_exec)

        # Log aggregated LLM usage
        log_llm_usage(
            tenant_id=tenant_id,
            operation="playbook_chat",
            model=done_data.get("model", client.default_model),
            input_tokens=done_data.get("total_input_tokens", 0),
            output_tokens=done_data.get("total_output_tokens", 0),
            user_id=user_id,
            metadata={
                "agent_turn": True,
                "tool_calls": len(done_data.get("tool_calls", [])),
            },
        )

    db.session.commit()

    # Log assistant chat event
    if user_id:
        _log_event(
            tenant_id=tenant_id,
            user_id=user_id,
            doc_id=doc_id,
            event_type="chat_assistant",
            payload={
                "message": assistant_content[:500],
                "tool_calls": done_data.get("tool_calls", []) if done_data else [],
            },
        )

    result = {
        "user_message": user_msg.to_dict(),
        "assistant_message": assistant_msg.to_dict(),
    }
    if done_data and done_data.get("tool_calls"):
        result["tool_calls"] = done_data["tool_calls"]

    return jsonify(result), 201
