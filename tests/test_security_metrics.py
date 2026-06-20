"""Tests for security event metrics recording."""

from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest


class TestRecordSecurityEvent:
    """Test record_security_event with real prometheus_client (if available)."""

    def test_auth_failure_does_not_crash(self):
        from bitmod.metrics import record_security_event
        record_security_event("auth_failure")

    def test_rate_limited_does_not_crash(self):
        from bitmod.metrics import record_security_event
        record_security_event("rate_limited")

    def test_auth_success_does_not_crash(self):
        from bitmod.metrics import record_security_event
        record_security_event("auth_success")

    def test_injection_blocked_does_not_crash(self):
        from bitmod.metrics import record_security_event
        record_security_event("injection_blocked")

    def test_path_traversal_blocked_does_not_crash(self):
        from bitmod.metrics import record_security_event
        record_security_event("path_traversal_blocked")

    def test_invalid_input_does_not_crash(self):
        from bitmod.metrics import record_security_event
        record_security_event("invalid_input")

    def test_namespace_access_denied_does_not_crash(self):
        from bitmod.metrics import record_security_event
        record_security_event("namespace_access_denied")

    def test_unknown_event_type_does_not_crash(self):
        """Arbitrary event types should not raise -- Prometheus accepts any label value."""
        from bitmod.metrics import record_security_event
        record_security_event("totally_unknown_event_xyz")

    def test_empty_string_event_does_not_crash(self):
        from bitmod.metrics import record_security_event
        record_security_event("")

    def test_multiple_calls_do_not_raise(self):
        from bitmod.metrics import record_security_event
        for _ in range(100):
            record_security_event("auth_failure")
        for _ in range(50):
            record_security_event("rate_limited")


class TestPrometheusAvailability:
    """Test the prometheus_available() flag."""

    def test_prometheus_available_returns_bool(self):
        from bitmod.metrics import prometheus_available
        assert isinstance(prometheus_available(), bool)


class TestSecurityEventsCounter:
    """Test SECURITY_EVENTS_TOTAL counter behavior."""

    def test_counter_exists(self):
        from bitmod.metrics import SECURITY_EVENTS_TOTAL
        assert SECURITY_EVENTS_TOTAL is not None

    def test_counter_labels_method_exists(self):
        from bitmod.metrics import SECURITY_EVENTS_TOTAL
        labeled = SECURITY_EVENTS_TOTAL.labels(event_type="test")
        assert hasattr(labeled, "inc")


class TestNoOpFallback:
    """Verify that when prometheus_client is not installed, metrics are no-ops."""

    def test_noop_stubs_accept_labels_and_inc(self):
        """Simulate prometheus_client being unavailable by testing the _NoOpLabeled stub."""
        # Import the stub class directly
        # When prometheus is available, the stubs are not used, but we can still test them
        from bitmod.metrics import _PROMETHEUS_AVAILABLE

        if _PROMETHEUS_AVAILABLE:
            # prometheus_client IS installed -- test the noop class directly
            from bitmod.metrics import _NoOpLabeled
            noop = _NoOpLabeled()
            # All these should be silent no-ops
            noop.labels(event_type="auth_failure").inc()
            noop.labels(event_type="rate_limited").inc(5)
            noop.labels(foo="bar").observe(1.5)
            noop.labels(x="y").dec()
            noop.set(42)
        else:
            # prometheus_client is NOT installed -- real metrics are already no-ops
            from bitmod.metrics import record_security_event
            record_security_event("auth_failure")
            record_security_event("rate_limited")

    def test_noop_chaining(self):
        """_NoOpLabeled.labels() returns self, allowing method chaining."""
        from bitmod.metrics import _NoOpLabeled
        noop = _NoOpLabeled()
        result = noop.labels(a="1")
        assert result is noop
        # Double chaining
        noop.labels(a="1").labels(b="2").inc()


class TestOtherSecurityRelatedMetrics:
    """Verify other convenience helpers don't crash with security-adjacent events."""

    def test_record_cache_hit_does_not_crash(self):
        from bitmod.metrics import record_cache_hit
        record_cache_hit("exact", tenant_id="tenant-1")

    def test_record_cache_miss_does_not_crash(self):
        from bitmod.metrics import record_cache_miss
        record_cache_miss(tenant_id="tenant-1")

    def test_record_llm_call_does_not_crash(self):
        from bitmod.metrics import record_llm_call
        record_llm_call("openai", "gpt-4o", 1.5, status="success")
        record_llm_call("anthropic", "claude-sonnet-4-20250514", 2.0, status="error")

    def test_record_cost_saved_does_not_crash(self):
        from bitmod.metrics import record_cost_saved
        record_cost_saved(0.05, tenant_id="tenant-1")

    def test_record_request_duration_does_not_crash(self):
        from bitmod.metrics import record_request_duration
        record_request_duration("POST", "/v1/ask", 200, 0.150)
