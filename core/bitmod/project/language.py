"""Language detection and file filtering for project indexing."""

from __future__ import annotations

import os
from pathlib import Path

# Extension → language mapping
EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".scala": "scala",
    ".r": "r",
    ".R": "r",
    ".sql": "sql",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".xml": "xml",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "css",
    ".sass": "css",
    ".md": "markdown",
    ".mdx": "markdown",
    ".txt": "text",
    ".env": "dotenv",
    ".dockerfile": "dockerfile",
    ".tf": "terraform",
    ".tfvars": "terraform",
    ".proto": "protobuf",
    ".graphql": "graphql",
    ".gql": "graphql",
    ".lua": "lua",
    ".zig": "zig",
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",
    ".hs": "haskell",
    ".ml": "ocaml",
    ".mli": "ocaml",
    ".clj": "clojure",
    ".cljs": "clojure",
    ".dart": "dart",
    ".vue": "vue",
    ".svelte": "svelte",
}

# Files to always skip
SKIP_DIRS: set[str] = {
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".next",
    ".nuxt",
    ".output",
    "dist",
    "build",
    "out",
    "target",
    ".venv",
    "venv",
    "env",
    ".env",
    ".tox",
    ".nox",
    "vendor",
    "third_party",
    ".idea",
    ".vscode",
    "coverage",
    ".coverage",
    "htmlcov",
    ".terraform",
    ".serverless",
    "eggs",
    "*.egg-info",
}

SKIP_FILES: set[str] = {
    ".DS_Store",
    "Thumbs.db",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Pipfile.lock",
    "poetry.lock",
    "go.sum",
    "Cargo.lock",
    # Secret and credential files — must never be indexed
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.staging",
    ".env.test",
    "credentials.json",
    "service-account.json",
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
    "id_dsa",
    ".netrc",
    ".pgpass",
    ".htpasswd",
}

# Patterns for secret files that match by extension or prefix
_SECRET_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pem",
        ".key",
        ".p12",
        ".pfx",
    }
)

_SECRET_PREFIXES: tuple[str, ...] = (
    ".env.",  # catches .env.anything
)

# Max file size to index (1MB)
MAX_FILE_SIZE = 1_000_000

# Binary file extensions to skip
BINARY_EXTENSIONS: set[str] = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".svg",
    ".webp",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".wav",
    ".flac",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".rar",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".o",
    ".a",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".otf",
    ".pyc",
    ".pyo",
    ".class",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".bin",
    ".dat",
}


def detect_language(path: str) -> str:
    """Detect the programming language from a file path."""
    ext = Path(path).suffix.lower()
    # Special case: Dockerfile (no extension)
    name = Path(path).name.lower()
    if name == "dockerfile" or name.startswith("dockerfile."):
        return "dockerfile"
    if name == "makefile" or name == "gnumakefile":
        return "makefile"
    if name == "cmakelists.txt":
        return "cmake"
    return EXTENSION_MAP.get(ext, "")


def detect_framework(files: set[str]) -> str:
    """Detect the likely framework from a set of file paths."""
    names = {os.path.basename(f).lower() for f in files}
    # Check for framework indicators
    if "next.config.mjs" in names or "next.config.js" in names or "next.config.ts" in names:
        return "nextjs"
    if "nuxt.config.ts" in names or "nuxt.config.js" in names:
        return "nuxt"
    if "angular.json" in names:
        return "angular"
    if "svelte.config.js" in names:
        return "svelte"
    if "vite.config.ts" in names or "vite.config.js" in names:
        return "vite"
    if "manage.py" in names:
        return "django"
    if "app.py" in names or "wsgi.py" in names:
        return "flask"
    if "fastapi" in " ".join(names):
        return "fastapi"
    if "cargo.toml" in names:
        return "rust"
    if "go.mod" in names:
        return "go"
    if "build.gradle" in names or "build.gradle.kts" in names:
        return "gradle"
    if "pom.xml" in names:
        return "maven"
    if "pyproject.toml" in names or "setup.py" in names:
        return "python"
    if "package.json" in names:
        return "node"
    return ""


def should_index(path: str, root: str) -> bool:
    """Determine if a file should be indexed."""
    rel = os.path.relpath(path, root)
    parts = Path(rel).parts

    # Skip hidden files (except specific configs)
    for part in parts:
        if part in SKIP_DIRS:
            return False
        # Wildcard match for egg-info
        if part.endswith(".egg-info"):
            return False

    name = os.path.basename(path)

    # Skip specific files
    if name in SKIP_FILES:
        return False

    # Skip secret files by extension (.pem, .key, .p12, .pfx)
    ext = Path(path).suffix.lower()
    if ext in _SECRET_EXTENSIONS:
        return False

    # Skip secret files by prefix (.env.*)
    name_lower = name.lower()
    if any(name_lower.startswith(prefix) for prefix in _SECRET_PREFIXES):
        return False

    # Skip binary files
    if ext in BINARY_EXTENSIONS:
        return False

    # Skip files too large
    try:
        if os.path.getsize(path) > MAX_FILE_SIZE:
            return False
    except OSError:
        return False

    # Must have a recognized language or be a known config file
    if not detect_language(path) and ext not in {".cfg", ".ini", ".conf", ".editorconfig"}:
        return False

    return True
