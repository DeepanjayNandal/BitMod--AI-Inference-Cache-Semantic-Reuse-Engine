"""BitMod SDK exceptions."""

from __future__ import annotations


class BitmodError(Exception):
    """Base exception for all BitMod SDK errors."""

    def __init__(self, message: str, status_code: int | None = None, body: dict | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body or {}


class BitmodConnectionError(BitmodError):
    """Raised when the SDK cannot reach the BitMod gateway."""


class BitmodTimeoutError(BitmodError):
    """Raised when a request to the BitMod gateway times out."""


class BitmodAuthError(BitmodError):
    """Raised on 401/403 — invalid or missing API key."""


class BitmodRateLimitError(BitmodError):
    """Raised on 429 — too many requests.

    Attributes:
        retry_after: Seconds to wait before retrying (from Retry-After header).
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        status_code: int = 429,
        body: dict | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, status_code, body)
        self.retry_after = retry_after


class BitmodNotFoundError(BitmodError):
    """Raised on 404 — requested resource does not exist."""


class BitmodValidationError(BitmodError):
    """Raised on 422 — request payload failed validation."""


class BitmodServerError(BitmodError):
    """Raised on 5xx — server-side failure."""
