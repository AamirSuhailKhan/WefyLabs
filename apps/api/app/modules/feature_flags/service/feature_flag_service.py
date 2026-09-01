import logging
from typing import Optional, Any, Dict
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.infrastructure_models import FeatureFlag
from app.infrastructure.cache.query_cache import AsyncQueryCacheService, CacheTTL

logger = logging.getLogger(__name__)


class FeatureFlagService:
    """
    Enterprise Feature Flag Service.
    Evaluation order: user → workspace → organization → global.
    Cached in Redis/Memory for sub-millisecond lookups.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    def _cache_key(self, key: str, scope: str, scope_id: Optional[str]) -> str:
        return f"ff:{key}:{scope}:{scope_id or 'null'}"

    async def is_enabled(
        self,
        key: str,
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        environment: str = "production",
    ) -> bool:
        """Evaluate a feature flag, checking most-specific scope first."""
        # Check scopes: user → workspace → organization → global
        scopes_to_check = []
        if user_id:
            scopes_to_check.append(("user", user_id))
        if workspace_id:
            scopes_to_check.append(("workspace", workspace_id))
        if organization_id:
            scopes_to_check.append(("organization", organization_id))
        scopes_to_check.append(("global", None))

        for scope, scope_id in scopes_to_check:
            cache_key = self._cache_key(key, scope, scope_id)
            cached = AsyncQueryCacheService.get(cache_key)
            if cached is not None:
                return cached.get("enabled", False)

            result = await self._fetch_flag(key, scope, scope_id, environment)
            if result is not None:
                AsyncQueryCacheService.set(cache_key, {"enabled": result}, ttl_seconds=CacheTTL.FEATURE_FLAGS)
                return result

        return False  # Default: disabled

    async def _fetch_flag(
        self, key: str, scope: str, scope_id: Optional[str], environment: str
    ) -> Optional[bool]:
        conditions = [
            FeatureFlag.key == key,
            FeatureFlag.scope == scope,
            FeatureFlag.environment == environment,
        ]
        if scope_id:
            conditions.append(FeatureFlag.scope_id == scope_id)
        else:
            conditions.append(FeatureFlag.scope_id.is_(None))

        stmt = select(FeatureFlag).where(and_(*conditions))
        result = await self.db.execute(stmt)
        flag = result.scalars().first()
        if flag:
            return flag.is_enabled
        return None

    async def set_flag(
        self,
        key: str,
        is_enabled: bool,
        scope: str = "global",
        scope_id: Optional[str] = None,
        rollout_percentage: float = 100.0,
        description: Optional[str] = None,
        environment: str = "production",
    ) -> FeatureFlag:
        """Create or update a feature flag."""
        stmt = select(FeatureFlag).where(
            FeatureFlag.key == key,
            FeatureFlag.scope == scope,
            FeatureFlag.scope_id == scope_id,
        )
        existing = (await self.db.execute(stmt)).scalars().first()

        if existing:
            existing.is_enabled = is_enabled
            existing.rollout_percentage = rollout_percentage
            flag = existing
        else:
            flag = FeatureFlag(
                key=key,
                scope=scope,
                scope_id=scope_id,
                is_enabled=is_enabled,
                rollout_percentage=rollout_percentage,
                description=description,
                environment=environment,
            )
            self.db.add(flag)

        await self.db.commit()

        # Invalidate cache
        AsyncQueryCacheService.invalidate(self._cache_key(key, scope, scope_id))
        logger.info(f"[FEATURE FLAG] Set '{key}' scope={scope}/{scope_id} enabled={is_enabled}")
        return flag

    async def list_flags(self, environment: str = "production") -> list:
        stmt = select(FeatureFlag).where(FeatureFlag.environment == environment)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
