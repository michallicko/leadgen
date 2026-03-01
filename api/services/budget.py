"""Token budget enforcement service.

Provides budget checking, credit reservation, consumption, and release
for the per-namespace token credit system (BL-056).
"""

from datetime import datetime, timezone
from calendar import monthrange
from dateutil.relativedelta import relativedelta

from ..models import NamespaceTokenBudget, db


class BudgetExceededError(Exception):
    """Raised when a namespace has exhausted its token budget."""

    def __init__(self, tenant_id, remaining, required):
        self.tenant_id = tenant_id
        self.remaining = remaining
        self.required = required
        super().__init__(
            f"Token budget exceeded: {remaining} credits remaining, {required} required"
        )


def check_budget(tenant_id, estimated_credits=0):
    """Check if tenant has sufficient budget for an LLM operation.

    Args:
        tenant_id: UUID string
        estimated_credits: Estimated credits for the operation (0 = skip estimate)

    Returns:
        NamespaceTokenBudget or None (None = no budget configured, allow all)

    Raises:
        BudgetExceededError: If enforcement_mode='hard' and budget exhausted,
                             or enforcement_mode='soft' and over 120%.
    """
    budget = NamespaceTokenBudget.query.filter_by(tenant_id=str(tenant_id)).first()
    if not budget:
        return None  # No budget = unlimited

    if budget.enforcement_mode == "monitor":
        return budget  # Log only, never block

    remaining = budget.remaining_credits

    if budget.enforcement_mode == "hard":
        if remaining <= 0 or (estimated_credits > 0 and remaining < estimated_credits):
            raise BudgetExceededError(tenant_id, remaining, estimated_credits)

    if budget.enforcement_mode == "soft":
        # Soft mode allows up to 120% of budget
        soft_limit = int(budget.total_budget * 1.2)
        effective_remaining = soft_limit - budget.used_credits - budget.reserved_credits
        if effective_remaining <= 0:
            raise BudgetExceededError(tenant_id, remaining, estimated_credits)

    return budget


def reserve_credits(tenant_id, credits):
    """Reserve credits for an in-flight operation.

    Args:
        tenant_id: UUID string
        credits: Number of credits to reserve

    Returns:
        The number of credits reserved.
    """
    budget = NamespaceTokenBudget.query.filter_by(tenant_id=str(tenant_id)).first()
    if budget:
        budget.reserved_credits += credits
        budget.updated_at = db.func.now()
        db.session.flush()
    return credits


def consume_credits(tenant_id, credits, reserved=0):
    """Move credits from reserved to used (or add directly to used).

    Called after an LLM call completes with actual credit count.

    Args:
        tenant_id: UUID string
        credits: Actual credits consumed
        reserved: Credits that were previously reserved for this operation
    """
    budget = NamespaceTokenBudget.query.filter_by(tenant_id=str(tenant_id)).first()
    if budget:
        if reserved > 0:
            budget.reserved_credits = max(0, budget.reserved_credits - reserved)
        budget.used_credits += credits
        budget.updated_at = db.func.now()
        db.session.flush()


def release_reservation(tenant_id, credits):
    """Release reserved credits without consuming (operation cancelled/failed).

    Args:
        tenant_id: UUID string
        credits: Credits to release from reservation
    """
    budget = NamespaceTokenBudget.query.filter_by(tenant_id=str(tenant_id)).first()
    if budget:
        budget.reserved_credits = max(0, budget.reserved_credits - credits)
        budget.updated_at = db.func.now()
        db.session.flush()


def get_budget_status(tenant_id):
    """Get the current budget status for a tenant.

    Returns:
        dict with budget info, or None if no budget configured.
    """
    budget = NamespaceTokenBudget.query.filter_by(tenant_id=str(tenant_id)).first()
    if not budget:
        return None
    return budget.to_dict()


def _compute_next_reset(reset_period, reset_day, from_date=None):
    """Compute the next reset date based on period and day.

    Args:
        reset_period: 'monthly' or 'quarterly'
        reset_day: Day of month to reset (1-31)
        from_date: Starting date (defaults to now UTC)

    Returns:
        datetime with timezone
    """
    now = from_date or datetime.now(timezone.utc)

    if reset_period == "monthly":
        # Next month on reset_day
        next_month = now + relativedelta(months=1)
        max_day = monthrange(next_month.year, next_month.month)[1]
        day = min(reset_day, max_day)
        return next_month.replace(day=day, hour=0, minute=0, second=0, microsecond=0)

    if reset_period == "quarterly":
        # Next quarter start on reset_day
        next_quarter = now + relativedelta(months=3)
        max_day = monthrange(next_quarter.year, next_quarter.month)[1]
        day = min(reset_day, max_day)
        return next_quarter.replace(day=day, hour=0, minute=0, second=0, microsecond=0)

    return None


def reset_expired_budgets():
    """Reset budgets where next_reset_at has passed.

    Returns:
        Number of budgets reset.
    """
    now = datetime.now(timezone.utc)
    expired = NamespaceTokenBudget.query.filter(
        NamespaceTokenBudget.next_reset_at <= now,
        NamespaceTokenBudget.reset_period.isnot(None),
    ).all()

    count = 0
    for budget in expired:
        budget.used_credits = 0
        budget.reserved_credits = 0
        budget.last_reset_at = now
        budget.next_reset_at = _compute_next_reset(
            budget.reset_period, budget.reset_day, now
        )
        budget.updated_at = now
        count += 1

    if count > 0:
        db.session.commit()

    return count
