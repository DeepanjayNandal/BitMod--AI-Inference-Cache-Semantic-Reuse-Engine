"""Tests for the Project Knowledge System.

Covers: project CRUD, file indexing, chunking, conversation memory,
corrections, and context assembly.
"""

import os
import sqlite3
import tempfile

import pytest

# Run migration on a fresh SQLite DB
def _make_db():
    """Create a temporary SQLite DB with all tables."""
    import importlib.util
    from bitmod.adapters.db_sqlite import SQLiteBackend

    db_path = tempfile.mktemp(suffix=".db")
    db = SQLiteBackend(db_path)
    db.initialize()

    spec = importlib.util.spec_from_file_location(
        "m006", os.path.join(os.path.dirname(__file__), "..", "db", "migrations", "006_add_project_knowledge.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    conn = sqlite3.connect(db_path)
    for stmt in mod.SQL_SQLITE.split(";"):
        stmt = stmt.strip()
        if stmt:
            try:
                conn.execute(stmt)
            except Exception:
                pass
    conn.commit()
    conn.close()

    return db, db_path


def _make_project_dir():
    """Create a temporary project directory with some files."""
    d = tempfile.mkdtemp()
    # Python file
    with open(os.path.join(d, "main.py"), "w") as f:
        f.write("def hello():\n    return 'world'\n\nclass MyApp:\n    pass\n")
    # JS file
    with open(os.path.join(d, "app.js"), "w") as f:
        f.write("function greet(name) {\n  return `Hello ${name}`;\n}\n")
    # Config
    with open(os.path.join(d, "config.yaml"), "w") as f:
        f.write("key: value\n")
    # Should be skipped
    os.makedirs(os.path.join(d, "node_modules", "dep"), exist_ok=True)
    with open(os.path.join(d, "node_modules", "dep", "index.js"), "w") as f:
        f.write("module.exports = {}")
    with open(os.path.join(d, "image.png"), "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
    return d


# ===========================================================================
# Language detection
# ===========================================================================

class TestLanguageDetection:
    def test_python(self):
        from bitmod.project.language import detect_language
        assert detect_language("test.py") == "python"
        assert detect_language("test.pyi") == "python"

    def test_typescript(self):
        from bitmod.project.language import detect_language
        assert detect_language("app.tsx") == "typescript"
        assert detect_language("app.ts") == "typescript"

    def test_go(self):
        from bitmod.project.language import detect_language
        assert detect_language("main.go") == "go"

    def test_dockerfile(self):
        from bitmod.project.language import detect_language
        assert detect_language("Dockerfile") == "dockerfile"

    def test_unknown(self):
        from bitmod.project.language import detect_language
        assert detect_language("test.xyz") == ""

    def test_should_index_skips_node_modules(self):
        from bitmod.project.language import should_index
        assert not should_index("/proj/node_modules/x/index.js", "/proj")

    def test_should_index_skips_binary(self):
        from bitmod.project.language import should_index
        assert not should_index("/proj/image.png", "/proj")

    def test_should_index_allows_python(self):
        from bitmod.project.language import should_index
        # Create a real temp file so getsize works
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(b"print('hi')")
            path = f.name
        try:
            assert should_index(path, os.path.dirname(path))
        finally:
            os.unlink(path)

    def test_detect_framework(self):
        from bitmod.project.language import detect_framework
        assert detect_framework({"next.config.mjs", "package.json"}) == "nextjs"
        assert detect_framework({"manage.py", "settings.py"}) == "django"
        assert detect_framework({"go.mod", "main.go"}) == "go"


# ===========================================================================
# Symbol extraction & chunking
# ===========================================================================

class TestChunking:
    def test_extract_python_symbols(self):
        from bitmod.project.indexer import _extract_symbols
        code = "def foo():\n    pass\n\nclass Bar:\n    def baz(self):\n        pass\n"
        symbols = _extract_symbols(code, "python")
        names = [s[1] for s in symbols]
        assert "foo" in names
        assert "Bar" in names
        assert "baz" in names

    def test_extract_typescript_symbols(self):
        from bitmod.project.indexer import _extract_symbols
        code = "export class UserService {\n}\n\nexport const fetchData = async () => {}\n"
        symbols = _extract_symbols(code, "typescript")
        names = [s[1] for s in symbols]
        assert "UserService" in names
        assert "fetchData" in names

    def test_chunk_small_file(self):
        from bitmod.project.indexer import _chunk_file
        code = "line1\nline2\nline3\n"
        chunks = _chunk_file(code, "python")
        assert len(chunks) == 1
        assert chunks[0]["start_line"] == 1

    def test_chunk_large_file(self):
        from bitmod.project.indexer import _chunk_file
        code = "\n".join(f"line_{i}" for i in range(200))
        chunks = _chunk_file(code, "python")
        assert len(chunks) > 1
        # All lines should be covered
        covered = set()
        for c in chunks:
            for line in range(c["start_line"], c["end_line"] + 1):
                covered.add(line)
        assert len(covered) == 200


# ===========================================================================
# Project CRUD
# ===========================================================================

class TestProjectCRUD:
    def test_create_and_get(self):
        db, path = _make_db()
        from bitmod.interfaces.database import ProjectRecord
        project = ProjectRecord(name="test", root_path="/tmp/test-" + os.urandom(4).hex())
        with db.session() as s:
            db.project_create(s, project)
            found = db.project_get(s, project.id)
            assert found is not None
            assert found.name == "test"
        os.unlink(path)

    def test_get_by_path(self):
        db, path = _make_db()
        from bitmod.interfaces.database import ProjectRecord
        rp = "/tmp/unique-" + os.urandom(4).hex()
        project = ProjectRecord(name="test", root_path=rp)
        with db.session() as s:
            db.project_create(s, project)
            found = db.project_get_by_path(s, rp)
            assert found is not None
            assert found.id == project.id
        os.unlink(path)

    def test_list_active(self):
        db, path = _make_db()
        from bitmod.interfaces.database import ProjectRecord
        p1 = ProjectRecord(name="active", root_path="/tmp/a-" + os.urandom(4).hex())
        p2 = ProjectRecord(name="inactive", root_path="/tmp/b-" + os.urandom(4).hex(), is_active=False)
        with db.session() as s:
            db.project_create(s, p1)
            db.project_create(s, p2)
            active = db.project_list(s, active_only=True)
            all_ = db.project_list(s, active_only=False)
            assert len(active) == 1
            assert len(all_) == 2
        os.unlink(path)

    def test_update(self):
        db, path = _make_db()
        from bitmod.interfaces.database import ProjectRecord
        project = ProjectRecord(name="test", root_path="/tmp/u-" + os.urandom(4).hex())
        with db.session() as s:
            db.project_create(s, project)
            db.project_update(s, project.id, language="python", file_count=42)
            found = db.project_get(s, project.id)
            assert found.language == "python"
            assert found.file_count == 42
        os.unlink(path)

    def test_delete_cascade(self):
        db, path = _make_db()
        from bitmod.interfaces.database import ProjectRecord, ProjectFileRecord, ProjectChunkRecord
        project = ProjectRecord(name="test", root_path="/tmp/d-" + os.urandom(4).hex())
        with db.session() as s:
            db.project_create(s, project)
            pf = ProjectFileRecord(project_id=project.id, relative_path="test.py")
            db.project_file_upsert(s, pf)
            chunk = ProjectChunkRecord(file_id=pf.id, project_id=project.id, content="hello")
            db.project_chunk_store(s, chunk)

            db.project_delete(s, project.id)
            assert db.project_get(s, project.id) is None
            assert db.project_files_list(s, project.id) == []
        os.unlink(path)


# ===========================================================================
# Project Indexer (full flow)
# ===========================================================================

class TestProjectIndexer:
    def test_register_and_scan(self):
        db, db_path = _make_db()
        proj_dir = _make_project_dir()
        from bitmod.project.indexer import ProjectIndexer

        indexer = ProjectIndexer(db=db)
        project = indexer.register_project(proj_dir, name="test-proj")
        assert project.name == "test-proj"

        stats = indexer.scan(project.id)
        assert stats["files_scanned"] >= 3  # main.py, app.js, config.yaml
        assert stats["files_changed"] >= 3
        assert stats["chunks_created"] >= 3

        # node_modules and .png should be skipped
        with db.session() as s:
            files = db.project_files_list(s, project.id)
            paths = {f.relative_path for f in files}
            assert "main.py" in paths
            assert "app.js" in paths
            assert "node_modules/dep/index.js" not in paths
            assert "image.png" not in paths

        os.unlink(db_path)

    def test_rescan_unchanged(self):
        db, db_path = _make_db()
        proj_dir = _make_project_dir()
        from bitmod.project.indexer import ProjectIndexer

        indexer = ProjectIndexer(db=db)
        project = indexer.register_project(proj_dir)
        indexer.scan(project.id)

        # Second scan: nothing changed
        stats = indexer.scan(project.id)
        assert stats["files_changed"] == 0

        os.unlink(db_path)

    def test_rescan_detects_changes(self):
        db, db_path = _make_db()
        proj_dir = _make_project_dir()
        from bitmod.project.indexer import ProjectIndexer

        indexer = ProjectIndexer(db=db)
        project = indexer.register_project(proj_dir)
        indexer.scan(project.id)

        # Modify a file
        with open(os.path.join(proj_dir, "main.py"), "a") as f:
            f.write("\ndef new_func():\n    pass\n")

        stats = indexer.scan(project.id)
        assert stats["files_changed"] == 1

        os.unlink(db_path)

    def test_rescan_detects_deletions(self):
        db, db_path = _make_db()
        proj_dir = _make_project_dir()
        from bitmod.project.indexer import ProjectIndexer

        indexer = ProjectIndexer(db=db)
        project = indexer.register_project(proj_dir)
        indexer.scan(project.id)

        # Delete a file
        os.unlink(os.path.join(proj_dir, "app.js"))

        stats = indexer.scan(project.id)
        assert stats["files_deleted"] == 1

        os.unlink(db_path)

    def test_register_idempotent(self):
        db, db_path = _make_db()
        proj_dir = _make_project_dir()
        from bitmod.project.indexer import ProjectIndexer

        indexer = ProjectIndexer(db=db)
        p1 = indexer.register_project(proj_dir)
        p2 = indexer.register_project(proj_dir)
        assert p1.id == p2.id

        os.unlink(db_path)


# ===========================================================================
# Conversation Memory
# ===========================================================================

class TestConversationMemory:
    def test_record_and_list(self):
        db, db_path = _make_db()
        from bitmod.project.memory import ConversationMemory

        mem = ConversationMemory(db=db)
        conv = mem.record(
            user_message="What is HIPAA?",
            assistant_response="HIPAA is...",
            model_used="llama3.2",
            generation_ms=1500,
        )
        assert conv.id

        recent = mem.list_recent()
        assert len(recent) == 1
        assert recent[0].user_message == "What is HIPAA?"

        os.unlink(db_path)

    def test_rate(self):
        db, db_path = _make_db()
        from bitmod.project.memory import ConversationMemory

        mem = ConversationMemory(db=db)
        conv = mem.record("test q", "test a")
        mem.rate(conv.id, 5, "Great!")

        with db.session() as s:
            found = db.conversation_get(s, conv.id)
            assert found.rating == 5
            assert found.feedback == "Great!"

        os.unlink(db_path)

    def test_rate_validation(self):
        db, db_path = _make_db()
        from bitmod.project.memory import ConversationMemory

        mem = ConversationMemory(db=db)
        with pytest.raises(ValueError):
            mem.rate("fake-id", 0)
        with pytest.raises(ValueError):
            mem.rate("fake-id", 6)

        os.unlink(db_path)

    def test_correct(self):
        db, db_path = _make_db()
        from bitmod.project.memory import ConversationMemory

        mem = ConversationMemory(db=db)
        conv = mem.record("What is SOC 2?", "SOC 2 is wrong answer")
        correction = mem.correct(
            conv.id,
            corrected_answer="SOC 2 is a framework for...",
            correction_type="factual",
        )
        assert correction.original_question == "What is SOC 2?"
        assert correction.corrected_answer == "SOC 2 is a framework for..."

        corrections = mem.list_corrections()
        assert len(corrections) == 1

        os.unlink(db_path)

    def test_correct_nonexistent(self):
        db, db_path = _make_db()
        from bitmod.project.memory import ConversationMemory

        mem = ConversationMemory(db=db)
        with pytest.raises(ValueError):
            mem.correct("nonexistent-id", "corrected")

        os.unlink(db_path)

    def test_search_falls_back_to_recent(self):
        db, db_path = _make_db()
        from bitmod.project.memory import ConversationMemory

        mem = ConversationMemory(db=db)  # No embedder
        mem.record("question 1", "answer 1")
        mem.record("question 2", "answer 2")

        results = mem.search("question")
        assert len(results) == 2  # Falls back to recent

        os.unlink(db_path)


# ===========================================================================
# Context Assembler
# ===========================================================================

class TestContextAssembler:
    def test_empty_without_project(self):
        db, db_path = _make_db()
        from bitmod.project.context import ContextAssembler

        assembler = ContextAssembler(db=db)
        ctx = assembler.assemble("test query")
        assert ctx.is_empty
        assert ctx.total_tokens == 0

        os.unlink(db_path)

    def test_assembled_context_format(self):
        from bitmod.project.context import AssembledContext

        ctx = AssembledContext(
            project_context="def foo(): pass",
            history_context="Q: x\nA: y",
            corrections_context="Wrong: a\nRight: b",
        )
        full = ctx.full_context
        assert "Relevant Project Code" in full
        assert "Previous Corrections" in full
        assert "Related Past Conversations" in full
        assert not ctx.is_empty


# ===========================================================================
# Project File Upsert
# ===========================================================================

class TestProjectFileUpsert:
    def test_upsert_creates_new(self):
        db, db_path = _make_db()
        from bitmod.interfaces.database import ProjectRecord, ProjectFileRecord

        project = ProjectRecord(name="test", root_path="/tmp/up-" + os.urandom(4).hex())
        with db.session() as s:
            db.project_create(s, project)
            pf = ProjectFileRecord(
                project_id=project.id, relative_path="main.py",
                file_hash="abc123", language="python", size_bytes=100,
            )
            db.project_file_upsert(s, pf)
            found = db.project_file_get(s, project.id, "main.py")
            assert found is not None
            assert found.file_hash == "abc123"

        os.unlink(db_path)

    def test_upsert_updates_existing(self):
        db, db_path = _make_db()
        from bitmod.interfaces.database import ProjectRecord, ProjectFileRecord

        project = ProjectRecord(name="test", root_path="/tmp/up2-" + os.urandom(4).hex())
        with db.session() as s:
            db.project_create(s, project)
            pf = ProjectFileRecord(
                project_id=project.id, relative_path="main.py",
                file_hash="abc123", language="python",
            )
            db.project_file_upsert(s, pf)

            # Update with new hash
            pf2 = ProjectFileRecord(
                project_id=project.id, relative_path="main.py",
                file_hash="def456", language="python",
            )
            db.project_file_upsert(s, pf2)

            found = db.project_file_get(s, project.id, "main.py")
            assert found.file_hash == "def456"

        os.unlink(db_path)


# ===========================================================================
# Pipeline Integration — cache key scoping, tool layer, schema
# ===========================================================================

class TestPipelineIntegration:
    def test_cache_key_includes_project_id(self):
        """Same query produces different cache keys with different project_ids."""
        from bitmod.cache_engine import compute_answer_key
        key_no_proj = compute_answer_key("What is HIPAA?")
        key_proj_a = compute_answer_key("What is HIPAA?", project_id="proj-a")
        key_proj_b = compute_answer_key("What is HIPAA?", project_id="proj-b")

        assert key_no_proj != key_proj_a
        assert key_proj_a != key_proj_b
        # Same project produces same key
        assert compute_answer_key("What is HIPAA?", project_id="proj-a") == key_proj_a

    def test_cache_key_without_project_unchanged(self):
        """Cache keys without project_id are unchanged (backwards compat)."""
        from bitmod.cache_engine import compute_answer_key
        key = compute_answer_key("test query", filters={"jurisdiction": "CA"})
        key2 = compute_answer_key("test query", filters={"jurisdiction": "CA"}, project_id=None)
        assert key == key2

    def test_chat_request_accepts_project_id(self):
        """ChatRequest schema accepts optional project_id."""
        from bitmod.schemas import ChatRequest
        req = ChatRequest(message="Hello", project_id="abc-123")
        assert req.project_id == "abc-123"

        req_no_proj = ChatRequest(message="Hello")
        assert req_no_proj.project_id is None

    def test_search_project_tool_defined(self):
        """search_project tool is in ALL_TOOLS."""
        from bitmod.tool_layer import ALL_TOOLS
        names = {t.name for t in ALL_TOOLS}
        assert "search_project" in names
        assert "search_data" in names
        assert "get_section" in names

    def test_search_project_no_project(self):
        """search_project returns error when no project_id."""
        from bitmod.tool_layer import execute_tool
        db, db_path = _make_db()
        result = execute_tool("search_project", {"query": "test"}, db, project_id=None)
        assert "error" in result
        os.unlink(db_path)

    def test_search_project_with_project(self):
        """search_project searches project chunks when project_id is set."""
        db, db_path = _make_db()
        from bitmod.interfaces.database import ProjectRecord, ProjectFileRecord, ProjectChunkRecord
        from bitmod.tool_layer import execute_tool

        project = ProjectRecord(name="test", root_path="/tmp/sp-" + os.urandom(4).hex())
        with db.session() as s:
            db.project_create(s, project)
            pf = ProjectFileRecord(
                project_id=project.id, relative_path="main.py",
                file_hash="abc", language="python",
            )
            db.project_file_upsert(s, pf)
            chunk = ProjectChunkRecord(
                file_id=pf.id, project_id=project.id,
                content="def calculate_tax(): return 0.15",
                start_line=1, end_line=1,
                symbol_name="calculate_tax", symbol_type="function",
            )
            db.project_chunk_store(s, chunk)

        # Symbol search (no embedder needed)
        result = execute_tool(
            "search_project",
            {"query": "tax calculation", "symbol": "calculate_tax"},
            db, project_id=project.id,
        )
        assert result["total"] >= 1
        assert any(r.get("symbol_name") == "calculate_tax" for r in result["results"])

        os.unlink(db_path)

    def test_search_project_finds_conversations(self):
        """search_project tool does not crash without embedder."""
        db, db_path = _make_db()
        from bitmod.interfaces.database import ProjectRecord
        from bitmod.tool_layer import execute_tool

        project = ProjectRecord(name="test", root_path="/tmp/sc-" + os.urandom(4).hex())
        with db.session() as s:
            db.project_create(s, project)

        # Without embedder, should still return results (empty but no crash)
        result = execute_tool(
            "search_project",
            {"query": "test query"},
            db, project_id=project.id,
        )
        assert "results" in result
        assert isinstance(result["results"], list)

        os.unlink(db_path)
