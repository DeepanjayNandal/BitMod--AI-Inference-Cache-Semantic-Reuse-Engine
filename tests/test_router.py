"""Tests for LLMRouter — primary/fallback chain, retry logic, and circuit breaker."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest

from bitmod.interfaces.llm import LLMMessage, LLMProvider, LLMResponse, ToolDefinition
from bitmod.router import CircuitBreaker, CircuitOpenError, CircuitState, LLMRouter


# ---------------------------------------------------------------------------
# Mock LLM providers
# ---------------------------------------------------------------------------

class SuccessLLM(LLMProvider):
    """Always succeeds."""
    def __init__(self, label: str = "success"):
        self.label = label
        self.call_count = 0

    async def generate(self, messages, model="", tools=None,
                       temperature=0.0, max_tokens=4096):
        self.call_count += 1
        return LLMResponse(
            content=f"Response from {self.label}",
            model=self.label,
            usage={"input_tokens": 5, "output_tokens": 10},
        )

    async def stream(self, messages, model="", temperature=0.0, max_tokens=4096):
        self.call_count += 1
        for token in ["Hello", " from", f" {self.label}"]:
            yield token


class FailLLM(LLMProvider):
    """Always fails."""
    def __init__(self):
        self.call_count = 0

    async def generate(self, messages, model="", tools=None,
                       temperature=0.0, max_tokens=4096):
        self.call_count += 1
        raise ConnectionError("LLM unavailable")

    async def stream(self, messages, model="", temperature=0.0, max_tokens=4096):
        self.call_count += 1
        raise ConnectionError("LLM stream unavailable")
        yield  # make it a generator


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _collect_stream(async_gen):
    chunks = []
    async for chunk in async_gen:
        chunks.append(chunk)
    return chunks


# ---------------------------------------------------------------------------
# Generate tests
# ---------------------------------------------------------------------------

class TestGenerate:
    def test_primary_success(self):
        primary = SuccessLLM("primary")
        router = LLMRouter(primary=primary)
        msgs = [LLMMessage(role="user", content="Hello")]

        result = _run(router.generate(msgs))
        assert result.content == "Response from primary"
        assert primary.call_count == 1

    def test_primary_failure_fallback_success(self):
        primary = FailLLM()
        fallback = SuccessLLM("fallback")
        router = LLMRouter(primary=primary, fallback=fallback, max_retries=2)
        msgs = [LLMMessage(role="user", content="Hello")]

        result = _run(router.generate(msgs))
        assert result.content == "Response from fallback"
        assert primary.call_count == 2  # Retried twice
        assert fallback.call_count == 1

    def test_both_fail_raises(self):
        primary = FailLLM()
        fallback = FailLLM()
        router = LLMRouter(primary=primary, fallback=fallback, max_retries=1)
        msgs = [LLMMessage(role="user", content="Hello")]

        with pytest.raises(ConnectionError):
            _run(router.generate(msgs))

    def test_no_fallback_raises(self):
        primary = FailLLM()
        router = LLMRouter(primary=primary, max_retries=1)
        msgs = [LLMMessage(role="user", content="Hello")]

        with pytest.raises(RuntimeError, match="All LLM providers failed"):
            _run(router.generate(msgs))


# ---------------------------------------------------------------------------
# Stream tests
# ---------------------------------------------------------------------------

class TestStream:
    def test_primary_stream_success(self):
        primary = SuccessLLM("primary")
        router = LLMRouter(primary=primary)
        msgs = [LLMMessage(role="user", content="Hello")]

        chunks = _run(_collect_stream(router.stream(msgs)))
        assert len(chunks) == 3
        assert "primary" in chunks[-1]
        assert primary.call_count == 1

    def test_primary_stream_failure_fallback_success(self):
        primary = FailLLM()
        fallback = SuccessLLM("fallback")
        router = LLMRouter(primary=primary, fallback=fallback)
        msgs = [LLMMessage(role="user", content="Hello")]

        chunks = _run(_collect_stream(router.stream(msgs)))
        assert len(chunks) == 3
        assert "fallback" in chunks[-1]

    def test_primary_stream_failure_no_fallback_raises(self):
        primary = FailLLM()
        router = LLMRouter(primary=primary)
        msgs = [LLMMessage(role="user", content="Hello")]

        with pytest.raises(RuntimeError, match="All LLM providers failed"):
            _run(_collect_stream(router.stream(msgs)))


# ---------------------------------------------------------------------------
# Circuit breaker unit tests
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state is CircuitState.CLOSED
        assert cb.can_execute() is True

    def test_opens_after_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        for _ in range(3):
            cb.track_failure()
        assert cb.state is CircuitState.OPEN
        assert cb.can_execute() is False

    def test_stays_closed_below_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        cb.track_failure()
        cb.track_failure()
        assert cb.state is CircuitState.CLOSED
        assert cb.can_execute() is True

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        cb.track_failure()
        cb.track_failure()
        cb.track_success()
        cb.track_failure()
        assert cb.state is CircuitState.CLOSED

    def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=10.0)
        cb.track_failure()
        assert cb.state is CircuitState.OPEN

        with patch("bitmod.router.time") as mock_time:
            mock_time.monotonic.return_value = time.monotonic() + 11.0
            assert cb.can_execute() is True
            assert cb.state is CircuitState.HALF_OPEN

    def test_half_open_limits_calls(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.0, half_open_max=2)
        cb.track_failure()
        # Recovery timeout = 0 so it transitions to HALF_OPEN immediately
        assert cb.can_execute() is True  # transitions to half-open, call 0
        assert cb.can_execute() is True  # call 1
        # After half_open_max calls are allowed, should deny
        cb._half_open_calls = 2
        assert cb.can_execute() is False

    def test_half_open_success_closes(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.0)
        cb.track_failure()
        cb.can_execute()  # transitions to half-open
        cb.track_success()
        assert cb.state is CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=300.0)
        cb.track_failure()
        # Manually force half-open for deterministic test
        with cb._lock:
            cb._state = CircuitState.HALF_OPEN
        cb.track_failure()
        assert cb.state is CircuitState.OPEN
        assert cb.can_execute() is False


# ---------------------------------------------------------------------------
# Circuit breaker integration with router
# ---------------------------------------------------------------------------

class TestRouterCircuitBreaker:
    def test_circuit_opens_skips_primary(self):
        primary = FailLLM()
        fallback = SuccessLLM("fallback")
        router = LLMRouter(
            primary=primary, fallback=fallback, max_retries=1, failure_threshold=2,
        )
        msgs = [LLMMessage(role="user", content="Hello")]

        # First call: primary fails (1 retry), falls back
        _run(router.generate(msgs))
        assert primary.call_count == 1

        # Second call: primary fails again, reaches threshold (2 failures)
        _run(router.generate(msgs))
        assert primary.call_count == 2

        # Third call: circuit open, skips primary entirely
        primary.call_count = 0
        _run(router.generate(msgs))
        assert primary.call_count == 0
        assert fallback.call_count == 3

    def test_both_circuits_open_raises(self):
        primary = FailLLM()
        fallback = FailLLM()
        router = LLMRouter(
            primary=primary, fallback=fallback, max_retries=1, failure_threshold=1,
        )
        msgs = [LLMMessage(role="user", content="Hello")]

        # First call opens primary circuit, fallback fails and opens its circuit
        with pytest.raises(ConnectionError):
            _run(router.generate(msgs))

        # Both circuits open now
        with pytest.raises(CircuitOpenError):
            _run(router.generate(msgs))

    def test_stream_circuit_opens_skips_primary(self):
        primary = FailLLM()
        fallback = SuccessLLM("fallback")
        router = LLMRouter(
            primary=primary, fallback=fallback, max_retries=1, failure_threshold=2,
        )
        msgs = [LLMMessage(role="user", content="Hello")]

        # Two calls to trip the primary circuit
        _run(_collect_stream(router.stream(msgs)))
        _run(_collect_stream(router.stream(msgs)))

        # Third call: primary circuit open, goes straight to fallback
        primary.call_count = 0
        chunks = _run(_collect_stream(router.stream(msgs)))
        assert primary.call_count == 0
        assert "fallback" in chunks[-1]

    def test_default_behavior_unchanged(self):
        """Default circuit breaker (threshold=5) should not change normal retry behavior."""
        primary = FailLLM()
        fallback = SuccessLLM("fallback")
        router = LLMRouter(primary=primary, fallback=fallback, max_retries=2)
        msgs = [LLMMessage(role="user", content="Hello")]

        # With threshold=5, first call (2 retries = 2 failures) should still go to fallback
        result = _run(router.generate(msgs))
        assert result.content == "Response from fallback"
        assert primary.call_count == 2
