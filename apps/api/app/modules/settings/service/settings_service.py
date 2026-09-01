import logging
from typing import Optional, Any, Dict
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.models.infrastructure_models import Setting
from app.infrastructure.cache.query_cache import AsyncQueryCacheService, CacheTTL

logger = logging.getLogger(__name__)


class SettingsService:
    """
    Hierarchical Settings Service.
    Inheritance: global → organization → workspace → user.
    Most-specific scope wins. All settings cached per TTL.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    def _cache_key(self, key: str, scope: str, scope_id: Optional[str]) -> str:
        return f"setting:{key}:{scope}:{scope_id or 'null'}"

    async def get(
        self,
        key: str,
        organization_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[Any]:
        """Get a setting value, cascading from most-specific to global scope."""
        scopes = []
        if user_id:
            scopes.append(("user", user_id))
        if workspace_id:
            scopes.append(("workspace", workspace_id))
        if organization_id:
            scopes.append(("organization", organization_id))
        scopes.append(("global", None))

        for scope, scope_id in scopes:
            cache_key = self._cache_key(key, scope, scope_id)
            cached = AsyncQueryCacheService.get(cache_key)
            if cached is not None:
                return cached.get("value")

            value = await self._fetch(key, scope, scope_id)
            if value is not None:
                AsyncQueryCacheService.set(cache_key, {"value": value}, ttl_seconds=CacheTTL.SETTINGS)
                return value

        return None

    async def _fetch(self, key: str, scope: str, scope_id: Optional[str]) -> Optional[Any]:
        conditions = [Setting.key == key, Setting.scope == scope]
        if scope_id:
            conditions.append(Setting.scope_id == scope_id)
        else:
            conditions.append(Setting.scope_id.is_(None))

        stmt = select(Setting).where(and_(*conditions))
        result = await self.db.execute(stmt)
        setting = result.scalars().first()
        return setting.value if setting else None

    async def set(
        self,
        key: str,
        value: Any,
        scope: str = "organization",
        scope_id: Optional[str] = None,
        value_type: str = "string",
        description: Optional[str] = None,
        updated_by: Optional[str] = None,
        is_sensitive: bool = False,
    ) -> Setting:
        stmt = select(Setting).where(
            Setting.key == key,
            Setting.scope == scope,
            Setting.scope_id == scope_id,
        )
        existing = (await self.db.execute(stmt)).scalars().first()

        if existing:
            existing.value = value
            existing.updated_by = updated_by
            existing.updated_at = datetime.now(timezone.utc)
            setting = existing
        else:
            setting = Setting(
                key=key,
                scope=scope,
                scope_id=scope_id,
                value=value,
                value_type=value_type,
                description=description,
                is_sensitive=is_sensitive,
                updated_by=updated_by,
            )
            self.db.add(setting)

        await self.db.commit()
        # Invalidate cached setting
        AsyncQueryCacheService.invalidate(self._cache_key(key, scope, scope_id))
        logger.info(f"[SETTINGS] Set '{key}' scope={scope}/{scope_id}")
        return setting

    async def get_all(
        self,
        scope: str,
        scope_id: Optional[str] = None,
        include_sensitive: bool = False,
    ) -> list:
        conditions = [Setting.scope == scope]
        if scope_id:
            conditions.append(Setting.scope_id == scope_id)
        if not include_sensitive:
            conditions.append(Setting.is_sensitive == False)

        stmt = select(Setting).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
