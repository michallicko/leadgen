"""Message tools for the Outreach Agent subgraph.

Provides tool handlers for generating, listing, updating, and managing
outreach messages. All DB queries filter by tenant_id for multi-tenant
isolation.

Tools (5): generate_message, list_messages, update_message,
get_message_templates, generate_variants.

Registered with the AGENT tool registry at app startup.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from ..models import Contact, Company, Message, db
from ..services.tool_registry import ToolContext, ToolDefinition

logger = logging.getLogger(__name__)

# Message templates/frameworks available for generation
MESSAGE_TEMPLATES = [
    {
        "id": "pain_point",
        "name": "Pain Point",
        "description": "Lead with a specific pain point the prospect faces, then position your solution.",
        "structure": "Pain → Empathy → Solution → CTA",
        "best_for": "Cold outreach to senior decision-makers",
    },
    {
        "id": "mutual_connection",
        "name": "Mutual Connection",
        "description": "Reference a shared connection, event, or context to build rapport.",
        "structure": "Connection → Relevance → Value → CTA",
        "best_for": "Warm outreach via LinkedIn",
    },
    {
        "id": "insight_led",
        "name": "Insight-Led",
        "description": "Share a relevant industry insight or data point, then connect to your offering.",
        "structure": "Insight → Implication → How we help → CTA",
        "best_for": "Thought leadership positioning",
    },
    {
        "id": "trigger_event",
        "name": "Trigger Event",
        "description": "Reference a recent company event (funding, hire, product launch) as conversation starter.",
        "structure": "Event → Congratulations → Relevance → CTA",
        "best_for": "Time-sensitive outreach after news",
    },
    {
        "id": "value_first",
        "name": "Value First",
        "description": "Offer something valuable upfront (report, benchmark, introduction) before asking.",
        "structure": "Gift → Context → Why relevant → Soft CTA",
        "best_for": "Building goodwill with skeptical prospects",
    },
]


def _get_contact_context(contact_id: str, tenant_id: str) -> dict | None:
    """Fetch contact + company enrichment data for message personalization."""
    contact = Contact.query.filter_by(id=contact_id, tenant_id=tenant_id).first()
    if not contact:
        return None

    ctx = {
        "contact_id": str(contact.id),
        "first_name": contact.first_name,
        "last_name": contact.last_name or "",
        "full_name": contact.full_name,
        "job_title": contact.job_title or "",
        "email": contact.email_address or "",
        "linkedin_url": contact.linkedin_url or "",
        "seniority_level": contact.seniority_level or "",
        "department": contact.department or "",
    }

    if contact.company_id:
        company = Company.query.filter_by(
            id=contact.company_id, tenant_id=tenant_id
        ).first()
        if company:
            ctx["company"] = {
                "name": company.name,
                "domain": company.domain or "",
                "industry": company.industry or "",
                "employee_count": company.employee_count,
                "description": company.description or "",
            }

    return ctx


def generate_message(args: dict, ctx: ToolContext) -> dict:
    """Generate a personalized outreach message for a contact.

    Args:
        args: {
            "contact_id": "uuid",
            "channel": "linkedin" | "email" (default: "linkedin"),
            "template": template id (optional),
            "tone": "professional" | "casual" | "friendly" (default: "professional"),
            "context_notes": additional context for personalization (optional)
        }
        ctx: ToolContext with tenant_id.

    Returns:
        {"id": "uuid", "contact_id": ..., "subject": ..., "body": ...,
         "channel": ..., "status": "draft", "contact_context": {...}}
    """
    contact_id = args.get("contact_id")
    if not contact_id:
        return {"error": "contact_id is required"}

    channel = args.get("channel", "linkedin")
    tone = args.get("tone", "professional")
    template_id = args.get("template")
    context_notes = args.get("context_notes", "")

    # Fetch contact context for personalization
    contact_ctx = _get_contact_context(contact_id, ctx.tenant_id)
    if not contact_ctx:
        return {"error": "Contact not found: {}".format(contact_id)}

    # Build personalized message using contact data
    first_name = contact_ctx.get("first_name", "there")
    job_title = contact_ctx.get("job_title", "")
    company_name = (contact_ctx.get("company") or {}).get("name", "your company")
    industry = (contact_ctx.get("company") or {}).get("industry", "")

    # Select template framework
    template_info = None
    if template_id:
        template_info = next(
            (t for t in MESSAGE_TEMPLATES if t["id"] == template_id), None
        )

    # Generate subject and body based on channel and context
    if channel == "email":
        subject = "Quick question about {} at {}".format(
            job_title or "your role", company_name
        )
        body = _build_email_body(
            first_name,
            job_title,
            company_name,
            industry,
            tone,
            template_info,
            context_notes,
        )
    else:
        subject = None
        body = _build_linkedin_body(
            first_name,
            job_title,
            company_name,
            industry,
            tone,
            template_info,
            context_notes,
        )

    # Create message record
    message_id = str(uuid.uuid4())
    message = Message(
        id=message_id,
        tenant_id=ctx.tenant_id,
        contact_id=contact_id,
        channel=channel,
        subject=subject,
        body=body,
        status="draft",
        tone=tone,
        language="en",
    )
    db.session.add(message)
    db.session.commit()

    return {
        "id": message_id,
        "contact_id": contact_id,
        "subject": subject,
        "body": body,
        "channel": channel,
        "status": "draft",
        "tone": tone,
        "template_used": template_id,
        "contact_context": contact_ctx,
        "summary": "Generated {} message for {} at {}".format(
            channel, first_name, company_name
        ),
    }


def _build_email_body(
    first_name: str,
    job_title: str,
    company_name: str,
    industry: str,
    tone: str,
    template_info: dict | None,
    context_notes: str = "",
) -> str:
    """Build a draft email body. This is a structured template that the LLM
    will further personalize in the agent loop."""
    greeting = "Hi {}".format(first_name)
    if tone == "casual":
        greeting = "Hey {}".format(first_name)

    role_mention = ""
    if job_title:
        role_mention = " as {}".format(job_title)

    industry_mention = ""
    if industry:
        industry_mention = " in the {} space".format(industry)

    template_hint = ""
    if template_info:
        template_hint = "\n\n[Framework: {}]".format(template_info["structure"])

    context_hint = ""
    if context_notes:
        context_hint = "\n\n[Context: {}]".format(context_notes)

    return (
        "{},\n\n"
        "I noticed your work{} at {}{} and wanted to reach out.\n\n"
        "[Personalized value proposition based on their company and role]\n\n"
        "Would you be open to a brief conversation about how we might help?\n\n"
        "Best regards{}{}".format(
            greeting,
            role_mention,
            company_name,
            industry_mention,
            template_hint,
            context_hint,
        )
    )


def _build_linkedin_body(
    first_name: str,
    job_title: str,
    company_name: str,
    industry: str,
    tone: str,
    template_info: dict | None,
    context_notes: str = "",
) -> str:
    """Build a draft LinkedIn message body."""
    greeting = "Hi {}".format(first_name)
    if tone == "casual":
        greeting = "Hey {}".format(first_name)

    role_mention = ""
    if job_title:
        role_mention = " in your role as {}".format(job_title)

    context_hint = ""
    if context_notes:
        context_hint = "\n\n[Context: {}]".format(context_notes)

    return (
        "{} — I came across your profile{} at {} and was impressed "
        "by what the team is doing.\n\n"
        "[Personalized hook based on their background]\n\n"
        "Would love to connect and share some ideas.{}"
    ).format(greeting, role_mention, company_name, context_hint)


def list_messages(args: dict, ctx: ToolContext) -> dict:
    """List messages for a contact or tag (batch).

    Args:
        args: {
            "contact_id": "uuid" (optional),
            "tag_id": "uuid" (optional),
            "status": "draft" | "approved" | "sent" | "rejected" (optional),
            "limit": int (default 20, max 50)
        }
        ctx: ToolContext with tenant_id.

    Returns:
        {"messages": [...], "total": int}
    """
    contact_id = args.get("contact_id")
    tag_id = args.get("tag_id")
    status = args.get("status")
    limit = min(args.get("limit", 20), 50)

    query = Message.query.filter_by(tenant_id=ctx.tenant_id)

    if contact_id:
        query = query.filter_by(contact_id=contact_id)
    if tag_id:
        query = query.filter_by(tag_id=tag_id)
    if status:
        query = query.filter_by(status=status)

    query = query.order_by(Message.created_at.desc())
    total = query.count()
    messages = query.limit(limit).all()

    return {
        "messages": [
            {
                "id": str(m.id),
                "contact_id": str(m.contact_id),
                "channel": m.channel,
                "subject": m.subject,
                "body": m.body[:200] + "..."
                if m.body and len(m.body) > 200
                else m.body,
                "status": m.status,
                "tone": m.tone,
                "variant": m.variant,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
        "total": total,
        "summary": "Found {} messages".format(total),
    }


def update_message(args: dict, ctx: ToolContext) -> dict:
    """Update a message's content, status, or review notes.

    Args:
        args: {
            "message_id": "uuid",
            "body": new body text (optional),
            "subject": new subject (optional),
            "status": "draft" | "approved" | "rejected" (optional),
            "review_notes": reviewer feedback (optional),
            "tone": new tone (optional)
        }
        ctx: ToolContext with tenant_id.

    Returns:
        {"id": "uuid", "status": ..., "updated_fields": [...]}
    """
    message_id = args.get("message_id")
    if not message_id:
        return {"error": "message_id is required"}

    message = Message.query.filter_by(id=message_id, tenant_id=ctx.tenant_id).first()
    if not message:
        return {"error": "Message not found: {}".format(message_id)}

    updated_fields = []

    if "body" in args:
        # Track original before first edit
        if not message.original_body:
            message.original_body = message.body
        message.body = args["body"]
        updated_fields.append("body")

    if "subject" in args:
        if not message.original_subject:
            message.original_subject = message.subject
        message.subject = args["subject"]
        updated_fields.append("subject")

    if "status" in args:
        new_status = args["status"]
        # "sent" is not allowed here — it is set exclusively by the campaign
        # system when a message is actually dispatched via Lemlist/LinkedIn.
        if new_status in ("draft", "approved", "rejected"):
            message.status = new_status
            if new_status == "approved":
                message.approved_at = datetime.now(timezone.utc)
            updated_fields.append("status")

    if "review_notes" in args:
        message.review_notes = args["review_notes"]
        updated_fields.append("review_notes")

    if "tone" in args:
        message.tone = args["tone"]
        updated_fields.append("tone")

    if updated_fields:
        message.updated_at = datetime.now(timezone.utc)
        db.session.commit()

    return {
        "id": str(message.id),
        "status": message.status,
        "updated_fields": updated_fields,
        "summary": "Updated message: {}".format(", ".join(updated_fields)),
    }


def get_message_templates(args: dict, ctx: ToolContext) -> dict:
    """Return available message templates/frameworks.

    Args:
        args: {} (no parameters needed)
        ctx: ToolContext (unused but required by interface).

    Returns:
        {"templates": [...]}
    """
    return {
        "templates": MESSAGE_TEMPLATES,
        "summary": "Returned {} message templates".format(len(MESSAGE_TEMPLATES)),
    }


def generate_variants(args: dict, ctx: ToolContext) -> dict:
    """Generate an A/B variant of an existing message with a different angle.

    Args:
        args: {
            "message_id": "uuid" of the original message,
            "angle": description of the variant angle/approach,
            "tone": optional tone override
        }
        ctx: ToolContext with tenant_id.

    Returns:
        {"id": "uuid", "variant": "b", "body": ..., "original_message_id": ...}
    """
    message_id = args.get("message_id")
    if not message_id:
        return {"error": "message_id is required"}

    angle = args.get("angle", "alternative approach")

    original = Message.query.filter_by(id=message_id, tenant_id=ctx.tenant_id).first()
    if not original:
        return {"error": "Original message not found: {}".format(message_id)}

    # Determine variant label (b, c, d...)
    existing_variants = (
        Message.query.filter_by(
            tenant_id=ctx.tenant_id,
            contact_id=original.contact_id,
            channel=original.channel,
        )
        .filter(Message.variant_group == (original.variant_group or original.id))
        .count()
    )
    if existing_variants >= 26:
        return {"error": "Maximum 26 variants per message"}
    variant_label = chr(ord("a") + existing_variants)

    # Create variant message
    variant_id = str(uuid.uuid4())
    variant_group = str(original.variant_group or original.id)

    variant_body = "[Variant {}: {}]\n\n{}".format(
        variant_label.upper(), angle, original.body
    )

    variant_msg = Message(
        id=variant_id,
        tenant_id=ctx.tenant_id,
        contact_id=original.contact_id,
        owner_id=original.owner_id,
        tag_id=original.tag_id,
        channel=original.channel,
        sequence_step=original.sequence_step,
        variant=variant_label,
        subject=original.subject,
        body=variant_body,
        status="draft",
        tone=args.get("tone", original.tone),
        language=original.language,
        variant_group=variant_group,
        variant_angle=angle,
    )
    db.session.add(variant_msg)
    db.session.commit()

    return {
        "id": variant_id,
        "variant": variant_label,
        "body": variant_body,
        "channel": original.channel,
        "original_message_id": str(original.id),
        "variant_group": variant_group,
        "angle": angle,
        "summary": "Created variant {} with angle: {}".format(
            variant_label.upper(), angle
        ),
    }


# ---------------------------------------------------------------------------
# Tool definitions for registry
# ---------------------------------------------------------------------------

MESSAGE_TOOLS = [
    ToolDefinition(
        name="generate_message",
        description=(
            "Generate a personalized outreach message for a contact. "
            "Uses the contact's enrichment data, company context, and "
            "strategy positioning to create a tailored message. "
            "Returns the draft message with contact context."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "contact_id": {
                    "type": "string",
                    "description": "UUID of the contact to generate a message for.",
                },
                "channel": {
                    "type": "string",
                    "enum": ["linkedin", "email"],
                    "description": "Message channel. Default: linkedin.",
                },
                "template": {
                    "type": "string",
                    "description": (
                        "Template framework ID (pain_point, mutual_connection, "
                        "insight_led, trigger_event, value_first). Optional."
                    ),
                },
                "tone": {
                    "type": "string",
                    "enum": ["professional", "casual", "friendly"],
                    "description": "Message tone. Default: professional.",
                },
                "context_notes": {
                    "type": "string",
                    "description": "Additional context for personalization.",
                },
            },
            "required": ["contact_id"],
        },
        handler=generate_message,
    ),
    ToolDefinition(
        name="list_messages",
        description=(
            "List outreach messages for a contact or batch. "
            "Filter by contact, tag (batch), or status. "
            "Returns message summaries with truncated bodies."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "contact_id": {
                    "type": "string",
                    "description": "Filter by contact UUID.",
                },
                "tag_id": {
                    "type": "string",
                    "description": "Filter by tag/batch UUID.",
                },
                "status": {
                    "type": "string",
                    "enum": ["draft", "approved", "sent", "rejected"],
                    "description": "Filter by message status.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max messages to return (default 20, max 50).",
                },
            },
        },
        handler=list_messages,
    ),
    ToolDefinition(
        name="update_message",
        description=(
            "Edit or update an outreach message. Can change body, subject, "
            "status (approve/reject), tone, or add review notes. "
            "Tracks original content before edits."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "UUID of the message to update.",
                },
                "body": {
                    "type": "string",
                    "description": "New message body text.",
                },
                "subject": {
                    "type": "string",
                    "description": "New email subject line.",
                },
                "status": {
                    "type": "string",
                    "enum": ["draft", "approved", "rejected"],
                    "description": "New message status.",
                },
                "review_notes": {
                    "type": "string",
                    "description": "Reviewer feedback or notes.",
                },
                "tone": {
                    "type": "string",
                    "enum": ["professional", "casual", "friendly"],
                    "description": "New message tone.",
                },
            },
            "required": ["message_id"],
        },
        handler=update_message,
    ),
    ToolDefinition(
        name="get_message_templates",
        description=(
            "Get available message templates and frameworks. "
            "Returns template names, descriptions, structures, and "
            "best-use-case recommendations. Use before generate_message "
            "to pick the right framework."
        ),
        input_schema={
            "type": "object",
            "properties": {},
        },
        handler=get_message_templates,
    ),
    ToolDefinition(
        name="generate_variants",
        description=(
            "Create an A/B test variant of an existing message with a "
            "different angle or tone. The variant is linked to the original "
            "via variant_group for comparison tracking."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "UUID of the original message to create a variant of.",
                },
                "angle": {
                    "type": "string",
                    "description": (
                        "Description of the variant's different angle or approach "
                        "(e.g., 'focus on cost savings', 'lead with social proof')."
                    ),
                },
                "tone": {
                    "type": "string",
                    "enum": ["professional", "casual", "friendly"],
                    "description": "Optional tone override for the variant.",
                },
            },
            "required": ["message_id"],
        },
        handler=generate_variants,
    ),
]
