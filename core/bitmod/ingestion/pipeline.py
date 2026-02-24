"""Ingestion pipeline — ties parsing, chunking, embedding, and storage together.

This is the main entry point for getting data into Bitmod.

Usage:
    from bitmod.ingestion import ingest_file, ingest_text

    # Ingest a PDF with automatic embedding
    result = ingest_file(
        "report.pdf",
        document_type="report",
        source="uploads",
        backend=my_backend,
        embedder=my_embedder,
    )
    print(f"Ingested {result['sections']} sections, {result['chunks']} chunks")
"""

import hashlib
import uuid
from typing import TYPE_CHECKING

from bitmod.ingestion.chunker import ChunkConfig, chunk_text
from bitmod.ingestion.parser import ParsedDocument, parse_file, parse_text

if TYPE_CHECKING:
    from bitmod.interfaces.database import DatabaseBackend
    from bitmod.interfaces.embeddings import EmbeddingProvider


def ingest_file(
    file_path: str,
    document_type: str = "document",
    source: str = "upload",
    title: str | None = None,
    jurisdiction: str | None = None,
    tags: list[str] | None = None,
    metadata: dict | None = None,
    backend: "DatabaseBackend | None" = None,
    embedder: "EmbeddingProvider | None" = None,
    chunk_config: ChunkConfig | None = None,
    allowed_base_dirs: list[str] | None = None,
    generate_blocks: bool = True,
    generate_tags: bool = True,
) -> dict:
    """Ingest a file into Bitmod's 3-tier schema.

    Args:
        allowed_base_dirs: Optional list of allowed base directories for
            file path validation. Prevents path traversal attacks.
    """
    parsed = parse_file(file_path, title=title, allowed_base_dirs=allowed_base_dirs)
    return _ingest_parsed(
        parsed,
        document_type,
        source,
        jurisdiction,
        tags,
        metadata,
        backend,
        embedder,
        chunk_config,
        generate_blocks=generate_blocks,
        generate_tags=generate_tags,
    )


def ingest_text(
    text: str,
    title: str = "Untitled",
    document_type: str = "text",
    source: str = "inline",
    jurisdiction: str | None = None,
    tags: list[str] | None = None,
    metadata: dict | None = None,
    backend: "DatabaseBackend | None" = None,
    embedder: "EmbeddingProvider | None" = None,
    chunk_config: ChunkConfig | None = None,
    generate_blocks: bool = True,
    generate_tags: bool = True,
) -> dict:
    """Ingest raw text into Bitmod's 3-tier schema."""
    parsed = parse_text(text, title=title)
    return _ingest_parsed(
        parsed,
        document_type,
        source,
        jurisdiction,
        tags,
        metadata,
        backend,
        embedder,
        chunk_config,
        generate_blocks=generate_blocks,
        generate_tags=generate_tags,
    )


def _ingest_parsed(
    parsed: ParsedDocument,
    document_type: str,
    source: str,
    jurisdiction: str | None,
    tags: list[str] | None,
    metadata: dict | None,
    backend: "DatabaseBackend | None",
    embedder: "EmbeddingProvider | None",
    chunk_config: ChunkConfig | None,
    generate_blocks: bool = True,
    generate_tags: bool = True,
) -> dict:
    """Core ingestion logic for a parsed document.

    Supports re-ingestion: if a document with the same title+source already exists,
    updates existing sections in-place (preserving section IDs for cache integrity)
    and marks removed sections as not current.
    """
    if backend is None:
        from bitmod.adapters import get_backend

        backend = get_backend()
        backend.initialize()

    from bitmod.interfaces.database import ChunkRecord, DocumentRecord, SectionRecord

    chunk_config = chunk_config or ChunkConfig()
    doc_metadata = {**(parsed.metadata or {}), **(metadata or {})}
    doc_metadata["source_format"] = parsed.source_format

    total_sections = 0
    total_chunks = 0
    total_blocks = 0
    total_tags = 0
    sections_updated = 0
    sections_unchanged = 0
    is_reingest = False

    # Lazy-init block generator and auto-tagger
    block_generator = None
    auto_tagger = None
    if generate_blocks:
        from bitmod.blocks import BlockGenerator

        block_generator = BlockGenerator()
    if generate_tags:
        from bitmod.tags import AutoTagger

        auto_tagger = AutoTagger()

    with backend.session() as session:
        # Check for existing document (re-ingestion detection)
        existing_doc = None
        if hasattr(backend, "find_document_by_title_and_source"):
            existing_doc = backend.find_document_by_title_and_source(
                session,
                parsed.title,
                source,
            )

        if existing_doc:
            # Re-ingestion: update existing document's sections
            is_reingest = True
            doc_id = existing_doc.id
            existing_sections = backend.get_sections_for_document(session, doc_id)

            # Build lookup by section_number or section_title for matching
            existing_by_key: dict[str, SectionRecord] = {}
            for s in existing_sections:
                key = s.section_number or s.section_title or ""
                if key:
                    existing_by_key[key] = s

            matched_section_ids: set[str] = set()

            for parsed_section in parsed.sections:
                if not parsed_section.text.strip():
                    continue

                version_hash = hashlib.sha256(parsed_section.text.encode()).hexdigest()

                # Try to match to existing section
                match_key = parsed_section.section_number or parsed_section.title or ""
                existing = existing_by_key.get(match_key) if match_key else None

                if existing:
                    matched_section_ids.add(existing.id)
                    section_id = existing.id

                    if existing.version_hash == version_hash:
                        # Content unchanged — skip
                        sections_unchanged += 1
                        total_sections += 1
                        continue

                    # Content changed — update in place
                    backend.update_section_content(session, section_id, parsed_section.text, version_hash)
                    sections_updated += 1

                    # Regenerate blocks for changed section
                    if block_generator is not None:
                        backend.invalidate_blocks(session, section_id)
                        temp_record = SectionRecord(
                            id=section_id,
                            document_id=doc_id,
                            text_content=parsed_section.text,
                            version_hash=version_hash,
                            section_number=parsed_section.section_number,
                            section_title=parsed_section.title,
                            hierarchy_path="/".join(parsed_section.hierarchy_path)
                            if isinstance(parsed_section.hierarchy_path, list)
                            else parsed_section.hierarchy_path,
                            metadata=parsed_section.metadata,  # type: ignore[arg-type]  # type: ignore[arg-type]
                            tags=tags,
                        )
                        blocks = block_generator.generate_blocks(temp_record, backend, session)
                        total_blocks += len(blocks)

                    # Delete old chunks and re-chunk
                    backend.delete_chunks_by_section(session, section_id)
                else:
                    # New section in re-ingested document
                    section_id = str(uuid.uuid4())
                    section_record = SectionRecord(
                        id=section_id,
                        document_id=doc_id,
                        text_content=parsed_section.text,
                        version_hash=version_hash,
                        citation=None,
                        section_number=parsed_section.section_number,
                        section_title=parsed_section.title,
                        hierarchy_path="/".join(parsed_section.hierarchy_path)
                        if isinstance(parsed_section.hierarchy_path, list)
                        else parsed_section.hierarchy_path,
                        metadata=parsed_section.metadata,  # type: ignore[arg-type]
                        tags=tags,
                    )
                    backend.store_section(session, section_record)

                    if block_generator is not None:
                        blocks = block_generator.generate_blocks(section_record, backend, session)
                        total_blocks += len(blocks)

                    if auto_tagger is not None:
                        section_tags = auto_tagger.generate_tags(section_record, existing_doc)
                        for tag in section_tags:
                            backend.store_tag(session, tag)
                        total_tags += len(section_tags)

                total_sections += 1

                # Chunk and embed (for both new and updated sections)
                chunks = chunk_text(parsed_section.text, chunk_config)
                chunk_texts = [c.text for c in chunks]
                embeddings: list[list[float] | None] = [None] * len(chunks)
                if embedder and chunk_texts:
                    try:
                        embeddings = embedder.embed_batch(chunk_texts)  # type: ignore[assignment]
                    except Exception:
                        embeddings = [None] * len(chunks)

                for chunk, embedding in zip(chunks, embeddings):
                    backend.store_chunk(
                        session,
                        ChunkRecord(
                            id=str(uuid.uuid4()),
                            section_id=section_id,
                            chunk_index=chunk.chunk_index,
                            text_content=chunk.text,
                            embedding=embedding,
                            document_type=document_type,
                            jurisdiction=jurisdiction,
                            char_offset=chunk.char_offset,
                        ),
                    )
                    total_chunks += 1

            # Mark sections that no longer exist as not current
            for existing_s in existing_sections:
                if existing_s.id not in matched_section_ids:
                    backend.mark_section_not_current(session, existing_s.id)

        else:
            # First ingestion — create new document
            doc_id = str(uuid.uuid4())
            doc_record = DocumentRecord(
                id=doc_id,
                document_type=document_type,
                source=source,
                title=parsed.title,
                jurisdiction=jurisdiction,
                source_format=parsed.source_format,
                metadata=doc_metadata,
                tags=tags,
            )
            backend.store_document(session, doc_record)

            for parsed_section in parsed.sections:
                if not parsed_section.text.strip():
                    continue

                version_hash = hashlib.sha256(parsed_section.text.encode()).hexdigest()
                section_id = str(uuid.uuid4())

                section_record = SectionRecord(
                    id=section_id,
                    document_id=doc_id,
                    text_content=parsed_section.text,
                    version_hash=version_hash,
                    citation=None,
                    section_number=parsed_section.section_number,
                    section_title=parsed_section.title,
                    hierarchy_path="/".join(parsed_section.hierarchy_path)
                    if isinstance(parsed_section.hierarchy_path, list)
                    else parsed_section.hierarchy_path,
                    metadata=parsed_section.metadata,  # type: ignore[arg-type]
                    tags=tags,
                )
                backend.store_section(session, section_record)
                total_sections += 1

                if block_generator is not None:
                    blocks = block_generator.generate_blocks(section_record, backend, session)
                    total_blocks += len(blocks)

                if auto_tagger is not None:
                    section_tags = auto_tagger.generate_tags(section_record, doc_record)
                    for tag in section_tags:
                        backend.store_tag(session, tag)
                    total_tags += len(section_tags)

                chunks = chunk_text(parsed_section.text, chunk_config)
                chunk_texts = [c.text for c in chunks]
                embeddings: list[list[float] | None] = [None] * len(chunks)  # type: ignore[no-redef]
                if embedder and chunk_texts:
                    try:
                        embeddings = embedder.embed_batch(chunk_texts)  # type: ignore[assignment]
                    except Exception:
                        embeddings = [None] * len(chunks)

                for chunk, embedding in zip(chunks, embeddings):
                    backend.store_chunk(
                        session,
                        ChunkRecord(
                            id=str(uuid.uuid4()),
                            section_id=section_id,
                            chunk_index=chunk.chunk_index,
                            text_content=chunk.text,
                            embedding=embedding,
                            document_type=document_type,
                            jurisdiction=jurisdiction,
                            char_offset=chunk.char_offset,
                        ),
                    )
                    total_chunks += 1

    return {
        "document_id": doc_id,
        "title": parsed.title,
        "source_format": parsed.source_format,
        "sections": total_sections,
        "chunks": total_chunks,
        "blocks": total_blocks,
        "tags": total_tags,
        "embedded": embedder is not None,
        "is_reingest": is_reingest,
        "sections_updated": sections_updated,
        "sections_unchanged": sections_unchanged,
    }
