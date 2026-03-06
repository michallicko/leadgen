"""Tests for agent resilience module (BL-271)."""

import time

import pytest

from api.agents.resilience import (
    CircuitBreaker,
    ModelFallbackChain,
    RetryConfig,
    RetryPolicy,
    execute_with_resilience,
    get_retry_config,
)


# ---------------------------------------------------------------------------
# ModelFallbackChain tests
# ---------------------------------------------------------------------------


class TestModelFallbackChain:
    def test_primary_model_succeeds(self):
        chain = ModelFallbackChain(primary="haiku")

        def model_fn(model_name):
            return "result from {}".format(model_name)

        result = chain.invoke(model_fn)
        assert result.success
        assert result.model_used == "haiku"
        assert result.result == "result from haiku"
        assert result.attempts == 1
        assert not result.fallback_triggered

    def test_fallback_on_primary_failure(self):
        chain = ModelFallbackChain(
            primary="haiku",
            fallbacks=["sonnet"],
        )
        call_count = 0

        def model_fn(model_name):
            nonlocal call_count
            call_count += 1
            if model_name == "haiku":
                raise ConnectionError("API down")
            return "result from {}".format(model_name)

        result = chain.invoke(model_fn)
        assert result.success
        assert result.model_used == "sonnet"
        assert result.fallback_triggered
        assert result.attempts == 2

    def test_all_models_fail(self):
        chain = ModelFallbackChain(
            primary="haiku",
            fallbacks=["sonnet"],
        )

        def model_fn(model_name):
            raise ConnectionError("All down")

        result = chain.invoke(model_fn)
        assert not result.success
        assert "All models failed" in result.error
        assert result.attempts == 2
        assert result.fallback_triggered

    def test_fallback_callback(self):
        chain = ModelFallbackChain(
            primary="haiku",
            fallbacks=["sonnet"],
        )
        fallback_calls = []

        def model_fn(model_name):
            if model_name == "haiku":
                raise ConnectionError("down")
            return "ok"

        def on_fallback(from_model, to_model, error_msg):
            fallback_calls.append((from_model, to_model, error_msg))

        result = chain.invoke(model_fn, on_fallback=on_fallback)
        assert result.success
        assert len(fallback_calls) == 1
        assert fallback_calls[0] == ("haiku", "sonnet", "down")

    def test_get_chain(self):
        chain = ModelFallbackChain(
            primary="haiku",
            fallbacks=["sonnet", "haiku"],
        )
        # Primary + fallbacks
        result = chain.get_chain()
        assert result[0] == "haiku"
        assert "sonnet" in result


# ---------------------------------------------------------------------------
# RetryPolicy tests
# ---------------------------------------------------------------------------


class TestRetryPolicy:
    def test_successful_first_attempt(self):
        config = RetryConfig(max_retries=3)
        policy = RetryPolicy(config)

        result = policy.execute(lambda: "success")
        assert result == "success"

    def test_retries_on_transient_failure(self):
        config = RetryConfig(
            max_retries=3,
            base_delay_seconds=0.01,  # Fast for tests
            retryable_exceptions=(ConnectionError,),
        )
        policy = RetryPolicy(config)
        attempts = 0

        def flaky_fn():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ConnectionError("transient")
            return "success"

        result = policy.execute(flaky_fn)
        assert result == "success"
        assert attempts == 3

    def test_exhausts_retries(self):
        config = RetryConfig(
            max_retries=2,
            base_delay_seconds=0.01,
            retryable_exceptions=(ConnectionError,),
        )
        policy = RetryPolicy(config)

        def always_fail():
            raise ConnectionError("persistent failure")

        with pytest.raises(ConnectionError, match="persistent failure"):
            policy.execute(always_fail)

    def test_non_retryable_exception_raises_immediately(self):
        config = RetryConfig(
            max_retries=3,
            retryable_exceptions=(ConnectionError,),
        )
        policy = RetryPolicy(config)
        attempts = 0

        def bad_fn():
            nonlocal attempts
            attempts += 1
            raise ValueError("non-retryable")

        with pytest.raises(ValueError):
            policy.execute(bad_fn)
        assert attempts == 1

    def test_exponential_backoff_delay(self):
        config = RetryConfig(
            base_delay_seconds=1.0,
            exponential_base=2.0,
            max_delay_seconds=30.0,
        )
        policy = RetryPolicy(config)
        assert policy._delay_for_attempt(0) == 1.0
        assert policy._delay_for_attempt(1) == 2.0
        assert policy._delay_for_attempt(2) == 4.0
        assert policy._delay_for_attempt(3) == 8.0

    def test_max_delay_cap(self):
        config = RetryConfig(
            base_delay_seconds=10.0,
            exponential_base=3.0,
            max_delay_seconds=20.0,
        )
        policy = RetryPolicy(config)
        assert policy._delay_for_attempt(5) == 20.0


# ---------------------------------------------------------------------------
# CircuitBreaker tests
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker()
        assert not cb.is_open("test_tool")

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, window_seconds=60.0)
        cb.record_failure("test_tool")
        cb.record_failure("test_tool")
        assert not cb.is_open("test_tool")

        opened = cb.record_failure("test_tool")
        assert opened
        assert cb.is_open("test_tool")

    def test_success_resets_failures(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure("test_tool")
        cb.record_failure("test_tool")
        cb.record_success("test_tool")
        cb.record_failure("test_tool")  # Should be 1 now, not 3
        assert not cb.is_open("test_tool")

    def test_independent_circuits(self):
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure("tool_a")
        cb.record_failure("tool_a")
        assert cb.is_open("tool_a")
        assert not cb.is_open("tool_b")

    def test_get_status(self):
        cb = CircuitBreaker(failure_threshold=3)
        status = cb.get_status("test_tool")
        assert status["status"] == "closed"
        assert status["failures"] == 0

        cb.record_failure("test_tool")
        status = cb.get_status("test_tool")
        assert status["failures"] == 1

    def test_reset_specific(self):
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure("tool_a")
        cb.record_failure("tool_a")
        assert cb.is_open("tool_a")

        cb.reset("tool_a")
        assert not cb.is_open("tool_a")

    def test_reset_all(self):
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure("tool_a")
        cb.record_failure("tool_a")
        cb.record_failure("tool_b")
        cb.record_failure("tool_b")

        cb.reset()
        assert not cb.is_open("tool_a")
        assert not cb.is_open("tool_b")

    def test_recovery_after_timeout(self):
        cb = CircuitBreaker(
            failure_threshold=2,
            recovery_seconds=0.05,  # 50ms for testing
        )
        cb.record_failure("test_tool")
        cb.record_failure("test_tool")
        assert cb.is_open("test_tool")

        time.sleep(0.06)
        assert not cb.is_open("test_tool")


# ---------------------------------------------------------------------------
# RetryConfig lookup tests
# ---------------------------------------------------------------------------


class TestRetryConfigLookup:
    def test_default_config(self):
        config = get_retry_config("unknown_tool")
        assert config.max_retries == 3
        assert config.timeout_seconds == 30.0

    def test_web_search_config(self):
        config = get_retry_config("web_search")
        assert config.max_retries == 2
        assert config.timeout_seconds == 15.0


# ---------------------------------------------------------------------------
# execute_with_resilience tests
# ---------------------------------------------------------------------------


class TestExecuteWithResilience:
    def test_success(self):
        cb = CircuitBreaker()
        result = execute_with_resilience(
            "test_tool",
            lambda: "success",
            retry_config=RetryConfig(max_retries=1, base_delay_seconds=0.01),
            breaker=cb,
        )
        assert result == "success"

    def test_circuit_open_raises(self):
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure("test_tool")
        assert cb.is_open("test_tool")

        with pytest.raises(RuntimeError, match="temporarily disabled"):
            execute_with_resilience(
                "test_tool",
                lambda: "success",
                breaker=cb,
            )

    def test_failure_records_to_breaker(self):
        cb = CircuitBreaker(failure_threshold=5)
        config = RetryConfig(
            max_retries=0,
            retryable_exceptions=(ConnectionError,),
        )

        with pytest.raises(ConnectionError):
            execute_with_resilience(
                "test_tool",
                lambda: (_ for _ in ()).throw(ConnectionError("fail")),
                retry_config=config,
                breaker=cb,
            )

        status = cb.get_status("test_tool")
        assert status["failures"] >= 1
