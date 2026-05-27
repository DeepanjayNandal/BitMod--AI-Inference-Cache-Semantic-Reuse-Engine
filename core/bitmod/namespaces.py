"""Multi-tenant namespace isolation for Bitmod.

Provides namespace-scoped cache isolation for enterprise deployments.
Each namespace gets its own cache partition — queries in one namespace
never leak into another unless public_fallback is enabled (in which case,
on a namespace cache miss, the system falls through to the global/public cache).

Namespace lifecycle:
1. Create namespace via API (POST /v1/namespaces)
2. Pass X-Bitmod-Namespace header on all requests to scope cache operations
3. Cache hits/misses are isolated per namespace
4. Delete namespace to remove isolation (cached data remains until TTL)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from bitmod.interfaces.database import DatabaseBackend

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Namespace:
    """A tenant namespace for cache isolation."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    owner_key_id: str = ""  # API key that created it
    isolation: str = "strict"  # strict = no cross-namespace leaks
    public_fallback: bool = False  # on miss, fall through to public cache
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "owner_key_id": self.owner_key_id,
            "isolation": self.isolation,
            "public_fallback": self.public_fallback,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Namespace Manager
# ---------------------------------------------------------------------------


class NamespaceManager:
    """CRUD operations for multi-tenant namespaces.

    All operations go through the DatabaseBackend interface. The backend
    must have the namespaces table created (see SQLiteBackend.initialize).
    """

    def __init__(self, backend: DatabaseBackend):
        self._backend = backend

    def create(
        self,
        name: str,
        owner_key_id: str,
        isolation: str = "strict",
        public_fallback: bool = False,
        authenticated_key_id: str | None = None,
    ) -> Namespace:
        """Create a new namespace.

        Args:
            name: Human-readable namespace name (must be unique).
            owner_key_id: ID of the API key creating this namespace.
            isolation: Isolation mode. "strict" = no cross-namespace leaks.
            public_fallback: If True, cache misses fall through to public cache.
            authenticated_key_id: The key ID from the authenticated session.
                When provided, must match owner_key_id to prevent a user from
                creating namespaces owned by a different key.

        Returns:
            The created Namespace.

        Raises:
            ValueError: If name is empty or isolation mode is invalid.
            PermissionError: If authenticated_key_id does not match owner_key_id.
            Exception: If namespace name already exists (unique constraint).
        """
        if not name or not name.strip():
            raise ValueError("Namespace name cannot be empty")

        if isolation not in ("strict", "shared"):
            raise ValueError(f"Invalid isolation mode: {isolation}. Must be 'strict' or 'shared'.")

        if not owner_key_id:
            raise ValueError("owner_key_id is required")

        if authenticated_key_id is not None and authenticated_key_id != owner_key_id:
            logger.warning(
                "Namespace creation denied: authenticated_key=%s tried to set owner=%s",
                authenticated_key_id,
                owner_key_id,
            )
            raise PermissionError("Cannot create namespace with a different owner's key")

        ns = Namespace(
            id=str(uuid.uuid4()),
            name=name.strip(),
            owner_key_id=owner_key_id,
            isolation=isolation,
            public_fallback=public_fallback,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        with self._backend.session() as session:
            self._backend.namespace_create(session, ns)

        logger.info("Namespace created: id=%s name=%s owner=%s", ns.id, ns.name, ns.owner_key_id)
        return ns

    def get(self, namespace_id: str) -> Namespace | None:
        """Get a namespace by ID. Returns None if not found."""
        with self._backend.session() as session:
            return self._backend.namespace_get(session, namespace_id)  # type: ignore[no-any-return]

    def get_by_name(self, name: str) -> Namespace | None:
        """Get a namespace by name. Returns None if not found."""
        with self._backend.session() as session:
            return self._backend.namespace_get_by_name(session, name)  # type: ignore[no-any-return]

    def list_for_owner(self, owner_key_id: str) -> list[Namespace]:
        """List all namespaces owned by a specific API key."""
        with self._backend.session() as session:
            return self._backend.namespace_list_for_owner(session, owner_key_id)

    def list_all(self) -> list[Namespace]:
        """List all namespaces (admin use)."""
        with self._backend.session() as session:
            return self._backend.namespace_list_all(session)

    def delete(self, namespace_id: str, owner_key_id: str) -> bool:
        """Delete a namespace. Only the owner can delete.

        Args:
            namespace_id: ID of the namespace to delete.
            owner_key_id: Must match the namespace's owner_key_id.

        Returns:
            True if deleted, False if not found or not authorized.
        """
        ns = self.get(namespace_id)
        if ns is None:
            return False
        if ns.owner_key_id != owner_key_id:
            logger.warning(
                "Namespace delete denied: ns=%s owner=%s requester=%s",
                namespace_id,
                ns.owner_key_id,
                owner_key_id,
            )
            return False

        with self._backend.session() as session:
            self._backend.namespace_delete(session, namespace_id)

        logger.info("Namespace deleted: id=%s name=%s", namespace_id, ns.name)
        return True

    def is_accessible(self, namespace_id: str, key_id: str) -> bool:
        """Check if a given key_id has access to a namespace.

        Returns True if the key_id is the owner of the namespace or if
        the namespace has public_fallback enabled. Returns False otherwise
        (including when the namespace does not exist).
        """
        ns = self.get(namespace_id)
        if ns is None:
            return False
        if ns.owner_key_id == key_id:
            return True
        return ns.public_fallback

    def get_cache_stats(self, namespace_id: str) -> dict:
        """Get cache statistics scoped to a specific namespace."""
        with self._backend.session() as session:
            return self._backend.namespace_cache_stats(session, namespace_id)


# ---------------------------------------------------------------------------
# Utility: resolve namespace from request context
# ---------------------------------------------------------------------------


def resolve_namespace_id(
    header_value: str | None,
    backend: DatabaseBackend,
) -> str | None:
    """Resolve an X-Bitmod-Namespace header value to a namespace ID.

    The header can contain either a namespace ID (UUID) or a namespace name.
    Returns None if no header or namespace not found.
    """
    if not header_value or not header_value.strip():
        return None

    value = header_value.strip()

    # Try as UUID first (direct ID)
    mgr = NamespaceManager(backend)
    ns = mgr.get(value)
    if ns:
        return ns.id

    # Try as name
    ns = mgr.get_by_name(value)
    if ns:
        return ns.id

    logger.warning("Namespace not found: %s", value)
    return None


def get_namespace_fallback(namespace_id: str, backend: DatabaseBackend) -> bool:
    """Check if a namespace allows public fallback on cache miss."""
    mgr = NamespaceManager(backend)
    ns = mgr.get(namespace_id)
    if ns is None:
        return False
    return ns.public_fallback
