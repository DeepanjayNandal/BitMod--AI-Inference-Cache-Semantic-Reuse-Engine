"""Tests for Content Blocks, Auto-Tagging, and Section Relationships."""

import json

import pytest

from bitmod.adapters.db_sqlite import SQLiteBackend
from bitmod.blocks import BlockGenerator, _estimate_tokens, _extract_headline, _extract_structured
from bitmod.interfaces.database import (
    ContentBlock,
    DocumentRecord,
    SectionRecord,
    SectionRelationship,
    SectionTag,
)
from bitmod.tags import AutoTagger


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def doc():
    return DocumentRecord(
        id="doc-b1",
        document_type="statute",
        source="test",
        title="Employment Law Handbook",
        jurisdiction="US",
        source_format="text",
        metadata={"year": 2024},
    )


@pytest.fixture
def narrative_section():
    return SectionRecord(
        id="sec-narr",
        document_id="doc-b1",
        text_content=(
            "The Supreme Court ruled on January 15, 2024 that 42 U.S.C. § 1983 "
            "provides a cause of action for individuals deprived of rights. "
            "The decision was unanimous, with Chief Justice Roberts writing the opinion. "
            "The plaintiff, John Smith Corporation, was awarded $1,500,000 in damages. "
            "This represents a 15.5% increase over the previous award."
        ),
        version_hash="hash_narr",
        section_title="Supreme Court Decision",
        hierarchy_path="chapter1/decisions",
        section_number="1.1",
    )


@pytest.fixture
def table_section():
    return SectionRecord(
        id="sec-table",
        document_id="doc-b1",
        text_content=(
            "| State | Minimum Wage | Effective Date |\n"
            "|-------|-------------|----------------|\n"
            "| CA | $15.50 | 2024-01-01 |\n"
            "| NY | $15.00 | 2024-01-01 |\n"
            "| TX | $7.25 | 2023-01-01 |"
        ),
        version_hash="hash_table",
        section_title="Minimum Wage Table",
        hierarchy_path="chapter2/wages",
        section_number="2.1",
    )


@pytest.fixture
def list_section():
    return SectionRecord(
        id="sec-list",
        document_id="doc-b1",
        text_content=(
            "Required documents for filing:\n"
            "- Form W-2 from employer\n"
            "- Identification documents\n"
            "- Proof of residency\n"
            "- Filing fee receipt"
        ),
        version_hash="hash_list",
        section_title="Filing Requirements",
        hierarchy_path="chapter3/filing",
        section_number="3.1",
    )


@pytest.fixture
def kv_section():
    return SectionRecord(
        id="sec-kv",
        document_id="doc-b1",
        text_content=(
            "Case Number: 2024-CV-12345\n"
            "Filing Date: March 15, 2024\n"
            "Jurisdiction: Federal District Court\n"
            "Plaintiff: Acme Corporation\n"
            "Defendant: Beta Industries"
        ),
        version_hash="hash_kv",
        section_title="Case Details",
        hierarchy_path="cases/details",
        section_number="4.1",
    )


@pytest.fixture
def short_section():
    return SectionRecord(
        id="sec-short",
        document_id="doc-b1",
        text_content="This is a brief note.",
        version_hash="hash_short",
        section_title="Brief Note",
        section_number="5.1",
    )


@pytest.fixture
def numbered_list_section():
    return SectionRecord(
        id="sec-numlist",
        document_id="doc-b1",
        text_content=(
            "Steps to complete registration:\n"
            "1. Submit application form\n"
            "2. Pay the registration fee\n"
            "3. Attend orientation session\n"
            "4. Complete background check"
        ),
        version_hash="hash_numlist",
        section_title="Registration Steps",
        hierarchy_path="chapter4/registration",
        section_number="6.1",
    )


# ---------------------------------------------------------------------------
# Token Estimation
# ---------------------------------------------------------------------------

class TestTokenEstimation:
    def test_empty_string(self):
        assert _estimate_tokens("") == 1  # min 1

    def test_single_word(self):
        assert _estimate_tokens("hello") == 1

    def test_sentence(self):
        text = "The quick brown fox jumps over the lazy dog"
        tokens = _estimate_tokens(text)
        assert tokens == int(9 * 1.3)  # 9 words * 1.3

    def test_multiline(self):
        text = "Line one has words.\nLine two also has words."
        tokens = _estimate_tokens(text)
        assert tokens > 0


# ---------------------------------------------------------------------------
# Headline Extraction
# ---------------------------------------------------------------------------

class TestHeadlineExtraction:
    def test_uses_section_title_when_present(self):
        headline = _extract_headline("Some long text content.", "My Title")
        assert headline == "My Title"

    def test_extracts_first_sentence(self):
        text = "This is the first sentence. And this is the second."
        headline = _extract_headline(text, None)
        assert headline == "This is the first sentence."

    def test_truncates_long_text(self):
        text = "A " * 200  # No sentence boundary
        headline = _extract_headline(text, None)
        assert len(headline) <= 130  # 120 + "..."

    def test_empty_text(self):
        assert _extract_headline("", None) == ""

    def test_empty_title_uses_text(self):
        text = "First sentence here. Second sentence."
        headline = _extract_headline(text, "")
        assert headline == "First sentence here."


# ---------------------------------------------------------------------------
# Structured Extraction
# ---------------------------------------------------------------------------

class TestStructuredExtraction:
    def test_table_extraction(self, table_section):
        result = _extract_structured(table_section.text_content)
        assert result["type"] == "table"
        assert "headers" in result
        assert len(result["rows"]) >= 2

    def test_key_value_extraction(self, kv_section):
        result = _extract_structured(kv_section.text_content)
        assert result["type"] == "key_value"
        assert "Case Number" in result["data"]
        assert result["data"]["Case Number"] == "2024-CV-12345"

    def test_bullet_list_extraction(self, list_section):
        result = _extract_structured(list_section.text_content)
        assert result["type"] == "bullet_list"
        assert len(result["items"]) == 4
        assert "Form W-2 from employer" in result["items"]

    def test_numbered_list_extraction(self, numbered_list_section):
        result = _extract_structured(numbered_list_section.text_content)
        assert result["type"] == "numbered_list"
        assert len(result["items"]) == 4

    def test_narrative_extraction(self, narrative_section):
        result = _extract_structured(narrative_section.text_content)
        assert result["type"] == "narrative"
        assert "facts" in result

    def test_empty_text(self):
        result = _extract_structured("")
        assert result["type"] == "empty"

    def test_narrative_extracts_dates(self, narrative_section):
        result = _extract_structured(narrative_section.text_content)
        assert "dates" in result["facts"]

    def test_narrative_extracts_amounts(self, narrative_section):
        result = _extract_structured(narrative_section.text_content)
        assert "amounts" in result["facts"]
        assert any("1,500,000" in a for a in result["facts"]["amounts"])

    def test_narrative_extracts_percentages(self, narrative_section):
        result = _extract_structured(narrative_section.text_content)
        assert "percentages" in result["facts"]
        assert "15.5%" in result["facts"]["percentages"]


# ---------------------------------------------------------------------------
# BlockGenerator — full integration with backend
# ---------------------------------------------------------------------------

class TestBlockGenerator:
    def test_generates_three_blocks(self, backend, doc, narrative_section):
        gen = BlockGenerator()
        with backend.session() as session:
            backend.store_document(session, doc)
            backend.store_section(session, narrative_section)
            blocks = gen.generate_blocks(narrative_section, backend, session)

        assert len(blocks) == 3
        compressions = {b.compression for b in blocks}
        assert compressions == {"full", "headline", "structured"}

    def test_full_block_content(self, backend, doc, narrative_section):
        gen = BlockGenerator()
        with backend.session() as session:
            backend.store_document(session, doc)
            backend.store_section(session, narrative_section)
            blocks = gen.generate_blocks(narrative_section, backend, session)

        full = [b for b in blocks if b.compression == "full"][0]
        assert full.content == narrative_section.text_content
        assert full.token_count > 0
        assert full.version_hash == "hash_narr"

    def test_headline_block(self, backend, doc, narrative_section):
        gen = BlockGenerator()
        with backend.session() as session:
            backend.store_document(session, doc)
            backend.store_section(session, narrative_section)
            blocks = gen.generate_blocks(narrative_section, backend, session)

        headline = [b for b in blocks if b.compression == "headline"][0]
        assert headline.content == "Supreme Court Decision"

    def test_structured_block_is_valid_json(self, backend, doc, narrative_section):
        gen = BlockGenerator()
        with backend.session() as session:
            backend.store_document(session, doc)
            backend.store_section(session, narrative_section)
            blocks = gen.generate_blocks(narrative_section, backend, session)

        structured = [b for b in blocks if b.compression == "structured"][0]
        data = json.loads(structured.content)
        assert "type" in data

    def test_blocks_stored_in_db(self, backend, doc, narrative_section):
        gen = BlockGenerator()
        with backend.session() as session:
            backend.store_document(session, doc)
            backend.store_section(session, narrative_section)
            gen.generate_blocks(narrative_section, backend, session)

        with backend.session() as session:
            blocks = backend.get_blocks(session, "sec-narr")
            assert len(blocks) == 3

    def test_get_blocks_by_compression(self, backend, doc, narrative_section):
        gen = BlockGenerator()
        with backend.session() as session:
            backend.store_document(session, doc)
            backend.store_section(session, narrative_section)
            gen.generate_blocks(narrative_section, backend, session)

        with backend.session() as session:
            headlines = backend.get_blocks(session, "sec-narr", compression="headline")
            assert len(headlines) == 1
            assert headlines[0].compression == "headline"


# ---------------------------------------------------------------------------
# Block Invalidation
# ---------------------------------------------------------------------------

class TestBlockInvalidation:
    def test_invalidate_blocks(self, backend, doc, narrative_section):
        gen = BlockGenerator()
        with backend.session() as session:
            backend.store_document(session, doc)
            backend.store_section(session, narrative_section)
            gen.generate_blocks(narrative_section, backend, session)

        with backend.session() as session:
            count = backend.invalidate_blocks(session, "sec-narr")
            assert count == 3

        with backend.session() as session:
            blocks = backend.get_blocks(session, "sec-narr")
            assert len(blocks) == 0

    def test_invalidate_nonexistent(self, backend):
        with backend.session() as session:
            count = backend.invalidate_blocks(session, "nonexistent")
            assert count == 0


# ---------------------------------------------------------------------------
# AutoTagger
# ---------------------------------------------------------------------------

class TestAutoTagger:
    def test_generates_domain_tag(self, narrative_section, doc):
        tagger = AutoTagger()
        tags = tagger.generate_tags(narrative_section, doc)
        domain_tags = [t for t in tags if t.tag_key == "domain"]
        assert len(domain_tags) == 1
        assert domain_tags[0].tag_value == "legal"

    def test_generates_topic_tags(self, narrative_section, doc):
        tagger = AutoTagger()
        tags = tagger.generate_tags(narrative_section, doc)
        topic_tags = [t for t in tags if t.tag_key == "topic"]
        assert len(topic_tags) >= 1
        # Section title should be a topic
        topic_values = [t.tag_value for t in topic_tags]
        assert "supreme court decision" in topic_values

    def test_generates_entity_tags(self, narrative_section, doc):
        tagger = AutoTagger()
        tags = tagger.generate_tags(narrative_section, doc)
        entity_tags = [t for t in tags if t.tag_key == "entities"]
        entity_values = [t.tag_value for t in entity_tags]
        # Should find the citation
        assert any("42 U.S.C." in v for v in entity_values)
        # Should find the dollar amount
        assert any("$1,500,000" in v for v in entity_values)

    def test_generates_complexity_tag(self, narrative_section, doc):
        tagger = AutoTagger()
        tags = tagger.generate_tags(narrative_section, doc)
        complexity_tags = [t for t in tags if t.tag_key == "complexity"]
        assert len(complexity_tags) == 1
        assert complexity_tags[0].tag_value in ("low", "medium", "high")

    def test_generates_format_hint_tag(self, narrative_section, doc):
        tagger = AutoTagger()
        tags = tagger.generate_tags(narrative_section, doc)
        fmt_tags = [t for t in tags if t.tag_key == "format_hint"]
        assert len(fmt_tags) == 1

    def test_table_format_hint(self, table_section, doc):
        tagger = AutoTagger()
        tags = tagger.generate_tags(table_section, doc)
        fmt_tags = [t for t in tags if t.tag_key == "format_hint"]
        assert fmt_tags[0].tag_value == "structured_data"

    def test_list_format_hint(self, list_section, doc):
        tagger = AutoTagger()
        tags = tagger.generate_tags(list_section, doc)
        fmt_tags = [t for t in tags if t.tag_key == "format_hint"]
        assert fmt_tags[0].tag_value == "list"

    def test_simple_format_hint(self, short_section, doc):
        tagger = AutoTagger()
        tags = tagger.generate_tags(short_section, doc)
        fmt_tags = [t for t in tags if t.tag_key == "format_hint"]
        assert fmt_tags[0].tag_value == "simple"

    def test_entity_type_detection(self, narrative_section, doc):
        tagger = AutoTagger()
        tags = tagger.generate_tags(narrative_section, doc)
        etype_tags = [t for t in tags if t.tag_key == "entity_type"]
        etype_values = [t.tag_value for t in etype_tags]
        assert "statute" in etype_values

    def test_tags_stored_in_db(self, backend, doc, narrative_section):
        tagger = AutoTagger()
        with backend.session() as session:
            backend.store_document(session, doc)
            backend.store_section(session, narrative_section)
            tags = tagger.generate_tags(narrative_section, doc)
            for tag in tags:
                backend.store_tag(session, tag)

        with backend.session() as session:
            stored = backend.get_tags(session, "sec-narr")
            assert len(stored) >= 4  # domain, topic, complexity, format_hint at minimum

    def test_search_by_tag(self, backend, doc, narrative_section):
        tagger = AutoTagger()
        with backend.session() as session:
            backend.store_document(session, doc)
            backend.store_section(session, narrative_section)
            tags = tagger.generate_tags(narrative_section, doc)
            for tag in tags:
                backend.store_tag(session, tag)

        with backend.session() as session:
            results = backend.search_by_tag(session, "domain", "legal")
            assert len(results) >= 1
            assert results[0].id == "sec-narr"


# ---------------------------------------------------------------------------
# Section Relationships
# ---------------------------------------------------------------------------

class TestSectionRelationships:
    def test_store_and_get_relationship(self, backend, doc, narrative_section, table_section):
        with backend.session() as session:
            backend.store_document(session, doc)
            backend.store_section(session, narrative_section)
            backend.store_section(session, table_section)
            rel = SectionRelationship(
                section_a_id="sec-narr",
                section_b_id="sec-table",
                relationship="related",
                strength=0.8,
                source="rule",
            )
            backend.store_relationship(session, rel)

        with backend.session() as session:
            rels = backend.get_relationships(session, "sec-narr")
            assert len(rels) == 1
            assert rels[0].section_b_id == "sec-table"
            assert rels[0].relationship == "related"
            assert rels[0].strength == 0.8

    def test_get_relationships_both_sides(self, backend, doc, narrative_section, table_section):
        with backend.session() as session:
            backend.store_document(session, doc)
            backend.store_section(session, narrative_section)
            backend.store_section(session, table_section)
            rel = SectionRelationship(
                section_a_id="sec-narr",
                section_b_id="sec-table",
                relationship="co_retrieval",
            )
            backend.store_relationship(session, rel)

        with backend.session() as session:
            # Should find via section_b_id too
            rels = backend.get_relationships(session, "sec-table")
            assert len(rels) == 1

    def test_increment_relationship_creates_new(self, backend, doc, narrative_section, table_section):
        with backend.session() as session:
            backend.store_document(session, doc)
            backend.store_section(session, narrative_section)
            backend.store_section(session, table_section)
            backend.increment_relationship(session, "sec-narr", "sec-table", "co_retrieval")

        with backend.session() as session:
            rels = backend.get_relationships(session, "sec-narr")
            assert len(rels) == 1
            assert rels[0].hit_count == 1

    def test_increment_relationship_increments_existing(self, backend, doc, narrative_section, table_section):
        with backend.session() as session:
            backend.store_document(session, doc)
            backend.store_section(session, narrative_section)
            backend.store_section(session, table_section)
            backend.increment_relationship(session, "sec-narr", "sec-table", "co_retrieval")

        with backend.session() as session:
            backend.increment_relationship(session, "sec-narr", "sec-table", "co_retrieval")

        with backend.session() as session:
            rels = backend.get_relationships(session, "sec-narr")
            assert len(rels) == 1
            assert rels[0].hit_count == 2

    def test_no_relationships_for_unknown_section(self, backend):
        with backend.session() as session:
            rels = backend.get_relationships(session, "nonexistent")
            assert rels == []


# ---------------------------------------------------------------------------
# Ingestion Pipeline Integration
# ---------------------------------------------------------------------------

class TestIngestionIntegration:
    def test_ingest_text_generates_blocks_and_tags(self, backend):
        from bitmod.ingestion.pipeline import ingest_text
        result = ingest_text(
            "The Supreme Court decided that 42 U.S.C. § 1983 applies broadly. "
            "The ruling affects employment law nationwide.",
            title="Court Ruling",
            document_type="statute",
            backend=backend,
        )
        assert result["blocks"] >= 3  # at least 3 per section
        assert result["tags"] >= 3    # domain, complexity, format_hint at minimum

    def test_ingest_text_blocks_disabled(self, backend):
        from bitmod.ingestion.pipeline import ingest_text
        result = ingest_text(
            "Simple test content for ingestion.",
            title="Test",
            backend=backend,
            generate_blocks=False,
        )
        assert result["blocks"] == 0

    def test_ingest_text_tags_disabled(self, backend):
        from bitmod.ingestion.pipeline import ingest_text
        result = ingest_text(
            "Simple test content for ingestion.",
            title="Test",
            backend=backend,
            generate_tags=False,
        )
        assert result["tags"] == 0


# ---------------------------------------------------------------------------
# Domain Detection Edge Cases
# ---------------------------------------------------------------------------

class TestDomainDetection:
    def test_finance_domain(self):
        doc = DocumentRecord(id="d1", document_type="financial", title="Q4 Report")
        section = SectionRecord(
            id="s1", document_id="d1",
            text_content="The stock price increased by 25% due to strong revenue growth.",
            version_hash="h1",
        )
        tagger = AutoTagger()
        tags = tagger.generate_tags(section, doc)
        domain_tags = [t for t in tags if t.tag_key == "domain"]
        assert domain_tags[0].tag_value == "finance"

    def test_general_domain_fallback(self):
        doc = DocumentRecord(id="d1", document_type="misc", title="Random Notes")
        section = SectionRecord(
            id="s1", document_id="d1",
            text_content="Just some random notes about nothing in particular.",
            version_hash="h1",
        )
        tagger = AutoTagger()
        tags = tagger.generate_tags(section, doc)
        domain_tags = [t for t in tags if t.tag_key == "domain"]
        assert domain_tags[0].tag_value == "general"
