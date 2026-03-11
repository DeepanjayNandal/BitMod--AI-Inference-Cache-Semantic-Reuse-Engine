"""Observability: structured logging, correlation IDs, OpenTelemetry traces."""

from __future__ import annotations

import json
import logging
import os
import uuid
from contextvars import ContextVar
from typing import Any

# Correlation ID for request tracing across services
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
_tenant_id: ContextVar[str] = ContextVar("tenant_id", default="default")


def get_correlation_id() -> str:
    return _correlation_id.get() or str(uuid.uuid4())[:8]


def set_correlation_id(cid: str) -> None:
    _correlation_id.set(cid)


def get_tenant_id() -> str:
    return _tenant_id.get()


def set_tenant_id(tid: str) -> None:
    _tenant_id.set(tid)


# ---------------------------------------------------------------------------
# Dedicated security logger
# ---------------------------------------------------------------------------

security_logger = logging.getLogger("bitmod.security")


def log_security_event(event_type: str, **kwargs: Any) -> None:
    """Log a security event at WARNING level with structured fields.

    Args:
        event_type: Event category (e.g. auth_failure, injection_blocked).
        **kwargs: Additional context fields (actor, source_ip, resource, etc.).
    """
    security_logger.warning(
        "security_event: %s | %s",
        event_type,
        " ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None),
    )


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter with correlation IDs."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
            "tenant_id": get_tenant_id(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        # Add extra fields
        for key in ("request_id", "method", "path", "status_code", "duration_ms", "model", "cached", "cache_layer"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)
        return json.dumps(log_entry)


def _configure_structlog(json_format: bool, level: str) -> bool:
    """Try to configure structlog. Returns True if successful, False if not installed."""
    try:
        import structlog
    except ImportError:
        return False

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_format:
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root.handlers = [handler]
    return True


def configure_logging(json_format: bool | None = None, level: str | None = None) -> None:
    """Configure logging for BitMod services.

    Args:
        json_format: Use JSON structured logging. Defaults to True if BITMOD_LOG_JSON=true.
        level: Log level. Defaults to BITMOD_LOG_LEVEL env var or INFO.
    """
    if json_format is None:
        json_format = os.getenv("BITMOD_LOG_JSON", "false").lower() in ("true", "1")
    if level is None:
        level = os.getenv("BITMOD_LOG_LEVEL", "INFO")

    # Try structlog first; fall back to stdlib
    if _configure_structlog(json_format, level):
        return

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler()
    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s (%(correlation_id)s) %(message)s",
                defaults={"correlation_id": "-"},
            )
        )

    root.handlers = [handler]


# --- OpenTelemetry Integration (optional) ---

_tracer = None


def init_tracing(service_name: str = "bitmod", endpoint: str = "") -> None:
    """Initialize OpenTelemetry tracing. No-op if OTEL is not installed or endpoint is empty."""
    global _tracer
    if not endpoint:
        endpoint = os.getenv("BITMOD_OTEL_ENDPOINT", "")
    if not endpoint:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider()
        processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(service_name)
    except ImportError:
        pass


def get_tracer():
    """Return the OTEL tracer, or None if not initialized."""
    return _tracer


def trace_span(name: str, attributes: dict[str, Any] | None = None):
    """Create an OpenTelemetry span if available, or a no-op context manager."""
    tracer = get_tracer()
    if tracer:
        span = tracer.start_span(name)
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, v)
        return span

    # No-op context manager
    from contextlib import nullcontext

    return nullcontext()
