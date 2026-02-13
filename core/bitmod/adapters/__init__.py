"""Adapter registry — lazy-loading factories for all backends."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bitmod.config import DatabaseConfig, EmbeddingConfig, LLMConfig, VectorStoreConfig
    from bitmod.interfaces import DatabaseBackend, EmbeddingProvider, LLMProvider, VectorStore
    from bitmod.interfaces.messaging import MessagingPlatform


def get_backend(config: DatabaseConfig | None = None) -> DatabaseBackend:
    """Create a database backend from config. Defaults to SQLite."""
    if config is None:
        from bitmod.config import load_config

        config = load_config().db

    match config.backend:
        case "sqlite":
            from bitmod.adapters.db_sqlite import SQLiteBackend

            return SQLiteBackend(config.sqlite_path)
        case "postgresql":
            from bitmod.adapters.db_postgresql import PostgreSQLBackend

            return PostgreSQLBackend(config.url)
        case "mysql":
            from bitmod.adapters.db_mysql import MySQLBackend

            return MySQLBackend(config.url)
        case "mongodb":
            from bitmod.adapters.db_mongodb import MongoDBBackend

            return MongoDBBackend(url=config.mongodb_url, db_name=config.mongodb_db)
        case _:
            raise ValueError(f"Unknown database backend: {config.backend}")


def get_llm(config: LLMConfig | None = None) -> LLMProvider:
    """Create an LLM provider from config using auto-detection."""
    if config is None:
        from bitmod.config import load_config

        config = load_config().llm

    provider = config.resolve_provider()
    return make_llm(provider, config)


def _auto_detect_from_url(url: str) -> str:
    """Auto-detect provider from URL pattern."""
    url_lower = url.lower()
    if "anthropic" in url_lower:
        return "anthropic"
    if "googleapis" in url_lower or "generativelanguage" in url_lower:
        return "gemini"
    if "bedrock" in url_lower:
        return "bedrock"
    return "openai_compatible"


def make_llm(provider: str, config: LLMConfig) -> LLMProvider:
    model = config.resolve_model()

    match provider:
        case "auto" | "":
            # Auto-detect from URL, then recurse with resolved provider
            resolved = _auto_detect_from_url(config.url)
            return make_llm(resolved, config)
        case "anthropic":
            from bitmod.adapters.llm_anthropic import AnthropicAdapter

            return AnthropicAdapter(api_key=config.anthropic_api_key or config.api_key, model=model)
        case "openai":
            from bitmod.adapters.llm_openai import OpenAIAdapter

            return OpenAIAdapter(api_key=config.openai_api_key or config.api_key, model=model)
        case "openai_compatible":
            from bitmod.adapters.llm_openai_compat import OpenAICompatAdapter

            return OpenAICompatAdapter(
                base_url=config.openai_compatible_base_url or config.url,
                api_key=config.openai_compatible_api_key or config.api_key,
                model=model,
            )
        case "ollama":
            from bitmod.adapters.llm_ollama import OllamaAdapter

            return OllamaAdapter(base_url=config.ollama_url, model=model)
        case "gemini":
            from bitmod.adapters.llm_gemini import GeminiAdapter

            return GeminiAdapter(api_key=config.gemini_api_key or config.api_key, model=model)
        case "bedrock":
            from bitmod.adapters.llm_bedrock import BedrockAdapter

            return BedrockAdapter(model=model)
        case "azure_openai":
            from bitmod.adapters.llm_azure_openai import AzureOpenAIAdapter

            return AzureOpenAIAdapter(model=model)
        case "xai":
            from bitmod.adapters.llm_xai import XAIAdapter

            return XAIAdapter(api_key=config.xai_api_key or config.api_key, model=model)
        case "mistral":
            from bitmod.adapters.llm_mistral import MistralAdapter

            return MistralAdapter(api_key=config.mistral_api_key or config.api_key, model=model)
        case "perplexity":
            from bitmod.adapters.llm_perplexity import PerplexityAdapter

            return PerplexityAdapter(api_key=config.perplexity_api_key or config.api_key, model=model)
        case "openrouter":
            from bitmod.adapters.llm_openrouter import OpenRouterAdapter

            return OpenRouterAdapter(api_key=config.openrouter_api_key or config.api_key, model=model)
        case "huggingface":
            from bitmod.adapters.llm_huggingface import HuggingFaceAdapter

            return HuggingFaceAdapter(api_key=config.hf_api_key or config.api_key, model=model)
        case _:
            raise ValueError(f"Unknown LLM provider: {provider}")


def get_embedder(config: EmbeddingConfig | None = None) -> EmbeddingProvider:
    """Create an embedding provider from config."""
    if config is None:
        from bitmod.config import load_config

        config = load_config().embedding

    provider = config.provider
    match provider:
        case "local":
            from bitmod.adapters.embed_local import LocalEmbeddingAdapter

            return LocalEmbeddingAdapter(model=config.model, device=config.device)
        case "openai":
            from bitmod.adapters.embed_openai import OpenAIEmbeddingAdapter

            return OpenAIEmbeddingAdapter(model=config.model)
        case "cohere":
            from bitmod.adapters.embed_cohere import CohereEmbeddingAdapter

            return CohereEmbeddingAdapter(model=config.model)
        case "ollama":
            from bitmod.adapters.embed_ollama import OllamaEmbeddingAdapter

            return OllamaEmbeddingAdapter(model=config.model)
        case _:
            raise ValueError(f"Unknown embedding provider: {provider}")


def get_vector_store(config: VectorStoreConfig | None = None) -> VectorStore | None:
    """Create a vector store from config. Returns None if not configured."""
    if config is None:
        from bitmod.config import load_config

        config = load_config().vector_store

    if not config.store:
        return None

    match config.store:
        case "chroma":
            from bitmod.adapters.vec_chroma import ChromaAdapter

            return ChromaAdapter(path=config.chroma_path)
        case "qdrant":
            from bitmod.adapters.vec_qdrant import QdrantAdapter

            return QdrantAdapter(url=config.qdrant_url, api_key=config.qdrant_api_key)
        case "pinecone":
            from bitmod.adapters.vec_pinecone import PineconeAdapter

            return PineconeAdapter(api_key=config.pinecone_api_key, index_name=config.pinecone_index)
        case _:
            raise ValueError(f"Unknown vector store: {config.store}")


def get_messaging_platform(platform: str, **kwargs: object) -> MessagingPlatform:
    """Create a messaging platform adapter."""
    match platform:
        case "telegram":
            from bitmod.adapters.msg_telegram import TelegramAdapter

            return TelegramAdapter(**kwargs)  # type: ignore[arg-type]
        case "discord":
            from bitmod.adapters.msg_discord import DiscordAdapter

            return DiscordAdapter(**kwargs)  # type: ignore[arg-type]
        case "slack":
            from bitmod.adapters.msg_slack import SlackAdapter

            return SlackAdapter(**kwargs)  # type: ignore[arg-type]
        case "whatsapp":
            from bitmod.adapters.msg_whatsapp import WhatsAppAdapter

            return WhatsAppAdapter(**kwargs)  # type: ignore[arg-type]
        case "matrix":
            from bitmod.adapters.msg_matrix import MatrixAdapter

            return MatrixAdapter(**kwargs)  # type: ignore[arg-type]
        case _:
            raise ValueError(f"Unknown messaging platform: {platform}")
