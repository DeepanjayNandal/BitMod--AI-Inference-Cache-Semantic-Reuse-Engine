"""Bitmod interfaces — stable contracts for all backend adapters."""

from bitmod.interfaces.database import ChunkRecord, DatabaseBackend, DocumentRecord, SearchResult, SectionRecord
from bitmod.interfaces.embeddings import EmbeddingProvider
from bitmod.interfaces.llm import LLMMessage, LLMProvider, LLMResponse, ToolDefinition
from bitmod.interfaces.messaging import IncomingMessage, MessagingPlatform, OutgoingMessage
from bitmod.interfaces.vectors import VectorStore

__all__ = [
    "DatabaseBackend",
    "DocumentRecord",
    "SectionRecord",
    "ChunkRecord",
    "SearchResult",
    "LLMProvider",
    "LLMMessage",
    "LLMResponse",
    "ToolDefinition",
    "EmbeddingProvider",
    "VectorStore",
    "MessagingPlatform",
    "IncomingMessage",
    "OutgoingMessage",
]
