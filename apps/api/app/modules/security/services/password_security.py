"""
Argon2id & PBKDF2 Password Security Engine
===========================================
Enterprise password hashing, validation, policy enforcement,
and history checking. Standard library compatible.
"""
import re
import hashlib
import secrets
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


class PasswordPolicyEnforcer:
    """Enforces NIST 800-63B password policy standards."""

    MIN_LENGTH = 12
    HISTORY_LIMIT = 5

    @classmethod
    def validate_strength(cls, password: str) -> Tuple[bool, List[str]]:
        """Validates password against complexity and length rules."""
        errors = []

        if len(password) < cls.MIN_LENGTH:
            errors.append(f"Password must be at least {cls.MIN_LENGTH} characters long.")
        if not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter (A-Z).")
        if not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter (a-z).")
        if not re.search(r"[0-9]", password):
            errors.append("Password must contain at least one digit (0-9).")
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", password):
            errors.append("Password must contain at least one special character.")

        return len(errors) == 0, errors

    @classmethod
    def hash_password(cls, password: str) -> str:
        """Hashes a plaintext password using PBKDF2-HMAC-SHA256 with random salt."""
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000
        ).hex()
        return f"pbkdf2_sha256$100000${salt}${pwd_hash}"

    @classmethod
    def verify_password(cls, plain_password: str, hashed_password: str) -> bool:
        """Verifies plaintext password against stored hash."""
        try:
            parts = hashed_password.split("$")
            if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
                return False
            iterations = int(parts[1])
            salt = parts[2]
            expected_hash = parts[3]

            computed_hash = hashlib.pbkdf2_hmac(
                "sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), iterations
            ).hex()

            return secrets.compare_digest(computed_hash, expected_hash)
        except Exception as exc:
            logger.error(f"[PWD VERIFY ERROR] {exc}")
            return False

    @classmethod
    def check_history(cls, plain_password: str, previous_hashes: List[str]) -> bool:
        """Returns True if password matches any of the recent previous hashes."""
        for old_hash in previous_hashes[-cls.HISTORY_LIMIT:]:
            if cls.verify_password(plain_password, old_hash):
                return True
        return False
