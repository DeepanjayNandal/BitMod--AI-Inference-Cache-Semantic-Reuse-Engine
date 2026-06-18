"""Expanded CLI integration tests exercising bitmod commands via subprocess."""

from __future__ import annotations

import json
import re
import subprocess
import sys

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SQLITE_ENV = {
    "BITMOD_DB_BACKEND": "sqlite",
    "BITMOD_SQLITE_PATH": ":memory:",
}


def run_cli(
    *args: str,
    timeout: int = 30,
    input_text: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run ``python -m bitmod <args>`` with SQLite in-memory defaults."""
    import os

    env = {**os.environ, **_SQLITE_ENV, **(extra_env or {})}
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "bitmod", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        input=input_text,
        env=env,
    )


# ---------------------------------------------------------------------------
# bitmod --version
# ---------------------------------------------------------------------------


class TestVersion:
    def test_version_outputs_semver(self):
        result = run_cli("--version")
        assert result.returncode == 0
        assert "bitmod" in result.stdout.lower()
        assert re.search(r"\d+\.\d+\.\d+", result.stdout), f"No semver in output: {result.stdout!r}"


# ---------------------------------------------------------------------------
# bitmod status
# ---------------------------------------------------------------------------


class TestStatus:
    def test_status_runs(self):
        result = run_cli("status", timeout=30)
        assert result.returncode == 0, f"status failed (rc={result.returncode}): {result.stderr}"

    def test_status_json_output(self):
        result = run_cli("--format", "json", "status", timeout=30)
        assert result.returncode == 0, f"status --format json failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert "db_backend" in data
        assert "cache_stats" in data

    def test_status_json_has_provider_info(self):
        result = run_cli("--format", "json", "status", timeout=30)
        assert result.returncode == 0, f"status --format json failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert "llm_provider" in data
        assert "embedding_provider" in data


# ---------------------------------------------------------------------------
# bitmod config show
# ---------------------------------------------------------------------------


class TestConfigShow:
    def test_config_show_runs(self):
        result = run_cli("config", "show", timeout=15)
        assert result.returncode == 0
        assert len(result.stdout.strip()) > 0

    def test_config_show_json(self):
        result = run_cli("--format", "json", "config", "show", timeout=15)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    def test_config_show_masks_sensitive(self):
        """Sensitive values like API keys should be masked."""
        result = run_cli(
            "--format",
            "json",
            "config",
            "show",
            extra_env={"ANTHROPIC_API_KEY": "sk-ant-secret123"},
            timeout=15,
        )
        assert result.returncode == 0
        raw = result.stdout
        assert "sk-ant-secret123" not in raw


# ---------------------------------------------------------------------------
# bitmod doctor
# ---------------------------------------------------------------------------


class TestDoctor:
    def test_doctor_runs_without_crash(self):
        result = run_cli("doctor", timeout=60)
        # doctor exits 0 when healthy, 1 when issues found — both are valid
        assert result.returncode in (0, 1)
        # But it must actually produce output
        combined = result.stdout + result.stderr
        assert len(combined.strip()) > 0, "doctor produced no output"

    def test_doctor_json_output(self):
        result = run_cli("--format", "json", "doctor", timeout=60)
        assert result.returncode in (0, 1)
        assert result.stdout.strip(), f"doctor --format json produced no output (rc={result.returncode})"
        data = json.loads(result.stdout)
        assert isinstance(data, dict)
        # Must contain at least one of the expected top-level keys
        assert "healthy" in data or "data_directory" in data, f"Unexpected doctor output: {list(data.keys())}"

    def test_doctor_checks_database(self):
        result = run_cli("--format", "json", "doctor", timeout=60)
        assert result.returncode in (0, 1)
        assert result.stdout.strip(), "doctor produced no output"
        data = json.loads(result.stdout)
        assert "database" in data, f"doctor JSON missing 'database' key: {list(data.keys())}"


# ---------------------------------------------------------------------------
# bitmod cache stats
# ---------------------------------------------------------------------------


class TestCacheStats:
    def test_cache_stats_runs(self):
        result = run_cli("cache", "stats", timeout=15)
        assert result.returncode == 0, f"cache stats failed (rc={result.returncode}): {result.stderr}"

    def test_cache_stats_json(self):
        result = run_cli("--format", "json", "cache", "stats", timeout=15)
        assert result.returncode == 0, f"cache stats --format json failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# bitmod query
# ---------------------------------------------------------------------------


class TestQuery:
    def test_query_missing_question_fails(self):
        result = run_cli("query", timeout=15)
        assert result.returncode != 0

    def test_query_json_offline_mode(self):
        """With no server running, query should fail gracefully with error JSON."""
        result = run_cli(
            "--format",
            "json",
            "query",
            "What is a test?",
            extra_env={"BITMOD_URL": "http://127.0.0.1:19999"},
            timeout=30,
        )
        # Query to unreachable server should fail
        assert result.returncode != 0 or result.stdout.strip()
        # If there's output, it should be valid JSON
        if result.stdout.strip():
            data = json.loads(result.stdout)
            assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# bitmod ingest
# ---------------------------------------------------------------------------


class TestIngest:
    def test_ingest_missing_path_fails(self):
        result = run_cli("ingest", timeout=15)
        assert result.returncode != 0

    def test_ingest_nonexistent_path_fails(self):
        result = run_cli("ingest", "/nonexistent/path/foo.txt", timeout=15)
        assert result.returncode != 0

    def test_ingest_stdin_empty_fails(self):
        result = run_cli("ingest", "-", input_text="", timeout=15)
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestErrorCases:
    def test_unknown_command_fails(self):
        result = run_cli("nonexistent_command", timeout=10)
        assert result.returncode != 0

    def test_no_command_shows_help(self):
        result = run_cli(timeout=10)
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "usage" in combined.lower(), f"No usage text in output: {combined[:200]}"

    def test_cache_missing_action_fails(self):
        result = run_cli("cache", timeout=10)
        assert result.returncode != 0

    def test_config_missing_action_fails(self):
        result = run_cli("config", timeout=10)
        assert result.returncode != 0

    def test_completions_missing_shell_fails(self):
        result = run_cli("completions", timeout=10)
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# Global flags
# ---------------------------------------------------------------------------


class TestGlobalFlags:
    def test_quiet_suppresses_output(self):
        """--quiet should produce less stdout than normal mode."""
        normal = run_cli("doctor", timeout=60)
        quiet = run_cli("--quiet", "doctor", timeout=60)
        assert quiet.returncode in (0, 1)
        # Quiet mode should produce less stdout (or equal if already minimal)
        assert len(quiet.stdout) <= len(normal.stdout)

    def test_json_format_flag(self):
        result = run_cli("--format", "json", "doctor", timeout=60)
        assert result.returncode in (0, 1)
        assert result.stdout.strip(), "JSON format produced no output"
        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    def test_help_on_each_subcommand(self):
        for cmd in ("init", "doctor", "ingest", "query", "serve", "status", "cache", "migrate"):
            result = run_cli(cmd, "--help", timeout=10)
            assert result.returncode == 0, f"{cmd} --help returned {result.returncode}"
