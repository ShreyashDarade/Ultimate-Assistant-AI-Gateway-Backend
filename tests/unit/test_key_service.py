"""Tests for BYOK key encryption."""

import pytest

from app.core.security import decrypt_api_key, encrypt_api_key


@pytest.fixture(autouse=True)
def set_master_key(monkeypatch):
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    monkeypatch.setattr("app.core.config.settings.MASTER_ENCRYPTION_KEY", key)


def test_encrypt_decrypt_roundtrip():
    original = "sk-test-key-12345678"
    encrypted = encrypt_api_key(original)
    assert encrypted != original
    decrypted = decrypt_api_key(encrypted)
    assert decrypted == original


def test_different_encryptions():
    key = "sk-test-key-12345678"
    enc1 = encrypt_api_key(key)
    enc2 = encrypt_api_key(key)
    # Fernet uses random IV, so encryptions should differ
    assert enc1 != enc2
    # But both decrypt to same value
    assert decrypt_api_key(enc1) == decrypt_api_key(enc2) == key
