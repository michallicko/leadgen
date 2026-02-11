"""Enum → display translation maps.

The API returns display-format values (matching what the n8n webhooks returned)
so the dashboard JS computePipelineData() needs zero changes.
"""

STATUS_DISPLAY = {
    "new": "New",
    "enrichment_failed": "Enrichment Failed",
    "triage_passed": "Triage: Passed",
    "triage_review": "Triage: Review",
    "triage_disqualified": "Triage: Disqualified",
    "enrichment_l2_failed": "Enrichment L2 Failed",
    "enriched_l2": "Enriched L2",
    "synced": "Synced",
    "needs_review": "Needs Review",
    "enriched": "Enriched",
    "error_pushing_lemlist": "Error pushing to Lemlist",
}

TIER_DISPLAY = {
    "tier_1_platinum": "Tier 1 - Platinum",
    "tier_2_gold": "Tier 2 - Gold",
    "tier_3_silver": "Tier 3 - Silver",
    "tier_4_bronze": "Tier 4 - Bronze",
    "tier_5_copper": "Tier 5 - Copper",
    "deprioritize": "Deprioritize",
}

MESSAGE_STATUS_DISPLAY = {
    "not_started": "not_started",
    "generating": "generating",
    "pending_review": "pending_review",
    "approved": "approved",
    "sent": "sent",
    "replied": "replied",
    "no_channel": "no_channel",
    "generation_failed": "generation_failed",
}

REVIEW_STATUS_DISPLAY = {
    "draft": "draft",
    "approved": "approved",
    "rejected": "rejected",
    "sent": "sent",
    "delivered": "delivered",
    "replied": "replied",
}


def display_status(v):
    return STATUS_DISPLAY.get(v, v) if v else v


def display_tier(v):
    return TIER_DISPLAY.get(v, v) if v else v


def display_message_status(v):
    return MESSAGE_STATUS_DISPLAY.get(v, v) if v else v
