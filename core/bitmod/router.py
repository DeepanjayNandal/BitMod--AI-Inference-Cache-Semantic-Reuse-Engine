"""LLM Router with primary/fallback chain, retry logic, and circuit breaker."""

from __future__ import annotations

import enum
import logging
import threading
import time
from collections.abc import AsyncIterator

from bitmod.interfaces.llm import LLMMessage, LLMProvider, LLMResponse, ToolDefinition

logger = logging.getLogger(__name__)


class CircuitState(enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Thread-safe circuit breaker for LLM provider calls."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max: int = 2,
    ):
        self._name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max = half_open_max

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0
        self._opened_at: float = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state is CircuitState.OPEN:
                if time.monotonic() - self._opened_at >= self._recovery_timeout:
                    self._transition(CircuitState.HALF_OPEN)
            return self._state

    def can_execute(self) -> bool:
        with self._lock:
            if self._state is CircuitState.CLOSED:
                return True
            if self._state is CircuitState.OPEN:
                if time.monotonic() - self._opened_at >= self._recovery_timeout:
                    self._transition(CircuitState.HALF_OPEN)
                    return True
                return False
            # HALF_OPEN
            return self._half_open_calls < self._half_open_max

    def track_success(self) -> None:
        with self._lock:
            if self._state is CircuitState.HALF_OPEN:
                self._transition(CircuitState.CLOSED)
            self._failure_count = 0
            self._half_open_calls = 0

    def track_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            if self._state is CircuitState.HALF_OPEN:
                self._transition(CircuitState.OPEN)
            elif self._failure_count >= self._failure_threshold:
                self._transition(CircuitState.OPEN)

    def _transition(self, new_state: CircuitState) -> None:
        """Transition state. Caller must hold self._lock."""
        old = self._state
        self._state = new_state
        if new_state is CircuitState.OPEN:
            self._opened_at = time.monotonic()
            self._half_open_calls = 0
        elif new_state is CircuitState.HALF_OPEN:
            self._half_open_calls = 0
        elif new_state is CircuitState.CLOSED:
            self._failure_count = 0
            self._half_open_calls = 0
        logger.warning("Circuit breaker '%s': %s -> %s", self._name, old.value, new_state.value)


class CircuitOpenError(RuntimeError):
    """Raised when all provider circuits are open."""


class LLMRouter:
    """Routes LLM calls through primary -> fallback chain with error handling."""

    def __init__(
        self,
        primary: LLMProvider,
        fallback: LLMProvider | None = None,
        max_retries: int = 2,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max: int = 2,
    ):
        self._primary = primary
        self._fallback = fallback
        self._max_retries = max_retries
        self._primary_cb = CircuitBreaker(
            "primary",
            failure_threshold,
            recovery_timeout,
            half_open_max,
        )
        self._fallback_cb = CircuitBreaker(
            "fallback",
            failure_threshold,
            recovery_timeout,
            half_open_max,
        )

    async def generate(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        # Try primary if circuit allows
        if self._primary_cb.can_execute():
            for attempt in range(self._max_retries):
                try:
                    result = await self._primary.generate(
                        messages,
                        tools=tools,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    self._primary_cb.track_success()
                    return result
                except Exception as e:
                    logger.warning("Primary LLM attempt %d failed: %s", attempt + 1, e)
                    self._primary_cb.track_failure()
                    if attempt == self._max_retries - 1:
                        break

        # Try fallback
        if self._fallback:
            if not self._fallback_cb.can_execute():
                raise CircuitOpenError("All LLM provider circuits are open")
            logger.info("Falling back to secondary LLM provider")
            try:
                result = await self._fallback.generate(
                    messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                self._fallback_cb.track_success()
                return result
            except Exception as e:
                logger.error("Fallback LLM also failed: %s", e)
                self._fallback_cb.track_failure()
                raise

        raise RuntimeError("All LLM providers failed")

    async def stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        yielded = False

        # Try primary with retries if circuit allows
        if self._primary_cb.can_execute():
            for attempt in range(self._max_retries):
                try:
                    async for token in self._primary.stream(
                        messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    ):
                        yielded = True
                        yield token
                    self._primary_cb.track_success()
                    return
                except Exception as e:
                    self._primary_cb.track_failure()
                    if yielded:
                        logger.warning(
                            "Primary LLM stream failed after tokens were sent; "
                            "cannot retry without garbling output: %s",
                            e,
                        )
                        return
                    logger.warning("Primary LLM stream attempt %d failed: %s", attempt + 1, e)
                    if attempt == self._max_retries - 1:
                        break

        # Try fallback (only reachable if no tokens were yielded)
        if self._fallback:
            if not self._fallback_cb.can_execute():
                raise CircuitOpenError("All LLM provider circuits are open")
            logger.info("Falling back to secondary LLM for streaming")
            try:
                async for token in self._fallback.stream(
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ):
                    yield token
                self._fallback_cb.track_success()
                return
            except Exception as e:
                logger.error("Fallback LLM stream also failed: %s", e)
                self._fallback_cb.track_failure()
                raise

        raise RuntimeError("All LLM providers failed for streaming")
