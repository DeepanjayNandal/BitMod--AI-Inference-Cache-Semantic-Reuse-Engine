"""Dynamic model pricing for token cost estimation.

Loads pricing from pricing.json (alongside this file) and auto-reloads
when the file changes. Tracks last-updated date so the frontend can
warn when pricing data is stale.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_PRICING_FILE = Path(__file__).parent / "pricing.json"
_STALE_DAYS = 7  # pricing considered stale after this many days

# Module-level cache
_pricing: dict[str, tuple[float, float]] = {}
_updated_at: str = ""
_file_mtime: float = 0.0


def _load_pricing() -> None:
    """Load or reload pricing from JSON file."""
    global _pricing, _updated_at, _file_mtime

    if not _PRICING_FILE.exists():
        logger.warning("Pricing file not found at %s, using empty pricing", _PRICING_FILE)
        _pricing = {"_default": (0.50, 1.50)}
        _updated_at = ""
        return

    try:
        mtime = _PRICING_FILE.stat().st_mtime
        # Skip reload if file hasn't changed
        if mtime == _file_mtime and _pricing:
            return

        data = json.loads(_PRICING_FILE.read_text())
        models = data.get("models", {})
        _pricing = {
            name: (rates[0], rates[1]) for name, rates in models.items() if isinstance(rates, list) and len(rates) == 2
        }
        _updated_at = data.get("_meta", {}).get("updated", "")
        _file_mtime = mtime

        if "_default" not in _pricing:
            _pricing["_default"] = (0.50, 1.50)

        logger.info(
            "Loaded pricing for %d models (updated: %s)",
            len(_pricing) - 1,
            _updated_at,
        )
    except Exception:
        logger.error("Failed to load pricing file", exc_info=True)
        if not _pricing:
            _pricing = {"_default": (0.50, 1.50)}


def get_pricing(model: str) -> tuple[float, float]:
    """Get (input_per_1M, output_per_1M) pricing for a model.

    Matches by exact name first, then by prefix.
    Auto-reloads pricing file if it has changed on disk.
    """
    _load_pricing()

    if model in _pricing:
        return _pricing[model]
    # Prefix match (e.g. 'gpt-4o-2024-08-06' matches 'gpt-4o')
    for key in sorted(_pricing.keys(), key=len, reverse=True):
        if key != "_default" and model.startswith(key):
            return _pricing[key]
    return _pricing.get("_default", (0.50, 1.50))


def get_updated_at() -> str:
    """Return the ISO date string when pricing was last updated."""
    _load_pricing()
    return _updated_at


def is_stale() -> bool:
    """Return True if pricing data is older than _STALE_DAYS."""
    _load_pricing()
    if not _updated_at:
        return True
    try:
        updated = datetime.strptime(_updated_at, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - updated
        return age.days > _STALE_DAYS
    except ValueError:
        return True


def estimate_cost(input_tokens: int, output_tokens: int, model: str = "") -> float:
    """Estimate USD cost for a given token count and model."""
    input_rate, output_rate = get_pricing(model)
    return round(
        input_tokens * (input_rate / 1_000_000) + output_tokens * (output_rate / 1_000_000),
        6,
    )


def list_models() -> dict[str, tuple[float, float]]:
    """Return all known model pricing (for admin/debug endpoints)."""
    _load_pricing()
    return dict(_pricing)
