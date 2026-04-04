"""
Secret-handling utilities for encrypted at-rest configuration values.
"""

from __future__ import annotations

import hashlib

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from config import settings


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _fernet() -> MultiFernet:
    return MultiFernet([Fernet(key.encode("utf-8")) for key in settings.webhook_secret_encryption_keys])


def encrypt_webhook_secret(secret: str) -> str:
    if not secret:
        return ""
    return _fernet().encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_webhook_secret(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Invalid encrypted webhook secret") from exc
