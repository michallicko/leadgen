"""Tenant token budgets, usage warnings, and pre-operation cost estimates.

Implements cost controls per tenant:
- Monthly token budgets with configurable limits
- Warning thresholds at 50%, 75%, 90% of budget
- Hard block at 100% (configurable)
- Pre-operation cost estimation with user confirmation
- All models available to all users (no gatekeeping)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default budget: 1M tokens/month (~$0.80 at Haiku pricing)
DEFAULT_MONTHLY_TOKEN_LIMIT = 1_000_000

# Warning thresholds (percentage of budget)
WARNING_THRESHOLDS = [50, 75, 90]


class BudgetStatus(str, Enum):
    """Budget status levels."""

    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    EXCEEDED = "exceeded"


@dataclass
class BudgetCheck:
    """Result of checking a tenant's budget status."""

    tenant_id: str
    status: BudgetStatus
    usage_percent: float
    tokens_used: int
    tokens_limit: int
    tokens_remaining: int
    warning_message: Optional[str] = None
    block: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API/SSE response."""
        result: dict[str, Any] = {
            "status": self.status.value,
            "usage_percent": round(self.usage_percent, 1),
            "tokens_used": self.tokens_used,
            "tokens_limit": self.tokens_limit,
            "tokens_remaining": self.tokens_remaining,
        }
        if self.warning_message:
            result["warning_message"] = self.warning_message
        if self.block:
            result["block"] = True
        return result


@dataclass
class OperationEstimate:
    """Pre-operation cost estimate for user confirmation."""

    model: str
    operation_name: str
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_total_tokens: int
    estimated_cost_usd: str
    estimated_credits: int
    budget_after: Optional[BudgetCheck] = None
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API/SSE response."""
        result = {
            "model": self.model,
            "operation": self.operation_name,
            "estimated_input_tokens": self.estimated_input_tokens,
            "estimated_output_tokens": self.estimated_output_tokens,
            "estimated_total_tokens": self.estimated_total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "estimated_credits": self.estimated_credits,
            "requires_confirmation": self.requires_confirmation,
        }
        if self.budget_after:
            result["budget_after"] = self.budget_after.to_dict()
        return result


# ---------------------------------------------------------------------------
# Budget management
# ---------------------------------------------------------------------------


def get_tenant_budget(
    db_session: Any,
    tenant_id: str,
) -> dict[str, Any]:
    """Get or create the tenant's budget configuration.

    Returns:
        Dict with monthly_token_limit, warn_at_percent, hard_limit_percent.
    """
    from sqlalchemy import text

    try:
        result = db_session.execute(
            text(
                """
                SELECT monthly_token_limit, warn_at_percent, hard_limit_percent,
                       current_period_start
                FROM tenant_token_budgets
                WHERE tenant_id = :tenant_id
                """
            ),
            {"tenant_id": tenant_id},
        )
        row = result.fetchone()

        if row:
            return {
                "monthly_token_limit": row.monthly_token_limit,
                "warn_at_percent": row.warn_at_percent,
                "hard_limit_percent": row.hard_limit_percent,
                "current_period_start": row.current_period_start,
            }

        # Return defaults for tenants without explicit budget
        return {
            "monthly_token_limit": DEFAULT_MONTHLY_TOKEN_LIMIT,
            "warn_at_percent": 75,
            "hard_limit_percent": 100,
            "current_period_start": datetime.now(timezone.utc).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            ),
        }

    except Exception as exc:
        logger.error("Failed to get tenant budget: %s", exc)
        return {
            "monthly_token_limit": DEFAULT_MONTHLY_TOKEN_LIMIT,
            "warn_at_percent": 75,
            "hard_limit_percent": 100,
            "current_period_start": datetime.now(timezone.utc).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            ),
        }


def check_budget(
    db_session: Any,
    tenant_id: str,
    additional_tokens: int = 0,
) -> BudgetCheck:
    """Check a tenant's current budget status.

    Args:
        db_session: SQLAlchemy session.
        tenant_id: Tenant UUID.
        additional_tokens: Tokens about to be consumed (for pre-check).

    Returns:
        BudgetCheck with status, usage, and any warnings.
    """
    from sqlalchemy import text

    budget = get_tenant_budget(db_session, tenant_id)
    token_limit = budget["monthly_token_limit"]
    warn_at = budget["warn_at_percent"]
    hard_limit = budget["hard_limit_percent"]

    # Get current month's usage
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    try:
        result = db_session.execute(
            text(
                """
                SELECT COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens
                FROM agent_metrics
                WHERE tenant_id = :tenant_id
                    AND created_at >= :period_start
                """
            ),
            {"tenant_id": tenant_id, "period_start": period_start},
        )
        row = result.fetchone()
        tokens_used = (row.total_tokens if row else 0) + additional_tokens

    except Exception as exc:
        logger.error("Failed to query token usage: %s", exc)
        tokens_used = additional_tokens

    usage_percent = (tokens_used / token_limit * 100) if token_limit > 0 else 0
    tokens_remaining = max(0, token_limit - tokens_used)

    # Determine status
    status = BudgetStatus.OK
    warning_message = None
    block = False

    if usage_percent >= hard_limit:
        status = BudgetStatus.EXCEEDED
        warning_message = (
            "You've reached your monthly token limit ({:,} tokens). "
            "Contact your admin to increase the budget or wait for the next billing cycle."
        ).format(token_limit)
        block = True
    elif usage_percent >= 90:
        status = BudgetStatus.CRITICAL
        warning_message = (
            "You've used {:.0f}% of your monthly token budget ({:,}/{:,} tokens). "
            "Consider prioritizing essential operations."
        ).format(usage_percent, tokens_used, token_limit)
    elif usage_percent >= warn_at:
        status = BudgetStatus.WARNING
        warning_message = (
            "You've used {:.0f}% of your monthly token budget ({:,}/{:,} tokens)."
        ).format(usage_percent, tokens_used, token_limit)

    return BudgetCheck(
        tenant_id=tenant_id,
        status=status,
        usage_percent=usage_percent,
        tokens_used=tokens_used,
        tokens_limit=token_limit,
        tokens_remaining=tokens_remaining,
        warning_message=warning_message,
        block=block,
    )


# ---------------------------------------------------------------------------
# Pre-operation estimation
# ---------------------------------------------------------------------------

# Typical token counts by operation type
OPERATION_ESTIMATES: dict[str, dict[str, int]] = {
    "research": {"input": 5000, "output": 2000},
    "strategy_generation": {"input": 8000, "output": 4000},
    "message_generation": {"input": 6000, "output": 3000},
    "enrichment": {"input": 3000, "output": 1500},
    "general": {"input": 2000, "output": 1000},
}

# Operations that require confirmation (expensive)
CONFIRMATION_THRESHOLD_CREDITS = 50  # ~$0.05


def estimate_operation(
    model: str,
    operation_name: str,
    db_session: Any | None = None,
    tenant_id: str | None = None,
) -> OperationEstimate:
    """Estimate the cost of a planned operation.

    Args:
        model: Model to use.
        operation_name: Type of operation (research, strategy_generation, etc.)
        db_session: Optional DB session for budget check.
        tenant_id: Optional tenant ID for budget check.

    Returns:
        OperationEstimate with cost breakdown and confirmation requirement.
    """
    from .analytics import estimate_cost

    token_est = OPERATION_ESTIMATES.get(operation_name, OPERATION_ESTIMATES["general"])
    input_tokens = token_est["input"]
    output_tokens = token_est["output"]

    cost = estimate_cost(model, input_tokens, output_tokens)
    credits = int(cost / Decimal("0.001"))

    requires_confirmation = credits >= CONFIRMATION_THRESHOLD_CREDITS

    budget_after = None
    if db_session and tenant_id:
        budget_after = check_budget(
            db_session,
            tenant_id,
            additional_tokens=input_tokens + output_tokens,
        )
        # Also require confirmation if budget would exceed warning threshold
        if budget_after.status in (BudgetStatus.CRITICAL, BudgetStatus.EXCEEDED):
            requires_confirmation = True

    return OperationEstimate(
        model=model,
        operation_name=operation_name,
        estimated_input_tokens=input_tokens,
        estimated_output_tokens=output_tokens,
        estimated_total_tokens=input_tokens + output_tokens,
        estimated_cost_usd=str(cost.quantize(Decimal("0.000001"))),
        estimated_credits=credits,
        budget_after=budget_after,
        requires_confirmation=requires_confirmation,
    )


def set_tenant_budget(
    db_session: Any,
    tenant_id: str,
    monthly_token_limit: int = DEFAULT_MONTHLY_TOKEN_LIMIT,
    warn_at_percent: int = 75,
    hard_limit_percent: int = 100,
) -> dict[str, Any]:
    """Create or update a tenant's budget configuration.

    Args:
        db_session: SQLAlchemy session.
        tenant_id: Tenant UUID.
        monthly_token_limit: Monthly token limit.
        warn_at_percent: Warning threshold percentage.
        hard_limit_percent: Hard limit percentage (100 = exact limit).

    Returns:
        Dict with the saved budget configuration.
    """
    from sqlalchemy import text

    try:
        db_session.execute(
            text(
                """
                INSERT INTO tenant_token_budgets
                    (tenant_id, monthly_token_limit, warn_at_percent,
                     hard_limit_percent, updated_at)
                VALUES
                    (:tenant_id, :monthly_token_limit, :warn_at_percent,
                     :hard_limit_percent, now())
                ON CONFLICT (tenant_id) DO UPDATE SET
                    monthly_token_limit = :monthly_token_limit,
                    warn_at_percent = :warn_at_percent,
                    hard_limit_percent = :hard_limit_percent,
                    updated_at = now()
                """
            ),
            {
                "tenant_id": tenant_id,
                "monthly_token_limit": monthly_token_limit,
                "warn_at_percent": warn_at_percent,
                "hard_limit_percent": hard_limit_percent,
            },
        )
        db_session.commit()

        return {
            "tenant_id": tenant_id,
            "monthly_token_limit": monthly_token_limit,
            "warn_at_percent": warn_at_percent,
            "hard_limit_percent": hard_limit_percent,
        }

    except Exception as exc:
        logger.error("Failed to set tenant budget: %s", exc)
        db_session.rollback()
        raise
