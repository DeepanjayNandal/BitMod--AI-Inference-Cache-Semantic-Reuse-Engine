"""BitMod SDK data models."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

_logger = logging.getLogger(__name__)


def _check_response_shape(cls_name: str, data: dict[str, Any], expected_keys: set[str]) -> None:
    """Log a warning if the response dict has none of the expected keys."""
    if not data or not any(k in data for k in expected_keys):
        _logger.debug(
            "Unexpected response shape for %s (keys: %s), using defaults",
            cls_name,
            sorted(data.keys()) if data else "empty",
        )


@dataclass(frozen=True)
class LookupResult:
    """Result of a cache-only lookup (no LLM call)."""

    hit: bool
    answer: str | None = None
    confidence: float = 0.0
    cache_layer: str | None = None
    latency_ms: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LookupResult:
        _check_response_shape("LookupResult", data, {"hit", "answer", "confidence"})
        return cls(
            hit=data.get("hit", False),
            answer=data.get("answer"),
            confidence=float(data.get("confidence", 0.0)),
            cache_layer=data.get("cache_layer"),
            latency_ms=float(data.get("latency_ms", 0.0)),
        )


@dataclass(frozen=True)
class AskResult:
    """Result of a full query (cache check + optional LLM fallback)."""

    answer: str
    cached: bool
    cache_layer: str | None = None
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    cost_saved: float = 0.0
    latency_ms: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AskResult:
        _check_response_shape("AskResult", data, {"answer", "cached", "model"})
        return cls(
            answer=data.get("answer", ""),
            cached=data.get("cached", False),
            cache_layer=data.get("cache_layer"),
            model=data.get("model", ""),
            input_tokens=int(data.get("input_tokens", 0)),
            output_tokens=int(data.get("output_tokens", 0)),
            cost_usd=float(data.get("cost_usd", 0.0)),
            cost_saved=float(data.get("cost_saved", 0.0)),
            latency_ms=float(data.get("latency_ms", 0.0)),
        )


@dataclass(frozen=True)
class SearchResult:
    """A single search result."""

    id: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SearchResult:
        _check_response_shape("SearchResult", data, {"id", "text", "score"})
        return cls(
            id=data.get("id", ""),
            text=data.get("text", ""),
            score=float(data.get("score", 0.0)),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class IngestResult:
    """Result of a text or file ingestion."""

    id: str
    chunks: int = 0
    status: str = "ok"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IngestResult:
        _check_response_shape("IngestResult", data, {"id", "chunks", "status"})
        return cls(
            id=data.get("id", ""),
            chunks=int(data.get("chunks", 0)),
            status=data.get("status", "ok"),
        )


@dataclass(frozen=True)
class UsageStats:
    """Aggregated usage and savings statistics."""

    total_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    hit_rate_pct: float = 0.0
    total_cost_usd: float = 0.0
    total_savings_usd: float = 0.0
    daily_breakdown: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UsageStats:
        _check_response_shape("UsageStats", data, {"total_queries", "cache_hits", "hit_rate_pct"})
        return cls(
            total_queries=int(data.get("total_queries", 0)),
            cache_hits=int(data.get("cache_hits", 0)),
            cache_misses=int(data.get("cache_misses", 0)),
            hit_rate_pct=float(data.get("hit_rate_pct", 0.0)),
            total_cost_usd=float(data.get("total_cost_usd", 0.0)),
            total_savings_usd=float(data.get("total_savings_usd", 0.0)),
            daily_breakdown=data.get("daily_breakdown", []),
        )


@dataclass(frozen=True)
class HealthStatus:
    """Gateway health check response."""

    status: str
    version: str = ""
    cache_layers: int = 0
    uptime_seconds: float = 0.0

    @property
    def healthy(self) -> bool:
        return self.status == "ok"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HealthStatus:
        _check_response_shape("HealthStatus", data, {"status", "version"})
        return cls(
            status=data.get("status", "unknown"),
            version=data.get("version", ""),
            cache_layers=int(data.get("cache_layers", 0)),
            uptime_seconds=float(data.get("uptime_seconds", 0.0)),
        )
