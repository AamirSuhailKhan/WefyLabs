import hashlib
import secrets
import logging
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crm_models import ApiKey

logger = logging.getLogger(__name__)


class ApiKeyService:
    """
    Enterprise API Key Management Service.
    Keys are SHA-256 hashed before storage. Raw key is returned ONCE only on creation.
    Supports scoped permissions, expiration, rotation, and revocation.
    """

    PREFIX = "bl_"

    def __init__(self, db: AsyncSession):
        self.db = db

    def _generate_key(self) -> tuple[str, str, str]:
        """Returns (raw_key, key_hash, key_prefix)."""
        raw = self.PREFIX + secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(raw.encode()).hexdigest()
        prefix = raw[:10]
        return raw, key_hash, prefix

    async def create(
        self,
        organization_id: str,
        broker_id: str,
        name: str,
        scopes: List[str],
        expires_at: Optional[datetime] = None,
    ) -> dict:
        raw_key, key_hash, prefix = self._generate_key()

        api_key = ApiKey(
            organization_id=organization_id,
            broker_id=broker_id,
            name=name,
            key_hash=key_hash,
            key_prefix=prefix,
            scopes=scopes,
            is_active=True,
            expires_at=expires_at,
        )
        self.db.add(api_key)
        await self.db.commit()
        logger.info(f"[API KEY] Created '{name}' for org={organization_id}")

        return {
            "id": str(api_key.id),
            "name": name,
            "key": raw_key,      # Shown ONCE, never stored in plaintext
            "prefix": prefix,
            "scopes": scopes,
            "expires_at": expires_at,
            "created_at": api_key.created_at,
        }

    async def rotate(self, key_id: str, organization_id: str) -> dict:
        """Rotate an API key — invalidates old, returns new raw key."""
        stmt = select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.organization_id == organization_id,
            ApiKey.is_active == True,
        )
        result = await self.db.execute(stmt)
        key = result.scalars().first()
        if not key:
            raise ValueError("API key not found or already revoked.")

        raw_key, key_hash, prefix = self._generate_key()
        key.key_hash = key_hash
        key.key_prefix = prefix
        await self.db.commit()
        logger.info(f"[API KEY] Rotated key ID={key_id}")
        return {"id": key_id, "key": raw_key, "prefix": prefix}

    async def revoke(self, key_id: str, organization_id: str) -> bool:
        stmt = (
            update(ApiKey)
            .where(ApiKey.id == key_id, ApiKey.organization_id == organization_id)
            .values(is_active=False)
        )
        await self.db.execute(stmt)
        await self.db.commit()
        logger.info(f"[API KEY] Revoked key ID={key_id}")
        return True

    async def list_keys(self, organization_id: str) -> list:
        stmt = select(ApiKey).where(ApiKey.organization_id == organization_id).order_by(ApiKey.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def verify(self, raw_key: str) -> Optional[ApiKey]:
        """Verify an incoming API key. Returns the key entity if valid."""
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        stmt = select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
        result = await self.db.execute(stmt)
        key = result.scalars().first()
        if key:
            key.last_used_at = datetime.now(timezone.utc)
            await self.db.commit()
        return key
