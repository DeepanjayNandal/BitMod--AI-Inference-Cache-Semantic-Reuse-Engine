"""Audit event logging for Bitmod.

Records security and operational events to the audit_events table.
Designed to be non-intrusive: audit logging failures never crash the
main request path.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class AuditLogger:
    """Write audit events to a database backend.

    Usage::

        audit = AuditLogger(db_backend)
        audit.log_event("auth_success", actor="user-1", action="login", outcome="success")
    """

    def __init__(self, backend) -> None:  # noqa: ANN001
        self._backend = backend

    def log_event(
        self,
        event_type: str,
        actor: str | None = None,
        action: str = "",
        outcome: str = "",
        *,
        source_ip: str | None = None,
        resource: str | None = None,
        details: dict | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Record an audit event. Never raises."""
        try:
            record = {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "actor": actor,
                "source_ip": source_ip,
                "resource": resource,
                "action": action,
                "outcome": outcome,
                "details_json": json.dumps(details) if isinstance(details, dict) else None,
                "correlation_id": correlation_id,
            }
            with self._backend.session() as session:
                self._backend.store_audit_event(session, record)
        except Exception:
            logger.debug("Failed to write audit event", exc_info=True)
