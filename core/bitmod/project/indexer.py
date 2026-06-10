"""Project indexer — scans, chunks, and embeds project files."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from bitmod.interfaces.database import (
    DatabaseBackend,
    ProjectChunkRecord,
    ProjectFileRecord,
    ProjectRecord,
)
from bitmod.project.language import (
    detect_framework,
    detect_language,
    should_index,
)

logger = logging.getLogger(__name__)

# Chunk sizing
DEFAULT_CHUNK_LINES = 60
CHUNK_OVERLAP_LINES = 10
MAX_CHUNK_TOKENS = 512


def _file_hash(path: str) -> str:
    """SHA-256 hash of file contents."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(8192), b""):
                h.update(block)
    except OSError:
        return ""
    return h.hexdigest()


def _estimate_tokens(text: str) -> int:
    """Rough token count (~4 chars per token for code)."""
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Symbol extraction — lightweight regex-based, no AST parsing needed
# ---------------------------------------------------------------------------

_SYMBOL_PATTERNS: dict[str, list[tuple[str, re.Pattern]]] = {
    "python": [
        ("function", re.compile(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(", re.MULTILINE)),
        ("class", re.compile(r"^class\s+(\w+)\s*[\(:]", re.MULTILINE)),
    ],
    "javascript": [
        ("function", re.compile(r"(?:^|\s)(?:async\s+)?function\s+(\w+)\s*\(", re.MULTILINE)),
        ("function", re.compile(r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(", re.MULTILINE)),
        ("class", re.compile(r"^class\s+(\w+)", re.MULTILINE)),
    ],
    "typescript": [
        ("function", re.compile(r"(?:^|\s)(?:export\s+)?(?:async\s+)?function\s+(\w+)", re.MULTILINE)),
        ("function", re.compile(r"(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*(?:async\s+)?\(", re.MULTILINE)),
        ("class", re.compile(r"(?:export\s+)?class\s+(\w+)", re.MULTILINE)),
        ("interface", re.compile(r"(?:export\s+)?interface\s+(\w+)", re.MULTILINE)),
        ("type", re.compile(r"(?:export\s+)?type\s+(\w+)\s*=", re.MULTILINE)),
    ],
    "go": [
        ("function", re.compile(r"^func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(", re.MULTILINE)),
        ("struct", re.compile(r"^type\s+(\w+)\s+struct\s*\{", re.MULTILINE)),
        ("interface", re.compile(r"^type\s+(\w+)\s+interface\s*\{", re.MULTILINE)),
    ],
    "rust": [
        ("function", re.compile(r"^(?:pub\s+)?(?:async\s+)?fn\s+(\w+)", re.MULTILINE)),
        ("struct", re.compile(r"^(?:pub\s+)?struct\s+(\w+)", re.MULTILINE)),
        ("trait", re.compile(r"^(?:pub\s+)?trait\s+(\w+)", re.MULTILINE)),
        ("enum", re.compile(r"^(?:pub\s+)?enum\s+(\w+)", re.MULTILINE)),
    ],
    "java": [
        ("class", re.compile(r"(?:public|private|protected)?\s*class\s+(\w+)", re.MULTILINE)),
        ("method", re.compile(r"(?:public|private|protected)\s+\w+\s+(\w+)\s*\(", re.MULTILINE)),
        ("interface", re.compile(r"(?:public\s+)?interface\s+(\w+)", re.MULTILINE)),
    ],
}

# Copy TS patterns for tsx/jsx
_SYMBOL_PATTERNS["tsx"] = _SYMBOL_PATTERNS["typescript"]
_SYMBOL_PATTERNS["jsx"] = _SYMBOL_PATTERNS["javascript"]


def _extract_symbols(content: str, language: str) -> list[tuple[str, str, int]]:
    """Extract (symbol_type, symbol_name, line_number) from content."""
    patterns = _SYMBOL_PATTERNS.get(language, [])
    symbols = []
    for sym_type, pattern in patterns:
        for match in pattern.finditer(content):
            line_num = content[: match.start()].count("\n") + 1
            symbols.append((sym_type, match.group(1), line_num))
    return symbols


# ---------------------------------------------------------------------------
# Chunking — line-based with symbol awareness
# ---------------------------------------------------------------------------


def _chunk_file(content: str, language: str) -> list[dict]:
    """Split file content into chunks, respecting symbol boundaries when possible.

    Returns list of dicts: {content, start_line, end_line, symbol_name, symbol_type}.
    """
    lines = content.split("\n")
    if not lines:
        return []

    symbols = _extract_symbols(content, language)
    # Map line numbers to symbols
    symbol_at: dict[int, tuple[str, str]] = {}
    for sym_type, sym_name, line in symbols:
        symbol_at[line] = (sym_type, sym_name)

    chunks = []
    i = 0
    total = len(lines)

    while i < total:
        end = min(i + DEFAULT_CHUNK_LINES, total)

        # Try to break at the start of the next symbol after the chunk boundary
        # to keep symbols intact
        if end < total:
            best_break = end
            for check in range(max(end - 15, i + 20), min(end + 15, total)):
                if check + 1 in symbol_at:  # +1 because symbols are 1-indexed
                    best_break = check
                    break
            end = best_break

        chunk_lines = lines[i:end]
        chunk_text = "\n".join(chunk_lines)

        # Skip empty trailing chunks
        if not chunk_text.strip():
            break

        # Find the primary symbol for this chunk
        sym_name = None  # type: ignore[assignment]
        sym_type = None  # type: ignore[assignment]
        for line_num in range(i + 1, end + 1):
            if line_num in symbol_at:
                sym_type, sym_name = symbol_at[line_num]
                break  # Use first symbol in chunk

        chunks.append(
            {
                "content": chunk_text,
                "start_line": i + 1,  # 1-indexed
                "end_line": end,
                "symbol_name": sym_name,
                "symbol_type": sym_type,
            }
        )

        # For small files that fit in one chunk, we're done
        if end >= total:
            break

        # Advance with overlap
        next_i = end - CHUNK_OVERLAP_LINES
        if next_i <= i:
            next_i = end  # Prevent infinite loop on tiny files
        i = next_i

    return chunks


# ---------------------------------------------------------------------------
# ProjectIndexer
# ---------------------------------------------------------------------------


class ProjectIndexer:
    """Indexes project files into searchable chunks with optional embeddings."""

    def __init__(self, db: DatabaseBackend, embed_fn: Any = None):
        """
        Args:
            db: Database backend.
            embed_fn: Optional callable(texts: list[str]) -> list[list[float]].
                      If None, chunks are stored without embeddings.
        """
        self._db = db
        self._embed_fn = embed_fn

    def register_project(
        self,
        root_path: str,
        name: str | None = None,
        description: str = "",
    ) -> ProjectRecord:
        """Register a new project for tracking. Returns existing if path already tracked."""
        root = os.path.abspath(root_path)

        # C2: Verify the path exists as a directory and resolve symlinks
        if not os.path.isdir(root):
            raise ValueError("Project path is not an existing directory")
        root = os.path.realpath(root)

        with self._db.session() as s:
            existing = self._db.project_get_by_path(s, root)
            if existing:
                logger.info("Project already registered: %s", existing.name)
                return existing

            project = ProjectRecord(
                name=name or os.path.basename(root),
                root_path=root,
                description=description,
            )
            self._db.project_create(s, project)
            logger.info("Registered project: %s at %s", project.name, root)
            return project

    def scan(self, project_id: str) -> dict:
        """Scan a project directory and index changed files.

        Returns stats dict: files_scanned, files_changed, chunks_created, files_deleted.
        """
        with self._db.session() as s:
            project = self._db.project_get(s, project_id)
            if not project:
                raise ValueError(f"Project not found: {project_id}")

            root = project.root_path
            if not os.path.isdir(root):
                raise FileNotFoundError(f"Project directory not found: {root}")

            stats = {
                "files_scanned": 0,
                "files_changed": 0,
                "files_deleted": 0,
                "chunks_created": 0,
            }

            # Walk the project directory
            current_paths: set[str] = set()
            all_files: list[str] = []

            # H1: Resolve the project root to its real path for symlink checks
            real_root = os.path.realpath(root)

            for dirpath, dirnames, filenames in os.walk(root):
                # Prune skip dirs in-place
                dirnames[:] = [
                    d
                    for d in dirnames
                    if d
                    not in {
                        ".git",
                        ".svn",
                        ".hg",
                        "node_modules",
                        "__pycache__",
                        ".pytest_cache",
                        ".mypy_cache",
                        ".next",
                        ".nuxt",
                        "dist",
                        "build",
                        "out",
                        "target",
                        ".venv",
                        "venv",
                        "env",
                        ".tox",
                        ".nox",
                        "vendor",
                        "third_party",
                        ".idea",
                        ".vscode",
                        "coverage",
                        ".terraform",
                        ".serverless",
                        "eggs",
                    }
                    and not d.endswith(".egg-info")
                ]

                for fname in filenames:
                    full_path = os.path.join(dirpath, fname)

                    # H1: Resolve symlinks and verify file is still under project root
                    real_path = os.path.realpath(full_path)
                    if not (real_path.startswith(real_root + os.sep) or real_path == real_root):
                        logger.debug("Skipping symlink escape: %s -> %s", full_path, real_path)
                        continue

                    if should_index(full_path, root):
                        all_files.append(full_path)

            # Detect framework from file list
            framework = detect_framework(set(all_files))

            for full_path in all_files:
                stats["files_scanned"] += 1
                rel_path = os.path.relpath(full_path, root)

                # M1: Reject paths that escape the project root via ..
                if ".." in rel_path:
                    logger.debug("Skipping path traversal in relative path: %s", rel_path)
                    continue

                current_paths.add(rel_path)

                # Check if file has changed
                new_hash = _file_hash(full_path)
                existing = self._db.project_file_get(s, project_id, rel_path)

                if existing and existing.file_hash == new_hash:
                    continue  # Unchanged

                stats["files_changed"] += 1
                language = detect_language(full_path)

                try:
                    with open(full_path, encoding="utf-8", errors="replace") as f:
                        content = f.read()
                except OSError:
                    continue

                # Chunk the file
                chunks = _chunk_file(content, language)

                # Create/update file record
                file_id = existing.id if existing else str(uuid.uuid4())
                file_rec = ProjectFileRecord(
                    id=file_id,
                    project_id=project_id,
                    relative_path=rel_path,
                    file_hash=new_hash,
                    language=language,
                    size_bytes=os.path.getsize(full_path),
                    last_modified=datetime.fromtimestamp(os.path.getmtime(full_path), tz=timezone.utc).isoformat(),
                    is_indexed=True,
                    chunk_count=len(chunks),
                )

                # Delete old chunks if re-indexing
                if existing:
                    self._db.project_chunks_delete_by_file(s, file_id)

                self._db.project_file_upsert(s, file_rec)

                # Generate embeddings in batch if available
                embeddings = None
                if self._embed_fn and chunks:
                    try:
                        texts = [c["content"] for c in chunks]
                        embeddings = self._embed_fn(texts)
                    except Exception:
                        logger.warning("Embedding failed for %s", rel_path)

                # Store chunks
                for idx, chunk_data in enumerate(chunks):
                    emb = embeddings[idx] if embeddings and idx < len(embeddings) else None
                    chunk_rec = ProjectChunkRecord(
                        file_id=file_id,
                        project_id=project_id,
                        chunk_index=idx,
                        content=chunk_data["content"],
                        start_line=chunk_data["start_line"],
                        end_line=chunk_data["end_line"],
                        symbol_name=chunk_data["symbol_name"],
                        symbol_type=chunk_data["symbol_type"],
                        embedding=emb,
                        token_count=_estimate_tokens(chunk_data["content"]),
                    )
                    self._db.project_chunk_store(s, chunk_rec)
                    stats["chunks_created"] += 1

            # Remove stale files
            stale = self._db.project_files_stale(s, project_id, current_paths)
            for sf in stale:
                self._db.project_chunks_delete_by_file(s, sf.id)
                self._db.project_file_delete(s, sf.id)
                stats["files_deleted"] += 1

            # Detect primary language from file counts
            lang_counts: dict[str, int] = {}
            for fp in all_files:
                lang = detect_language(fp)
                if lang:
                    lang_counts[lang] = lang_counts.get(lang, 0) + 1
            primary_lang = max(lang_counts, key=lang_counts.get) if lang_counts else ""  # type: ignore[arg-type]

            # Update project metadata
            self._db.project_update(
                s,
                project_id,
                language=primary_lang,
                framework=framework,
                file_count=len(current_paths),
                total_chunks=stats["chunks_created"],
                last_scanned_at=datetime.now(timezone.utc).isoformat(),
            )

            logger.info(
                "Scan complete: %d files, %d changed, %d chunks, %d deleted",
                stats["files_scanned"],
                stats["files_changed"],
                stats["chunks_created"],
                stats["files_deleted"],
            )
            return stats

    def remove_project(self, project_id: str) -> None:
        """Remove a project and all its indexed data."""
        with self._db.session() as s:
            self._db.project_delete(s, project_id)
