"""BitMod Python SDK — Intelligent AI Cache Infrastructure.

Quick start::

    from bitmod_client import BitmodClient

    bm = BitmodClient(api_key="bm_...")
    result = bm.ask("What is HIPAA?", model="gpt-4o", llm_key="sk-...")
    print(result.answer, f"Saved: ${result.cost_saved:.4f}")
"""

from .client import AsyncBitmodClient, BitmodClient
from .exceptions import (
    BitmodAuthError,
    BitmodConnectionError,
    BitmodError,
    BitmodNotFoundError,
    BitmodRateLimitError,
    BitmodServerError,
    BitmodTimeoutError,
    BitmodValidationError,
)
from .models import (
    AskResult,
    HealthStatus,
    IngestResult,
    LookupResult,
    SearchResult,
    UsageStats,
)

__all__ = [
    # Clients
    "BitmodClient",
    "AsyncBitmodClient",
    # Models
    "AskResult",
    "HealthStatus",
    "IngestResult",
    "LookupResult",
    "SearchResult",
    "UsageStats",
    # Exceptions
    "BitmodError",
    "BitmodConnectionError",
    "BitmodTimeoutError",
    "BitmodAuthError",
    "BitmodRateLimitError",
    "BitmodNotFoundError",
    "BitmodServerError",
    "BitmodValidationError",
]

__version__ = "0.2.0"
