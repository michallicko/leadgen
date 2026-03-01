"""LLM usage logging service.

Tracks per-call token usage and cost for all LLM API calls.
"""

from decimal import Decimal, ROUND_HALF_UP

from ..models import LlmUsageLog, db

# Pricing per 1M tokens (input/output) as Decimal
# Keys: "provider/model" or "provider/*" for wildcard fallback
MODEL_PRICING = {
    "anthropic/claude-sonnet-4-5-20250929": {
        "input": Decimal("3.00"),
        "output": Decimal("15.00"),
    },
    "anthropic/claude-haiku-3-5-20241022": {
        "input": Decimal("0.80"),
        "output": Decimal("4.00"),
    },
    "anthropic/claude-opus-4-20250514": {
        "input": Decimal("15.00"),
        "output": Decimal("75.00"),
    },
    # Wildcard fallback for unknown Anthropic models
    "anthropic/*": {
        "input": Decimal("3.00"),
        "output": Decimal("15.00"),
    },
    # Anthropic Haiku 4.5
    "anthropic/claude-haiku-4-5-20251001": {
        "input": Decimal("0.80"),
        "output": Decimal("4.00"),
    },
    # Perplexity models
    "perplexity/sonar": {
        "input": Decimal("1.00"),
        "output": Decimal("1.00"),
    },
    "perplexity/sonar-pro": {
        "input": Decimal("3.00"),
        "output": Decimal("15.00"),
    },
    "perplexity/sonar-reasoning-pro": {
        "input": Decimal("2.00"),
        "output": Decimal("8.00"),
    },
    "perplexity/sonar-reasoning": {
        "input": Decimal("1.00"),
        "output": Decimal("5.00"),
    },
    "perplexity/*": {
        "input": Decimal("1.00"),
        "output": Decimal("1.00"),
    },
}

_ONE_MILLION = Decimal("1000000")


def compute_cost(provider, model, input_tokens, output_tokens):
    """Compute cost in USD for a single LLM call.

    Args:
        provider: e.g. "anthropic"
        model: e.g. "claude-sonnet-4-5-20250929"
        input_tokens: number of input tokens
        output_tokens: number of output tokens

    Returns:
        Decimal rounded to 6 decimal places.
    """
    key = provider + "/" + model
    pricing = MODEL_PRICING.get(key)
    if not pricing:
        # Try wildcard fallback
        pricing = MODEL_PRICING.get(provider + "/*")
    if not pricing:
        return Decimal("0")

    input_cost = pricing["input"] * Decimal(str(input_tokens)) / _ONE_MILLION
    output_cost = pricing["output"] * Decimal(str(output_tokens)) / _ONE_MILLION
    total = (input_cost + output_cost).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    return total


def compute_credits(cost_usd):
    """Convert USD cost to credits (1 credit = $0.001).

    Args:
        cost_usd: Decimal or float cost in USD

    Returns:
        int credits
    """
    return int(Decimal(str(cost_usd)) * 1000)


def log_llm_usage(
    tenant_id,
    operation,
    model,
    input_tokens,
    output_tokens,
    provider="anthropic",
    user_id=None,
    duration_ms=None,
    metadata=None,
    reserved_credits=0,
):
    """Create an LlmUsageLog entry and add to the current session.

    Does NOT commit -- caller's transaction includes it.
    Also consumes credits from the tenant's budget if one exists.

    Args:
        tenant_id: UUID string
        operation: e.g. "csv_column_mapping"
        model: e.g. "claude-sonnet-4-5-20250929"
        input_tokens: int
        output_tokens: int
        provider: defaults to "anthropic"
        user_id: optional UUID string
        duration_ms: optional int
        metadata: optional dict
        reserved_credits: credits previously reserved for this operation

    Returns:
        The created LlmUsageLog instance.
    """
    cost = compute_cost(provider, model, input_tokens, output_tokens)
    credits = compute_credits(cost)

    entry = LlmUsageLog(
        tenant_id=str(tenant_id),
        user_id=str(user_id) if user_id else None,
        operation=operation,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        credits_consumed=credits,
        duration_ms=duration_ms,
        extra=metadata or {},
    )
    db.session.add(entry)

    # Consume credits from budget (moves reserved -> used)
    from .budget import consume_credits

    consume_credits(tenant_id, credits, reserved=reserved_credits)

    return entry
