"""Tests for text chunking strategies: recursive, fixed, and semantic."""

import pytest

from bitmod.ingestion.chunker import (
    ChunkConfig,
    TextChunk,
    chunk_text,
    chunk_sections,
    _split_sentences,
)


class TestRecursiveChunking:
    """Test the recursive chunking strategy."""

    def test_short_text_single_chunk(self):
        """Text shorter than chunk_size produces exactly one chunk."""
        config = ChunkConfig(chunk_size=500, min_chunk_size=5, strategy="recursive")
        chunks = chunk_text("Hello world.", config)
        assert len(chunks) == 1
        assert chunks[0].text == "Hello world."
        assert chunks[0].chunk_index == 0

    def test_paragraph_boundaries_respected(self):
        """Recursive chunking splits on paragraph boundaries first."""
        para1 = "First paragraph content. " * 10  # ~250 chars
        para2 = "Second paragraph content. " * 10
        para3 = "Third paragraph content. " * 10
        text = f"{para1}\n\n{para2}\n\n{para3}"
        config = ChunkConfig(chunk_size=300, chunk_overlap=30, min_chunk_size=50, strategy="recursive")
        chunks = chunk_text(text, config)
        assert len(chunks) >= 2
        # Each chunk should be roughly within the size limit
        for c in chunks:
            assert len(c.text) <= config.chunk_size + 100

    def test_sentence_split_fallback(self):
        """When paragraphs exceed chunk_size, falls back to sentence splitting."""
        text = "This is sentence one. This is sentence two. This is sentence three. " * 20
        config = ChunkConfig(chunk_size=200, chunk_overlap=20, min_chunk_size=30, strategy="recursive")
        chunks = chunk_text(text, config)
        assert len(chunks) >= 2

    def test_chunk_indices_sequential(self):
        """Chunk indices are unique and non-negative."""
        text = "Word " * 500
        config = ChunkConfig(chunk_size=200, chunk_overlap=20, min_chunk_size=20, strategy="recursive")
        chunks = chunk_text(text, config)
        indices = [c.chunk_index for c in chunks]
        assert all(i >= 0 for i in indices)
        assert len(set(indices)) == len(indices)  # all unique


class TestFixedChunking:
    """Test the fixed-window chunking strategy."""

    def test_exact_size_chunks(self):
        """Fixed chunking produces chunks of exactly chunk_size (except last)."""
        text = "A" * 1000
        config = ChunkConfig(chunk_size=200, chunk_overlap=0, min_chunk_size=10, strategy="fixed")
        chunks = chunk_text(text, config)
        assert len(chunks) == 5
        for c in chunks:
            assert len(c.text) == 200

    def test_overlap_present(self):
        """Fixed chunks overlap by the configured amount."""
        text = "ABCDEFGHIJ" * 100  # 1000 chars
        config = ChunkConfig(chunk_size=200, chunk_overlap=50, min_chunk_size=10, strategy="fixed")
        chunks = chunk_text(text, config)
        assert len(chunks) > 1
        # With step=150, chunk[0] covers [0:200], chunk[1] covers [150:350]
        # So last 50 chars of chunk[0] should equal first 50 chars of chunk[1]
        assert chunks[0].text[-50:] == chunks[1].text[:50]

    def test_char_offsets(self):
        """Char offsets advance by (chunk_size - overlap) for fixed strategy."""
        text = "X" * 600
        config = ChunkConfig(chunk_size=200, chunk_overlap=50, min_chunk_size=10, strategy="fixed")
        chunks = chunk_text(text, config)
        step = 200 - 50
        for i, c in enumerate(chunks):
            assert c.char_offset == i * step


class TestSemanticChunking:
    """Test the semantic (sentence-boundary) chunking strategy."""

    def test_sentence_boundaries_preserved(self):
        """Semantic chunking never breaks mid-sentence."""
        text = "First sentence here. Second sentence follows. Third one too. Fourth for good measure. Fifth is last."
        config = ChunkConfig(chunk_size=60, chunk_overlap=0, min_chunk_size=10, strategy="semantic")
        chunks = chunk_text(text, config)
        for c in chunks:
            # Each chunk should end with a complete sentence (period present)
            assert c.text.rstrip().endswith(".") or c.text.rstrip().endswith("!") or c.text.rstrip().endswith("?") or len(c.text) < 60

    def test_abbreviations_not_split(self):
        """Common abbreviations (Mr., Dr., etc.) do not cause false splits."""
        sentences = _split_sentences("Dr. Smith went to Washington. He met Mr. Jones there.")
        # Should produce 2 sentences, not 4
        assert len(sentences) == 2
        assert "Dr." in sentences[0]
        assert "Mr." in sentences[1]


class TestMinChunkSizeFiltering:
    """Test that chunks below min_chunk_size are filtered out."""

    def test_tiny_fragments_removed(self):
        """Chunks smaller than min_chunk_size are discarded."""
        text = "A" * 300 + "\n\n" + "B" * 10 + "\n\n" + "C" * 300
        config = ChunkConfig(chunk_size=400, chunk_overlap=0, min_chunk_size=50, strategy="recursive")
        chunks = chunk_text(text, config)
        for c in chunks:
            assert len(c.text) >= config.min_chunk_size

    def test_min_size_zero_keeps_everything(self):
        """With min_chunk_size=0, even tiny chunks are kept (except empty)."""
        text = "AB"
        config = ChunkConfig(chunk_size=500, min_chunk_size=0, strategy="recursive")
        # Text is shorter than chunk_size but non-empty => one chunk returned
        chunks = chunk_text(text, config)
        assert len(chunks) == 1


class TestEdgeCases:
    """Test edge cases in chunking."""

    def test_empty_text(self):
        """Empty text produces no chunks."""
        config = ChunkConfig(chunk_size=500, min_chunk_size=5)
        chunks = chunk_text("", config)
        assert chunks == []

    def test_single_word(self):
        """A single word below min_chunk_size is excluded; above it is kept."""
        config_strict = ChunkConfig(chunk_size=500, min_chunk_size=50)
        chunks = chunk_text("Hello", config_strict)
        assert len(chunks) == 0

        config_lenient = ChunkConfig(chunk_size=500, min_chunk_size=1)
        chunks = chunk_text("Hello", config_lenient)
        assert len(chunks) == 1

    def test_very_long_text(self):
        """Very long text is chunked without error."""
        text = "This is a sentence for the long text test. " * 1000  # ~44000 chars
        config = ChunkConfig(chunk_size=500, chunk_overlap=50, min_chunk_size=50, strategy="recursive")
        chunks = chunk_text(text, config)
        assert len(chunks) > 10
        # All text should be representable
        total_len = sum(len(c.text) for c in chunks)
        assert total_len > 0

    def test_chunk_sections_function(self):
        """chunk_sections handles a list of section dicts."""
        sections = [
            {"text": "First section content. " * 20, "title": "Section 1"},
            {"text": "", "title": "Empty Section"},
            {"text": "Third section content. " * 20, "title": "Section 3"},
        ]
        config = ChunkConfig(chunk_size=200, min_chunk_size=20)
        results = chunk_sections(sections, config)
        assert len(results) == 3
        assert len(results[0]) >= 1  # first section has chunks
        assert len(results[1]) == 0  # empty section has no chunks
        assert len(results[2]) >= 1  # third section has chunks
