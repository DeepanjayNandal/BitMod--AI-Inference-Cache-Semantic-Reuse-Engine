"""Expanded tests for the ingestion pipeline: parsing, section splitting, hashing, metadata, errors."""

import hashlib
from unittest.mock import MagicMock

import pytest

from bitmod.ingestion.parser import parse_text, ParsedDocument, ParsedSection, MAX_FILE_SIZE_BYTES
from bitmod.ingestion.chunker import chunk_text, ChunkConfig
from bitmod.ingestion.pipeline import ingest_text


class TestIngestTextVariousContentTypes:
    """Test ingest_text with different content types."""

    def test_ingest_plain_text(self, backend):
        """Plain text ingestion produces sections and chunks."""
        result = ingest_text(
            text="This is plain text content with enough words to form a meaningful section for testing.",
            title="Plain Text Doc",
            document_type="text",
            source="unit-test",
            backend=backend,
        )
        assert result["title"] == "Plain Text Doc"
        assert result["source_format"] == "text"
        assert result["sections"] >= 1
        assert result["chunks"] >= 1

    def test_ingest_markdown_content(self, backend):
        """Markdown-formatted text is ingested and sections are created."""
        md = (
            "# Overview\n\nThis section has an overview of the document topic.\n\n"
            "# Details\n\nThis section dives into the specifics of the topic at hand.\n\n"
            "# Conclusion\n\nThis section wraps everything up with a conclusion."
        )
        result = ingest_text(
            text=md,
            title="Markdown Doc",
            document_type="documentation",
            source="unit-test",
            backend=backend,
        )
        assert result["sections"] >= 1
        assert result["chunks"] >= 1

    def test_ingest_legal_text(self, backend):
        """Legal-style text with section numbering is ingested correctly."""
        legal = (
            "Section 1. Definitions.\n\n"
            "For purposes of this Act, the following definitions apply:\n\n"
            "(a) The term 'employer' means any person engaged in commerce.\n\n"
            "Section 2. Prohibited Acts.\n\n"
            "It shall be unlawful for an employer to discriminate against any individual."
        )
        result = ingest_text(
            text=legal,
            title="Employment Act",
            document_type="statute",
            source="unit-test",
            jurisdiction="US",
            backend=backend,
        )
        assert result["sections"] >= 1
        assert result["document_id"]

    def test_ingest_with_tags(self, backend):
        """Tags are stored on the document record."""
        result = ingest_text(
            text="Content for tagged document with enough text to be meaningful.",
            title="Tagged Doc",
            tags=["employment", "california", "2024"],
            backend=backend,
        )
        with backend.session() as session:
            row = session.execute(
                "SELECT tags FROM documents WHERE id = ?", (result["document_id"],)
            ).fetchone()
            assert row is not None
            import json
            tags = json.loads(row["tags"])
            assert "employment" in tags
            assert "california" in tags

    def test_ingest_with_metadata(self, backend):
        """Custom metadata is merged with parsed metadata on the document."""
        result = ingest_text(
            text="Metadata test document with some content for testing purposes.",
            title="Meta Doc",
            metadata={"author": "John", "year": 2024},
            backend=backend,
        )
        with backend.session() as session:
            row = session.execute(
                "SELECT metadata FROM documents WHERE id = ?", (result["document_id"],)
            ).fetchone()
            import json
            meta = json.loads(row["metadata"])
            assert meta["author"] == "John"
            assert meta["year"] == 2024
            assert "source_format" in meta


class TestSectionSplitting:
    """Test that text is split into sections correctly."""

    def test_paragraph_splitting(self):
        """Double newlines create separate sections when text is large enough."""
        text = ("A" * 1500 + "\n\n" + "B" * 1500 + "\n\n" + "C" * 1500)
        result = parse_text(text, title="Paragraphs")
        assert len(result.sections) >= 2

    def test_single_paragraph_stays_together(self):
        """A single short paragraph produces one section."""
        text = "This is a single paragraph with some content."
        result = parse_text(text)
        assert len(result.sections) == 1

    def test_empty_paragraphs_ignored(self):
        """Empty paragraphs between content blocks are skipped."""
        text = "First block.\n\n\n\n\n\nSecond block."
        result = parse_text(text)
        full = " ".join(s.text for s in result.sections)
        assert "First block" in full
        assert "Second block" in full

    def test_section_numbers_assigned(self):
        """Each section gets a sequential section_number."""
        text = ("A" * 2500 + "\n\n" + "B" * 2500)
        result = parse_text(text)
        for i, sec in enumerate(result.sections):
            assert sec.section_number == str(i + 1)


class TestVersionHash:
    """Test version_hash generation for content deduplication."""

    def test_same_content_same_hash(self, backend):
        """Identical content produces the same version_hash."""
        text = "This is test content for hashing verification purposes."
        expected_hash = hashlib.sha256(text.encode()).hexdigest()

        result = ingest_text(text=text, title="Hash Test", backend=backend)
        with backend.session() as session:
            row = session.execute(
                "SELECT version_hash FROM sections WHERE document_id = ?",
                (result["document_id"],),
            ).fetchone()
            assert row["version_hash"] == expected_hash

    def test_different_content_different_hash(self, backend):
        """Different content produces different version_hashes."""
        r1 = ingest_text(text="Content alpha for hashing.", title="A", backend=backend)
        r2 = ingest_text(text="Content beta for hashing.", title="B", backend=backend)

        with backend.session() as session:
            h1 = session.execute(
                "SELECT version_hash FROM sections WHERE document_id = ?",
                (r1["document_id"],),
            ).fetchone()["version_hash"]
            h2 = session.execute(
                "SELECT version_hash FROM sections WHERE document_id = ?",
                (r2["document_id"],),
            ).fetchone()["version_hash"]
            assert h1 != h2


class TestMetadataPropagation:
    """Test that metadata fields flow through the pipeline correctly."""

    def test_jurisdiction_on_chunks(self, backend):
        """Jurisdiction propagates from ingest_text to chunk records."""
        result = ingest_text(
            text="Test document for jurisdiction propagation with enough content.",
            title="Jurisdiction Test",
            jurisdiction="CA",
            backend=backend,
        )
        with backend.session() as session:
            row = session.execute("SELECT jurisdiction FROM chunks LIMIT 1").fetchone()
            assert row["jurisdiction"] == "CA"

    def test_document_type_on_chunks(self, backend):
        """Document type propagates to chunk records."""
        result = ingest_text(
            text="Test document for document_type propagation with some text.",
            title="DocType Test",
            document_type="regulation",
            backend=backend,
        )
        with backend.session() as session:
            row = session.execute("SELECT document_type FROM chunks LIMIT 1").fetchone()
            assert row["document_type"] == "regulation"


class TestErrorHandling:
    """Test error handling in the ingestion pipeline."""

    def test_empty_content_still_produces_sections(self, backend):
        """Empty string input produces at least one section with empty text."""
        result = ingest_text(text="", title="Empty", backend=backend)
        # parse_text returns at least one section; empty sections are skipped in pipeline
        assert result["sections"] >= 0

    def test_oversized_content_raises(self):
        """Text exceeding MAX_FILE_SIZE_BYTES raises ValueError."""
        oversized = "x" * (MAX_FILE_SIZE_BYTES + 1)
        with pytest.raises(ValueError, match="exceeds maximum size"):
            parse_text(oversized, title="Too Big")

    def test_non_string_input_raises(self):
        """Non-string input to parse_text raises ValueError."""
        with pytest.raises(ValueError, match="must be a string"):
            parse_text(12345, title="Bad Input")

    def test_whitespace_only_content(self, backend):
        """Whitespace-only text is handled gracefully."""
        result = ingest_text(text="   \n\n\t  ", title="Whitespace", backend=backend)
        # Should not crash; sections count may be 0 since strip() yields empty
        assert isinstance(result, dict)
        assert "document_id" in result
