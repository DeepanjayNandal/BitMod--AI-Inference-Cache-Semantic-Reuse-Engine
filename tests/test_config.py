"""Tests for Bitmod configuration."""

import os

import pytest

from bitmod.config import BitmodConfig, DatabaseConfig, LLMConfig, load_config


class TestDefaultConfig:
    def test_default_config(self):
        """Defaults are sensible."""
        config = BitmodConfig()
        assert config.db.backend in ("sqlite", "postgresql")
        assert config.llm.url  # non-empty default URL
        assert config.embedding.provider in ("local", "openai", "cohere", "ollama")
        assert config.gateway.port > 0
        assert config.db.pool_size > 0

    def test_default_sqlite_path(self):
        """Default SQLite path is set."""
        config = DatabaseConfig()
        assert config.sqlite_path  # non-empty

    def test_default_llm_url(self):
        """Default LLM URL points to local Ollama."""
        config = LLMConfig()
        assert "localhost:11434" in config.url

    def test_resolve_provider_default(self):
        """Default resolution returns a valid provider string."""
        config = LLMConfig()
        resolved = config.resolve_provider()
        # Result depends on env vars that may be set by other tests or the environment
        assert isinstance(resolved, str) and len(resolved) > 0

    def test_resolve_model(self):
        """Universal model field takes priority over legacy."""
        config = LLMConfig()
        config.model = "test-model"
        config.primary_model = "legacy-model"
        assert config.resolve_model() == "test-model"

    def test_resolve_model_fallback(self):
        """Falls back to primary_model when model is empty."""
        config = LLMConfig()
        config.model = ""
        config.primary_model = "legacy-model"
        assert config.resolve_model() == "legacy-model"


class TestEnvOverride:
    def test_env_override(self, monkeypatch):
        """Environment variables override defaults."""
        monkeypatch.setenv("BITMOD_DB_BACKEND", "postgresql")
        monkeypatch.setenv("GATEWAY_PORT", "9999")

        config = BitmodConfig()
        assert config.db.backend == "postgresql"
        assert config.gateway.port == 9999

    def test_env_override_llm(self, monkeypatch):
        """LLM env vars override defaults."""
        monkeypatch.setenv("BITMOD_LLM_PRIMARY", "openai")
        monkeypatch.setenv("BITMOD_LLM_PRIMARY_MODEL", "gpt-4o")

        config = LLMConfig()
        assert config.primary == "openai"
        assert config.primary_model == "gpt-4o"


class TestLoadConfig:
    def test_load_config(self):
        """Factory function returns a BitmodConfig."""
        config = load_config()
        assert isinstance(config, BitmodConfig)
        assert hasattr(config, "db")
        assert hasattr(config, "llm")
        assert hasattr(config, "embedding")
        assert hasattr(config, "vector_store")
        assert hasattr(config, "gateway")
