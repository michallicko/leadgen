"""Message generation engine for campaigns.

Generates personalized outreach messages for each contact in a campaign
using Claude API. Runs as a background thread with progress tracking.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from decimal import Decimal

from ..models import Message, db
from .generation_prompts import SYSTEM_PROMPT, build_generation_prompt, CHANNEL_CONSTRAINTS
from .llm_logger import log_llm_usage, compute_cost

logger = logging.getLogger(__name__)

# Generation model config
GENERATION_MODEL = "claude-haiku-3-5-20241022"
GENERATION_PROVIDER = "anthropic"

# Estimated tokens per message (for cost estimation)
EST_INPUT_TOKENS = 800
EST_OUTPUT_TOKENS = 200


def estimate_generation_cost(template_config: list, total_contacts: int) -> dict:
    """Estimate the cost of generating messages for a campaign.

    Returns dict with total_cost, per_contact_cost, total_messages, and breakdown.
    """
    enabled_steps = [s for s in template_config if s.get("enabled")]
    total_messages = len(enabled_steps) * total_contacts

    per_message_cost = compute_cost(
        GENERATION_PROVIDER, GENERATION_MODEL,
        EST_INPUT_TOKENS, EST_OUTPUT_TOKENS,
    )
    total_cost = per_message_cost * total_messages
    per_contact_cost = per_message_cost * len(enabled_steps)

    return {
        "total_cost": float(total_cost),
        "per_contact_cost": float(per_contact_cost),
        "total_messages": total_messages,
        "enabled_steps": len(enabled_steps),
        "total_contacts": total_contacts,
        "model": GENERATION_MODEL,
        "breakdown": [
            {"step": s.get("step"), "label": s.get("label"), "channel": s.get("channel")}
            for s in enabled_steps
        ],
    }


def start_generation(app, campaign_id: str, tenant_id: str, user_id: str = None):
    """Start message generation in a background thread.

    Args:
        app: Flask app instance (for application context)
        campaign_id: UUID of the campaign
        tenant_id: UUID of the tenant
        user_id: optional UUID of the user who triggered generation
    """
    thread = threading.Thread(
        target=_run_generation,
        args=(app, campaign_id, tenant_id, user_id),
        daemon=True,
    )
    thread.start()
    return thread


def _run_generation(app, campaign_id: str, tenant_id: str, user_id: str):
    """Background thread: generate messages for all contacts in campaign."""
    with app.app_context():
        try:
            _generate_all(campaign_id, tenant_id, user_id)
        except Exception:
            logger.exception("Generation failed for campaign %s", campaign_id)
            # Mark campaign as review (partial results available)
            try:
                db.session.execute(
                    db.text("UPDATE campaigns SET status = 'review' WHERE id = :id"),
                    {"id": campaign_id},
                )
                db.session.commit()
            except Exception:
                logger.exception("Failed to update campaign status after error")


def _generate_all(campaign_id: str, tenant_id: str, user_id: str):
    """Core generation loop: iterate contacts × steps."""
    # Load campaign config
    campaign = db.session.execute(
        db.text("""
            SELECT template_config, generation_config, owner_id
            FROM campaigns WHERE id = :id AND tenant_id = :t
        """),
        {"id": campaign_id, "t": tenant_id},
    ).fetchone()

    if not campaign:
        logger.error("Campaign %s not found", campaign_id)
        return

    template_config = json.loads(campaign[0]) if isinstance(campaign[0], str) else (campaign[0] or [])
    generation_config = json.loads(campaign[1]) if isinstance(campaign[1], str) else (campaign[1] or {})
    owner_id = campaign[2]

    enabled_steps = [s for s in template_config if s.get("enabled")]
    if not enabled_steps:
        logger.warning("No enabled steps for campaign %s", campaign_id)
        db.session.execute(
            db.text("UPDATE campaigns SET status = 'review' WHERE id = :id"),
            {"id": campaign_id},
        )
        db.session.commit()
        return

    total_steps = len(enabled_steps)

    # Load contacts
    contacts = db.session.execute(
        db.text("""
            SELECT
                cc.id AS cc_id, cc.contact_id,
                ct.first_name, ct.last_name, ct.job_title,
                ct.email_address, ct.linkedin_url,
                ct.seniority_level, ct.department,
                ct.company_id
            FROM campaign_contacts cc
            JOIN contacts ct ON cc.contact_id = ct.id
            WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
                AND cc.status NOT IN ('excluded', 'generated', 'failed')
            ORDER BY ct.contact_score DESC NULLS LAST
        """),
        {"cid": campaign_id, "t": tenant_id},
    ).fetchall()

    total_contacts = len(contacts)
    generated_count = 0
    total_cost = Decimal("0")

    for i, contact_row in enumerate(contacts):
        cc_id = contact_row[0]
        contact_id = str(contact_row[1])

        try:
            # Mark contact as generating
            db.session.execute(
                db.text("UPDATE campaign_contacts SET status = 'generating' WHERE id = :id"),
                {"id": cc_id},
            )
            db.session.commit()

            # Load enrichment data
            contact_data = {
                "first_name": contact_row[2],
                "last_name": contact_row[3],
                "job_title": contact_row[4],
                "email_address": contact_row[5],
                "linkedin_url": contact_row[6],
                "seniority_level": contact_row[7],
                "department": contact_row[8],
            }
            company_id = str(contact_row[9]) if contact_row[9] else None
            company_data, enrichment_data = _load_enrichment_context(contact_id, company_id)

            # Generate each enabled step
            contact_cost = Decimal("0")
            for step in enabled_steps:
                msg_cost = _generate_single_message(
                    campaign_id=campaign_id,
                    tenant_id=tenant_id,
                    cc_id=cc_id,
                    contact_id=contact_id,
                    owner_id=owner_id,
                    contact_data=contact_data,
                    company_data=company_data,
                    enrichment_data=enrichment_data,
                    generation_config=generation_config,
                    step=step,
                    total_steps=total_steps,
                    user_id=user_id,
                )
                contact_cost += msg_cost

            # Mark contact as generated
            db.session.execute(
                db.text("""
                    UPDATE campaign_contacts
                    SET status = 'generated', generation_cost = :cost, generated_at = CURRENT_TIMESTAMP
                    WHERE id = :id
                """),
                {"cost": float(contact_cost), "id": cc_id},
            )
            generated_count += 1
            total_cost += contact_cost

        except Exception:
            logger.exception("Generation failed for contact %s in campaign %s", contact_id, campaign_id)
            db.session.rollback()
            db.session.execute(
                db.text("""
                    UPDATE campaign_contacts
                    SET status = 'failed', error = 'Generation error'
                    WHERE id = :id
                """),
                {"id": cc_id},
            )

        # Update campaign progress
        db.session.execute(
            db.text("""
                UPDATE campaigns
                SET generated_count = :gc, generation_cost = :cost
                WHERE id = :id
            """),
            {"gc": generated_count, "cost": float(total_cost), "id": campaign_id},
        )
        db.session.commit()

        # Small delay between contacts to avoid rate limits
        if i < total_contacts - 1:
            time.sleep(0.5)

    # Mark campaign as review
    db.session.execute(
        db.text("""
            UPDATE campaigns
            SET status = 'review', generation_completed_at = CURRENT_TIMESTAMP
            WHERE id = :id
        """),
        {"id": campaign_id},
    )
    db.session.commit()

    logger.info(
        "Generation complete: campaign=%s contacts=%d messages=%d cost=$%.4f",
        campaign_id, generated_count, generated_count * total_steps, float(total_cost),
    )


def _load_enrichment_context(contact_id: str, company_id: str) -> tuple[dict, dict]:
    """Load company and enrichment data for a contact."""
    company_data = {}
    enrichment_data = {"l2": {}, "person": {}}

    if company_id:
        row = db.session.execute(
            db.text("""
                SELECT name, domain, industry, hq_country, summary
                FROM companies WHERE id = :id
            """),
            {"id": company_id},
        ).fetchone()
        if row:
            company_data = {
                "name": row[0], "domain": row[1], "industry": row[2],
                "hq_country": row[3], "summary": row[4],
            }

        l2_row = db.session.execute(
            db.text("""
                SELECT company_intel, recent_news, ai_opportunities
                FROM company_enrichment_l2 WHERE company_id = :id
            """),
            {"id": company_id},
        ).fetchone()
        if l2_row:
            enrichment_data["l2"] = {
                "company_intel": l2_row[0],
                "recent_news": l2_row[1],
                "ai_opportunities": l2_row[2],
            }

    person_row = db.session.execute(
        db.text("""
            SELECT person_summary, relationship_synthesis
            FROM contact_enrichment WHERE contact_id = :id
        """),
        {"id": contact_id},
    ).fetchone()
    if person_row:
        enrichment_data["person"] = {
            "person_summary": person_row[0],
            "relationship_synthesis": person_row[1],
        }

    return company_data, enrichment_data


def _generate_single_message(
    *,
    campaign_id: str,
    tenant_id: str,
    cc_id: str,
    contact_id: str,
    owner_id: str,
    contact_data: dict,
    company_data: dict,
    enrichment_data: dict,
    generation_config: dict,
    step: dict,
    total_steps: int,
    user_id: str,
) -> Decimal:
    """Generate a single message for one contact × one step.

    Calls Claude API, parses response, saves Message, logs cost.
    Returns the cost of this generation call.
    """
    prompt = build_generation_prompt(
        channel=step["channel"],
        step_label=step.get("label", f"Step {step['step']}"),
        contact_data=contact_data,
        company_data=company_data,
        enrichment_data=enrichment_data,
        generation_config=generation_config,
        step_number=step["step"],
        total_steps=total_steps,
    )

    start_time = time.time()

    # Call Claude API
    import anthropic
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=GENERATION_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    duration_ms = int((time.time() - start_time) * 1000)

    # Parse response
    raw_text = response.content[0].text
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        # Try to extract JSON from response
        import re
        match = re.search(r'\{[^}]+\}', raw_text, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
        else:
            parsed = {"body": raw_text}

    subject = parsed.get("subject")
    body = parsed.get("body", raw_text)

    # Enforce channel constraints
    constraints = CHANNEL_CONSTRAINTS.get(step["channel"], {})
    max_chars = constraints.get("max_chars", 5000)
    if len(body) > max_chars:
        body = body[:max_chars]

    # Log cost
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost = compute_cost(GENERATION_PROVIDER, GENERATION_MODEL, input_tokens, output_tokens)

    log_llm_usage(
        tenant_id=tenant_id,
        operation="message_generation",
        model=GENERATION_MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        provider=GENERATION_PROVIDER,
        user_id=user_id,
        duration_ms=duration_ms,
        metadata={
            "campaign_id": campaign_id,
            "contact_id": contact_id,
            "channel": step["channel"],
            "step": step["step"],
        },
    )

    # Save message
    msg = Message(
        tenant_id=tenant_id,
        contact_id=contact_id,
        owner_id=owner_id,
        channel=step["channel"],
        sequence_step=step["step"],
        variant="a",
        label=step.get("label"),
        subject=subject,
        body=body,
        status="draft",
        tone=generation_config.get("tone", "professional"),
        language=generation_config.get("language", "en"),
        generation_cost_usd=float(cost),
        campaign_contact_id=cc_id,
    )
    db.session.add(msg)
    db.session.flush()

    return cost


def estimate_regeneration_cost(message_id: str, tenant_id: str) -> dict:
    """Estimate the cost of regenerating a single message.

    Counts tokens from the enrichment context to give a real estimate.
    Returns dict with cost, input_tokens, output_tokens, model.
    """
    msg = db.session.execute(
        db.text("""
            SELECT m.contact_id, ct.company_id, m.channel
            FROM messages m
            JOIN contacts ct ON m.contact_id = ct.id
            WHERE m.id = :id AND m.tenant_id = :t
        """),
        {"id": message_id, "t": tenant_id},
    ).fetchone()

    if not msg:
        return None

    contact_id = str(msg[0])
    company_id = str(msg[1]) if msg[1] else None
    channel = msg[2]

    # Load enrichment to estimate prompt size
    company_data, enrichment_data = _load_enrichment_context(contact_id, company_id)

    # Build a sample prompt to count tokens (approximate)
    sample_prompt = build_generation_prompt(
        channel=channel,
        step_label="Step 1",
        contact_data={"first_name": "X"},
        company_data=company_data,
        enrichment_data=enrichment_data,
        generation_config={},
        step_number=1,
        total_steps=1,
    )

    # Rough token estimate: ~4 chars per token
    est_input = max(len(sample_prompt) // 4, EST_INPUT_TOKENS)
    est_output = EST_OUTPUT_TOKENS

    cost = compute_cost(GENERATION_PROVIDER, GENERATION_MODEL, est_input, est_output)

    return {
        "estimated_cost": float(cost),
        "input_tokens": est_input,
        "output_tokens": est_output,
        "model": GENERATION_MODEL,
    }


def regenerate_message(
    message_id: str,
    tenant_id: str,
    user_id: str = None,
    language: str = None,
    formality: str = None,
    tone: str = None,
    instruction: str = None,
) -> dict:
    """Regenerate a single message with optional overrides.

    Preserves the original body/subject on first regeneration.
    Returns the updated message dict or None if message not found.
    """
    # Load message with context
    row = db.session.execute(
        db.text("""
            SELECT m.id, m.tenant_id, m.contact_id, m.owner_id,
                   m.channel, m.sequence_step, m.variant, m.label,
                   m.subject, m.body, m.status, m.tone, m.language,
                   m.generation_cost_usd, m.campaign_contact_id,
                   m.original_body, m.original_subject,
                   m.regen_count, m.regen_config,
                   ct.first_name, ct.last_name, ct.job_title,
                   ct.email_address, ct.linkedin_url,
                   ct.seniority_level, ct.department, ct.company_id
            FROM messages m
            JOIN contacts ct ON m.contact_id = ct.id
            WHERE m.id = :id AND m.tenant_id = :t
        """),
        {"id": message_id, "t": tenant_id},
    ).fetchone()

    if not row:
        return None

    contact_id = str(row[2])
    channel = row[4]
    sequence_step = row[5]
    label = row[7]
    current_subject = row[8]
    current_body = row[9]
    current_tone = row[11]
    current_language = row[12]
    cc_id = row[14]
    original_body = row[15]
    original_subject = row[16]
    regen_count = row[17] or 0
    company_id = str(row[27]) if row[27] else None

    # Preserve originals on first regen/edit
    if original_body is None:
        original_body = current_body
    if original_subject is None and current_subject:
        original_subject = current_subject

    # Load enrichment context
    contact_data = {
        "first_name": row[19],
        "last_name": row[20],
        "job_title": row[21],
        "email_address": row[22],
        "linkedin_url": row[23],
        "seniority_level": row[24],
        "department": row[25],
    }
    company_data, enrichment_data = _load_enrichment_context(contact_id, company_id)

    # Load campaign generation config
    campaign_config = {}
    if cc_id:
        camp_row = db.session.execute(
            db.text("""
                SELECT c.generation_config, c.template_config
                FROM campaigns c
                JOIN campaign_contacts cc ON cc.campaign_id = c.id
                WHERE cc.id = :cc_id
            """),
            {"cc_id": cc_id},
        ).fetchone()
        if camp_row:
            campaign_config = json.loads(camp_row[0]) if isinstance(camp_row[0], str) else (camp_row[0] or {})
            template_config = json.loads(camp_row[1]) if isinstance(camp_row[1], str) else (camp_row[1] or [])
            total_steps = len([s for s in template_config if s.get("enabled")])
        else:
            total_steps = 1
    else:
        total_steps = 1

    # Apply overrides
    effective_language = language or current_language or campaign_config.get("language", "en")
    effective_tone = tone or current_tone or campaign_config.get("tone", "professional")

    gen_config = dict(campaign_config)
    gen_config["language"] = effective_language
    gen_config["tone"] = effective_tone

    prompt = build_generation_prompt(
        channel=channel,
        step_label=label or f"Step {sequence_step}",
        contact_data=contact_data,
        company_data=company_data,
        enrichment_data=enrichment_data,
        generation_config=gen_config,
        step_number=sequence_step or 1,
        total_steps=total_steps,
        formality=formality,
        per_message_instruction=instruction,
    )

    start_time = time.time()

    import anthropic
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=GENERATION_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    duration_ms = int((time.time() - start_time) * 1000)

    # Parse response
    raw_text = response.content[0].text
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{[^}]+\}', raw_text, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
        else:
            parsed = {"body": raw_text}

    new_subject = parsed.get("subject")
    new_body = parsed.get("body", raw_text)

    constraints = CHANNEL_CONSTRAINTS.get(channel, {})
    max_chars = constraints.get("max_chars", 5000)
    if len(new_body) > max_chars:
        new_body = new_body[:max_chars]

    # Log cost
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost = compute_cost(GENERATION_PROVIDER, GENERATION_MODEL, input_tokens, output_tokens)

    log_llm_usage(
        tenant_id=tenant_id,
        operation="message_regeneration",
        model=GENERATION_MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        provider=GENERATION_PROVIDER,
        user_id=user_id,
        duration_ms=duration_ms,
        metadata={
            "message_id": message_id,
            "contact_id": contact_id,
            "channel": channel,
            "overrides": {
                "language": language,
                "formality": formality,
                "tone": tone,
                "instruction": instruction,
            },
        },
    )

    # Store regen config
    regen_config = {
        "language": effective_language,
        "formality": formality,
        "tone": effective_tone,
        "instruction": instruction,
    }

    # Update message
    db.session.execute(
        db.text("""
            UPDATE messages
            SET body = :body,
                subject = :subject,
                original_body = :orig_body,
                original_subject = :orig_subject,
                regen_count = :regen_count,
                regen_config = :regen_config,
                generation_cost_usd = COALESCE(generation_cost_usd, 0) + :cost,
                language = :language,
                tone = :tone,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
        """),
        {
            "body": new_body,
            "subject": new_subject,
            "orig_body": original_body,
            "orig_subject": original_subject,
            "regen_count": regen_count + 1,
            "regen_config": json.dumps(regen_config),
            "cost": float(cost),
            "language": effective_language,
            "tone": effective_tone,
            "id": message_id,
        },
    )
    db.session.commit()

    return {
        "id": message_id,
        "body": new_body,
        "subject": new_subject,
        "original_body": original_body,
        "original_subject": original_subject,
        "regen_count": regen_count + 1,
        "regen_config": regen_config,
        "language": effective_language,
        "tone": effective_tone,
        "generation_cost_usd": float(cost),
    }
