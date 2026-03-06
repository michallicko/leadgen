"""Error handling, retry logic, circuit breaker, and model fallback.

Provides resilient execution wrappers for the LangGraph agent:
- ModelFallbackChain: Tries alternate models on failure
- RetryPolicy: Exponential backoff for transient failures
- CircuitBreaker: Disables failing tools temporarily
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Default model fallback order
DEFAULT_FALLBACK_CHAIN = [
    "claude-sonnet-4-5-20241022",
    "claude-haiku-4-5-20251001",
]


# ---------------------------------------------------------------------------
# Model Fallback Chain
# ---------------------------------------------------------------------------


@dataclass
class FallbackResult:
    """Result of a model fallback attempt."""

    success: bool
    model_used: str
    result: Any = None
    error: Optional[str] = None
    attempts: int = 0
    fallback_triggered: bool = False


class ModelFallbackChain:
    """Tries alternate models when the primary model fails.

    Usage:
        chain = ModelFallbackChain(primary="claude-sonnet-4-5-20241022")
        result = chain.invoke(model_fn, *args)
    """

    def __init__(
        self,
        primary: str = "claude-haiku-4-5-20251001",
        fallbacks: list[str] | None = None,
    ):
        self.primary = primary
        self.fallbacks = fallbacks or list(DEFAULT_FALLBACK_CHAIN)

    def get_chain(self) -> list[str]:
        """Get the full model chain: primary + fallbacks (deduplicated in order)."""
        chain = [self.primary]
        for model in self.fallbacks:
            if model not in chain:
                chain.append(model)
        return chain

    def invoke(
        self,
        model_fn: Callable[[str], Any],
        on_fallback: Callable[[str, str, str], None] | None = None,
    ) -> FallbackResult:
        """Try the primary model, then fallbacks on failure.

        Args:
            model_fn: Callable that takes a model name and returns result.
                Should raise an exception on failure.
            on_fallback: Optional callback(from_model, to_model, error_msg)
                called when falling back to a different model.

        Returns:
            FallbackResult with the successful result or final error.
        """
        chain = self.get_chain()
        last_error = ""

        for i, model_name in enumerate(chain):
            try:
                result = model_fn(model_name)
                return FallbackResult(
                    success=True,
                    model_used=model_name,
                    result=result,
                    attempts=i + 1,
                    fallback_triggered=i > 0,
                )
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "Model '%s' failed (attempt %d/%d): %s",
                    model_name,
                    i + 1,
                    len(chain),
                    last_error,
                )

                if on_fallback and i + 1 < len(chain):
                    next_model = chain[i + 1]
                    on_fallback(model_name, next_model, last_error)

        return FallbackResult(
            success=False,
            model_used=chain[-1] if chain else "",
            error="All models failed. Last error: {}".format(last_error),
            attempts=len(chain),
            fallback_triggered=len(chain) > 1,
        )


# ---------------------------------------------------------------------------
# Retry Policy
# ---------------------------------------------------------------------------


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    exponential_base: float = 2.0
    timeout_seconds: float = 30.0
    retryable_exceptions: tuple = (TimeoutError, ConnectionError, OSError)


# Per-tool retry configuration overrides
TOOL_RETRY_CONFIGS: dict[str, RetryConfig] = {
    "web_search": RetryConfig(max_retries=2, timeout_seconds=15.0),
    "research_own_company": RetryConfig(max_retries=2, timeout_seconds=45.0),
}

DEFAULT_RETRY_CONFIG = RetryConfig()


def get_retry_config(tool_name: str) -> RetryConfig:
    """Get the retry config for a specific tool."""
    return TOOL_RETRY_CONFIGS.get(tool_name, DEFAULT_RETRY_CONFIG)


class RetryPolicy:
    """Exponential backoff retry for tool execution.

    Usage:
        policy = RetryPolicy(config)
        result = policy.execute(fn, *args, **kwargs)
    """

    def __init__(self, config: RetryConfig | None = None):
        self.config = config or DEFAULT_RETRY_CONFIG

    def _delay_for_attempt(self, attempt: int) -> float:
        """Calculate delay for a given retry attempt (0-indexed)."""
        delay = self.config.base_delay_seconds * (self.config.exponential_base**attempt)
        return min(delay, self.config.max_delay_seconds)

    def execute(
        self,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute function with retry on transient failures.

        Args:
            fn: Function to execute.
            *args, **kwargs: Arguments to pass to fn.

        Returns:
            Result of fn.

        Raises:
            The last exception if all retries are exhausted.
        """
        last_exception: Exception | None = None

        for attempt in range(self.config.max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except self.config.retryable_exceptions as exc:
                last_exception = exc
                if attempt < self.config.max_retries:
                    delay = self._delay_for_attempt(attempt)
                    logger.warning(
                        "Retry %d/%d after %.1fs for %s: %s",
                        attempt + 1,
                        self.config.max_retries,
                        delay,
                        getattr(fn, "__name__", "unknown"),
                        exc,
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "All %d retries exhausted for %s: %s",
                        self.config.max_retries,
                        getattr(fn, "__name__", "unknown"),
                        exc,
                    )
            except Exception:
                # Non-retryable exceptions are raised immediately
                raise

        if last_exception:
            raise last_exception
        # Should not reach here, but satisfy type checker
        raise RuntimeError("Retry policy exhausted with no result")


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------


@dataclass
class _CircuitState:
    """Internal state for a single circuit."""

    failures: list[float] = field(default_factory=list)
    open_until: float = 0.0


class CircuitBreaker:
    """Per-tool circuit breaker that disables failing tools temporarily.

    If a tool fails `failure_threshold` times within `window_seconds`,
    the circuit opens and the tool is disabled for `recovery_seconds`.

    Usage:
        breaker = CircuitBreaker()
        if breaker.is_open("web_search"):
            return "Tool temporarily disabled"
        try:
            result = tool_fn()
            breaker.record_success("web_search")
        except Exception:
            breaker.record_failure("web_search")
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        window_seconds: float = 600.0,
        recovery_seconds: float = 300.0,
    ):
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.recovery_seconds = recovery_seconds
        self._circuits: dict[str, _CircuitState] = defaultdict(_CircuitState)

    def is_open(self, tool_name: str) -> bool:
        """Check if the circuit is open (tool is disabled)."""
        state = self._circuits.get(tool_name)
        if state is None:
            return False

        now = time.monotonic()
        if state.open_until > now:
            return True

        # If recovery period passed, reset
        if state.open_until > 0 and state.open_until <= now:
            state.open_until = 0.0
            state.failures.clear()

        return False

    def record_failure(self, tool_name: str) -> bool:
        """Record a failure and return True if circuit just opened."""
        now = time.monotonic()
        state = self._circuits[tool_name]

        # Remove failures outside the window
        cutoff = now - self.window_seconds
        state.failures = [t for t in state.failures if t > cutoff]
        state.failures.append(now)

        if len(state.failures) >= self.failure_threshold:
            state.open_until = now + self.recovery_seconds
            logger.warning(
                "Circuit breaker OPEN for '%s': %d failures in %.0fs window. "
                "Disabled for %.0fs.",
                tool_name,
                len(state.failures),
                self.window_seconds,
                self.recovery_seconds,
            )
            return True

        return False

    def record_success(self, tool_name: str) -> None:
        """Record a success, clearing failure history."""
        state = self._circuits.get(tool_name)
        if state:
            state.failures.clear()
            state.open_until = 0.0

    def get_status(self, tool_name: str) -> dict[str, Any]:
        """Get the current circuit status for a tool."""
        state = self._circuits.get(tool_name)
        if state is None:
            return {"status": "closed", "failures": 0}

        is_open = self.is_open(tool_name)
        now = time.monotonic()

        return {
            "status": "open" if is_open else "closed",
            "failures": len(state.failures),
            "recovery_remaining_seconds": (
                max(0, state.open_until - now) if is_open else 0
            ),
        }

    def reset(self, tool_name: str | None = None) -> None:
        """Reset circuit(s). If tool_name is None, reset all."""
        if tool_name:
            self._circuits.pop(tool_name, None)
        else:
            self._circuits.clear()


# Module-level circuit breaker instance (shared across requests)
circuit_breaker = CircuitBreaker()


def execute_with_resilience(
    tool_name: str,
    fn: Callable[..., Any],
    *args: Any,
    retry_config: RetryConfig | None = None,
    breaker: CircuitBreaker | None = None,
    **kwargs: Any,
) -> Any:
    """Execute a tool function with circuit breaker and retry logic.

    Args:
        tool_name: Name of the tool (for circuit breaker tracking).
        fn: The tool handler function.
        *args, **kwargs: Arguments for the tool handler.
        retry_config: Optional retry config override.
        breaker: Optional circuit breaker override (defaults to module-level).

    Returns:
        Tool execution result.

    Raises:
        RuntimeError: If circuit is open.
        Exception: If all retries exhausted.
    """
    cb = breaker or circuit_breaker

    if cb.is_open(tool_name):
        raise RuntimeError(
            "Tool '{}' is temporarily disabled due to repeated failures. "
            "It will be re-enabled automatically.".format(tool_name)
        )

    config = retry_config or get_retry_config(tool_name)
    policy = RetryPolicy(config)

    try:
        result = policy.execute(fn, *args, **kwargs)
        cb.record_success(tool_name)
        return result
    except Exception:
        cb.record_failure(tool_name)
        raise
