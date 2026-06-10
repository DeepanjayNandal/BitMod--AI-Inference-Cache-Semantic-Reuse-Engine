"""Project Knowledge System — local project indexing and conversation memory.

Tracks project files, indexes code/text into searchable chunks,
records conversations for context-aware AI responses, and learns
from user corrections.
"""

from bitmod.project.context import ContextAssembler
from bitmod.project.indexer import ProjectIndexer
from bitmod.project.memory import ConversationMemory

__all__ = ["ProjectIndexer", "ConversationMemory", "ContextAssembler"]
