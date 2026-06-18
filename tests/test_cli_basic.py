"""Tests for the BitMod CLI (core/bitmod/cli.py)."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest  # noqa: F401

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_cli(*args: str, timeout: int = 15, input_text: str | None = None) -> subprocess.CompletedProcess:
    """Run `python -m bitmod <args>` and capture output."""
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "bitmod", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        input=input_text,
    )


# ---------------------------------------------------------------------------
# Entry Point & Help
# ---------------------------------------------------------------------------


class TestCLIEntryPoint:
    """Test that CLI commands are reachable."""

    def test_python_m_bitmod_shows_help(self):
        result = run_cli()
        assert result.returncode == 1
        assert "usage" in result.stderr.lower() or "usage" in result.stdout.lower() or "bitmod" in result.stdout.lower()

    def test_bitmod_help_flag(self):
        result = run_cli("--help")
        assert result.returncode == 0
        assert "bitmod" in result.stdout.lower()

    def test_version_flag(self):
        result = run_cli("--version")
        assert result.returncode == 0
        # Should contain a version string like "bitmod 0.2.0"
        assert "bitmod" in result.stdout.lower()

    def test_subcommand_help(self):
        commands = (
            "init", "doctor", "ingest", "query", "serve", "status",
            "cache", "migrate", "backup", "proxy", "update", "completions",
        )
        for cmd in commands:
            result = run_cli(cmd, "--help")
            assert result.returncode == 0, f"{cmd} --help failed"


# ---------------------------------------------------------------------------
# Doctor
# ---------------------------------------------------------------------------


class TestCLIDoctor:
    def test_doctor_runs(self):
        result = run_cli("doctor", timeout=60)
        assert result.returncode in (0, 1)

    def test_doctor_json(self):
        result = run_cli("--format", "json", "doctor", timeout=60)
        if result.returncode in (0, 1):
            data = json.loads(result.stdout)
            assert "healthy" in data
            assert "issues" in data
            assert "data_directory" in data

    def test_doctor_no_crash(self):
        result = run_cli("doctor", timeout=60)
        # Should not have a Python traceback
        assert "Traceback" not in result.stderr


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


class TestCLIStatus:
    def test_status_runs(self):
        result = run_cli("status")
        assert result.returncode in (0, 1)

    def test_status_json_output(self):
        result = run_cli("--format", "json", "status")
        if result.returncode == 0:
            data = json.loads(result.stdout)
            assert "db_backend" in data
            assert "documents" in data
            assert "cache_stats" in data


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestCLIConfig:
    def test_config_show_runs(self):
        result = run_cli("config", "show")
        assert result.returncode in (0, 1)

    def test_config_json_output(self):
        result = run_cli("--format", "json", "config", "show")
        if result.returncode == 0:
            data = json.loads(result.stdout)
            assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


class TestCLICache:
    def test_cache_stats_runs(self):
        result = run_cli("cache", "stats")
        assert result.returncode in (0, 1)

    def test_cache_stats_json(self):
        result = run_cli("--format", "json", "cache", "stats")
        if result.returncode == 0:
            data = json.loads(result.stdout)
            assert isinstance(data, dict)

    def test_cache_recent_runs(self):
        result = run_cli("cache", "recent")
        assert result.returncode in (0, 1)

    def test_cache_recent_json(self):
        result = run_cli("--format", "json", "cache", "recent")
        if result.returncode == 0:
            data = json.loads(result.stdout)
            assert "entries" in data

    def test_cache_search_no_query(self):
        result = run_cli("cache", "search")
        assert result.returncode == 1

    def test_cache_search_runs(self):
        result = run_cli("cache", "search", "test query")
        assert result.returncode in (0, 1)

    def test_cache_search_json(self):
        result = run_cli("--format", "json", "cache", "search", "test")
        if result.returncode == 0:
            data = json.loads(result.stdout)
            assert "results" in data

    def test_cache_help(self):
        result = run_cli("cache", "--help")
        assert result.returncode == 0
        assert "stats" in result.stdout
        assert "recent" in result.stdout
        assert "search" in result.stdout


# ---------------------------------------------------------------------------
# Completions
# ---------------------------------------------------------------------------


class TestCLICompletions:
    def test_bash_completion(self):
        result = run_cli("completions", "bash")
        assert result.returncode == 0
        assert "complete" in result.stdout
        assert "_bitmod" in result.stdout

    def test_zsh_completion(self):
        result = run_cli("completions", "zsh")
        assert result.returncode == 0
        assert "compdef" in result.stdout or "_bitmod" in result.stdout

    def test_fish_completion(self):
        result = run_cli("completions", "fish")
        assert result.returncode == 0
        assert "complete -c bitmod" in result.stdout

    def test_completions_help_shows_install(self):
        result = run_cli("completions", "--help")
        assert result.returncode == 0
        assert "install" in result.stdout.lower()


# ---------------------------------------------------------------------------
# Quiet Flag
# ---------------------------------------------------------------------------


class TestCLIQuiet:
    def test_quiet_suppresses_output(self):
        result = run_cli("--quiet", "status")
        if result.returncode == 0:
            # Quiet mode should produce less output than normal
            normal = run_cli("status")
            if normal.returncode == 0:
                assert len(result.stdout) <= len(normal.stdout)


# ---------------------------------------------------------------------------
# Format Flag
# ---------------------------------------------------------------------------


class TestCLIFormat:
    def test_format_json_valid(self):
        result = run_cli("--format", "json", "status")
        if result.returncode == 0:
            data = json.loads(result.stdout)
            assert isinstance(data, dict)

    def test_format_text_default(self):
        result = run_cli("status")
        if result.returncode == 0:
            # Text mode should not be valid JSON
            with pytest.raises(json.JSONDecodeError):
                json.loads(result.stdout)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


class TestCLIUpdate:
    def test_update_runs(self):
        result = run_cli("update", timeout=20)
        # May fail due to network, but should not crash
        assert result.returncode in (0, 1)
        assert "Traceback" not in result.stderr


# ---------------------------------------------------------------------------
# Migrate
# ---------------------------------------------------------------------------


class TestCLIMigrate:
    def test_migrate_status(self):
        result = run_cli("migrate", "--status")
        assert result.returncode in (0, 1)

    def test_migrate_status_json(self):
        result = run_cli("--format", "json", "migrate", "--status")
        if result.returncode in (0, 1):
            data = json.loads(result.stdout)
            assert "current_version" in data or "error" in data

    def test_migrate_runs(self):
        result = run_cli("migrate")
        assert result.returncode in (0, 1)


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------


class TestCLIBackup:
    def test_backup_list(self):
        result = run_cli("backup", "list")
        assert result.returncode in (0, 1)

    def test_backup_list_json(self):
        result = run_cli("--format", "json", "backup", "list")
        if result.returncode == 0:
            data = json.loads(result.stdout)
            assert "sessions" in data

    def test_backup_show_requires_id(self):
        result = run_cli("backup", "show")
        # Should fail but not crash
        assert result.returncode in (0, 1)


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------


class TestCLIIngest:
    def test_ingest_missing_path(self):
        result = run_cli("ingest", "/nonexistent/path/to/file.txt")
        assert result.returncode == 1
        assert "not found" in result.stdout.lower() or "error" in result.stderr.lower()

    def test_ingest_stdin_no_input(self):
        result = run_cli("ingest", "-", input_text="")
        assert result.returncode == 1

    def test_ingest_help(self):
        result = run_cli("ingest", "--help")
        assert result.returncode == 0
        assert "stdin" in result.stdout.lower() or "-" in result.stdout


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


class TestCLIQuery:
    def test_query_help(self):
        result = run_cli("query", "--help")
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Proxy
# ---------------------------------------------------------------------------


class TestCLIProxy:
    def test_proxy_help(self):
        result = run_cli("proxy", "--help")
        assert result.returncode == 0
        assert "port" in result.stdout.lower()


# ---------------------------------------------------------------------------
# Build Parser
# ---------------------------------------------------------------------------


class TestBuildParser:
    def test_parser_has_all_commands(self):
        from bitmod.cli import build_parser

        parser = build_parser()
        # Check all subcommands are registered
        choices = parser._subparsers._group_actions[0].choices  # type: ignore[union-attr]
        expected = {
            "init", "doctor", "ingest", "query", "serve", "proxy",
            "status", "cache", "migrate", "backup", "update", "config",
            "completions",
        }
        assert expected.issubset(set(choices.keys()))

    def test_parser_global_flags(self):
        from bitmod.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["--format", "json", "--quiet", "status"])
        assert args.format == "json"
        assert args.quiet is True
        assert args.command == "status"

    def test_parser_format_default(self):
        from bitmod.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["status"])
        assert args.format == "text"
        assert args.quiet is False
