"""Tests for AuditLogger."""

from __future__ import annotations

import json
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from bitmod.audit import AuditLogger


class FakeBackend:
    """In-memory audit backend for testing."""

    def __init__(self, *, fail: bool = False):
        self.events: list[dict] = []
        self._fail = fail

    @contextmanager
    def session(self):
        yield "fake-session"

    def store_audit_event(self, session, record: dict) -> None:
        if self._fail:
            raise RuntimeError("simulated backend failure")
        self.events.append(record)


class TestAuditLogger:
    """Verify audit event recording, field population, and graceful failure."""

    @pytest.fixture
    def backend(self):
        return FakeBackend()

    @pytest.fixture
    def audit(self, backend):
        return AuditLogger(backend)

    def test_log_event_creates_record(self, audit, backend):
        """A basic log_event call stores exactly one record."""
        audit.log_event("auth_success", actor="user-1", action="login", outcome="success")
        assert len(backend.events) == 1

    def test_record_has_required_fields(self, audit, backend):
        """Stored record contains id, timestamp, event_type, actor, action, outcome."""
        audit.log_event("key_created", actor="admin", action="create_key", outcome="success")
        record = backend.events[0]
        assert record["event_type"] == "key_created"
        assert record["actor"] == "admin"
        assert record["action"] == "create_key"
        assert record["outcome"] == "success"
        assert record["id"]  # UUID present
        assert record["timestamp"]  # ISO timestamp present

    def test_event_type_auth_failure(self, audit, backend):
        """auth_failure event type is recorded correctly."""
        audit.log_event("auth_failure", actor="unknown", action="login", outcome="denied",
                        source_ip="10.0.0.1")
        record = backend.events[0]
        assert record["event_type"] == "auth_failure"
        assert record["source_ip"] == "10.0.0.1"

    def test_details_serialized_as_json(self, audit, backend):
        """details dict is serialized to JSON string in details_json."""
        audit.log_event("config_change", details={"old": 1, "new": 2})
        record = backend.events[0]
        assert json.loads(record["details_json"]) == {"old": 1, "new": 2}

    def test_details_none_when_not_dict(self, audit, backend):
        """Non-dict details are stored as None."""
        audit.log_event("test", details=None)
        record = backend.events[0]
        assert record["details_json"] is None

    def test_correlation_id_stored(self, audit, backend):
        """correlation_id kwarg is passed through to the record."""
        audit.log_event("test", correlation_id="req-abc")
        assert backend.events[0]["correlation_id"] == "req-abc"

    def test_resource_stored(self, audit, backend):
        """resource kwarg is passed through."""
        audit.log_event("access", resource="/api/keys")
        assert backend.events[0]["resource"] == "/api/keys"

    def test_graceful_failure_never_raises(self):
        """Backend crash is swallowed -- audit logging never crashes the request."""
        failing_backend = FakeBackend(fail=True)
        audit = AuditLogger(failing_backend)
        # Must not raise
        audit.log_event("auth_success", actor="user-1", action="login", outcome="ok")

    def test_multiple_events_independent(self, audit, backend):
        """Multiple events are stored independently with unique IDs."""
        audit.log_event("auth_success", actor="user-1")
        audit.log_event("auth_failure", actor="user-2")
        assert len(backend.events) == 2
        assert backend.events[0]["id"] != backend.events[1]["id"]
        assert backend.events[0]["event_type"] == "auth_success"
        assert backend.events[1]["event_type"] == "auth_failure"
