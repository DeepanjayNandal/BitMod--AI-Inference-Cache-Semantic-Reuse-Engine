"""LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field


@dataclass
class LLMMessage:
    role: str  # system, user, assistant, tool
    content: str
    tool_call_id: str | None = None
    tool_calls: list[dict] | None = None


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[dict] | None = None
    model: str = ""
    usage: dict = field(default_factory=dict)


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict


class LLMProvider(ABC):
    """Abstract interface for LLM providers.

    Implementations: Anthropic, OpenAI, OpenAI-Compatible, Ollama,
    Gemini, AWS Bedrock, Azure OpenAI.
    """

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        model: str = "",
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Generate a response from the LLM."""

    @abstractmethod
    def stream(
        self,
        messages: list[LLMMessage],
        model: str = "",
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream tokens from the LLM."""
        ...
