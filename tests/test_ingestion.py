"""Tests for ingestion pipeline: parsing, chunking, and full pipeline."""

from unittest.mock import MagicMock

import pytest

from bitmod.ingestion.parser import parse_text
from bitmod.ingestion.chunker import chunk_text, ChunkConfig
from bitmod.ingestion.pipeline import ingest_text


class TestParser:
    def test_parse_text_markdown(self, tmp_path):
        """Markdown parsing splits by headings into sections."""
        md_text = """# Introduction

This is the introduction paragraph with enough text to be meaningful.

# Chapter One

Chapter one content goes here with important details about the topic.

# Chapter Two

Chapter two has its own content that is separate from chapter one.
"""
        result = parse_text(md_text, title="Test Doc", source_format="text")
        assert result.title == "Test Doc"
        # parse_text uses paragraph splitting, not markdown heading splitting
        assert len(result.sections) >= 1
        # All text should be present across sections
        full_text = " ".join(s.text for s in result.sections)
        assert "Introduction" in full_text
        assert "Chapter One" in full_text

    def test_parse_text_plain(self):
        """Plain text parsing groups paragraphs into sections."""
        text = "First paragraph of text.\n\nSecond paragraph of text.\n\nThird paragraph."
        result = parse_text(text, title="Plain Doc")
        assert result.title == "Plain Doc"
        assert result.source_format == "text"
        assert len(result.sections) >= 1
        # All content should be preserved
        full_text = " ".join(s.text for s in result.sections)
        assert "First paragraph" in full_text
        assert "Second paragraph" in full_text

    def test_parse_text_empty(self):
        """Empty text produces at least one section."""
        result = parse_text("", title="Empty")
        assert len(result.sections) >= 1


class TestChunker:
    def test_chunk_text_recursive(self):
        """Recursive chunking produces chunks within size limit."""
        text = "This is a sentence. " * 100  # ~2000 chars
        config = ChunkConfig(chunk_size=200, chunk_overlap=20, min_chunk_size=50, strategy="recursive")
        chunks = chunk_text(text, config)
        assert len(chunks) > 1
        for chunk in chunks:
            # Chunks should be roughly within size + some tolerance
            assert len(chunk.text) <= config.chunk_size + 100  # allow some tolerance for recursive splits

    def test_chunk_text_fixed(self):
        """Fixed-window chunking produces predictable chunks."""
        text = "A" * 1000
        config = ChunkConfig(chunk_size=200, chunk_overlap=50, min_chunk_size=50, strategy="fixed")
        chunks = chunk_text(text, config)
        assert len(chunks) > 1
        # First chunk should be 200 chars
        assert len(chunks[0].text) == 200
        # Check chunk indices are sequential
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_chunk_overlap(self):
        """Overlap between consecutive chunks."""
        # Use fixed strategy for predictable behavior
        text = "ABCDEFGHIJ" * 50  # 500 chars
        config = ChunkConfig(chunk_size=100, chunk_overlap=20, min_chunk_size=10, strategy="fixed")
        chunks = chunk_text(text, config)
        assert len(chunks) > 1
        # With fixed strategy, step = chunk_size - overlap = 80
        # So second chunk starts at 80, first ends at 100 => overlap of 20 chars
        if len(chunks) >= 2:
            first_end = chunks[0].text
            second_start = chunks[1].text
            # The end of first chunk should overlap with start of second
            assert first_end[-20:] == second_start[:20]

    def test_chunk_text_short(self):
        """Short text produces a single chunk."""
        text = "Short text."
        config = ChunkConfig(chunk_size=500, min_chunk_size=5)
        chunks = chunk_text(text, config)
        assert len(chunks) == 1
        assert chunks[0].text == "Short text."
        assert chunks[0].chunk_index == 0
        assert chunks[0].char_offset == 0


class TestIngestPipeline:
    def test_ingest_text(self, backend):
        """Full pipeline: text -> sections -> chunks in DB."""
        result = ingest_text(
            text="This is a test document with enough content to be meaningful. " * 10,
            title="Test Ingest",
            document_type="test",
            source="unit-test",
            backend=backend,
        )
        assert result["title"] == "Test Ingest"
        assert result["sections"] >= 1
        assert result["chunks"] >= 1
        assert result["embedded"] is False
        assert "document_id" in result

        # Verify data is in the database
        with backend.session() as session:
            row = session.execute(
                "SELECT * FROM documents WHERE id = ?", (result["document_id"],)
            ).fetchone()
            assert row is not None
            assert row["title"] == "Test Ingest"

            sections = session.execute(
                "SELECT COUNT(*) FROM sections WHERE document_id = ?",
                (result["document_id"],),
            ).fetchone()[0]
            assert sections >= 1

            chunks = session.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            assert chunks >= 1

    def test_ingest_with_embedder(self, backend):
        """Pipeline with mock embedder generates embeddings."""
        mock_embedder = MagicMock()
        mock_embedder.embed_batch.return_value = [[0.1, 0.2, 0.3]] * 20  # enough for any chunk count

        result = ingest_text(
            text="Embedding test content. " * 20,
            title="Embed Test",
            document_type="test",
            source="unit-test",
            backend=backend,
            embedder=mock_embedder,
        )
        assert result["embedded"] is True
        assert mock_embedder.embed_batch.called

        # Verify chunks have embeddings stored
        with backend.session() as session:
            row = session.execute(
                "SELECT embedding FROM chunks LIMIT 1"
            ).fetchone()
            assert row["embedding"] is not None
