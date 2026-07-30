import secrets
import hashlib
from typing import Tuple

class APIKeyService:
    """
    Enterprise API Key Management Platform for Developer Integrations.
    Generates secure 'bl_live_...' API keys and stores SHA-256 hashes in database.
    """
    KEY_PREFIX = "bl_live_"

    @classmethod
    def generate_api_key(cls) -> Tuple[str, str]:
        """
        Generates a new API key tuple: (raw_key, hashed_key).
        Only raw_key is returned ONCE to the user upon creation.
        """
        random_bytes = secrets.token_hex(24)
        raw_key = f"{cls.KEY_PREFIX}{random_bytes}"
        hashed_key = cls.hash_api_key(raw_key)
        return raw_key, hashed_key

    @classmethod
    def hash_api_key(cls, raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    @classmethod
    def verify_api_key(cls, raw_key: str, stored_hash: str) -> bool:
        if not raw_key or not raw_key.startswith(cls.KEY_PREFIX):
            return False
        calculated_hash = cls.hash_api_key(raw_key)
        return secrets.compare_digest(calculated_hash, stored_hash)
