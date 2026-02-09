"""Bitmod Encryption at Rest — envelope encryption.

Uses AES-256-GCM with envelope encryption: a random Data Encryption Key (DEK)
encrypts each payload, then the DEK itself is wrapped (encrypted) with a
Key Encryption Key (KEK) loaded from the environment.

KEK sourcing (first match wins):
  1. BITMOD_ENCRYPTION_KEY env var — 64-char hex string (32 bytes)
  2. BITMOD_ENCRYPTION_KEY_FILE env var — path to a file containing the hex key

When neither is set, encryption is disabled and all functions gracefully degrade.
"""

from __future__ import annotations

import base64
import json
import logging
import os

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False

logger = logging.getLogger(__name__)

_ENVELOPE_MARKER = '{"ciphertext":'
_kek_cache: bytes | None = None
_kek_cache_set: bool = False  # distinguish "cached None" from "never loaded"
_KEY_BYTES = 32  # AES-256
_NONCE_BYTES = 12  # GCM standard


def generate_dek() -> bytes:
    """Generate a 32-byte random data encryption key."""
    return os.urandom(_KEY_BYTES)


def _wrap_dek(dek: bytes, kek: bytes) -> tuple[bytes, bytes]:
    """Encrypt the DEK with the KEK using AES-256-GCM. Returns (wrapped_dek, nonce)."""
    nonce = os.urandom(_NONCE_BYTES)
    aesgcm = AESGCM(kek)
    wrapped = aesgcm.encrypt(nonce, dek, None)
    return wrapped, nonce


def _unwrap_dek(wrapped_dek: bytes, kek: bytes, nonce: bytes) -> bytes:
    """Decrypt the DEK with the KEK using AES-256-GCM."""
    aesgcm = AESGCM(kek)
    result: bytes = aesgcm.decrypt(nonce, wrapped_dek, None)
    return result


def encrypt(plaintext: str, kek: bytes) -> dict:
    """Encrypt plaintext using envelope encryption.

    A fresh DEK encrypts the data, then the DEK is wrapped with the KEK.

    Returns:
        {"ciphertext": base64, "wrapped_dek": base64, "nonce": base64,
         "dek_nonce": base64, "version": 1}
    """
    dek = generate_dek()

    # Encrypt plaintext with DEK
    data_nonce = os.urandom(_NONCE_BYTES)
    data_aesgcm = AESGCM(dek)
    ciphertext = data_aesgcm.encrypt(data_nonce, plaintext.encode("utf-8"), None)

    # Wrap DEK with KEK
    wrapped_dek, dek_nonce = _wrap_dek(dek, kek)

    return {
        "ciphertext": base64.b64encode(ciphertext).decode(),
        "wrapped_dek": base64.b64encode(wrapped_dek).decode(),
        "nonce": base64.b64encode(data_nonce).decode(),
        "dek_nonce": base64.b64encode(dek_nonce).decode(),
        "version": 1,
    }


def decrypt(envelope: dict, kek: bytes) -> str:
    """Decrypt an envelope-encrypted payload.

    Unwraps the DEK with the KEK, then decrypts the ciphertext with the DEK.
    """
    wrapped_dek = base64.b64decode(envelope["wrapped_dek"])
    dek_nonce = base64.b64decode(envelope["dek_nonce"])
    ciphertext = base64.b64decode(envelope["ciphertext"])
    data_nonce = base64.b64decode(envelope["nonce"])

    dek = _unwrap_dek(wrapped_dek, kek, dek_nonce)

    data_aesgcm = AESGCM(dek)
    plaintext_bytes: bytes = data_aesgcm.decrypt(data_nonce, ciphertext, None)
    return plaintext_bytes.decode("utf-8")


def clear_kek_cache() -> None:
    """Clear the cached KEK. Useful for testing or key rotation."""
    global _kek_cache, _kek_cache_set  # noqa: PLW0603
    _kek_cache = None
    _kek_cache_set = False


def load_kek() -> bytes | None:
    """Load the Key Encryption Key from environment.

    Checks BITMOD_ENCRYPTION_KEY (hex string) first, then
    BITMOD_ENCRYPTION_KEY_FILE (path to file containing hex string).
    Returns None if neither is configured.

    The result is cached after the first call. Use clear_kek_cache()
    to force a re-read (e.g. after key rotation or in tests).
    """
    global _kek_cache, _kek_cache_set  # noqa: PLW0603
    if _kek_cache_set:
        return _kek_cache

    result = _load_kek_from_env()
    _kek_cache = result
    _kek_cache_set = True
    return result


def _load_kek_from_env() -> bytes | None:
    """Internal: read KEK from environment (uncached)."""
    hex_key = os.environ.get("BITMOD_ENCRYPTION_KEY", "").strip()
    if hex_key:
        try:
            kek = bytes.fromhex(hex_key)
            if len(kek) != _KEY_BYTES:
                logger.error("BITMOD_ENCRYPTION_KEY must be %d hex chars (got %d bytes)", _KEY_BYTES * 2, len(kek))
                return None
            return kek
        except ValueError:
            logger.error("BITMOD_ENCRYPTION_KEY is not valid hex")
            return None

    key_file = os.environ.get("BITMOD_ENCRYPTION_KEY_FILE", "").strip()
    if key_file:
        try:
            with open(key_file) as f:
                hex_key = f.read().strip()
            kek = bytes.fromhex(hex_key)
            if len(kek) != _KEY_BYTES:
                logger.error("BITMOD_ENCRYPTION_KEY_FILE key must be %d hex chars", _KEY_BYTES * 2)
                return None
            return kek
        except FileNotFoundError:
            logger.error("BITMOD_ENCRYPTION_KEY_FILE not found: %s", key_file)
            return None
        except ValueError:
            logger.error("BITMOD_ENCRYPTION_KEY_FILE does not contain valid hex")
            return None

    return None


def is_encryption_enabled() -> bool:
    """Return True if a KEK is available and cryptography library is installed."""
    return _HAS_CRYPTO and load_kek() is not None


def is_encrypted(text: str) -> bool:
    """Return True if a text string looks like an encryption envelope."""
    return text.startswith(_ENVELOPE_MARKER)


def encrypt_if_enabled(plaintext: str) -> str:
    """Encrypt plaintext if encryption is enabled, otherwise return as-is."""
    kek = load_kek()
    if kek is None:
        return plaintext
    return json.dumps(encrypt(plaintext, kek))


def decrypt_if_needed(text: str) -> str:
    """Decrypt text if it looks like an envelope, otherwise return as-is."""
    if not is_encrypted(text):
        return text
    kek = load_kek()
    if kek is None:
        logger.warning("Encrypted data found but no KEK configured — returning raw envelope")
        return text
    try:
        envelope = json.loads(text)
        return decrypt(envelope, kek)
    except Exception:
        logger.warning("Failed to decrypt envelope — returning raw text", exc_info=True)
        return text
