from __future__ import annotations

import logging
import time
import uuid
from typing import TYPE_CHECKING

from bitmod.observability import set_correlation_id, set_tenant_id

if TYPE_CHECKING:
    from fastapi import Request

logger = logging.getLogger(__name__)


async def correlation_id_middleware(request: Request, call_next):
    """Extract X-Correlation-ID from request (or generate one), set in context,
    log request start/end with method, path, status, duration_ms."""
    cid = request.headers.get("x-correlation-id") or str(uuid.uuid4())[:8]
    set_correlation_id(cid)

    tenant = request.headers.get("x-tenant-id", "default")
    set_tenant_id(tenant)

    method = request.method
    path = request.url.path
    logger.info("Request started", extra={"method": method, "path": path, "request_id": cid})

    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)

    response.headers["X-Correlation-ID"] = cid
    logger.info(
        "Request completed",
        extra={
            "method": method,
            "path": path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "request_id": cid,
        },
    )
    return response
