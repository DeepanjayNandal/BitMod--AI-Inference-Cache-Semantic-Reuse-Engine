"""Document ingestion and chunking for Bitmod.

Parses documents into the 3-tier schema (Document → Sections → Chunks)
with automatic embedding generation.

Supported formats:
- PDF (via PyMuPDF or pdfplumber)
- DOCX (via python-docx)
- HTML (via BeautifulSoup)
- Markdown
- CSV / JSON
- Plain text

Usage:
    from bitmod.ingestion import ingest_file, ingest_text

    # Ingest a file
    doc = ingest_file("report.pdf", document_type="report", source="uploads")

    # Ingest raw text
    doc = ingest_text("Some content...", title="My Doc", document_type="note")
"""

from bitmod.ingestion.chunker import ChunkConfig, TextChunk, chunk_sections
from bitmod.ingestion.parser import ParsedDocument, ParsedSection, parse_file, parse_text
from bitmod.ingestion.pipeline import ingest_file, ingest_text

__all__ = [
    "parse_file",
    "parse_text",
    "ParsedDocument",
    "ParsedSection",
    "chunk_sections",
    "ChunkConfig",
    "TextChunk",
    "ingest_file",
    "ingest_text",
]
