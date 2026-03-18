"""Shared fixtures for Bitmod tests."""

import os
import tempfile

import pytest

from bitmod.adapters.db_sqlite import SQLiteBackend
from bitmod.interfaces.database import (
    AnswerCacheRecord,
    ChunkRecord,
    DocumentRecord,
    SectionRecord,
)


@pytest.fixture
def tmp_db_path(tmp_path):
    """Temporary SQLite database path."""
    return str(tmp_path / "test_bitmod.db")


@pytest.fixture
def backend(tmp_db_path):
    """Initialized SQLiteBackend using a temporary file."""
    b = SQLiteBackend(path=tmp_db_path)
    b.initialize()
    return b


@pytest.fixture
def sample_document():
    """A sample DocumentRecord."""
    return DocumentRecord(
        id="doc-001",
        document_type="statute",
        source="test",
        title="Test Statute",
        jurisdiction="US",
        source_format="text",
        metadata={"year": 2024},
        tags=["test", "law"],
    )


@pytest.fixture
def sample_section():
    """A sample SectionRecord."""
    return SectionRecord(
        id="sec-001",
        document_id="doc-001",
        text_content="This is the full text of section one about employment law.",
        version_hash="abc123hash",
        citation="42 U.S.C. § 1983",
        section_number="1",
        section_title="Employment Law",
        hierarchy_path="doc/section1",
        is_current=True,
        metadata={"jurisdiction": "US"},
        tags=["employment"],
    )


@pytest.fixture
def sample_chunk():
    """A sample ChunkRecord."""
    return ChunkRecord(
        id="chunk-001",
        section_id="sec-001",
        chunk_index=0,
        text_content="This is a chunk of text about employment law.",
        embedding=[0.1, 0.2, 0.3, 0.4],
        document_type="statute",
        jurisdiction="US",
        char_offset=0,
    )


@pytest.fixture
def sample_cache_record():
    """A sample AnswerCacheRecord."""
    return AnswerCacheRecord(
        id="cache-001",
        answer_key="testkey123",
        question_raw="What is employment law?",
        question_normalized="employment law",
        filters={"jurisdiction": "US"},
        answer_text="Employment law governs the relationship between employers and employees.",
        source_sections=[
            {"section_id": "sec-001", "version_hash": "abc123hash"},
        ],
        model_used="claude-sonnet-4-20250514",
        generation_ms=1500,
        confidence=0.95,
    )
