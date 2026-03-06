"""Token tracking, metrics recording, and cost computation.

Lightweight self-hosted analytics for the LangGraph agent.
Records per-turn metrics to PostgreSQL for cost tracking,
tool performance monitoring, and tenant usage reporting.
No paid observability -- structured logging and PG storage only.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Model pricing (USD per million tokens)
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {"input_per_m": 0.80, "output_per_m": 4.0},
    "claude-sonnet-4-5-20241022": {"input_per_m": 3.0, "output_per_m": 15.0},
    "claude-opus-4-6": {"input_per_m": 15.0, "output_per_m": 75.0},
}

DEFAULT_PRICING = {"input_per_m": 3.0, "output_per_m": 15.0}


# ---------------------------------------------------------------------------
# Cost computation
# ---------------------------------------------------------------------------


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> Decimal:
    """Estimate USD cost for a model invocation.

    Args:
        model: Model name string.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.

    Returns:
        Decimal cost in USD.
    """
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
    input_cost = (
        Decimal(str(input_tokens))
        / Decimal("1000000")
        * Decimal(str(pricing["input_per_m"]))
    )
    output_cost = (
        Decimal(str(output_tokens))
        / Decimal("1000000")
        * Decimal(str(pricing["output_per_m"]))
    )
    return input_cost + output_cost


def estimate_operation_cost(
    model: str,
    estimated_input_tokens: int,
    estimated_output_tokens: int,
) -> dict[str, Any]:
    """Estimate cost for a planned operation (pre-execution).

    Returns a dict with cost breakdown for user-facing display.
    """
    cost = estimate_cost(model, estimated_input_tokens, estimated_output_tokens)

    # Convert to token credits (1 credit = $0.001)
    credits = int(cost / Decimal("0.001"))

    return {
        "model": model,
        "estimated_input_tokens": estimated_input_tokens,
        "estimated_output_tokens": estimated_output_tokens,
        "estimated_cost_usd": str(cost.quantize(Decimal("0.000001"))),
        "estimated_credits": credits,
    }


# ---------------------------------------------------------------------------
# Metrics recording
# ---------------------------------------------------------------------------


@dataclass
class TurnMetrics:
    """Metrics for a single agent turn."""

    trace_id: str
    tenant_id: str
    user_id: Optional[str] = None
    turn_index: int = 0
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal = field(default_factory=lambda: Decimal("0"))
    tool_calls: list[dict] = field(default_factory=list)
    duration_ms: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MetricsCollector:
    """Collects and records agent metrics per-turn.

    Usage:
        collector = MetricsCollector(trace_id, tenant_id, user_id)
        collector.record_llm_call(model, input_tokens, output_tokens)
        collector.record_tool_call(tool_name, duration_ms, status)
        metrics = collector.finalize()  # returns TurnMetrics
        collector.persist(db_session)    # writes to agent_metrics table
    """

    def __init__(
        self,
        trace_id: str | None = None,
        tenant_id: str = "",
        user_id: str | None = None,
        turn_index: int = 0,
    ):
        self.trace_id = trace_id or str(uuid.uuid4())
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.turn_index = turn_index
        self._model = ""
        self._input_tokens = 0
        self._output_tokens = 0
        self._cost = Decimal("0")
        self._tool_calls: list[dict] = []
        self._start_time = datetime.now(timezone.utc)
        self._start_monotonic: float | None = None

    def start_timer(self) -> None:
        """Start the turn timer."""
        import time

        self._start_monotonic = time.monotonic()

    def record_llm_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Record an LLM invocation within this turn."""
        self._model = model
        self._input_tokens += input_tokens
        self._output_tokens += output_tokens
        self._cost += estimate_cost(model, input_tokens, output_tokens)

        logger.debug(
            "LLM call: model=%s in=%d out=%d cost=$%s trace=%s",
            model,
            input_tokens,
            output_tokens,
            self._cost,
            self.trace_id,
        )

    def record_tool_call(
        self,
        tool_name: str,
        duration_ms: int,
        status: str = "success",
        error: str | None = None,
    ) -> None:
        """Record a tool execution within this turn."""
        call_record = {
            "tool_name": tool_name,
            "duration_ms": duration_ms,
            "status": status,
        }
        if error:
            call_record["error"] = error

        self._tool_calls.append(call_record)

        logger.debug(
            "Tool call: %s status=%s %dms trace=%s",
            tool_name,
            status,
            duration_ms,
            self.trace_id,
        )

    def finalize(self, duration_ms: int | None = None) -> TurnMetrics:
        """Finalize and return the collected metrics.

        Args:
            duration_ms: Total turn duration. If None, computed from timer.

        Returns:
            TurnMetrics dataclass.
        """
        if duration_ms is None and self._start_monotonic is not None:
            import time

            duration_ms = int((time.monotonic() - self._start_monotonic) * 1000)

        return TurnMetrics(
            trace_id=self.trace_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            turn_index=self.turn_index,
            model=self._model,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            cost_usd=self._cost,
            tool_calls=self._tool_calls,
            duration_ms=duration_ms or 0,
            created_at=self._start_time,
        )

    def persist(self, db_session: Any) -> None:
        """Persist metrics to the agent_metrics table.

        Args:
            db_session: SQLAlchemy session.
        """
        import json

        metrics = self.finalize()

        try:
            from sqlalchemy import text

            db_session.execute(
                text(
                    """
                    INSERT INTO agent_metrics
                        (tenant_id, user_id, trace_id, turn_index, model,
                         input_tokens, output_tokens, cost_usd, tool_calls,
                         duration_ms)
                    VALUES
                        (:tenant_id, :user_id, :trace_id, :turn_index, :model,
                         :input_tokens, :output_tokens, :cost_usd, :tool_calls,
                         :duration_ms)
                    """
                ),
                {
                    "tenant_id": metrics.tenant_id,
                    "user_id": metrics.user_id,
                    "trace_id": metrics.trace_id,
                    "turn_index": metrics.turn_index,
                    "model": metrics.model,
                    "input_tokens": metrics.input_tokens,
                    "output_tokens": metrics.output_tokens,
                    "cost_usd": str(metrics.cost_usd),
                    "tool_calls": json.dumps(metrics.tool_calls),
                    "duration_ms": metrics.duration_ms,
                },
            )
            db_session.commit()
            logger.info(
                "Persisted metrics: trace=%s tenant=%s cost=$%s",
                metrics.trace_id,
                metrics.tenant_id,
                metrics.cost_usd,
            )
        except Exception as exc:
            logger.error("Failed to persist metrics: %s", exc)
            db_session.rollback()


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def get_tenant_usage(
    db_session: Any,
    tenant_id: str,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> dict[str, Any]:
    """Query aggregated token usage for a tenant.

    Args:
        db_session: SQLAlchemy session.
        tenant_id: Tenant UUID.
        period_start: Start of period (default: first day of current month).
        period_end: End of period (default: now).

    Returns:
        Dict with total_input_tokens, total_output_tokens, total_cost_usd,
        total_tool_calls, model_breakdown.
    """
    from sqlalchemy import text

    if period_start is None:
        now = datetime.now(timezone.utc)
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period_end is None:
        period_end = datetime.now(timezone.utc)

    try:
        result = db_session.execute(
            text(
                """
                SELECT
                    COALESCE(SUM(input_tokens), 0) as total_input_tokens,
                    COALESCE(SUM(output_tokens), 0) as total_output_tokens,
                    COALESCE(SUM(cost_usd), 0) as total_cost_usd,
                    COUNT(*) as total_turns,
                    model,
                    COUNT(*) as model_turns
                FROM agent_metrics
                WHERE tenant_id = :tenant_id
                    AND created_at >= :period_start
                    AND created_at < :period_end
                GROUP BY model
                """
            ),
            {
                "tenant_id": tenant_id,
                "period_start": period_start,
                "period_end": period_end,
            },
        )

        rows = result.fetchall()
        total_input = 0
        total_output = 0
        total_cost = Decimal("0")
        total_turns = 0
        model_breakdown: dict[str, dict] = {}

        for row in rows:
            total_input += row.total_input_tokens
            total_output += row.total_output_tokens
            total_cost += Decimal(str(row.total_cost_usd))
            total_turns += row.model_turns
            model_breakdown[row.model] = {
                "input_tokens": row.total_input_tokens,
                "output_tokens": row.total_output_tokens,
                "cost_usd": str(Decimal(str(row.total_cost_usd))),
                "turns": row.model_turns,
            }

        return {
            "tenant_id": tenant_id,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "total_cost_usd": str(total_cost),
            "total_credits": int(total_cost / Decimal("0.001")),
            "total_turns": total_turns,
            "model_breakdown": model_breakdown,
        }

    except Exception as exc:
        logger.error("Failed to query tenant usage: %s", exc)
        return {
            "tenant_id": tenant_id,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "total_cost_usd": "0",
            "total_credits": 0,
            "total_turns": 0,
            "model_breakdown": {},
            "error": str(exc),
        }
