"""Resend email send service for campaign outreach.

Handles dispatching approved email messages via the Resend API,
with idempotent send tracking via EmailSendLog.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from ..models import (
    Campaign,
    CampaignContact,
    Contact,
    EmailSendLog,
    Message,
    Tenant,
    db,
)

logger = logging.getLogger(__name__)

# Rate limit: 100ms between sends (Resend allows 10 req/s)
SEND_DELAY_SECONDS = 0.1


def send_campaign_emails(campaign_id: str, tenant_id: str) -> dict:
    """Send all approved email messages for a campaign via Resend.

    Idempotent: skips messages that already have a non-failed EmailSendLog entry.

    Args:
        campaign_id: UUID of the campaign
        tenant_id: UUID of the tenant

    Returns:
        dict with sent_count, failed_count, skipped_count, total
    """
    import resend

    # 1. Load campaign and validate sender_config
    campaign = db.session.get(Campaign, campaign_id)
    if not campaign or str(campaign.tenant_id) != str(tenant_id):
        raise ValueError("Campaign not found")

    sender_config = campaign.sender_config
    if isinstance(sender_config, str):
        import json

        sender_config = json.loads(sender_config)
    sender_config = sender_config or {}

    from_email = sender_config.get("from_email")
    from_name = sender_config.get("from_name")
    reply_to = sender_config.get("reply_to")

    if not from_email:
        raise ValueError("Campaign sender_config missing from_email")

    # 2. Configure Resend API key from tenant settings
    tenant = db.session.get(Tenant, tenant_id)
    if not tenant:
        raise ValueError("Tenant not found")

    tenant_settings = tenant.settings
    if isinstance(tenant_settings, str):
        import json

        tenant_settings = json.loads(tenant_settings)
    tenant_settings = tenant_settings or {}

    api_key = tenant_settings.get("resend_api_key")
    if not api_key:
        raise ValueError("Tenant settings missing resend_api_key")

    resend.api_key = api_key

    # 3. Load approved email messages not yet sent (idempotent check)
    messages = (
        db.session.query(Message, Contact, CampaignContact)
        .join(CampaignContact, Message.campaign_contact_id == CampaignContact.id)
        .join(Contact, Message.contact_id == Contact.id)
        .filter(
            CampaignContact.campaign_id == campaign_id,
            CampaignContact.tenant_id == tenant_id,
            Message.status == "approved",
            Message.channel == "email",
        )
        .all()
    )

    sent_count = 0
    failed_count = 0
    skipped_count = 0

    for message, contact, cc in messages:
        # Idempotent: check if already sent (non-failed log exists)
        existing_log = (
            db.session.query(EmailSendLog)
            .filter(
                EmailSendLog.message_id == message.id,
                EmailSendLog.tenant_id == tenant_id,
                EmailSendLog.status != "failed",
            )
            .first()
        )
        if existing_log:
            skipped_count += 1
            continue

        to_email = contact.email_address
        if not to_email:
            # Create a failed log for contacts without email
            log = EmailSendLog(
                tenant_id=tenant_id,
                message_id=message.id,
                status="failed",
                from_email=from_email,
                error="Contact has no email address",
            )
            db.session.add(log)
            db.session.commit()
            failed_count += 1
            continue

        # Create queued log entry
        log = EmailSendLog(
            tenant_id=tenant_id,
            message_id=message.id,
            status="queued",
            from_email=from_email,
            to_email=to_email,
        )
        db.session.add(log)
        db.session.flush()

        # Build the email body as HTML
        body_html = _render_body_html(message.body)
        sender = f"{from_name} <{from_email}>" if from_name else from_email

        try:
            result = _send_single_email(
                to_email=to_email,
                sender=sender,
                reply_to=reply_to,
                subject=message.subject or "(no subject)",
                body_html=body_html,
            )

            # Update log with success
            log.resend_message_id = result.get("id")
            log.status = "sent"
            log.sent_at = datetime.now(timezone.utc)

            # Update message sent_at
            message.sent_at = datetime.now(timezone.utc)

            db.session.commit()
            sent_count += 1

        except Exception as e:
            logger.error("Failed to send email for message %s: %s", message.id, str(e))
            log.status = "failed"
            log.error = str(e)[:500]
            db.session.commit()
            failed_count += 1

        # Rate limit delay
        time.sleep(SEND_DELAY_SECONDS)

    return {
        "sent_count": sent_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "total": sent_count + failed_count + skipped_count,
    }


def _send_single_email(
    *,
    to_email: str,
    sender: str,
    reply_to: str | None,
    subject: str,
    body_html: str,
) -> dict:
    """Send a single email via the Resend API.

    Args:
        to_email: recipient email address
        sender: formatted sender (e.g. "Name <email>" or just "email")
        reply_to: optional reply-to address
        subject: email subject line
        body_html: HTML body content

    Returns:
        dict with Resend response (includes 'id')

    Raises:
        Exception on API error
    """
    import resend

    params = {
        "from_": sender,
        "to": [to_email],
        "subject": subject,
        "html": body_html,
    }
    if reply_to:
        params["reply_to"] = [reply_to]

    response = resend.Emails.send(params)

    # resend SDK returns an object with .id, convert to dict
    if hasattr(response, "id"):
        return {"id": response.id}
    if isinstance(response, dict):
        return response
    return {"id": str(response)}


def _render_body_html(body: str) -> str:
    """Render message body as HTML.

    For now, wraps plain text in basic HTML with proper formatting.
    Phase 2 will add template support.
    """
    if not body:
        return "<p></p>"

    # If body already contains HTML tags, return as-is
    if "<" in body and ">" in body:
        return body

    # Convert plain text to HTML paragraphs
    paragraphs = body.strip().split("\n\n")
    html_parts = []
    for para in paragraphs:
        # Convert single newlines to <br>
        para_html = para.strip().replace("\n", "<br>")
        html_parts.append(f"<p>{para_html}</p>")

    return "\n".join(html_parts)


def get_send_status(campaign_id: str, tenant_id: str) -> dict:
    """Get email send status summary for a campaign.

    Returns:
        dict with total, queued, sent, delivered, failed, bounced counts
    """
    # Get all email send logs for this campaign's messages
    rows = db.session.execute(
        db.text("""
            SELECT esl.status, COUNT(*) AS cnt
            FROM email_send_log esl
            JOIN messages m ON esl.message_id = m.id
            JOIN campaign_contacts cc ON m.campaign_contact_id = cc.id
            WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
            GROUP BY esl.status
        """),
        {"cid": campaign_id, "t": tenant_id},
    ).fetchall()

    status_counts = {r[0]: r[1] for r in rows}

    return {
        "total": sum(status_counts.values()),
        "queued": status_counts.get("queued", 0),
        "sent": status_counts.get("sent", 0),
        "delivered": status_counts.get("delivered", 0),
        "failed": status_counts.get("failed", 0),
        "bounced": status_counts.get("bounced", 0),
    }
