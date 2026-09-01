"""
Token Encryption Service
========================
Provides authenticated symmetric encryption (Fernet / AES-128-CBC + HMAC-SHA256)
for OAuth access tokens, refresh tokens, and sensitive integration credentials.
Tokens are never stored or logged in plaintext.
"""

import base64
import hashlib
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _get_fernet_key() -> bytes:
    """
    Derives a deterministic 32-byte URL-safe base64-encoded key from settings.SECRET_KEY.
    """
    secret = (getattr(settings, "TOKEN_ENCRYPTION_KEY", None) or settings.SECRET_KEY).encode("utf-8")
    digest = hashlib.sha256(secret).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_token(plaintext: Optional[str]) -> Optional[str]:
    """
    Encrypts a plaintext token string into an authenticated ciphertext string.
    Returns None if input is None or empty.
    """
    if not plaintext:
        return None
    key = _get_fernet_key()
    f = Fernet(key)
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: Optional[str]) -> Optional[str]:
    """
    Decrypts an authenticated ciphertext string back into the original plaintext token string.
    Returns None if input is None, empty, or if token has been tampered with.
    """
    if not ciphertext:
        return None
    key = _get_fernet_key()
    f = Fernet(key)
    try:
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return None
    except Exception:
        return None
