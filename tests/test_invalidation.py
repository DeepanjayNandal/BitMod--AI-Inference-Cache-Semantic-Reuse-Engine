"""Tests for the invalidation engine: change detection, change processing, bulk verification."""

import hashlib

import pytest

from bitmod.invalidation import detect_section_change, process_change_event, bulk_verify_sources
from bitmod.cache_engine import store_answer
from bitmod.interfaces.database import DocumentRecord, SectionRecord


def _setup_doc_and_section(backend, section_id="sec-inv-001", text="Original content."):
    """Helper: insert a document and section into the backend."""
    version_hash = hashlib.sha256(text.encode()).hexdigest()
    doc = DocumentRecord(
        id="doc-inv-001", document_type="test", source="test",
        title="Inv Doc", source_format="text",
    )
    sec = SectionRecord(
        id=section_id, document_id="doc-inv-001",
        text_content=text, version_hash=version_hash,
        is_current=True,
    )
    with backend.session() as session:
        backend.store_document(session, doc)
        backend.store_section(session, sec)
    return version_hash


class TestDetectSectionChange:
    """Test detect_section_change function."""

    def test_no_change_detected(self, backend):
        """Same content returns False (no change)."""
        text = "Original content."
        _setup_doc_and_section(backend, text=text)
        with backend.session() as session:
            assert detect_section_change(backend, session, "sec-inv-001", text) is False

    def test_change_detected(self, backend):
        """Different content returns True (change detected)."""
        _setup_doc_and_section(backend, text="Original content.")
        with backend.session() as session:
            assert detect_section_change(backend, session, "sec-inv-001", "Updated content.") is True

    def test_nonexistent_section(self, backend):
        """Nonexistent section returns False (no hash to compare)."""
        with backend.session() as session:
            result = detect_section_change(backend, session, "nonexistent", "any content")
            assert result is False


class TestProcessChangeEvent:
    """Test process_change_event function."""

    def test_no_change_event(self, backend):
        """When content is the same, returns changed=False."""
        text = "Original content."
        _setup_doc_and_section(backend, text=text)
        with backend.session() as session:
            result = process_change_event(backend, session, "sec-inv-001", text)
            assert result["changed"] is False
            assert result["invalidated_count"] == 0

    def test_change_invalidates_answers(self, backend):
        """When content changes, referencing answers are invalidated."""
        text = "Original content."
        old_hash = _setup_doc_and_section(backend, text=text)
        # Store an answer referencing this section
        with backend.session() as session:
            store_answer(
                backend, session, answer_key="change-ev-1",
                question_raw="q", question_normalized="q", filters={},
                answer_text="answer", model_used="test", generation_ms=100,
                source_sections=[{"section_id": "sec-inv-001", "version_hash": old_hash}],
            )
        with backend.session() as session:
            result = process_change_event(backend, session, "sec-inv-001", "Updated content.")
            assert result["changed"] is True
            assert result["invalidated_count"] == 1
            assert result["old_hash"] == old_hash
            assert result["new_hash"] != old_hash
            assert "processed_at" in result


class TestBulkVerifySources:
    """Test bulk_verify_sources function."""

    def test_bulk_verify_returns_stats(self, backend):
        """Bulk verify returns a summary dict with checked count and timestamp."""
        with backend.session() as session:
            result = bulk_verify_sources(backend, session)
            assert "total_checked" in result
            assert "verified_at" in result
            assert result["total_checked"] >= 0
