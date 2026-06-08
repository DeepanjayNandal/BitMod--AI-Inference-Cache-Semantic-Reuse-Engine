"""Block Generation Engine — multi-compression content blocks.

Generates three compression levels for each section:
- full: complete text with token count
- headline: first sentence or extracted title (rule-based)
- structured: key-value facts extracted from content (rule-based)

All extraction is rule-based — no LLM calls, no external dependencies.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import TYPE_CHECKING

from bitmod.interfaces.database import ContentBlock

if TYPE_CHECKING:
    from bitmod.interfaces.database import DatabaseBackend, SectionRecord


def _estimate_tokens(text: str) -> int:
    """Estimate token count using whitespace word count * 1.3 approximation."""
    words = text.split()
    return max(1, int(len(words) * 1.3))


def _extract_headline(text: str, section_title: str | None = None) -> str:
    """Extract a headline from section content.

    Priority:
    1. Section title if provided and non-empty
    2. First sentence of text (up to first period, question mark, or exclamation)
    3. First 120 characters if no sentence boundary found
    """
    if section_title and section_title.strip():
        return section_title.strip()

    text = text.strip()
    if not text:
        return ""

    # Look for first sentence boundary
    match = re.match(r"^(.+?[.!?])\s", text)
    if match:
        sentence = match.group(1).strip()
        if len(sentence) <= 200:
            return sentence

    # Fall back to first 120 chars at a word boundary
    if len(text) <= 120:
        return text
    truncated = text[:120]
    last_space = truncated.rfind(" ")
    if last_space > 40:
        return truncated[:last_space] + "..."
    return truncated + "..."


def _extract_structured(text: str) -> dict:
    """Extract structured data from text content using rule-based patterns.

    Detects:
    - Tables (pipe-delimited, tab-delimited)
    - Lists (bullets, numbered)
    - Key: value patterns
    - Named entities (proper nouns, numbers, dates, codes)
    """
    text = text.strip()
    if not text:
        return {"type": "empty", "data": {}}

    lines = text.split("\n")
    lines = [line.strip() for line in lines if line.strip()]

    # Detect pipe-delimited tables
    pipe_lines = [line for line in lines if line.count("|") >= 2]
    if len(pipe_lines) >= 2:
        return _extract_table(pipe_lines)

    # Detect key: value patterns (at least 2 lines with colon)
    kv_lines = [line for line in lines if re.match(r"^[^:]{1,60}:\s+.+", line)]
    if len(kv_lines) >= 2:
        return _extract_key_value(kv_lines)

    # Detect lists (bullet or numbered)
    list_lines = [line for line in lines if re.match(r"^[\-\*\u2022\u2023]\s+", line)]
    if len(list_lines) >= 2:
        return _extract_list(list_lines, "bullet")

    numbered_lines = [line for line in lines if re.match(r"^\d+[.)]\s+", line)]
    if len(numbered_lines) >= 2:
        return _extract_list(numbered_lines, "numbered")

    # For narrative text, extract entities and key facts
    return _extract_entities(text)


def _extract_table(pipe_lines: list[str]) -> dict:
    """Extract pipe-delimited table data as structured JSON."""
    rows = []
    headers: list[str] = []

    for i, line in enumerate(pipe_lines):
        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c and not re.match(r"^-+$", c)]
        if not cells:
            continue

        if i == 0:
            headers = cells
            continue

        # Skip separator rows (---|----|---)
        if all(re.match(r"^-+$", c) for c in cells):
            continue

        if headers and len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
        else:
            rows.append({"values": cells})  # type: ignore[dict-item]

    return {"type": "table", "headers": headers, "rows": rows}


def _extract_key_value(kv_lines: list[str]) -> dict:
    """Extract key: value pairs as structured JSON."""
    data = {}
    for line in kv_lines:
        match = re.match(r"^([^:]{1,60}):\s+(.+)", line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()
            data[key] = value
    return {"type": "key_value", "data": data}


def _extract_list(list_lines: list[str], list_type: str) -> dict:
    """Extract list items as structured JSON."""
    items = []
    for line in list_lines:
        # Strip bullet/number prefix
        cleaned = re.sub(r"^[\-\*\u2022\u2023]\s+", "", line)
        cleaned = re.sub(r"^\d+[.)]\s+", "", cleaned)
        if cleaned:
            items.append(cleaned)
    return {"type": list_type + "_list", "items": items}


def _extract_entities(text: str) -> dict:
    """Extract named entities from narrative text using patterns.

    Extracts: proper nouns, dates, monetary amounts, percentages, codes,
    legal citations, and numbers with context.
    """
    facts: dict[str, list[str]] = {}

    # Dates: various formats
    dates = re.findall(
        r"\b(?:\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|"
        r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+\d{1,2},?\s+\d{4}|"
        r"\d{4}-\d{2}-\d{2})\b",
        text,
    )
    if dates:
        facts["dates"] = list(set(dates))

    # Monetary amounts
    amounts = re.findall(r"\$[\d,]+(?:\.\d{2})?(?:\s*(?:million|billion|trillion))?", text, re.IGNORECASE)
    if amounts:
        facts["amounts"] = list(set(amounts))

    # Percentages
    pcts = re.findall(r"\d+(?:\.\d+)?%", text)
    if pcts:
        facts["percentages"] = list(set(pcts))

    # Legal citations (e.g., "42 U.S.C. § 1983")
    citations = re.findall(r"\d+\s+[A-Z][A-Za-z.]+\s+§\s*\d+", text)
    if citations:
        facts["citations"] = list(set(citations))

    # Codes/identifiers (uppercase sequences with numbers)
    codes = re.findall(r"\b[A-Z]{2,}[-\d]+[A-Z\d]*\b", text)
    if codes:
        facts["codes"] = list(set(codes))

    # Proper nouns (capitalized multi-word names)
    all_nouns = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text)
    all_nouns = list(set(all_nouns))
    if all_nouns:
        facts["proper_nouns"] = all_nouns[:20]  # Cap at 20

    return {"type": "narrative", "facts": facts}


class BlockGenerator:
    """Generates multi-compression content blocks for sections.

    Creates three block types per section:
    - full: complete text with token count
    - headline: extracted title or first sentence
    - structured: rule-based key-value extraction
    """

    def generate_blocks(
        self,
        section: SectionRecord,
        backend: DatabaseBackend,
        session,
    ) -> list[ContentBlock]:
        """Generate all block types for a section and store them.

        Returns the list of generated ContentBlock objects.
        """
        text = section.text_content or ""
        version_hash = section.version_hash or ""
        blocks: list[ContentBlock] = []

        # Full block
        full_block = ContentBlock(
            id=str(uuid.uuid4()),
            section_id=section.id,
            compression="full",
            content=text,
            version_hash=version_hash,
            token_count=_estimate_tokens(text),
        )
        blocks.append(full_block)

        # Headline block
        headline = _extract_headline(text, section.section_title)
        headline_block = ContentBlock(
            id=str(uuid.uuid4()),
            section_id=section.id,
            compression="headline",
            content=headline,
            version_hash=version_hash,
            token_count=_estimate_tokens(headline),
        )
        blocks.append(headline_block)

        # Structured block
        structured = _extract_structured(text)
        structured_json = json.dumps(structured)
        structured_block = ContentBlock(
            id=str(uuid.uuid4()),
            section_id=section.id,
            compression="structured",
            content=structured_json,
            version_hash=version_hash,
            token_count=_estimate_tokens(text),  # Token budget based on source text
        )
        blocks.append(structured_block)

        # Store all blocks
        for block in blocks:
            backend.store_block(session, block)

        return blocks
