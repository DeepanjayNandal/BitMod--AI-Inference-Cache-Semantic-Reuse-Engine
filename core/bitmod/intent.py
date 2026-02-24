"""Bitmod Intent Detection Engine.

Three-tier intent detection:
  Tier 1 — Rule engine: regex pattern matching, 0ms, $0
  Tier 2 — Classifier: lightweight local model (future)
  Tier 3 — LLM: fallback for ambiguous queries (future)

The rule engine handles 90%+ of queries with zero latency and zero cost.
Intent YAML files in bitmod/intents/ define per-intent configuration
(model tier, token budgets, cache TTL, system prompts, etc.).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class IntentAction(str, Enum):
    """What the user wants to DO."""

    # Passive retrieval
    CITE = "cite"
    LIST = "list"
    QUOTE = "quote"
    REFERENCE = "reference"
    LOOKUP = "lookup"
    FIND = "find"
    SHOW = "show"

    # Synthesis
    SUMMARIZE = "summarize"
    EXPLAIN = "explain"
    COMPARE = "compare"
    CONTRAST = "contrast"
    PARAPHRASE = "paraphrase"
    TRANSLATE = "translate"

    # Reasoning
    THINK = "think"
    HYPOTHESIZE = "hypothesize"
    ANALYZE = "analyze"
    THEORIZE = "theorize"
    EVALUATE = "evaluate"
    DEBATE = "debate"
    PREDICT = "predict"

    # Agentic
    EXECUTE = "execute"
    BUILD = "build"
    DEPLOY = "deploy"
    TRANSFORM = "transform"

    # Deterministic (zero-LLM)
    EXTRACT = "extract"
    CONVERT = "convert"
    COUNT = "count"
    CALCULATE = "calculate"
    VALIDATE = "validate"

    # Creative
    BRAINSTORM = "brainstorm"
    CREATE = "create"
    WRITE = "write"
    DRAFT = "draft"
    GENERATE = "generate"
    COMPOSE = "compose"

    # Meta / fallback
    CLARIFY = "clarify"
    UNKNOWN = "unknown"


class IntentFormat(str, Enum):
    """How the user wants the answer formatted."""

    PROSE = "prose"
    TABLE = "table"
    BULLETS = "bullets"
    JSON = "json"
    CODE = "code"
    CSV = "csv"
    MARKDOWN = "markdown"
    NUMBERED = "numbered"
    TIMELINE = "timeline"
    DIAGRAM = "diagram"
    AUTO = "auto"  # let the system decide


class IntentDepth(str, Enum):
    """How much detail the user wants."""

    BRIEF = "brief"
    STANDARD = "standard"
    DETAILED = "detailed"
    EXHAUSTIVE = "exhaustive"


class IntentMode(str, Enum):
    """High-level category for downstream routing."""

    INFORMATIONAL = "informational"
    ACTIONABLE = "actionable"
    CREATIVE = "creative"
    DETERMINISTIC = "deterministic"


# ---------------------------------------------------------------------------
# Detected Intent
# ---------------------------------------------------------------------------


@dataclass
class DetectedIntent:
    """Complete parsed intent from a user query."""

    action: IntentAction
    format: IntentFormat
    depth: IntentDepth
    entities: list[str] = field(default_factory=list)
    mode: IntentMode = IntentMode.INFORMATIONAL
    confidence: float = 0.0
    tier: int = 1  # 1=rule, 2=classifier, 3=llm
    cacheable: bool = True
    skip_llm: bool = False
    raw_query: str = ""
    matched_pattern: str = ""


# ---------------------------------------------------------------------------
# Mode classification
# ---------------------------------------------------------------------------

_ACTION_MODE_MAP: dict[IntentAction, IntentMode] = {
    # Passive retrieval → informational
    IntentAction.CITE: IntentMode.INFORMATIONAL,
    IntentAction.LIST: IntentMode.INFORMATIONAL,
    IntentAction.QUOTE: IntentMode.INFORMATIONAL,
    IntentAction.REFERENCE: IntentMode.INFORMATIONAL,
    IntentAction.LOOKUP: IntentMode.INFORMATIONAL,
    IntentAction.FIND: IntentMode.INFORMATIONAL,
    IntentAction.SHOW: IntentMode.INFORMATIONAL,
    # Synthesis → informational
    IntentAction.SUMMARIZE: IntentMode.INFORMATIONAL,
    IntentAction.EXPLAIN: IntentMode.INFORMATIONAL,
    IntentAction.COMPARE: IntentMode.INFORMATIONAL,
    IntentAction.CONTRAST: IntentMode.INFORMATIONAL,
    IntentAction.PARAPHRASE: IntentMode.INFORMATIONAL,
    IntentAction.TRANSLATE: IntentMode.INFORMATIONAL,
    # Reasoning → informational
    IntentAction.THINK: IntentMode.INFORMATIONAL,
    IntentAction.HYPOTHESIZE: IntentMode.INFORMATIONAL,
    IntentAction.ANALYZE: IntentMode.INFORMATIONAL,
    IntentAction.THEORIZE: IntentMode.INFORMATIONAL,
    IntentAction.EVALUATE: IntentMode.INFORMATIONAL,
    IntentAction.DEBATE: IntentMode.INFORMATIONAL,
    IntentAction.PREDICT: IntentMode.INFORMATIONAL,
    # Agentic → actionable
    IntentAction.EXECUTE: IntentMode.ACTIONABLE,
    IntentAction.BUILD: IntentMode.ACTIONABLE,
    IntentAction.DEPLOY: IntentMode.ACTIONABLE,
    IntentAction.TRANSFORM: IntentMode.ACTIONABLE,
    # Deterministic → deterministic
    IntentAction.EXTRACT: IntentMode.DETERMINISTIC,
    IntentAction.CONVERT: IntentMode.DETERMINISTIC,
    IntentAction.COUNT: IntentMode.DETERMINISTIC,
    IntentAction.CALCULATE: IntentMode.DETERMINISTIC,
    IntentAction.VALIDATE: IntentMode.DETERMINISTIC,
    # Creative → creative
    IntentAction.BRAINSTORM: IntentMode.CREATIVE,
    IntentAction.CREATE: IntentMode.CREATIVE,
    IntentAction.WRITE: IntentMode.CREATIVE,
    IntentAction.DRAFT: IntentMode.CREATIVE,
    IntentAction.GENERATE: IntentMode.CREATIVE,
    IntentAction.COMPOSE: IntentMode.CREATIVE,
    # Meta
    IntentAction.CLARIFY: IntentMode.INFORMATIONAL,
    IntentAction.UNKNOWN: IntentMode.INFORMATIONAL,
}

_SKIP_LLM_ACTIONS = frozenset(
    {
        IntentAction.EXTRACT,
        IntentAction.CONVERT,
        IntentAction.COUNT,
        IntentAction.CALCULATE,
        IntentAction.VALIDATE,
    }
)

_NON_CACHEABLE_ACTIONS = frozenset(
    {
        IntentAction.BRAINSTORM,
        IntentAction.CREATE,
        IntentAction.COMPOSE,
    }
)


# ---------------------------------------------------------------------------
# Pattern Definitions — Tier 1 Rule Engine
# ---------------------------------------------------------------------------


@dataclass
class _Pattern:
    """A single regex pattern mapping to an intent action."""

    regex: re.Pattern
    action: IntentAction
    confidence: float
    source: str  # human-readable label for debugging


def _p(pattern: str, action: IntentAction, confidence: float = 1.0, label: str = "") -> _Pattern:
    """Helper to build a pattern entry."""
    return _Pattern(
        regex=re.compile(pattern, re.IGNORECASE),
        action=action,
        confidence=confidence,
        source=label or pattern,
    )


# Ordered by specificity — first match at highest confidence wins.
# Patterns are grouped by intent family.
PATTERNS: list[_Pattern] = [
    # ── Deterministic (highest priority — skip LLM entirely) ──────────
    _p(r"^extract\b", IntentAction.EXTRACT, 1.0, "extract-start"),
    _p(r"\bextract\s+(all|every|the)\b", IntentAction.EXTRACT, 0.9, "extract-mid"),
    _p(r"^convert\b", IntentAction.CONVERT, 1.0, "convert-start"),
    _p(r"\bconvert\s+.+\s+(?:to|into)\b", IntentAction.CONVERT, 0.9, "convert-to"),
    _p(r"^count\b", IntentAction.COUNT, 1.0, "count-start"),
    _p(r"\bhow many\b", IntentAction.COUNT, 0.9, "how-many"),
    _p(r"^calculate\b", IntentAction.CALCULATE, 1.0, "calculate-start"),
    _p(r"^compute\b", IntentAction.CALCULATE, 0.9, "compute-start"),
    _p(r"\bwhat is\s+\d", IntentAction.CALCULATE, 0.7, "what-is-number"),
    _p(r"^validate\b", IntentAction.VALIDATE, 1.0, "validate-start"),
    _p(r"^verify\b", IntentAction.VALIDATE, 0.9, "verify-start"),
    _p(r"\bis\s+(?:this|it)\s+valid\b", IntentAction.VALIDATE, 0.8, "is-valid"),
    # ── Passive retrieval ─────────────────────────────────────────────
    _p(r"^cite\b", IntentAction.CITE, 1.0, "cite-start"),
    _p(r"\bcitation\s+for\b", IntentAction.CITE, 0.9, "citation-for"),
    _p(r"\bcite\s+(?:the|a|an)\b", IntentAction.CITE, 0.9, "cite-the"),
    _p(r"^list\b", IntentAction.LIST, 1.0, "list-start"),
    _p(r"\blist\s+(?:all|every|the|each)\b", IntentAction.LIST, 0.9, "list-all"),
    _p(r"\bgive\s+(?:me\s+)?a\s+list\b", IntentAction.LIST, 0.9, "give-list"),
    _p(r"^quote\b", IntentAction.QUOTE, 1.0, "quote-start"),
    _p(r"\bquote\s+(?:the|from)\b", IntentAction.QUOTE, 0.9, "quote-from"),
    _p(r"\bexact\s+(?:text|wording|language)\b", IntentAction.QUOTE, 0.8, "exact-text"),
    _p(r"^(?:find|search)\b", IntentAction.FIND, 1.0, "find-start"),
    _p(r"\bfind\s+(?:all|every|the|me)\b", IntentAction.FIND, 0.9, "find-all"),
    _p(r"^show\b", IntentAction.SHOW, 1.0, "show-start"),
    _p(r"\bshow\s+(?:me|us|the)\b", IntentAction.SHOW, 0.9, "show-me"),
    _p(r"^reference\b", IntentAction.REFERENCE, 1.0, "reference-start"),
    _p(r"\breference\s+(?:to|for)\b", IntentAction.REFERENCE, 0.8, "reference-to"),
    _p(r"^(?:lookup|look\s+up)\b", IntentAction.LOOKUP, 1.0, "lookup-start"),
    _p(r"\blook\s*up\b", IntentAction.LOOKUP, 0.8, "lookup-mid"),
    _p(r"^what\s+(?:is|are|was|were)\b", IntentAction.EXPLAIN, 0.7, "what-is"),
    _p(r"^who\s+(?:is|are|was|were)\b", IntentAction.LOOKUP, 0.7, "who-is"),
    _p(r"^where\s+(?:is|are|was|were)\b", IntentAction.LOOKUP, 0.7, "where-is"),
    _p(r"^when\s+(?:is|are|was|were|did)\b", IntentAction.LOOKUP, 0.7, "when-is"),
    # ── Synthesis ─────────────────────────────────────────────────────
    _p(r"^summarize\b", IntentAction.SUMMARIZE, 1.0, "summarize-start"),
    _p(r"^(?:give\s+(?:me\s+)?)?(?:a\s+)?summary\b", IntentAction.SUMMARIZE, 0.9, "summary"),
    _p(r"\bsummarize\s+(?:the|this|that)\b", IntentAction.SUMMARIZE, 0.9, "summarize-the"),
    _p(r"\btl;?dr\b", IntentAction.SUMMARIZE, 0.9, "tldr"),
    _p(r"^explain\b", IntentAction.EXPLAIN, 1.0, "explain-start"),
    _p(r"\bexplain\s+(?:how|why|what|the)\b", IntentAction.EXPLAIN, 0.9, "explain-how"),
    _p(r"\bwhat\s+does\s+.+\s+mean\b", IntentAction.EXPLAIN, 0.8, "what-means"),
    _p(r"^compare\b", IntentAction.COMPARE, 1.0, "compare-start"),
    _p(r"\bcompare\s+.+\s+(?:with|to|and|vs\.?|versus)\b", IntentAction.COMPARE, 0.9, "compare-with"),
    _p(r"\bcompared\s+to\b", IntentAction.COMPARE, 0.9, "compared-to"),
    _p(r"\bdifference(?:s)?\s+between\b", IntentAction.COMPARE, 0.9, "diff-between"),
    _p(r"\bvs\.?\b", IntentAction.COMPARE, 0.7, "vs"),
    _p(r"^contrast\b", IntentAction.CONTRAST, 1.0, "contrast-start"),
    _p(r"\bcontrast\s+.+\s+(?:with|and)\b", IntentAction.CONTRAST, 0.9, "contrast-with"),
    _p(r"^paraphrase\b", IntentAction.PARAPHRASE, 1.0, "paraphrase-start"),
    _p(
        r"\bput\s+(?:it|this|that)\s+in\s+(?:simpler|other|different)\s+words\b",
        IntentAction.PARAPHRASE,
        0.8,
        "simpler-words",
    ),
    _p(r"^translate\b", IntentAction.TRANSLATE, 1.0, "translate-start"),
    _p(r"\btranslate\s+.+\s+(?:to|into)\b", IntentAction.TRANSLATE, 0.9, "translate-to"),
    # ── Reasoning ─────────────────────────────────────────────────────
    _p(r"^analyze\b", IntentAction.ANALYZE, 1.0, "analyze-start"),
    _p(r"^analyse\b", IntentAction.ANALYZE, 1.0, "analyse-start"),
    _p(r"\banalyz(?:e|is)\b", IntentAction.ANALYZE, 0.8, "analyze-mid"),
    _p(r"^evaluate\b", IntentAction.EVALUATE, 1.0, "evaluate-start"),
    _p(r"\bevaluate\s+(?:the|this|whether)\b", IntentAction.EVALUATE, 0.9, "evaluate-the"),
    _p(r"^hypothesize\b", IntentAction.HYPOTHESIZE, 1.0, "hypothesize-start"),
    _p(r"\bwhat\s+(?:if|would\s+happen)\b", IntentAction.HYPOTHESIZE, 0.8, "what-if"),
    _p(r"^theorize\b", IntentAction.THEORIZE, 1.0, "theorize-start"),
    _p(r"\btheory\s+(?:about|on|behind)\b", IntentAction.THEORIZE, 0.8, "theory-about"),
    _p(r"^think\b", IntentAction.THINK, 1.0, "think-start"),
    _p(r"\bthink\s+(?:about|through)\b", IntentAction.THINK, 0.8, "think-about"),
    _p(r"\breason\s+(?:about|through)\b", IntentAction.THINK, 0.8, "reason-about"),
    _p(r"^debate\b", IntentAction.DEBATE, 1.0, "debate-start"),
    _p(r"\bpros?\s+and\s+cons?\b", IntentAction.DEBATE, 0.9, "pros-cons"),
    _p(r"\barguments?\s+(?:for|against)\b", IntentAction.DEBATE, 0.8, "arguments-for"),
    _p(r"^predict\b", IntentAction.PREDICT, 1.0, "predict-start"),
    _p(r"\bwhat\s+will\s+happen\b", IntentAction.PREDICT, 0.8, "what-will-happen"),
    _p(r"\bforecast\b", IntentAction.PREDICT, 0.8, "forecast"),
    # ── Agentic ───────────────────────────────────────────────────────
    _p(r"^execute\b", IntentAction.EXECUTE, 1.0, "execute-start"),
    _p(r"^run\b", IntentAction.EXECUTE, 0.9, "run-start"),
    _p(r"^build\b", IntentAction.BUILD, 1.0, "build-start"),
    _p(r"^deploy\b", IntentAction.DEPLOY, 1.0, "deploy-start"),
    _p(r"^transform\b", IntentAction.TRANSFORM, 1.0, "transform-start"),
    _p(r"\btransform\s+.+\s+(?:to|into)\b", IntentAction.TRANSFORM, 0.9, "transform-to"),
    # ── Creative ──────────────────────────────────────────────────────
    _p(r"^brainstorm\b", IntentAction.BRAINSTORM, 1.0, "brainstorm-start"),
    _p(r"\bbrainstorm\s+(?:ideas?|ways?|options?)\b", IntentAction.BRAINSTORM, 0.9, "brainstorm-ideas"),
    _p(r"^create\b", IntentAction.CREATE, 1.0, "create-start"),
    _p(r"^write\b", IntentAction.WRITE, 1.0, "write-start"),
    _p(r"\bwrite\s+(?:a|an|the|me)\b", IntentAction.WRITE, 0.9, "write-a"),
    _p(r"^draft\b", IntentAction.DRAFT, 1.0, "draft-start"),
    _p(r"\bdraft\s+(?:a|an|the)\b", IntentAction.DRAFT, 0.9, "draft-a"),
    _p(r"^generate\b", IntentAction.GENERATE, 1.0, "generate-start"),
    _p(r"\bgenerate\s+(?:a|an|the|some)\b", IntentAction.GENERATE, 0.9, "generate-a"),
    _p(r"^compose\b", IntentAction.COMPOSE, 1.0, "compose-start"),
    # ── Meta ──────────────────────────────────────────────────────────
    _p(r"^clarify\b", IntentAction.CLARIFY, 1.0, "clarify-start"),
    _p(r"\bwhat\s+do\s+you\s+mean\b", IntentAction.CLARIFY, 0.9, "what-do-you-mean"),
    _p(r"\bcan\s+you\s+clarify\b", IntentAction.CLARIFY, 0.9, "can-you-clarify"),
]


# ---------------------------------------------------------------------------
# Format Detection Patterns
# ---------------------------------------------------------------------------

FORMAT_PATTERNS: list[tuple[re.Pattern, IntentFormat]] = [
    (re.compile(r"\b(?:as\s+a\s+)?table\b", re.I), IntentFormat.TABLE),
    (re.compile(r"\b(?:in\s+)?(?:bullet|bulleted)\s*(?:point|list)?s?\b", re.I), IntentFormat.BULLETS),
    (re.compile(r"\b(?:as\s+)?json\b", re.I), IntentFormat.JSON),
    (re.compile(r"\b(?:as\s+)?csv\b", re.I), IntentFormat.CSV),
    (re.compile(r"\b(?:as\s+|in\s+)?code\b", re.I), IntentFormat.CODE),
    (re.compile(r"\b(?:as\s+|in\s+)?markdown\b", re.I), IntentFormat.MARKDOWN),
    (re.compile(r"\b(?:numbered|ordered)\s*list\b", re.I), IntentFormat.NUMBERED),
    (re.compile(r"\btimeline\b", re.I), IntentFormat.TIMELINE),
    (re.compile(r"\bdiagram\b", re.I), IntentFormat.DIAGRAM),
]

# Implicit format from action
_ACTION_FORMAT_HINTS: dict[IntentAction, IntentFormat] = {
    IntentAction.LIST: IntentFormat.BULLETS,
    IntentAction.COMPARE: IntentFormat.TABLE,
    IntentAction.CONTRAST: IntentFormat.TABLE,
    IntentAction.COUNT: IntentFormat.PROSE,
    IntentAction.EXTRACT: IntentFormat.JSON,
    IntentAction.CONVERT: IntentFormat.CODE,
}


# ---------------------------------------------------------------------------
# Depth Detection Patterns
# ---------------------------------------------------------------------------

DEPTH_PATTERNS: list[tuple[re.Pattern, IntentDepth]] = [
    (re.compile(r"\b(?:brief(?:ly)?|short(?:ly)?|quick(?:ly)?|concise(?:ly)?|tl;?dr)\b", re.I), IntentDepth.BRIEF),
    (
        re.compile(r"\b(?:detail(?:ed)?|in[\s-]depth|thorough(?:ly)?|comprehensive(?:ly)?)\b", re.I),
        IntentDepth.DETAILED,
    ),
    (re.compile(r"\b(?:exhaust(?:ive(?:ly)?)?|everything|all\s+(?:about|there\s+is))\b", re.I), IntentDepth.EXHAUSTIVE),
    (re.compile(r"\b(?:full(?:y)?|complete(?:ly)?)\b", re.I), IntentDepth.DETAILED),
]


# ---------------------------------------------------------------------------
# Entity Extraction
# ---------------------------------------------------------------------------

# Proper nouns: capitalized multi-word sequences (excluding sentence starts)
_PROPER_NOUN_RE = re.compile(
    r"(?:(?<=\s)|(?<=^))"  # preceded by space or start
    r"(?:(?:the|a|an|of|in|for|to|and|or|by|at|on|with|from)\s+)*"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)"  # two+ capitalized words
)

# Quoted strings
_QUOTED_RE = re.compile(r"""(?:"([^"]+)"|'([^']+)')""")

# Numbers with optional units
_NUMBER_RE = re.compile(r"\b(\d[\d,]*\.?\d*\s*(?:%|percent|dollars?|USD|EUR|GBP|kg|lb|mi|km|ft|m|cm|mm)?)\b")

# Codes: stock tickers, ISO codes, US state codes
_CODE_RE = re.compile(r"\b([A-Z]{2,5})\b")

# Email addresses
_EMAIL_RE = re.compile(r"\b([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b")

# URLs
_URL_RE = re.compile(r"(https?://[^\s]+)")


def extract_entities(query: str) -> list[str]:
    """Extract notable entities from a query.

    Returns a deduplicated list of: proper nouns, quoted strings, numbers,
    codes, emails, URLs.
    """
    entities: list[str] = []
    seen: set[str] = set()

    def _add(value: str) -> None:
        v = value.strip()
        if v and v not in seen:
            seen.add(v)
            entities.append(v)

    # Quoted strings (highest priority)
    for m in _QUOTED_RE.finditer(query):
        _add(m.group(1) or m.group(2))

    # URLs
    for m in _URL_RE.finditer(query):
        _add(m.group(1))

    # Emails
    for m in _EMAIL_RE.finditer(query):
        _add(m.group(1))

    # Proper nouns (multi-word capitalized)
    for m in _PROPER_NOUN_RE.finditer(query):
        _add(m.group(1))

    # Numbers with units
    for m in _NUMBER_RE.finditer(query):
        _add(m.group(1))

    # Codes (only if 3+ chars to reduce noise; skip common English words)
    common_upper = frozenset(
        {
            "THE",
            "AND",
            "FOR",
            "ARE",
            "BUT",
            "NOT",
            "YOU",
            "ALL",
            "CAN",
            "HER",
            "WAS",
            "ONE",
            "OUR",
            "OUT",
            "HIS",
            "HAS",
            "HOW",
            "WHO",
            "WHY",
            "WHAT",
            "WHEN",
            "WHERE",
            "LIST",
            "SHOW",
            "FIND",
            "GIVE",
            "MAKE",
            "DOES",
            "THIS",
            "THAT",
            "THEM",
            "THEN",
            "THAN",
            "WITH",
            "WILL",
            "FROM",
            "INTO",
            "JUST",
            "LIKE",
            "HAVE",
            "BEEN",
            "SOME",
            "ALSO",
            "EACH",
            "MORE",
            "ONLY",
            "VERY",
            "ABOUT",
            "BRIEF",
        }
    )
    for m in _CODE_RE.finditer(query):
        code = m.group(1)
        if len(code) >= 3 and code not in common_upper:
            _add(code)

    return entities


# ---------------------------------------------------------------------------
# Tier 1 — Rule Engine
# ---------------------------------------------------------------------------


def detect_format(query: str, action: IntentAction) -> IntentFormat:
    """Detect desired output format from query text."""
    for pattern, fmt in FORMAT_PATTERNS:
        if pattern.search(query):
            return fmt
    return _ACTION_FORMAT_HINTS.get(action, IntentFormat.AUTO)


def detect_depth(query: str) -> IntentDepth:
    """Detect desired depth from query text."""
    for pattern, depth in DEPTH_PATTERNS:
        if pattern.search(query):
            return depth
    return IntentDepth.STANDARD


def detect_intent(query: str) -> DetectedIntent:
    """Tier 1 rule-based intent detection.

    Scans the query against 50+ regex patterns, picks the highest-confidence
    match, extracts format/depth/entities, and returns a complete DetectedIntent.

    Runs in <1ms with zero external dependencies.
    """
    query = query.strip()
    if not query:
        return DetectedIntent(
            action=IntentAction.UNKNOWN,
            format=IntentFormat.AUTO,
            depth=IntentDepth.STANDARD,
            mode=IntentMode.INFORMATIONAL,
            confidence=0.0,
            tier=1,
            raw_query=query,
        )

    # Find best matching pattern
    best_action = IntentAction.UNKNOWN
    best_confidence = 0.0
    best_label = ""

    for pat in PATTERNS:
        m = pat.regex.search(query)
        if m and pat.confidence > best_confidence:
            best_action = pat.action
            best_confidence = pat.confidence
            best_label = pat.source

    # Derive mode, format, depth
    mode = _ACTION_MODE_MAP.get(best_action, IntentMode.INFORMATIONAL)
    fmt = detect_format(query, best_action)
    depth = detect_depth(query)
    entities = extract_entities(query)
    skip_llm = best_action in _SKIP_LLM_ACTIONS
    cacheable = best_action not in _NON_CACHEABLE_ACTIONS

    return DetectedIntent(
        action=best_action,
        format=fmt,
        depth=depth,
        entities=entities,
        mode=mode,
        confidence=best_confidence,
        tier=1,
        cacheable=cacheable,
        skip_llm=skip_llm,
        raw_query=query,
        matched_pattern=best_label,
    )


# ---------------------------------------------------------------------------
# Intent Registry — YAML-driven plugin architecture
# ---------------------------------------------------------------------------


@dataclass
class IntentConfig:
    """Configuration loaded from a YAML intent file."""

    name: str
    description: str = ""
    triggers: list[str] = field(default_factory=list)
    role: str = "narrator"
    compression: str = "standard"
    token_budget: int = 4096
    model_tier: str = "primary"
    cache_ttl: int = 3600
    cacheable: bool = True
    template: str = ""
    skip_llm: bool = False


class IntentRegistry:
    """Loads and manages intent YAML configurations.

    Usage:
        registry = IntentRegistry()
        registry.load()  # loads from default intents/ directory
        config = registry.get("summarize")
    """

    def __init__(self, intents_dir: str | Path | None = None):
        self._intents_dir = Path(intents_dir) if intents_dir else (Path(__file__).parent / "intents")
        self._configs: dict[str, IntentConfig] = {}
        self._loaded = False

    @property
    def loaded(self) -> bool:
        return self._loaded

    @property
    def intents(self) -> dict[str, IntentConfig]:
        return dict(self._configs)

    def load(self) -> None:
        """Load all YAML files from the intents directory.

        Uses a minimal YAML parser (no PyYAML dependency) that handles
        the simple key: value format used by intent files.
        """
        self._configs.clear()
        if not self._intents_dir.is_dir():
            logger.warning("Intents directory not found: %s", self._intents_dir)
            self._loaded = True
            return

        for yaml_path in sorted(self._intents_dir.glob("*.yaml")):
            try:
                config = self._parse_yaml(yaml_path)
                if config:
                    self._configs[config.name] = config
            except Exception:
                logger.exception("Failed to load intent YAML: %s", yaml_path)

        self._loaded = True
        logger.info("Loaded %d intent configs from %s", len(self._configs), self._intents_dir)

    def reload(self) -> None:
        """Hot-reload all intent configurations."""
        self.load()

    def get(self, name: str) -> IntentConfig | None:
        """Get intent config by name."""
        if not self._loaded:
            self.load()
        return self._configs.get(name)

    def get_for_action(self, action: IntentAction) -> IntentConfig | None:
        """Get intent config matching an IntentAction."""
        return self.get(action.value)

    def all_names(self) -> list[str]:
        """Return all loaded intent names."""
        if not self._loaded:
            self.load()
        return list(self._configs.keys())

    # --- Minimal YAML parser (stdlib only) ---

    @staticmethod
    def _parse_yaml(path: Path) -> IntentConfig | None:
        """Parse a simple YAML file into an IntentConfig.

        Handles: scalars, simple lists (- item), and booleans.
        Does NOT handle nested objects, multi-line strings, or anchors.
        """
        data: dict[str, Any] = {}
        current_key: str | None = None
        current_list: list[str] | None = None

        with open(path, encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.rstrip("\n")
                stripped = line.strip()

                # Skip comments and empty lines
                if not stripped or stripped.startswith("#"):
                    continue

                # List item
                if stripped.startswith("- "):
                    if current_key is not None and current_list is not None:
                        current_list.append(stripped[2:].strip().strip('"').strip("'"))
                    continue

                # Key: value
                if ":" in stripped:
                    # Flush any pending list
                    if current_key and current_list is not None:
                        data[current_key] = current_list
                        current_list = None

                    colon_idx = stripped.index(":")
                    key = stripped[:colon_idx].strip()
                    value = stripped[colon_idx + 1 :].strip()

                    if not value:
                        # Start of a list or empty value
                        current_key = key
                        current_list = []
                    else:
                        current_key = None
                        current_list = None
                        # Parse value
                        value = value.strip('"').strip("'")
                        data[key] = value

        # Flush final list
        if current_key and current_list is not None:
            data[current_key] = current_list

        name = data.get("name", "")
        if not name:
            # Use filename as name
            name = path.stem

        # Type coerce
        def _bool(v: Any) -> bool:
            if isinstance(v, bool):
                return v
            if isinstance(v, str):
                return v.lower() in ("true", "yes", "1")
            return bool(v)

        def _int(v: Any, default: int = 0) -> int:
            try:
                return int(v)
            except (ValueError, TypeError):
                return default

        triggers = data.get("triggers", [])
        if isinstance(triggers, str):
            triggers = [triggers]

        return IntentConfig(
            name=name,
            description=str(data.get("description", "")),
            triggers=triggers,
            role=str(data.get("role", "narrator")),
            compression=str(data.get("compression", "standard")),
            token_budget=_int(data.get("token_budget"), 4096),
            model_tier=str(data.get("model_tier", "primary")),
            cache_ttl=_int(data.get("cache_ttl"), 3600),
            cacheable=_bool(data.get("cacheable", True)),
            template=str(data.get("template", "")),
            skip_llm=_bool(data.get("skip_llm", False)),
        )
