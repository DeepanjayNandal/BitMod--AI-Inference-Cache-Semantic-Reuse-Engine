"""Tests for bitmod.crypto — envelope encryption."""

from __future__ import annotations

import json
import os

import pytest

cryptography = pytest.importorskip("cryptography")


@pytest.fixture(autouse=True)
def _clean_kek_cache(monkeypatch):
    """Clear KEK cache and env vars before each test."""
    from bitmod.crypto import clear_kek_cache

    monkeypatch.delenv("BITMOD_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("BITMOD_ENCRYPTION_KEY_FILE", raising=False)
    clear_kek_cache()
    yield
    clear_kek_cache()


def _test_kek_hex() -> str:
    return os.urandom(32).hex()


# -----------------------------------------------------------------------
# 1. encrypt/decrypt roundtrip
# -----------------------------------------------------------------------


def test_roundtrip(monkeypatch):
    from bitmod.crypto import clear_kek_cache, decrypt, encrypt, load_kek

    monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", _test_kek_hex())
    clear_kek_cache()
    kek = load_kek()
    assert kek is not None

    plaintext = "Hello, Bitmod! Unicode: \u00e9\u00e8\u00ea \U0001f512"
    envelope = encrypt(plaintext, kek)
    result = decrypt(envelope, kek)
    assert result == plaintext


def test_roundtrip_empty_string(monkeypatch):
    from bitmod.crypto import clear_kek_cache, decrypt, encrypt, load_kek

    monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", _test_kek_hex())
    clear_kek_cache()
    kek = load_kek()
    assert kek is not None

    envelope = encrypt("", kek)
    assert decrypt(envelope, kek) == ""


# -----------------------------------------------------------------------
# 2. Envelope format
# -----------------------------------------------------------------------


def test_envelope_format(monkeypatch):
    from bitmod.crypto import clear_kek_cache, encrypt, load_kek

    monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", _test_kek_hex())
    clear_kek_cache()
    kek = load_kek()
    assert kek is not None

    envelope = encrypt("test", kek)
    assert isinstance(envelope, dict)
    assert set(envelope.keys()) == {"ciphertext", "wrapped_dek", "nonce", "dek_nonce", "version"}
    assert envelope["version"] == 1
    # All base64-encoded fields are strings
    for k in ("ciphertext", "wrapped_dek", "nonce", "dek_nonce"):
        assert isinstance(envelope[k], str)


# -----------------------------------------------------------------------
# 3. KEK from env var
# -----------------------------------------------------------------------


def test_load_kek_from_env(monkeypatch):
    from bitmod.crypto import clear_kek_cache, load_kek

    hex_key = _test_kek_hex()
    monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", hex_key)
    clear_kek_cache()
    kek = load_kek()
    assert kek is not None
    assert isinstance(kek, bytes)
    assert len(kek) == 32
    assert kek == bytes.fromhex(hex_key)


# -----------------------------------------------------------------------
# 4. KEK from file
# -----------------------------------------------------------------------


def test_load_kek_from_file(monkeypatch, tmp_path):
    from bitmod.crypto import clear_kek_cache, load_kek

    hex_key = _test_kek_hex()
    key_file = tmp_path / "kek.hex"
    key_file.write_text(hex_key)

    monkeypatch.delenv("BITMOD_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("BITMOD_ENCRYPTION_KEY_FILE", str(key_file))
    clear_kek_cache()
    kek = load_kek()
    assert kek is not None
    assert kek == bytes.fromhex(hex_key)


def test_load_kek_file_missing(monkeypatch, tmp_path):
    from bitmod.crypto import clear_kek_cache, load_kek

    monkeypatch.delenv("BITMOD_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("BITMOD_ENCRYPTION_KEY_FILE", str(tmp_path / "nonexistent.hex"))
    clear_kek_cache()
    assert load_kek() is None


# -----------------------------------------------------------------------
# 5. Missing KEK graceful degradation
# -----------------------------------------------------------------------


def test_missing_kek_returns_none(monkeypatch):
    from bitmod.crypto import clear_kek_cache, load_kek

    monkeypatch.delenv("BITMOD_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("BITMOD_ENCRYPTION_KEY_FILE", raising=False)
    clear_kek_cache()
    assert load_kek() is None


def test_encrypt_if_enabled_no_kek(monkeypatch):
    from bitmod.crypto import clear_kek_cache, encrypt_if_enabled

    monkeypatch.delenv("BITMOD_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("BITMOD_ENCRYPTION_KEY_FILE", raising=False)
    clear_kek_cache()
    assert encrypt_if_enabled("plaintext data") == "plaintext data"


# -----------------------------------------------------------------------
# 6. Invalid hex handling
# -----------------------------------------------------------------------


def test_invalid_hex_returns_none(monkeypatch):
    from bitmod.crypto import clear_kek_cache, load_kek

    monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", "not-valid-hex-zzzz")
    clear_kek_cache()
    assert load_kek() is None


def test_wrong_length_hex_returns_none(monkeypatch):
    from bitmod.crypto import clear_kek_cache, load_kek

    monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", "aabb")  # 2 bytes, not 32
    clear_kek_cache()
    assert load_kek() is None


def test_invalid_hex_in_file(monkeypatch, tmp_path):
    from bitmod.crypto import clear_kek_cache, load_kek

    key_file = tmp_path / "bad.hex"
    key_file.write_text("not-hex-at-all")
    monkeypatch.delenv("BITMOD_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("BITMOD_ENCRYPTION_KEY_FILE", str(key_file))
    clear_kek_cache()
    assert load_kek() is None


# -----------------------------------------------------------------------
# 7. is_encrypted detection
# -----------------------------------------------------------------------


def test_is_encrypted_on_envelope(monkeypatch):
    from bitmod.crypto import clear_kek_cache, encrypt, is_encrypted, load_kek

    monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", _test_kek_hex())
    clear_kek_cache()
    kek = load_kek()
    envelope_json = json.dumps(encrypt("secret", kek))
    assert is_encrypted(envelope_json) is True


def test_is_encrypted_on_plaintext():
    from bitmod.crypto import is_encrypted

    assert is_encrypted("just a normal string") is False
    assert is_encrypted("") is False
    assert is_encrypted('{"key": "value"}') is False


# -----------------------------------------------------------------------
# 8. encrypt_if_enabled / decrypt_if_needed
# -----------------------------------------------------------------------


def test_encrypt_if_enabled_with_kek(monkeypatch):
    from bitmod.crypto import clear_kek_cache, decrypt_if_needed, encrypt_if_enabled

    monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", _test_kek_hex())
    clear_kek_cache()

    encrypted = encrypt_if_enabled("my secret data")
    assert encrypted != "my secret data"
    assert encrypted.startswith('{"ciphertext":')

    decrypted = decrypt_if_needed(encrypted)
    assert decrypted == "my secret data"


def test_decrypt_if_needed_plaintext(monkeypatch):
    from bitmod.crypto import clear_kek_cache, decrypt_if_needed

    monkeypatch.delenv("BITMOD_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("BITMOD_ENCRYPTION_KEY_FILE", raising=False)
    clear_kek_cache()
    assert decrypt_if_needed("not encrypted") == "not encrypted"


def test_decrypt_if_needed_no_kek_returns_raw(monkeypatch):
    """Encrypted data with no KEK configured returns raw envelope."""
    from bitmod.crypto import clear_kek_cache, encrypt, encrypt_if_enabled, load_kek

    hex_key = _test_kek_hex()
    monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", hex_key)
    clear_kek_cache()
    kek = load_kek()
    encrypted = json.dumps(encrypt("secret", kek))

    # Now remove the KEK
    monkeypatch.delenv("BITMOD_ENCRYPTION_KEY", raising=False)
    clear_kek_cache()

    from bitmod.crypto import decrypt_if_needed

    result = decrypt_if_needed(encrypted)
    assert result == encrypted  # returns raw envelope since no KEK


# -----------------------------------------------------------------------
# 9. Different plaintexts produce different ciphertexts (random DEK)
# -----------------------------------------------------------------------


def test_different_plaintexts_different_ciphertexts(monkeypatch):
    from bitmod.crypto import clear_kek_cache, encrypt, load_kek

    monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", _test_kek_hex())
    clear_kek_cache()
    kek = load_kek()

    env1 = encrypt("plaintext A", kek)
    env2 = encrypt("plaintext B", kek)
    assert env1["ciphertext"] != env2["ciphertext"]


def test_same_plaintext_different_ciphertexts(monkeypatch):
    """Same plaintext encrypted twice should produce different ciphertexts due to random DEK."""
    from bitmod.crypto import clear_kek_cache, encrypt, load_kek

    monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", _test_kek_hex())
    clear_kek_cache()
    kek = load_kek()

    env1 = encrypt("same data", kek)
    env2 = encrypt("same data", kek)
    assert env1["ciphertext"] != env2["ciphertext"]
    assert env1["wrapped_dek"] != env2["wrapped_dek"]


# -----------------------------------------------------------------------
# 10. Tampering detection
# -----------------------------------------------------------------------


def test_tampered_ciphertext_fails(monkeypatch):
    import base64

    from bitmod.crypto import clear_kek_cache, decrypt, encrypt, load_kek

    monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", _test_kek_hex())
    clear_kek_cache()
    kek = load_kek()

    envelope = encrypt("sensitive data", kek)

    # Tamper with ciphertext
    ct_bytes = bytearray(base64.b64decode(envelope["ciphertext"]))
    ct_bytes[0] ^= 0xFF  # flip bits
    envelope["ciphertext"] = base64.b64encode(bytes(ct_bytes)).decode()

    with pytest.raises(Exception):
        decrypt(envelope, kek)


def test_tampered_wrapped_dek_fails(monkeypatch):
    import base64

    from bitmod.crypto import clear_kek_cache, decrypt, encrypt, load_kek

    monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", _test_kek_hex())
    clear_kek_cache()
    kek = load_kek()

    envelope = encrypt("sensitive data", kek)

    # Tamper with wrapped DEK
    dek_bytes = bytearray(base64.b64decode(envelope["wrapped_dek"]))
    dek_bytes[-1] ^= 0xFF
    envelope["wrapped_dek"] = base64.b64encode(bytes(dek_bytes)).decode()

    with pytest.raises(Exception):
        decrypt(envelope, kek)


def test_wrong_kek_fails(monkeypatch):
    from bitmod.crypto import clear_kek_cache, decrypt, encrypt, load_kek

    monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", _test_kek_hex())
    clear_kek_cache()
    kek = load_kek()
    envelope = encrypt("data", kek)

    wrong_kek = os.urandom(32)
    with pytest.raises(Exception):
        decrypt(envelope, wrong_kek)


def test_decrypt_if_needed_tampered_returns_raw(monkeypatch):
    """Tampered envelope via decrypt_if_needed returns raw text (graceful)."""
    import base64

    from bitmod.crypto import clear_kek_cache, decrypt_if_needed, encrypt, load_kek

    hex_key = _test_kek_hex()
    monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", hex_key)
    clear_kek_cache()
    kek = load_kek()

    envelope = encrypt("secret", kek)
    # Tamper
    ct_bytes = bytearray(base64.b64decode(envelope["ciphertext"]))
    ct_bytes[0] ^= 0xFF
    envelope["ciphertext"] = base64.b64encode(bytes(ct_bytes)).decode()
    tampered_json = json.dumps(envelope)

    result = decrypt_if_needed(tampered_json)
    assert result == tampered_json  # graceful degradation


# -----------------------------------------------------------------------
# KEK caching
# -----------------------------------------------------------------------


def test_kek_caching(monkeypatch):
    from bitmod.crypto import clear_kek_cache, load_kek

    monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", _test_kek_hex())
    clear_kek_cache()

    kek1 = load_kek()
    kek2 = load_kek()
    assert kek1 is kek2  # same object reference — cached


def test_clear_kek_cache(monkeypatch):
    from bitmod.crypto import clear_kek_cache, load_kek

    hex1 = _test_kek_hex()
    monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", hex1)
    clear_kek_cache()
    kek1 = load_kek()

    hex2 = _test_kek_hex()
    monkeypatch.setenv("BITMOD_ENCRYPTION_KEY", hex2)
    clear_kek_cache()
    kek2 = load_kek()

    assert kek1 != kek2  # different after cache clear
