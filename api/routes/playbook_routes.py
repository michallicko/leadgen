"""Playbook (GTM Strategy) API routes."""

import json
import logging
import os
import re
import threading

from flask import Blueprint, Response, jsonify, request

from ..auth import require_auth, resolve_tenant
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
    Tenant,
    db,
)
from ..services.anthropic_client import AnthropicClient
from ..services.playbook_service import (
    build_extraction_prompt,
    build_messages,
    build_seeded_template,
    build_system_prompt,
)

logger = logging.getLogger(__name__)

playbook_bp = Blueprint("playbook", __name__)


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

    return jsonify(doc.to_dict()), 200


@playbook_bp.route("/api/playbook", methods=["PUT"])
@require_auth
def update_playbook():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    data = request.get_json(silent=True) or {}

    content = data.get("content", "")
    status = data.get("status")

    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc:
        return jsonify({"error": "No strategy document found"}), 404

    doc.content = content
    doc.version = doc.version + 1
    doc.updated_by = getattr(request, "user_id", None)
    if status:
        doc.status = status

    db.session.commit()
    return jsonify(doc.to_dict()), 200


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

    # Strip markdown code fences if the LLM wraps the JSON
    stripped = re.sub(r"```(?:json)?\s*(.*?)\s*```", r"\1", raw_text, flags=re.DOTALL)

    try:
        extracted_data = json.loads(stripped)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("LLM returned invalid JSON: %s", raw_text[:200])
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


def _run_self_research(app, company_id, tenant_id):
    """Run L1 + L2 enrichment in a background thread for self-company research."""
    with app.app_context():
        try:
            from api.services.l1_enricher import enrich_l1
            from api.services.l2_enricher import enrich_l2

            logger.info("Starting self-research for company %s", company_id)

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
                doc.content = build_seeded_template(doc.objective, enrichment_data)
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
                            doc.objective, enrichment_data
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
    domain = data.get("domain")
    objective = data.get("objective")

    # Fall back to tenant's domain if none provided
    if not domain:
        tenant = db.session.get(Tenant, tenant_id)
        domain = tenant.domain if tenant else None

    if not domain:
        return jsonify(
            {"error": "Domain is required (provide in body or set on tenant)"}
        ), 400

    # Derive company name from domain (strip TLD, capitalize)
    # e.g., "notion.so" → "Notion", "stripe.com" → "Stripe"
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
        daemon=True,
        name="self-research-{}".format(company.id),
    )
    t.start()

    return jsonify(
        {
            "status": "triggered",
            "company_id": company.id,
            "domain": company.domain,
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

    messages = (
        StrategyChatMessage.query.filter_by(document_id=doc.id)
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

    doc = _get_or_create_document(tenant_id)
    tenant = db.session.get(Tenant, tenant_id)
    user_id = getattr(request, "user_id", None)

    # Save the user message before any LLM work
    user_msg = StrategyChatMessage(
        tenant_id=tenant_id,
        document_id=doc.id,
        role="user",
        content=message_text,
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

    # Load chat history for context
    history = (
        StrategyChatMessage.query.filter_by(document_id=doc.id)
        .filter(StrategyChatMessage.id != user_msg.id)
        .order_by(StrategyChatMessage.created_at.asc())
        .all()
    )

    # Load enrichment data if research has been done
    enrichment_data = None
    if doc.enrichment_id:
        enrichment_data = _load_enrichment_data(doc.enrichment_id)

    # Determine phase for system prompt (request param overrides doc phase)
    phase = data.get("phase") or doc.phase or "strategy"

    # Build prompt and messages
    system_prompt = build_system_prompt(
        tenant, doc, enrichment_data=enrichment_data, phase=phase
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

    DB operations (saving the assistant message) happen inside the generator
    using the app context, since the generator runs outside the request context.
    """
    # Capture the app for use inside the generator (runs outside request context)
    from flask import current_app

    app = current_app._get_current_object()

    def generate():
        full_text = []

        try:
            for chunk in client.stream_query(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=4096,
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
        with app.app_context():
            assistant_msg = StrategyChatMessage(
                tenant_id=tenant_id,
                document_id=doc_id,
                role="assistant",
                content=assistant_content,
            )
            db.session.add(assistant_msg)
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


def _sync_response(
    client, system_prompt, messages, tenant_id, doc_id, user_msg, user_id=None
):
    """Return a non-streaming JSON response with the full LLM reply."""
    try:
        full_text = []
        for chunk in client.stream_query(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=4096,
            temperature=0.4,
        ):
            full_text.append(chunk)

        assistant_content = "".join(full_text)
    except Exception as e:
        logger.exception("LLM query error: %s", e)
        # Fall back to error message so the user message is still saved
        assistant_content = (
            "Sorry, I encountered an error generating a response. Please try again."
        )

    assistant_msg = StrategyChatMessage(
        tenant_id=tenant_id,
        document_id=doc_id,
        role="assistant",
        content=assistant_content,
    )
    db.session.add(assistant_msg)
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
