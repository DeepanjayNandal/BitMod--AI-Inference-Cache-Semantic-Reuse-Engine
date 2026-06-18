"""Tests for adapter factory functions."""

import pytest

from bitmod.adapters import get_backend, get_llm
from bitmod.adapters.db_sqlite import SQLiteBackend
from bitmod.config import DatabaseConfig, LLMConfig


class TestGetBackend:
    def test_get_backend_sqlite(self, tmp_path):
        """Default returns SQLiteBackend."""
        config = DatabaseConfig()
        config.backend = "sqlite"
        config.sqlite_path = str(tmp_path / "factory_test.db")
        backend = get_backend(config)
        assert isinstance(backend, SQLiteBackend)

    def test_get_backend_unknown_raises(self):
        """Invalid backend raises ValueError."""
        config = DatabaseConfig()
        config.backend = "nonexistent_db"
        with pytest.raises(ValueError, match="Unknown database backend"):
            get_backend(config)


class TestGetLLM:
    def test_get_llm_unknown_raises(self):
        """Invalid provider raises ValueError."""
        config = LLMConfig()
        config.provider = "nonexistent_provider"
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_llm(config)
