"""BitMod Python SDK — sync and async client for the BitMod intelligent cache gateway."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx

from .exceptions import (
    BitmodAuthError,
    BitmodConnectionError,
    BitmodError,
    BitmodNotFoundError,
    BitmodRateLimitError,
    BitmodServerError,
    BitmodTimeoutError,
    BitmodValidationError,
)
from .models import (
    AskResult,
    HealthStatus,
    IngestResult,
    LookupResult,
    SearchResult,
    UsageStats,
)

_DEFAULT_TIMEOUT = 60.0
_USER_AGENT = "bitmod-python/0.2.0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_api_key(api_key: str | None) -> str:
    key = api_key or os.environ.get("BITMOD_API_KEY")
    if not key:
        raise BitmodAuthError("No API key provided. Pass api_key= or set the BITMOD_API_KEY environment variable.")
    return key


def _resolve_base_url(base_url: str | None) -> str:
    url = base_url or os.environ.get("BITMOD_BASE_URL", "http://localhost:8000")
    return url.rstrip("/")


def _default_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
    }


def _raise_for_status(response: httpx.Response) -> None:
    """Translate HTTP errors into typed SDK exceptions."""
    if response.is_success:
        return

    try:
        body = response.json()
    except Exception:
        body = {"detail": response.text}

    msg = body.get("detail", body.get("error", response.text))
    code = response.status_code

    if code == 401 or code == 403:
        raise BitmodAuthError(msg, status_code=code, body=body)
    if code == 404:
        raise BitmodNotFoundError(msg, status_code=code, body=body)
    if code == 422:
        raise BitmodValidationError(msg, status_code=code, body=body)
    if code == 429:
        retry = response.headers.get("Retry-After")
        raise BitmodRateLimitError(
            msg,
            status_code=code,
            body=body,
            retry_after=float(retry) if retry else None,
        )
    if code >= 500:
        raise BitmodServerError(msg, status_code=code, body=body)

    raise BitmodError(msg, status_code=code, body=body)


# ---------------------------------------------------------------------------
# Synchronous client
# ---------------------------------------------------------------------------


class BitmodClient:
    """Official BitMod Python SDK.

    Usage::

        from bitmod_client import BitmodClient

        bm = BitmodClient(base_url="http://localhost:8000", api_key="bm_...")

        # Pattern A: Check cache before calling your LLM
        result = bm.lookup("What is HIPAA?")
        if result.hit:
            print(result.answer)  # Free, instant

        # Pattern B: Full query with automatic cache
        result = bm.ask("What is HIPAA?", model="gpt-4o", llm_key="sk-...")
        print(result.answer)
        print(f"Cached: {result.cached}, Saved: ${result.cost_saved:.4f}")

        # Pattern C: Drop-in OpenAI proxy
        openai_client = bm.openai_client(api_key="sk-...")

        # Pattern D: Drop-in Anthropic proxy
        anthropic_client = bm.anthropic_client(api_key="sk-ant-...")

        # Usage stats
        stats = bm.usage(days=30)
        print(f"Hit rate: {stats.hit_rate_pct}%, Saved: ${stats.total_savings_usd:.2f}")
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = 2,
    ) -> None:
        self._base_url = _resolve_base_url(base_url)
        self._api_key = _resolve_api_key(api_key)
        self._timeout = timeout
        self._max_retries = max_retries
        self._transport = httpx.HTTPTransport(retries=max_retries)
        self._client = httpx.Client(
            base_url=self._base_url,
            headers=_default_headers(self._api_key),
            timeout=httpx.Timeout(timeout),
            transport=self._transport,
        )

    # -- lifecycle ----------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> BitmodClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- private helpers ----------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type
        try:
            resp = self._client.request(
                method,
                path,
                json=json,
                params=params,
                files=files,
                headers=headers,
            )
        except httpx.ConnectError as exc:
            raise BitmodConnectionError(f"Cannot connect to BitMod at {self._base_url}: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise BitmodTimeoutError(f"Request to BitMod timed out after {self._timeout}s: {exc}") from exc

        _raise_for_status(resp)
        return resp.json()

    # -- public API ---------------------------------------------------------

    def lookup(self, query: str, *, confidence: float = 0.8) -> LookupResult:
        """Cache-only lookup. No LLM call is made.

        Args:
            query: The natural-language query.
            confidence: Minimum confidence threshold (0.0-1.0) to consider a hit.

        Returns:
            LookupResult with hit=True if a cached answer meets the threshold.
        """
        data = self._request(
            "POST",
            "/v1/lookup",
            json={"query": query, "confidence": confidence},
        )
        return LookupResult.from_dict(data)

    def ask(
        self,
        query: str,
        *,
        model: str | None = None,
        llm_key: str | None = None,
        temperature: float = 0.0,
        system_prompt: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AskResult:
        """Full query: checks cache first, falls back to LLM if needed.

        Args:
            query: The natural-language query.
            model: LLM model identifier (e.g. "gpt-4o", "claude-sonnet-4-20250514").
            llm_key: API key for the upstream LLM provider.
            temperature: Sampling temperature for the LLM (default 0.0 for determinism).
            system_prompt: Optional system prompt prepended to the LLM call.
            metadata: Arbitrary key-value metadata attached to this query for analytics.

        Returns:
            AskResult with the answer, cache status, cost, and latency.
        """
        payload: dict[str, Any] = {
            "query": query,
            "temperature": temperature,
        }
        if model:
            payload["model"] = model
        if llm_key:
            payload["llm_key"] = llm_key
        if system_prompt:
            payload["system_prompt"] = system_prompt
        if metadata:
            payload["metadata"] = metadata

        data = self._request("POST", "/v1/ask", json=payload)
        return AskResult.from_dict(data)

    def search(self, query: str, *, limit: int = 10, offset: int = 0) -> list[SearchResult]:
        """Hybrid semantic + keyword search across ingested content.

        Args:
            query: Search query.
            limit: Maximum number of results (default 10).
            offset: Number of results to skip for pagination (default 0).

        Returns:
            List of SearchResult ordered by relevance.
        """
        data = self._request(
            "POST",
            "/v1/search",
            json={"query": query, "limit": limit, "offset": offset},
        )
        results = data.get("results", data if isinstance(data, list) else [])
        return [SearchResult.from_dict(r) for r in results]

    def ingest_text(
        self,
        text: str,
        *,
        title: str | None = None,
        tags: Sequence[str] | None = None,
    ) -> IngestResult:
        """Ingest raw text into the BitMod knowledge store.

        Args:
            text: The text content to ingest.
            title: Optional title for the document.
            tags: Optional tags for filtering and organization.

        Returns:
            IngestResult with document id and chunk count.
        """
        payload: dict[str, Any] = {"text": text}
        if title:
            payload["title"] = title
        if tags:
            payload["tags"] = list(tags)

        data = self._request("POST", "/v1/ingest/text", json=payload)
        return IngestResult.from_dict(data)

    def ingest_file(self, path: str | Path) -> IngestResult:
        """Upload and ingest a file into the BitMod knowledge store.

        Supports PDF, DOCX, TXT, MD, HTML, and CSV.

        Args:
            path: Local filesystem path to the file.

        Returns:
            IngestResult with document id and chunk count.
        """
        filepath = Path(path)
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(filepath, "rb") as f:
            data = self._request(
                "POST",
                "/v1/ingest/file",
                files={"file": (filepath.name, f)},
            )
        return IngestResult.from_dict(data)

    def usage(self, *, days: int = 30, limit: int = 100, offset: int = 0) -> UsageStats:
        """Retrieve usage and cost-savings statistics.

        Args:
            days: Number of trailing days to aggregate (default 30).
            limit: Maximum number of daily breakdown entries (default 100).
            offset: Number of daily entries to skip for pagination (default 0).

        Returns:
            UsageStats with hit rates, costs, and daily breakdown.
        """
        data = self._request("GET", "/v1/usage", params={"days": days, "limit": limit, "offset": offset})
        return UsageStats.from_dict(data)

    def health(self) -> HealthStatus:
        """Check gateway health.

        Returns:
            HealthStatus indicating service availability.
        """
        data = self._request("GET", "/health")
        return HealthStatus.from_dict(data)

    def ingest_directory(self, directory: str | Path, **kwargs: Any) -> list[IngestResult]:
        """Ingest all supported files in a directory.

        Args:
            directory: Local filesystem path to the directory.
            **kwargs: Additional parameters forwarded to the API (e.g. recursive, glob).

        Returns:
            List of IngestResult, one per ingested file.
        """
        dirpath = Path(directory)
        if not dirpath.is_dir():
            raise NotADirectoryError(f"Not a directory: {dirpath}")

        payload: dict[str, Any] = {"path": str(dirpath.resolve()), **kwargs}
        data = self._request("POST", "/v1/ingest/directory", json=payload)
        results = data.get("results", data if isinstance(data, list) else [])
        return [IngestResult.from_dict(r) for r in results]

    def delete_document(self, document_id: str) -> dict[str, Any]:
        """Delete a document by ID.

        Args:
            document_id: The document identifier.

        Returns:
            Confirmation dict from the server.
        """
        return self._request("DELETE", f"/v1/documents/{document_id}")

    def update_document(self, document_id: str, **kwargs: Any) -> dict[str, Any]:
        """Update document metadata.

        Args:
            document_id: The document identifier.
            **kwargs: Fields to update (e.g. title, tags, metadata).

        Returns:
            Updated document dict from the server.
        """
        return self._request("PATCH", f"/v1/documents/{document_id}", json=kwargs)

    def list_documents(self, **kwargs: Any) -> dict[str, Any]:
        """List documents with optional filtering.

        Args:
            **kwargs: Query parameters (e.g. limit, offset, tag, status).

        Returns:
            Dict with documents list and pagination metadata.
        """
        return self._request("GET", "/v1/documents", params=kwargs or None)

    def get_document(self, document_id: str) -> dict[str, Any]:
        """Retrieve a single document by ID.

        Args:
            document_id: The document identifier.

        Returns:
            Document dict from the server.
        """
        return self._request("GET", f"/v1/documents/{document_id}")

    def cache_stats(self) -> dict[str, Any]:
        """Retrieve cache statistics.

        Returns:
            Dict with cache layer stats, hit rates, and memory usage.
        """
        return self._request("GET", "/v1/cache/stats")

    def keys_list(self) -> dict[str, Any]:
        """List all API keys (hashes only, not plaintext).

        Returns:
            Dict with keys list.
        """
        return self._request("GET", "/v1/auth/keys")

    def keys_create(self, name: str, **kwargs: Any) -> dict[str, Any]:
        """Create a new API key.

        Args:
            name: Human-readable name for the key.
            **kwargs: Additional parameters (e.g. scopes, expires_at).

        Returns:
            Dict with the new key (plaintext shown only once).
        """
        payload: dict[str, Any] = {"name": name, **kwargs}
        return self._request("POST", "/v1/auth/keys", json=payload)

    def keys_revoke(self, key_id: str) -> dict[str, Any]:
        """Revoke an API key.

        Args:
            key_id: The key identifier to revoke.

        Returns:
            Confirmation dict from the server.
        """
        return self._request("DELETE", f"/v1/auth/keys/{key_id}")

    # -- provider proxy clients ---------------------------------------------

    def openai_client(self, *, api_key: str) -> Any:
        """Return an OpenAI client that routes through BitMod's proxy.

        Requires ``pip install bitmod-client[openai]``.

        Args:
            api_key: Your OpenAI API key (forwarded to the upstream provider).

        Returns:
            An ``openai.OpenAI`` instance configured to use BitMod as a proxy.
        """
        try:
            import openai  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError("openai package is required. Install with: pip install bitmod-client[openai]")

        return openai.OpenAI(
            api_key=api_key,
            base_url=f"{self._base_url}/v1/proxy/openai",
            default_headers={
                "X-Bitmod-Key": self._api_key,
            },
        )

    def anthropic_client(self, *, api_key: str) -> Any:
        """Return an Anthropic client that routes through BitMod's proxy.

        Requires ``pip install bitmod-client[anthropic]``.

        Args:
            api_key: Your Anthropic API key (forwarded to the upstream provider).

        Returns:
            An ``anthropic.Anthropic`` instance configured to use BitMod as a proxy.
        """
        try:
            import anthropic  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError("anthropic package is required. Install with: pip install bitmod-client[anthropic]")

        return anthropic.Anthropic(
            api_key=api_key,
            base_url=f"{self._base_url}/v1/proxy/anthropic",
            default_headers={
                "X-Bitmod-Key": self._api_key,
            },
        )


# ---------------------------------------------------------------------------
# Async client
# ---------------------------------------------------------------------------


class AsyncBitmodClient:
    """Async version of the BitMod Python SDK.

    Usage::

        import asyncio
        from bitmod_client import AsyncBitmodClient

        async def main():
            async with AsyncBitmodClient(api_key="bm_...") as bm:
                result = await bm.lookup("What is HIPAA?")
                if result.hit:
                    print(result.answer)

        asyncio.run(main())
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = 2,
    ) -> None:
        self._base_url = _resolve_base_url(base_url)
        self._api_key = _resolve_api_key(api_key)
        self._timeout = timeout
        self._max_retries = max_retries
        self._transport = httpx.AsyncHTTPTransport(retries=max_retries)
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=_default_headers(self._api_key),
            timeout=httpx.Timeout(timeout),
            transport=self._transport,
        )

    # -- lifecycle ----------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying async HTTP connection pool."""
        await self._client.aclose()

    async def __aenter__(self) -> AsyncBitmodClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    # -- private helpers ----------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type
        try:
            resp = await self._client.request(
                method,
                path,
                json=json,
                params=params,
                files=files,
                headers=headers,
            )
        except httpx.ConnectError as exc:
            raise BitmodConnectionError(f"Cannot connect to BitMod at {self._base_url}: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise BitmodTimeoutError(f"Request to BitMod timed out after {self._timeout}s: {exc}") from exc

        _raise_for_status(resp)
        return resp.json()

    # -- public API ---------------------------------------------------------

    async def lookup(self, query: str, *, confidence: float = 0.8) -> LookupResult:
        """Cache-only lookup. No LLM call is made."""
        data = await self._request(
            "POST",
            "/v1/lookup",
            json={"query": query, "confidence": confidence},
        )
        return LookupResult.from_dict(data)

    async def ask(
        self,
        query: str,
        *,
        model: str | None = None,
        llm_key: str | None = None,
        temperature: float = 0.0,
        system_prompt: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AskResult:
        """Full query: checks cache first, falls back to LLM if needed."""
        payload: dict[str, Any] = {"query": query, "temperature": temperature}
        if model:
            payload["model"] = model
        if llm_key:
            payload["llm_key"] = llm_key
        if system_prompt:
            payload["system_prompt"] = system_prompt
        if metadata:
            payload["metadata"] = metadata

        data = await self._request("POST", "/v1/ask", json=payload)
        return AskResult.from_dict(data)

    async def search(self, query: str, *, limit: int = 10, offset: int = 0) -> list[SearchResult]:
        """Hybrid semantic + keyword search across ingested content."""
        data = await self._request(
            "POST",
            "/v1/search",
            json={"query": query, "limit": limit, "offset": offset},
        )
        results = data.get("results", data if isinstance(data, list) else [])
        return [SearchResult.from_dict(r) for r in results]

    async def ingest_text(
        self,
        text: str,
        *,
        title: str | None = None,
        tags: Sequence[str] | None = None,
    ) -> IngestResult:
        """Ingest raw text into the BitMod knowledge store."""
        payload: dict[str, Any] = {"text": text}
        if title:
            payload["title"] = title
        if tags:
            payload["tags"] = list(tags)

        data = await self._request("POST", "/v1/ingest/text", json=payload)
        return IngestResult.from_dict(data)

    async def ingest_file(self, path: str | Path) -> IngestResult:
        """Upload and ingest a file into the BitMod knowledge store."""
        filepath = Path(path)
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        content = filepath.read_bytes()
        data = await self._request(
            "POST",
            "/v1/ingest/file",
            files={"file": (filepath.name, content)},
        )
        return IngestResult.from_dict(data)

    async def usage(self, *, days: int = 30, limit: int = 100, offset: int = 0) -> UsageStats:
        """Retrieve usage and cost-savings statistics."""
        data = await self._request("GET", "/v1/usage", params={"days": days, "limit": limit, "offset": offset})
        return UsageStats.from_dict(data)

    async def health(self) -> HealthStatus:
        """Check gateway health."""
        data = await self._request("GET", "/health")
        return HealthStatus.from_dict(data)

    async def ingest_directory(self, directory: str | Path, **kwargs: Any) -> list[IngestResult]:
        """Ingest all supported files in a directory."""
        dirpath = Path(directory)
        if not dirpath.is_dir():
            raise NotADirectoryError(f"Not a directory: {dirpath}")

        payload: dict[str, Any] = {"path": str(dirpath.resolve()), **kwargs}
        data = await self._request("POST", "/v1/ingest/directory", json=payload)
        results = data.get("results", data if isinstance(data, list) else [])
        return [IngestResult.from_dict(r) for r in results]

    async def delete_document(self, document_id: str) -> dict[str, Any]:
        """Delete a document by ID."""
        return await self._request("DELETE", f"/v1/documents/{document_id}")

    async def update_document(self, document_id: str, **kwargs: Any) -> dict[str, Any]:
        """Update document metadata."""
        return await self._request("PATCH", f"/v1/documents/{document_id}", json=kwargs)

    async def list_documents(self, **kwargs: Any) -> dict[str, Any]:
        """List documents with optional filtering."""
        return await self._request("GET", "/v1/documents", params=kwargs or None)

    async def get_document(self, document_id: str) -> dict[str, Any]:
        """Retrieve a single document by ID."""
        return await self._request("GET", f"/v1/documents/{document_id}")

    async def cache_stats(self) -> dict[str, Any]:
        """Retrieve cache statistics."""
        return await self._request("GET", "/v1/cache/stats")

    async def keys_list(self) -> dict[str, Any]:
        """List all API keys (hashes only, not plaintext)."""
        return await self._request("GET", "/v1/auth/keys")

    async def keys_create(self, name: str, **kwargs: Any) -> dict[str, Any]:
        """Create a new API key."""
        payload: dict[str, Any] = {"name": name, **kwargs}
        return await self._request("POST", "/v1/auth/keys", json=payload)

    async def keys_revoke(self, key_id: str) -> dict[str, Any]:
        """Revoke an API key."""
        return await self._request("DELETE", f"/v1/auth/keys/{key_id}")

    # -- provider proxy clients ---------------------------------------------

    def openai_client(self, *, api_key: str) -> Any:
        """Return an async OpenAI client routed through BitMod's proxy."""
        try:
            import openai  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError("openai package is required. Install with: pip install bitmod-client[openai]")

        return openai.AsyncOpenAI(
            api_key=api_key,
            base_url=f"{self._base_url}/v1/proxy/openai",
            default_headers={
                "X-Bitmod-Key": self._api_key,
            },
        )

    def anthropic_client(self, *, api_key: str) -> Any:
        """Return an async Anthropic client routed through BitMod's proxy."""
        try:
            import anthropic  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError("anthropic package is required. Install with: pip install bitmod-client[anthropic]")

        return anthropic.AsyncAnthropic(
            api_key=api_key,
            base_url=f"{self._base_url}/v1/proxy/anthropic",
            default_headers={
                "X-Bitmod-Key": self._api_key,
            },
        )
