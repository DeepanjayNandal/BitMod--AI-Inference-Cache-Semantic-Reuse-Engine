"""LLM output filtering middleware for defense-in-depth monitoring.

Scans LLM responses for:
- Instruction injection markers (prompt injection leakage)
- Tool definition leakage (internal tool schemas in output)
- System prompt fragment leakage (chunks of system prompt in output)

This is a monitoring layer — it logs warnings but does NOT block responses.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re

logger = logging.getLogger(__name__)

_ENABLED = os.getenv("BITMOD_OUTPUT_FILTER_ENABLED", "true").lower() not in ("0", "false", "no")
_BLOCK_MODE = os.getenv("BITMOD_OUTPUT_FILTER_BLOCK", "false").lower() in ("1", "true", "yes")

_BLOCKED_RESPONSE = "Response filtered for safety. Please rephrase your query."

# High-severity prefixes that trigger blocking when _BLOCK_MODE is enabled
_HIGH_SEVERITY_PREFIXES = ("injection:", "tool_leak:", "prompt_leak:excessive")

# -- Instruction injection patterns --

_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ignore_previous", re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE)),
    ("new_persona", re.compile(r"you\s+are\s+now\s+(?:a|an|the)\b", re.IGNORECASE)),
    ("system_prefix", re.compile(r"^system\s*:", re.IGNORECASE | re.MULTILINE)),
    ("forget_instructions", re.compile(r"forget\s+(your|all|my)\s+instructions", re.IGNORECASE)),
    ("new_persona_alt", re.compile(r"new\s+persona\b", re.IGNORECASE)),
    ("override_rules", re.compile(r"override\s+(your|all|the)\s+rules", re.IGNORECASE)),
    ("disregard", re.compile(r"disregard\s+(all\s+)?(previous|above|prior)", re.IGNORECASE)),
]

# -- Tool definition leakage patterns --

_TOOL_LEAK_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("json_schema_tool", re.compile(r'"type"\s*:\s*"function"\s*,\s*"function"\s*:\s*\{', re.IGNORECASE)),
    ("openapi_tool", re.compile(r'"operationId"\s*:\s*"[^"]+"\s*,\s*"parameters"', re.IGNORECASE)),
    ("tool_use_block", re.compile(r'"type"\s*:\s*"tool_use"\s*,\s*"id"', re.IGNORECASE)),
    ("function_calling", re.compile(r'"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{', re.IGNORECASE)),
]


class OutputFilter:
    """Configurable LLM output filter for defense-in-depth monitoring.

    Each check category can be individually toggled. The filter logs warnings
    but does not modify or block responses by default.
    """

    def __init__(
        self,
        *,
        check_injection: bool = True,
        check_tool_leakage: bool = True,
        check_prompt_leakage: bool = True,
        system_prompt_hash: str | None = None,
    ) -> None:
        self.check_injection = check_injection
        self.check_tool_leakage = check_tool_leakage
        self.check_prompt_leakage = check_prompt_leakage
        self._system_prompt_hash = system_prompt_hash
        self._system_prompt_chunks: list[str] = []

    @staticmethod
    def hash_prompt(prompt: str) -> str:
        """Hash a system prompt for later leakage comparison."""
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    def set_system_prompt(self, prompt: str) -> None:
        """Register the system prompt for fragment-leak detection.

        Stores the hash and extracts meaningful chunks (6+ word phrases)
        for substring matching against output text.
        """
        self._system_prompt_hash = self.hash_prompt(prompt)
        # Extract unique phrases of 6+ words for fragment matching
        words = prompt.split()
        self._system_prompt_chunks = []
        chunk_size = 6
        for i in range(len(words) - chunk_size + 1):
            chunk = " ".join(words[i : i + chunk_size]).lower()
            # Skip very generic phrases
            if len(chunk) > 25:
                self._system_prompt_chunks.append(chunk)
        # Deduplicate while preserving order
        seen: set[str] = set()
        deduped: list[str] = []
        for c in self._system_prompt_chunks:
            if c not in seen:
                seen.add(c)
                deduped.append(c)
        self._system_prompt_chunks = deduped

    def filter_response(self, text: str) -> tuple[str, list[str]]:
        """Scan LLM output for concerning patterns.

        Returns:
            Tuple of (text, list of triggered rule descriptions).
            When BITMOD_OUTPUT_FILTER_BLOCK=true and a high-severity rule fires,
            the text is replaced with a safe message. Otherwise monitoring only.
        """
        if not _ENABLED or not text:
            return text, []

        triggered: list[str] = []

        if self.check_injection:
            triggered.extend(self._check_injection(text))

        if self.check_tool_leakage:
            triggered.extend(self._check_tool_leakage(text))

        if self.check_prompt_leakage:
            triggered.extend(self._check_prompt_leakage(text))

        if _BLOCK_MODE and triggered:
            has_high = any(t.startswith(_HIGH_SEVERITY_PREFIXES) for t in triggered)
            if has_high:
                logger.warning("Output blocked — high-severity triggers: %s", triggered)
                return _BLOCKED_RESPONSE, triggered

        return text, triggered

    def _check_injection(self, text: str) -> list[str]:
        results: list[str] = []
        for name, pattern in _INJECTION_PATTERNS:
            if pattern.search(text):
                results.append(f"injection:{name}")
        return results

    def _check_tool_leakage(self, text: str) -> list[str]:
        results: list[str] = []
        for name, pattern in _TOOL_LEAK_PATTERNS:
            if pattern.search(text):
                results.append(f"tool_leak:{name}")
        return results

    def _check_prompt_leakage(self, text: str) -> list[str]:
        if not self._system_prompt_chunks:
            return []
        text_lower = text.lower()
        leaked: list[str] = []
        match_count = 0
        for chunk in self._system_prompt_chunks:
            if chunk in text_lower:
                match_count += 1
                if match_count <= 3:
                    leaked.append(f"prompt_leak:fragment_match({chunk[:40]}...)")
        if match_count > 3:
            leaked.append(f"prompt_leak:excessive_matches({match_count} total)")
        return leaked
