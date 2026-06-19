"""Tests for encryption-at-rest integration with the cache engine."""

from __future__ import annotations

import json
import os

import pytest

cryptography = pytest.importorskip("cryptography")

from bitmod.adapters.db_sqlite import SQLiteBackend
from bitmod.cache_engine import compute_answer_key, store_answer, try_cache
from bitmod.crypto import clear_kek_cache


def _random_kek_hex() -> str:
    return os.urandom(32).hex()


@pytest.fixture(autouse=True)
def _clean_crypto(monkeypatch):
    """Reset encryption state before and after each test."""
    monkeypatch.delenv("BITMOD_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("BITMOD_ENCRYPTION_KEY_FILE", raising=False)
    clear_kek_cache()
    yield
    clear_kek_cache()


@pytest.fixture
def crypto_backend(tmp_path):
    b = SQLiteBackend(path=str(tmp_path / "crypto_test.db"))
    b.initialize()
    return b


# ---------------------------------------------------------------------------
# Encrypted storage
# ---------------------------------------------------------------------------


class TestEncryptedCacheStorage:
    def test_encrypted_answer_not_plaintext_in_db(self, crypto_backend, monkeypatch):
        """When encryption is enabled, the raw DB value must not be plaintext."""
        kek_hex = _random_kek_hex()
        monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", kek_hex)
        clear_kek_cache()

        plaintext = "Employment law governs employer-employee relationships."
        key = compute_answer_key("employment law")

        with crypto_backend.session() as session:
            store_answer(
                backend=crypto_backend,
                session=session,
                answer_key=key,
                question_raw="employment law",
                question_normalized="employment law",
                filters={},
                answer_text=plaintext,
                source_sections=[],
                model_used="test",
                generation_ms=100,
            )

        # Read the raw DB value — it should be an encrypted envelope, not plaintext
        with crypto_backend.session() as session:
            row = session.execute(
                "SELECT answer_text FROM answer_cache WHERE answer_key = ?",
                (key,),
            ).fetchone()
            raw = row["answer_text"]
            assert raw != plaintext
            envelope = json.loads(raw)
            assert "ciphertext" in envelope
            assert "wrapped_dek" in envelope

    def test_encrypted_answer_decrypted_on_retrieval(self, crypto_backend, monkeypatch):
        """try_cache returns decrypted plaintext when encryption is enabled."""
        kek_hex = _random_kek_hex()
        monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", kek_hex)
        clear_kek_cache()

        plaintext = "This is the secret answer."

        with crypto_backend.session() as session:
            store_answer(
                backend=crypto_backend,
                session=session,
                answer_key=compute_answer_key("secret"),
                question_raw="secret",
                question_normalized="secret",
                filters={},
                answer_text=plaintext,
                source_sections=[],
                model_used="test",
                generation_ms=50,
            )

        with crypto_backend.session() as session:
            hit = try_cache(crypto_backend, session, "secret")
            assert hit is not None
            assert hit.answer_text == plaintext


# ---------------------------------------------------------------------------
# Unencrypted storage
# ---------------------------------------------------------------------------


class TestUnencryptedCacheStorage:
    def test_plaintext_stored_when_encryption_disabled(self, crypto_backend):
        """Without a KEK, answer_text is stored as plaintext."""
        plaintext = "Visible answer."
        key = compute_answer_key("visible")

        with crypto_backend.session() as session:
            store_answer(
                backend=crypto_backend,
                session=session,
                answer_key=key,
                question_raw="visible",
                question_normalized="visible",
                filters={},
                answer_text=plaintext,
                source_sections=[],
                model_used="test",
                generation_ms=10,
            )

        with crypto_backend.session() as session:
            row = session.execute(
                "SELECT answer_text FROM answer_cache WHERE answer_key = ?",
                (key,),
            ).fetchone()
            assert row["answer_text"] == plaintext


# ---------------------------------------------------------------------------
# Mixed-mode: store encrypted, retrieve after disabling encryption
# ---------------------------------------------------------------------------


class TestMixedMode:
    def test_store_encrypted_retrieve_without_key_returns_envelope(self, crypto_backend, monkeypatch):
        """If encryption is disabled after storing, retrieval returns raw envelope gracefully."""
        kek_hex = _random_kek_hex()
        monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", kek_hex)
        clear_kek_cache()

        plaintext = "Encrypted then orphaned."

        with crypto_backend.session() as session:
            store_answer(
                backend=crypto_backend,
                session=session,
                answer_key=compute_answer_key("orphan"),
                question_raw="orphan",
                question_normalized="orphan",
                filters={},
                answer_text=plaintext,
                source_sections=[],
                model_used="test",
                generation_ms=10,
            )

        # Disable encryption
        monkeypatch.delenv("BITMOD_ENCRYPTION_KEY", raising=False)
        clear_kek_cache()

        with crypto_backend.session() as session:
            hit = try_cache(crypto_backend, session, "orphan")
            assert hit is not None
            # Without the KEK, decrypt_if_needed returns the raw envelope string
            assert hit.answer_text != plaintext
            assert '"ciphertext"' in hit.answer_text


# ---------------------------------------------------------------------------
# Full roundtrip: store -> lookup -> verify original text
# ---------------------------------------------------------------------------


class TestCacheRoundtrip:
    def test_full_roundtrip_encrypted(self, crypto_backend, monkeypatch):
        kek_hex = _random_kek_hex()
        monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", kek_hex)
        clear_kek_cache()

        original = "The quick brown fox jumps over the lazy dog."

        with crypto_backend.session() as session:
            stored = store_answer(
                backend=crypto_backend,
                session=session,
                answer_key=compute_answer_key("fox"),
                question_raw="fox",
                question_normalized="fox",
                filters={},
                answer_text=original,
                source_sections=[],
                model_used="test",
                generation_ms=10,
            )
            assert stored.id  # record created

        with crypto_backend.session() as session:
            hit = try_cache(crypto_backend, session, "fox")
            assert hit is not None
            assert hit.answer_text == original

    def test_full_roundtrip_unencrypted(self, crypto_backend):
        original = "Plaintext roundtrip value."

        with crypto_backend.session() as session:
            store_answer(
                backend=crypto_backend,
                session=session,
                answer_key=compute_answer_key("plain"),
                question_raw="plain",
                question_normalized="plain",
                filters={},
                answer_text=original,
                source_sections=[],
                model_used="test",
                generation_ms=10,
            )

        with crypto_backend.session() as session:
            hit = try_cache(crypto_backend, session, "plain")
            assert hit is not None
            assert hit.answer_text == original

    def test_unicode_content_encrypted_roundtrip(self, crypto_backend, monkeypatch):
        kek_hex = _random_kek_hex()
        monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", kek_hex)
        clear_kek_cache()

        original = "Schrodinger's cat: \u00e4\u00f6\u00fc\u00df \u2014 \u2603 snowman \u2764 heart"

        with crypto_backend.session() as session:
            store_answer(
                backend=crypto_backend,
                session=session,
                answer_key=compute_answer_key("unicode"),
                question_raw="unicode",
                question_normalized="unicode",
                filters={},
                answer_text=original,
                source_sections=[],
                model_used="test",
                generation_ms=10,
            )

        with crypto_backend.session() as session:
            hit = try_cache(crypto_backend, session, "unicode")
            assert hit is not None
            assert hit.answer_text == original
