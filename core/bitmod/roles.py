"""Bitmod Role Router.

Maps detected intents to LLM roles with appropriate model configuration.
Role definitions are loaded from roles.yaml for hot-reloadability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from bitmod.intent import DetectedIntent, IntentAction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Role Enum
# ---------------------------------------------------------------------------


class Role(str, Enum):
    """LLM behavioral role assigned based on intent."""

    NARRATOR = "narrator"
    SYNTHESIZER = "synthesizer"
    STRUCTURER = "structurer"
    REASONER = "reasoner"
    EXPLORER = "explorer"
    AGENT = "agent"


# ---------------------------------------------------------------------------
# Role Configuration
# ---------------------------------------------------------------------------


@dataclass
class RoleConfig:
    """Configuration for a single role."""

    role: Role
    description: str = ""
    model_tier: str = "primary"
    max_input_tokens: int = 8192
    max_output_tokens: int = 4096
    system_prompt: str = ""


# ---------------------------------------------------------------------------
# Default Role Mappings
# ---------------------------------------------------------------------------

_ACTION_ROLE_MAP: dict[IntentAction, Role] = {
    # Passive retrieval → narrator
    IntentAction.CITE: Role.NARRATOR,
    IntentAction.QUOTE: Role.NARRATOR,
    IntentAction.REFERENCE: Role.NARRATOR,
    IntentAction.LOOKUP: Role.NARRATOR,
    IntentAction.FIND: Role.NARRATOR,
    IntentAction.SHOW: Role.NARRATOR,
    # Lists → structurer
    IntentAction.LIST: Role.STRUCTURER,
    # Synthesis → synthesizer
    IntentAction.SUMMARIZE: Role.SYNTHESIZER,
    IntentAction.EXPLAIN: Role.NARRATOR,
    IntentAction.COMPARE: Role.SYNTHESIZER,
    IntentAction.CONTRAST: Role.SYNTHESIZER,
    IntentAction.PARAPHRASE: Role.SYNTHESIZER,
    IntentAction.TRANSLATE: Role.SYNTHESIZER,
    # Reasoning → reasoner
    IntentAction.THINK: Role.REASONER,
    IntentAction.HYPOTHESIZE: Role.REASONER,
    IntentAction.ANALYZE: Role.REASONER,
    IntentAction.THEORIZE: Role.REASONER,
    IntentAction.EVALUATE: Role.REASONER,
    IntentAction.DEBATE: Role.REASONER,
    IntentAction.PREDICT: Role.REASONER,
    # Agentic → agent
    IntentAction.EXECUTE: Role.AGENT,
    IntentAction.BUILD: Role.AGENT,
    IntentAction.DEPLOY: Role.AGENT,
    IntentAction.TRANSFORM: Role.AGENT,
    # Deterministic → structurer
    IntentAction.EXTRACT: Role.STRUCTURER,
    IntentAction.CONVERT: Role.STRUCTURER,
    IntentAction.COUNT: Role.STRUCTURER,
    IntentAction.CALCULATE: Role.STRUCTURER,
    IntentAction.VALIDATE: Role.STRUCTURER,
    # Creative → explorer
    IntentAction.BRAINSTORM: Role.EXPLORER,
    IntentAction.CREATE: Role.EXPLORER,
    IntentAction.WRITE: Role.EXPLORER,
    IntentAction.DRAFT: Role.EXPLORER,
    IntentAction.GENERATE: Role.EXPLORER,
    IntentAction.COMPOSE: Role.EXPLORER,
    # Meta
    IntentAction.CLARIFY: Role.NARRATOR,
    IntentAction.UNKNOWN: Role.NARRATOR,
}


# ---------------------------------------------------------------------------
# Role Registry
# ---------------------------------------------------------------------------


class RoleRegistry:
    """Loads role configurations from YAML and resolves intents to roles."""

    def __init__(self, config_path: str | Path | None = None):
        self._config_path = Path(config_path) if config_path else (Path(__file__).parent / "roles.yaml")
        self._configs: dict[Role, RoleConfig] = {}
        self._loaded = False

    @property
    def loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        """Load role configurations from YAML."""
        self._configs.clear()

        # Set defaults first
        for role in Role:
            self._configs[role] = RoleConfig(role=role)

        if self._config_path.is_file():
            data = self._parse_yaml(self._config_path)
            for role_name, role_data in data.items():
                try:
                    role = Role(role_name)
                except ValueError:
                    logger.warning("Unknown role in YAML: %s", role_name)
                    continue

                if isinstance(role_data, dict):
                    self._configs[role] = RoleConfig(
                        role=role,
                        description=str(role_data.get("description", "")),
                        model_tier=str(role_data.get("model_tier", "primary")),
                        max_input_tokens=int(role_data.get("max_input_tokens", 8192)),
                        max_output_tokens=int(role_data.get("max_output_tokens", 4096)),
                        system_prompt=str(role_data.get("system_prompt", "")),
                    )
        else:
            logger.warning("Roles config not found: %s", self._config_path)

        self._loaded = True
        logger.info("Loaded %d role configs", len(self._configs))

    def reload(self) -> None:
        """Hot-reload role configurations."""
        self.load()

    def get(self, role: Role) -> RoleConfig:
        """Get configuration for a role."""
        if not self._loaded:
            self.load()
        return self._configs.get(role, RoleConfig(role=role))

    def resolve(self, intent: DetectedIntent, section_tags: list[str] | None = None) -> tuple[Role, RoleConfig]:
        """Resolve a detected intent to a role and its configuration.

        Args:
            intent: The detected intent from the query.
            section_tags: Optional tags from matched document sections that may
                influence role selection (e.g., "legal" → NARRATOR for precision).

        Returns:
            Tuple of (Role, RoleConfig).
        """
        if not self._loaded:
            self.load()

        # Start with the default role for this action
        role = _ACTION_ROLE_MAP.get(intent.action, Role.NARRATOR)

        # Section tag overrides: domain-specific adjustments
        if section_tags:
            tag_set = set(t.lower() for t in section_tags)
            # Legal/regulatory content should use narrator for precision
            if tag_set & {"legal", "regulatory", "statute", "regulation", "law"}:
                if role == Role.SYNTHESIZER:
                    role = Role.NARRATOR
            # Technical content with reasoning intent stays as reasoner
            # Creative content on factual sources gets downgraded to synthesizer
            if tag_set & {"factual", "reference", "encyclopedia"}:
                if role == Role.EXPLORER:
                    role = Role.SYNTHESIZER

        config = self._configs.get(role, RoleConfig(role=role))
        return role, config

    # --- Minimal YAML parser ---

    @staticmethod
    def _parse_yaml(path: Path) -> dict[str, Any]:
        """Parse roles.yaml into a dict of {role_name: {key: value}}."""
        result: dict[str, Any] = {}
        current_section: str | None = None

        with open(path, encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.rstrip("\n")
                stripped = line.strip()

                if not stripped or stripped.startswith("#"):
                    continue

                # Top-level key (no leading spaces)
                if not line[0].isspace() and ":" in stripped:
                    colon_idx = stripped.index(":")
                    key = stripped[:colon_idx].strip()
                    value = stripped[colon_idx + 1 :].strip()
                    if not value:
                        current_section = key
                        result[key] = {}
                    else:
                        result[key] = value
                        current_section = None
                elif current_section and line[0].isspace() and ":" in stripped:
                    # Nested key
                    colon_idx = stripped.index(":")
                    key = stripped[:colon_idx].strip()
                    value = stripped[colon_idx + 1 :].strip().strip('"').strip("'")
                    if isinstance(result.get(current_section), dict):
                        result[current_section][key] = value

        return result
