"""Auto-Tagging Engine — rule-based structured tagging for sections.

Generates tags across multiple dimensions:
- domain: from document metadata, document_type, title patterns
- topic: from section_title, hierarchy_path, keyword extraction
- entity_type: from structural patterns (citation, regulation, etc.)
- entities: lightweight NER — proper nouns, citations, codes, dates, amounts
- complexity: token count + vocabulary diversity
- format_hint: tables → 'structured_data', dense prose → 'narrative', short → 'simple'

All rule-based, zero external dependencies, zero LLM calls.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from bitmod.interfaces.database import SectionTag

if TYPE_CHECKING:
    from bitmod.interfaces.database import DocumentRecord, SectionRecord


# ---------------------------------------------------------------------------
# Domain detection patterns
# ---------------------------------------------------------------------------

_DOMAIN_PATTERNS: list[tuple[str, list[str]]] = [
    (
        "legal",
        [
            "statute",
            "regulation",
            "law",
            "legal",
            "court",
            "judge",
            "plaintiff",
            "defendant",
            "jurisdiction",
            "ordinance",
            "code",
            "§",
        ],
    ),
    (
        "finance",
        [
            "financial",
            "banking",
            "investment",
            "securities",
            "stock",
            "bond",
            "revenue",
            "fiscal",
            "monetary",
            "tax",
            "interest rate",
        ],
    ),
    (
        "healthcare",
        [
            "medical",
            "health",
            "clinical",
            "patient",
            "hospital",
            "disease",
            "treatment",
            "pharmaceutical",
            "diagnosis",
            "therapy",
        ],
    ),
    (
        "technology",
        [
            "software",
            "hardware",
            "algorithm",
            "database",
            "network",
            "api",
            "cloud",
            "computing",
            "digital",
            "cyber",
            "protocol",
        ],
    ),
    (
        "government",
        [
            "government",
            "federal",
            "state",
            "municipal",
            "agency",
            "policy",
            "executive",
            "legislative",
            "congressional",
            "administrative",
        ],
    ),
    (
        "education",
        [
            "education",
            "school",
            "university",
            "curriculum",
            "academic",
            "student",
            "faculty",
            "research",
            "institution",
        ],
    ),
    (
        "environment",
        [
            "environment",
            "climate",
            "pollution",
            "emissions",
            "conservation",
            "ecological",
            "sustainability",
            "renewable",
        ],
    ),
]

# ---------------------------------------------------------------------------
# Entity type detection
# ---------------------------------------------------------------------------

_ENTITY_TYPE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("statute", re.compile(r"\d+\s+[A-Z][A-Za-z.]+\s+§")),
    ("regulation", re.compile(r"(?:regulation|rule|directive|order)\s+\d+", re.IGNORECASE)),
    ("contract", re.compile(r"(?:party|parties|agreement|contract|whereas|herein)", re.IGNORECASE)),
    ("citation", re.compile(r"\d+\s+[A-Z][a-z]+\.?\s+\d+")),
    ("table", re.compile(r"^\|.*\|.*\|", re.MULTILINE)),
    ("list", re.compile(r"^[\-\*\u2022]\s+", re.MULTILINE)),
    ("numbered_list", re.compile(r"^\d+[.)]\s+", re.MULTILINE)),
]


def _detect_domain(
    section: SectionRecord,
    document: DocumentRecord,
) -> tuple[str, float]:
    """Detect the domain from document and section content."""
    # Check document_type first (high confidence)
    doc_type = (document.document_type or "").lower()
    for domain, keywords in _DOMAIN_PATTERNS:
        if doc_type in keywords:
            return domain, 0.95

    # Check title and content
    text_to_scan = " ".join(
        [
            document.title or "",
            section.section_title or "",
            section.text_content[:500] if section.text_content else "",
        ]
    ).lower()

    best_domain = "general"
    best_score = 0.0

    for domain, keywords in _DOMAIN_PATTERNS:
        hits = sum(1 for kw in keywords if kw in text_to_scan)
        if hits > best_score:
            best_score = hits
            best_domain = domain

    if best_score >= 3:
        return best_domain, 0.9
    elif best_score >= 1:
        return best_domain, 0.7
    return "general", 0.5


def _extract_topics(section: SectionRecord) -> list[tuple[str, float]]:
    """Extract topic tags from section title, hierarchy, and content."""
    topics: list[tuple[str, float]] = []

    # Section title is a strong topic signal
    if section.section_title:
        topics.append((section.section_title.lower().strip(), 0.95))

    # Hierarchy path components
    if section.hierarchy_path:
        parts = section.hierarchy_path.split("/")
        for part in parts:
            cleaned = part.strip().lower()
            if cleaned and len(cleaned) > 2:
                topics.append((cleaned, 0.8))

    # Keyword extraction from content (most frequent non-stopword terms)
    if section.text_content:
        words = re.findall(r"\b[a-z]{4,}\b", section.text_content.lower())
        stopwords = frozenset(
            [
                "that",
                "this",
                "with",
                "from",
                "have",
                "been",
                "were",
                "will",
                "would",
                "could",
                "should",
                "shall",
                "which",
                "their",
                "there",
                "they",
                "than",
                "then",
                "also",
                "into",
                "some",
                "such",
                "each",
                "other",
                "more",
                "most",
                "only",
                "very",
                "when",
                "where",
                "what",
                "about",
                "after",
                "before",
                "between",
                "under",
                "over",
            ]
        )
        words = [w for w in words if w not in stopwords]
        if words:
            freq: dict[str, int] = {}
            for w in words:
                freq[w] = freq.get(w, 0) + 1
            top = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:3]
            for word, count in top:
                if count >= 2:
                    topics.append((word, min(0.7, 0.3 + count * 0.1)))

    return topics


def _detect_entity_types(text: str) -> list[tuple[str, float]]:
    """Detect entity types from structural patterns."""
    types: list[tuple[str, float]] = []
    for etype, pattern in _ENTITY_TYPE_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            confidence = min(0.95, 0.6 + len(matches) * 0.1)
            types.append((etype, confidence))
    return types


def _extract_entities(text: str) -> list[tuple[str, float, str]]:
    """Lightweight NER — extract entities with confidence and source type.

    Returns (entity_value, confidence, source) tuples.
    """
    entities: list[tuple[str, float, str]] = []

    # Legal citations
    for m in re.finditer(r"\d+\s+[A-Z][A-Za-z.]+\s+§\s*\d+", text):
        entities.append((m.group(), 0.95, "ner"))

    # Dates
    for m in re.finditer(
        r"\b(?:\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|"
        r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+\d{1,2},?\s+\d{4}|"
        r"\d{4}-\d{2}-\d{2})\b",
        text,
    ):
        entities.append((m.group(), 0.9, "ner"))

    # Monetary amounts
    for m in re.finditer(r"\$[\d,]+(?:\.\d{2})?(?:\s*(?:million|billion|trillion))?", text, re.IGNORECASE):
        entities.append((m.group(), 0.9, "ner"))

    # Percentages
    for m in re.finditer(r"\d+(?:\.\d+)?%", text):
        entities.append((m.group(), 0.85, "ner"))

    # Jurisdiction codes (2-letter uppercase)
    for m in re.finditer(r"\b[A-Z]{2}\b", text):
        code = m.group()
        # Filter out common non-jurisdiction abbreviations
        if code not in {
            "IN",
            "IT",
            "IS",
            "AN",
            "AT",
            "AS",
            "IF",
            "OR",
            "ON",
            "NO",
            "SO",
            "TO",
            "UP",
            "DO",
            "GO",
            "AM",
            "BE",
            "BY",
            "HE",
            "WE",
        }:
            entities.append((code, 0.6, "ner"))

    # Proper noun phrases (2+ capitalized words, not at sentence start)
    for m in re.finditer(r"(?<=\s)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", text):
        entities.append((m.group(), 0.7, "ner"))

    # Deduplicate
    seen: set[str] = set()
    unique: list[tuple[str, float, str]] = []
    for val, conf, src in entities:
        if val not in seen:
            seen.add(val)
            unique.append((val, conf, src))

    return unique[:30]  # Cap at 30 entities


def _compute_complexity(text: str) -> tuple[str, float]:
    """Compute complexity level from token count and vocabulary diversity.

    Returns (complexity_label, confidence).
    """
    words = text.lower().split()
    word_count = len(words)

    if word_count == 0:
        return "simple", 1.0

    unique_words = len(set(words))
    diversity = unique_words / word_count if word_count > 0 else 0

    # Scoring: combine length and diversity
    if word_count > 500 and diversity > 0.5:
        return "high", 0.85
    elif word_count > 200 or diversity > 0.6:
        return "medium", 0.8
    else:
        return "low", 0.85


def _detect_format_hint(text: str) -> tuple[str, float]:
    """Detect content format from structural patterns.

    Returns (format_hint, confidence).
    """
    lines = text.strip().split("\n")
    lines = [line.strip() for line in lines if line.strip()]

    if not lines:
        return "simple", 1.0

    # Tables: pipe-delimited or tab-delimited
    pipe_lines = sum(1 for line in lines if line.count("|") >= 2)
    if pipe_lines >= 2:
        return "structured_data", 0.95

    tab_lines = sum(1 for line in lines if line.count("\t") >= 1)
    if tab_lines >= 2:
        return "structured_data", 0.85

    # Lists
    list_lines = sum(1 for line in lines if re.match(r"^[\-\*\u2022\d]+[.)]\s+|^[\-\*\u2022]\s+", line))
    if list_lines >= 3:
        return "list", 0.9

    # Key: value
    kv_lines = sum(1 for line in lines if re.match(r"^[^:]{1,60}:\s+.+", line))
    if kv_lines >= 2:
        return "structured_data", 0.8

    # Short text
    word_count = len(text.split())
    if word_count < 30:
        return "simple", 0.9

    # Dense prose
    avg_words_per_line = word_count / len(lines) if lines else 0
    if avg_words_per_line > 15:
        return "narrative", 0.85

    return "narrative", 0.7


class AutoTagger:
    """Generates structured tags for sections using rule-based analysis.

    All tag generation is deterministic, stdlib-only, and requires no
    external services or LLM calls.
    """

    def generate_tags(
        self,
        section: SectionRecord,
        document: DocumentRecord,
    ) -> list[SectionTag]:
        """Generate all tag types for a section.

        Returns a list of SectionTag objects ready for storage.
        """
        tags: list[SectionTag] = []
        text = section.text_content or ""

        # Domain tag
        domain, domain_conf = _detect_domain(section, document)
        tags.append(
            SectionTag(
                section_id=section.id,
                tag_key="domain",
                tag_value=domain,
                confidence=domain_conf,
                source="rule",
            )
        )

        # Topic tags
        for topic, topic_conf in _extract_topics(section):
            tags.append(
                SectionTag(
                    section_id=section.id,
                    tag_key="topic",
                    tag_value=topic,
                    confidence=topic_conf,
                    source="rule",
                )
            )

        # Entity type tags
        for etype, etype_conf in _detect_entity_types(text):
            tags.append(
                SectionTag(
                    section_id=section.id,
                    tag_key="entity_type",
                    tag_value=etype,
                    confidence=etype_conf,
                    source="rule",
                )
            )

        # Entity tags (lightweight NER)
        for entity_val, entity_conf, entity_src in _extract_entities(text):
            tags.append(
                SectionTag(
                    section_id=section.id,
                    tag_key="entities",
                    tag_value=entity_val,
                    confidence=entity_conf,
                    source=entity_src,
                )
            )

        # Complexity tag
        complexity, complexity_conf = _compute_complexity(text)
        tags.append(
            SectionTag(
                section_id=section.id,
                tag_key="complexity",
                tag_value=complexity,
                confidence=complexity_conf,
                source="rule",
            )
        )

        # Format hint tag
        format_hint, format_conf = _detect_format_hint(text)
        tags.append(
            SectionTag(
                section_id=section.id,
                tag_key="format_hint",
                tag_value=format_hint,
                confidence=format_conf,
                source="rule",
            )
        )

        return tags
