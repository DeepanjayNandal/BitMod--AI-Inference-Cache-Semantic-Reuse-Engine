"""Expanded tests for Bitmod configuration: defaults, env overrides, validation."""

import os

import pytest

from bitmod.config import (
    BitmodConfig,
    DatabaseConfig,
    EmbeddingConfig,
    GatewayConfig,
    LLMConfig,
    RedisConfig,
    VectorStoreConfig,
    load_config,
)


class TestDefaultValues:
    """Test that default configuration values are sensible."""

    def test_database_defaults(self):
        """Database config has sensible defaults."""
        config = DatabaseConfig()
        assert config.backend in ("sqlite", "postgresql")
        assert config.sqlite_path  # non-empty
        assert config.pool_size > 0
        assert config.max_overflow > 0
        assert config.pool_recycle > 0

    def test_redis_defaults(self):
        """Redis config defaults to localhost:6379."""
        config = RedisConfig()
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.url == "redis://localhost:6379"

    def test_llm_defaults(self):
        """LLM config has universal URL and fallback model set."""
        config = LLMConfig()
        assert config.url  # non-empty default URL
        assert config.fallback_model  # non-empty

    def test_embedding_defaults(self):
        """Embedding config defaults to local provider with dimensions."""
        config = EmbeddingConfig()
        assert config.provider == "local"
        assert config.dimensions > 0
        assert config.device in ("cpu", "cuda", "mps")

    def test_vector_store_defaults(self):
        """Vector store config defaults to empty (use DB backend)."""
        config = VectorStoreConfig()
        assert config.store == ""

    def test_gateway_defaults(self):
        """Gateway config has a valid port."""
        config = GatewayConfig()
        assert config.port > 0
        assert isinstance(config.cors_origins, list)
        assert len(config.cors_origins) >= 1

    def test_bitmod_config_has_all_sub_configs(self):
        """Top-level config aggregates all sub-configs."""
        config = BitmodConfig()
        assert isinstance(config.db, DatabaseConfig)
        assert isinstance(config.redis, RedisConfig)
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.embedding, EmbeddingConfig)
        assert isinstance(config.vector_store, VectorStoreConfig)
        assert isinstance(config.gateway, GatewayConfig)


class TestEnvVarOverrides:
    """Test that environment variables override defaults."""

    def test_db_backend_override(self, monkeypatch):
        """BITMOD_DB_BACKEND env var overrides default."""
        monkeypatch.setenv("BITMOD_DB_BACKEND", "postgresql")
        config = DatabaseConfig()
        assert config.backend == "postgresql"

    def test_gateway_port_override(self, monkeypatch):
        """GATEWAY_PORT env var overrides default."""
        monkeypatch.setenv("GATEWAY_PORT", "9999")
        config = GatewayConfig()
        assert config.port == 9999

    def test_embedding_provider_override(self, monkeypatch):
        """BITMOD_EMBEDDING_PROVIDER env var overrides default."""
        monkeypatch.setenv("BITMOD_EMBEDDING_PROVIDER", "openai")
        config = EmbeddingConfig()
        assert config.provider == "openai"

    def test_redis_host_override(self, monkeypatch):
        """REDIS_HOST env var overrides default."""
        monkeypatch.setenv("REDIS_HOST", "redis.example.com")
        config = RedisConfig()
        assert config.host == "redis.example.com"
        assert "redis.example.com" in config.url

    def test_cors_origins_override(self, monkeypatch):
        """CORS_ORIGINS env var overrides default, split by comma."""
        monkeypatch.setenv("CORS_ORIGINS", "http://a.com,http://b.com")
        config = GatewayConfig()
        assert len(config.cors_origins) == 2
        assert "http://a.com" in config.cors_origins
        assert "http://b.com" in config.cors_origins


class TestLoadConfig:
    """Test the load_config factory function."""

    def test_returns_bitmod_config(self):
        """load_config returns a fully constructed BitmodConfig."""
        config = load_config()
        assert isinstance(config, BitmodConfig)

    def test_load_config_with_overrides(self, monkeypatch):
        """load_config picks up env var overrides."""
        monkeypatch.setenv("BITMOD_DB_BACKEND", "postgresql")
        monkeypatch.setenv("BITMOD_LLM_PRIMARY", "openai")
        config = load_config()
        assert config.db.backend == "postgresql"
        assert config.llm.primary == "openai"
