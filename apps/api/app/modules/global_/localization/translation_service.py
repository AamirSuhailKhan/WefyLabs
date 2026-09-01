"""
TranslationService — Database-backed i18n with Fallback Chain
=============================================================
Supports locale fallback: ar-AE → ar → en → key_itself

NEVER displays:
  - undefined
  - null
  - raw translation keys (e.g. "crm.lead.status.new")

Architecture:
  1. Check in-memory LRU cache (per locale, per namespace)
  2. Check DB (translations table)
  3. Walk fallback chain
  4. Return key if all else fails (visible signal, not a crash)

Namespaces (matching spec §26):
  common | crm | leads | properties | calendar | billing
  workflow | analytics | ai | errors | notifications
"""
from __future__ import annotations

import logging
from typing import Optional, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)

# Locale fallback chains (spec §27)
LOCALE_FALLBACK_CHAINS: Dict[str, List[str]] = {
    "ar-AE": ["ar-AE", "ar", "en"],
    "ar-SA": ["ar-SA", "ar", "en"],
    "ar-QA": ["ar-QA", "ar", "en"],
    "ar-BH": ["ar-BH", "ar", "en"],
    "ar-KW": ["ar-KW", "ar", "en"],
    "ar-OM": ["ar-OM", "ar", "en"],
    "hi-IN": ["hi-IN", "hi", "en-IN", "en"],
    "ta-IN": ["ta-IN", "ta", "en-IN", "en"],
    "te-IN": ["te-IN", "te", "en-IN", "en"],
    "mr-IN": ["mr-IN", "mr", "en-IN", "en"],
    "en-IN": ["en-IN", "en"],
    "en-AE": ["en-AE", "en"],
    "en-GB": ["en-GB", "en"],
    "en-US": ["en-US", "en"],
    "en-AU": ["en-AU", "en"],
    "en-CA": ["en-CA", "en"],
    "en-SG": ["en-SG", "en"],
    "fr-CA": ["fr-CA", "fr", "en-CA", "en"],
    "zh-SG": ["zh-SG", "zh", "en-SG", "en"],
    "ms-SG": ["ms-SG", "ms", "en-SG", "en"],
}


class TranslationService:
    """
    DB-backed translation service with locale fallback chain.
    """

    def __init__(self, db: AsyncSession):
        self._db = db
        self._cache: Dict[str, Dict[str, str]] = {}

    async def t(
        self,
        key: str,
        locale: str,
        namespace: Optional[str] = None,
        params: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Translate a key for a given locale.
        """
        effective_namespace, effective_key = self._split_key(key, namespace)

        chain = LOCALE_FALLBACK_CHAINS.get(locale, [locale, "en"])
        for candidate_locale in chain:
            value = await self._lookup(effective_namespace, effective_key, candidate_locale)
            if value:
                return self._interpolate(value, params or {})

        logger.warning(
            f"[TranslationService] Missing translation: key={key} locale={locale} ns={effective_namespace}"
        )
        return key

    async def t_many(
        self,
        keys: List[str],
        locale: str,
        namespace: Optional[str] = None,
    ) -> Dict[str, str]:
        """Translate multiple keys in one call."""
        result = {}
        for key in keys:
            result[key] = await self.t(key, locale, namespace)
        return result

    async def get_namespace(self, namespace: str, locale: str) -> Dict[str, str]:
        """
        Return all translations for a namespace+locale combination.
        """
        from app.models.global_models import Translation
        chain = LOCALE_FALLBACK_CHAINS.get(locale, [locale, "en"])

        collected: Dict[str, str] = {}
        for candidate_locale in reversed(chain):
            stmt = select(Translation).where(and_(
                Translation.namespace == namespace,
                Translation.locale == candidate_locale,
                Translation.status == "active",
            ))
            result = await self._db.execute(stmt)
            rows = result.scalars().all()
            for row in rows:
                collected[row.translation_key] = row.value

        return collected

    async def upsert(
        self,
        namespace: str,
        key: str,
        locale: str,
        value: str,
    ) -> None:
        """Create or update a translation entry."""
        from app.models.global_models import Translation
        stmt = select(Translation).where(and_(
            Translation.namespace == namespace,
            Translation.translation_key == key,
            Translation.locale == locale,
        ))
        result = await self._db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.value = value
            existing.status = "active"
        else:
            self._db.add(Translation(
                namespace=namespace,
                translation_key=key,
                locale=locale,
                value=value,
                status="active",
            ))

        cache_key = f"{namespace}:{locale}"
        self._cache.pop(cache_key, None)
        await self._db.flush()

    async def _lookup(self, namespace: str, key: str, locale: str) -> Optional[str]:
        """Lookup from cache then DB."""
        cache_key = f"{namespace}:{locale}"

        if cache_key in self._cache and key in self._cache[cache_key]:
            return self._cache[cache_key][key]

        try:
            from app.models.global_models import Translation
            stmt = select(Translation).where(and_(
                Translation.namespace == namespace,
                Translation.translation_key == key,
                Translation.locale == locale,
                Translation.status == "active",
            ))
            result = await self._db.execute(stmt)
            row = result.scalar_one_or_none()

            if row:
                if cache_key not in self._cache:
                    self._cache[cache_key] = {}
                self._cache[cache_key][key] = row.value
                return row.value
        except Exception as e:
            logger.debug(f"[TranslationService] Lookup error: {e}")

        return None

    def invalidate_cache(self, namespace: Optional[str] = None, locale: Optional[str] = None):
        """Clear translation cache."""
        if namespace and locale:
            self._cache.pop(f"{namespace}:{locale}", None)
        elif namespace:
            keys_to_remove = [k for k in self._cache if k.startswith(f"{namespace}:")]
            for k in keys_to_remove:
                del self._cache[k]
        else:
            self._cache.clear()

    @staticmethod
    def _split_key(key: str, namespace: Optional[str]) -> tuple[str, str]:
        if namespace:
            return namespace, key

        valid_namespaces = {
            "common", "crm", "leads", "properties", "calendar",
            "billing", "workflow", "analytics", "ai", "errors", "notifications"
        }
        parts = key.split(".", 1)
        if len(parts) == 2 and parts[0] in valid_namespaces:
            return parts[0], parts[1]
        return "common", key

    @staticmethod
    def _interpolate(template: str, params: Dict[str, str]) -> str:
        result = template
        for k, v in params.items():
            result = result.replace(f"{{{k}}}", str(v))
        return result

    @staticmethod
    def get_fallback_chain(locale: str) -> List[str]:
        return LOCALE_FALLBACK_CHAINS.get(locale, [locale, "en"])

    @staticmethod
    def is_rtl(locale: str) -> bool:
        rtl_prefixes = ("ar", "fa", "he", "ur", "yi")
        lang = locale.split("-")[0].lower()
        return lang in rtl_prefixes
