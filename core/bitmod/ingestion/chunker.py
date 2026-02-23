"""Text chunking engine for Bitmod.

Splits sections into overlapping chunks suitable for embedding and retrieval.

Strategies:
- recursive: Split by paragraph → sentence → word (default, best for prose)
- fixed: Fixed character windows with overlap (simple, predictable)
- semantic: Split on sentence boundaries preserving meaning (best quality)
"""

import re
from dataclasses import dataclass


@dataclass
class ChunkConfig:
    """Configuration for text chunking."""

    chunk_size: int = 500  # Target chunk size in characters
    chunk_overlap: int = 50  # Overlap between consecutive chunks
    min_chunk_size: int = 50  # Minimum chunk size (skip tiny fragments)
    strategy: str = "recursive"  # recursive, fixed, semantic


@dataclass
class TextChunk:
    """A single chunk of text with position metadata."""

    text: str
    chunk_index: int
    char_offset: int
    metadata: dict | None = None


def chunk_sections(
    sections: list[dict],
    config: ChunkConfig | None = None,
) -> list[list[TextChunk]]:
    """Chunk a list of sections. Returns a list of chunk lists (one per section).

    Each section dict should have at minimum: {"text": "...", "title": "..."}
    """
    config = config or ChunkConfig()
    results: list = []
    for section in sections:
        text = section.get("text", "")
        if not text.strip():
            results.append([])
            continue

        if config.strategy == "fixed":
            chunks = _chunk_fixed(text, config)
        elif config.strategy == "semantic":
            chunks = _chunk_semantic(text, config)
        else:
            chunks = _chunk_recursive(text, config)

        results.append(chunks)
    return results


def chunk_text(text: str, config: ChunkConfig | None = None) -> list[TextChunk]:
    """Chunk a single text string."""
    config = config or ChunkConfig()
    if config.strategy == "fixed":
        return _chunk_fixed(text, config)
    elif config.strategy == "semantic":
        return _chunk_semantic(text, config)
    return _chunk_recursive(text, config)


# ---------------------------------------------------------------------------
# Chunking strategies
# ---------------------------------------------------------------------------


def _chunk_recursive(text: str, config: ChunkConfig) -> list[TextChunk]:
    """Recursive chunking: try paragraph splits, then sentences, then words.

    This is the best general-purpose strategy. It preserves natural boundaries
    (paragraphs and sentences) while keeping chunks within the size limit.
    """
    if len(text) <= config.chunk_size:
        stripped = text.strip()
        if stripped and len(stripped) >= config.min_chunk_size:
            return [TextChunk(text=stripped, chunk_index=0, char_offset=0)]
        return []

    # Try splitting by paragraphs first
    separators = ["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " "]
    return _recursive_split(text, separators, config)


def _recursive_split(
    text: str,
    separators: list[str],
    config: ChunkConfig,
) -> list[TextChunk]:
    """Split text recursively using a hierarchy of separators."""
    if not separators:
        return _chunk_fixed(text, config)

    sep = separators[0]
    remaining_seps = separators[1:]

    parts = text.split(sep)
    chunks: list[TextChunk] = []
    current_parts: list[str] = []
    current_len = 0
    char_offset = 0

    for part in parts:
        part_len = len(part) + len(sep)
        if current_len + part_len > config.chunk_size and current_parts:
            chunk_text_str = sep.join(current_parts).strip()
            if len(chunk_text_str) >= config.min_chunk_size:
                chunks.append(
                    TextChunk(
                        text=chunk_text_str,
                        chunk_index=len(chunks),
                        char_offset=char_offset,
                    )
                )
            # Overlap: keep last part(s) that fit within overlap size
            overlap_parts: list[str] = []
            overlap_len = 0
            for p in reversed(current_parts):
                if overlap_len + len(p) > config.chunk_overlap:
                    break
                overlap_parts.insert(0, p)
                overlap_len += len(p) + len(sep)

            char_offset += current_len - overlap_len
            current_parts = overlap_parts
            current_len = overlap_len

        current_parts.append(part)
        current_len += part_len

    # Handle remaining text
    if current_parts:
        remaining = sep.join(current_parts).strip()
        if len(remaining) > config.chunk_size and remaining_seps:
            sub_chunks = _recursive_split(remaining, remaining_seps, config)
            for sc in sub_chunks:
                sc.chunk_index = len(chunks) + sc.chunk_index
                sc.char_offset += char_offset
                chunks.append(sc)
        elif len(remaining) >= config.min_chunk_size:
            chunks.append(
                TextChunk(
                    text=remaining,
                    chunk_index=len(chunks),
                    char_offset=char_offset,
                )
            )

    return chunks


def _chunk_fixed(text: str, config: ChunkConfig) -> list[TextChunk]:
    """Fixed-window chunking with overlap."""
    chunks: list = []
    start = 0
    while start < len(text):
        end = start + config.chunk_size
        chunk = text[start:end].strip()
        if len(chunk) >= config.min_chunk_size:
            chunks.append(
                TextChunk(
                    text=chunk,
                    chunk_index=len(chunks),
                    char_offset=start,
                )
            )
        start += config.chunk_size - config.chunk_overlap
    return chunks


def _chunk_semantic(text: str, config: ChunkConfig) -> list[TextChunk]:
    """Sentence-boundary chunking — split on sentence endings.

    Groups complete sentences into chunks up to chunk_size.
    Never breaks mid-sentence.
    """
    sentences = _split_sentences(text)
    chunks: list[TextChunk] = []
    current_sentences: list[str] = []
    current_len = 0
    char_offset = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if current_len + len(sentence) > config.chunk_size and current_sentences:
            chunk_text_str = " ".join(current_sentences)
            if len(chunk_text_str) >= config.min_chunk_size:
                chunks.append(
                    TextChunk(
                        text=chunk_text_str,
                        chunk_index=len(chunks),
                        char_offset=char_offset,
                    )
                )
            # Overlap: keep last sentence(s) within overlap
            overlap_sents: list[str] = []
            overlap_len = 0
            for s in reversed(current_sentences):
                if overlap_len + len(s) > config.chunk_overlap:
                    break
                overlap_sents.insert(0, s)
                overlap_len += len(s) + 1

            char_offset += current_len - overlap_len
            current_sentences = overlap_sents
            current_len = overlap_len

        current_sentences.append(sentence)
        current_len += len(sentence) + 1

    if current_sentences:
        chunk_text_str = " ".join(current_sentences)
        if len(chunk_text_str) >= config.min_chunk_size:
            chunks.append(
                TextChunk(
                    text=chunk_text_str,
                    chunk_index=len(chunks),
                    char_offset=char_offset,
                )
            )

    return chunks


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using regex."""
    # Handle common abbreviations to avoid false splits
    text = re.sub(r"(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|vs|etc|Inc|Ltd|Corp)\.", r"\1<DOT>", text)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.replace("<DOT>", ".") for s in sentences if s.strip()]
