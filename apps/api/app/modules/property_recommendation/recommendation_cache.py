"""
Part 21.3 — Recommendation Cache Service
=========================================
Tenant-isolated, evidence-hashed caching for AI property recommendations.
Prevents redundant database queries and AI evaluations when lead requirements
and tenant inventory remain unchanged.
"""
import json
import hashlib
import logging
from typing import Optional, Dict, Any

from app.modules.property_recommendation.dto import PropertyRecommendationResponseDTO
from app.modules.property_recommendation.metrics import (
    PROPERTY_RECOMMENDATION_CACHE_HITS_TOTAL, mask_org_id
)

logger = logging.getLogger(__name__)


def compute_recommendation_cache_key(
    organization_id: str,
    lead_id: str,
    intel_hash: str,
    inventory_hash: str,
    scoring_version: str = "v1.0-property-match",
    top_k: int = 5,
) -> str:
    """
    Computes a cryptographic fingerprint for caching recommendations.
    Format: rec:{org_id}:{lead_id}:{hash}
    """
    hasher = hashlib.sha256()
    hasher.update(organization_id.encode("utf-8"))
    hasher.update(lead_id.encode("utf-8"))
    hasher.update(intel_hash.encode("utf-8"))
    hasher.update(inventory_hash.encode("utf-8"))
    hasher.update(scoring_version.encode("utf-8"))
    hasher.update(str(top_k).encode("utf-8"))
    digest = hasher.hexdigest()[:16]
    return f"rec:{organization_id}:{lead_id}:{digest}"


class RecommendationCacheService:
    """
    Tenant-isolated cache manager for property recommendations.
    """
    _memory_cache: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get(cls, organization_id: str, cache_key: str) -> Optional[PropertyRecommendationResponseDTO]:
        """
        Retrieves cached recommendation response.
        Enforces tenant isolation by verifying the key namespace.
        """
        if not cache_key.startswith(f"rec:{organization_id}:"):
            logger.warning(f"[REC_CACHE] Cross-tenant cache access blocked for org {organization_id}")
            return None

        cached = cls._memory_cache.get(cache_key)
        if cached:
            try:
                PROPERTY_RECOMMENDATION_CACHE_HITS_TOTAL.labels(
                    org_hash=mask_org_id(organization_id)
                ).inc()
                return PropertyRecommendationResponseDTO(**cached)
            except Exception as exc:
                logger.error(f"[REC_CACHE] Failed to deserialize cached recommendation: {exc}")
                cls._memory_cache.pop(cache_key, None)
        return None

    @classmethod
    def set(cls, organization_id: str, cache_key: str, response: PropertyRecommendationResponseDTO) -> None:
        """Stores recommendation response in tenant cache."""
        if not cache_key.startswith(f"rec:{organization_id}:"):
            return
        cls._memory_cache[cache_key] = response.model_dump()

    @classmethod
    def invalidate_lead(cls, organization_id: str, lead_id: str) -> None:
        """Evicts all cached recommendations for a specific lead."""
        prefix = f"rec:{organization_id}:{lead_id}:"
        keys_to_delete = [k for k in cls._memory_cache if k.startswith(prefix)]
        for k in keys_to_delete:
            cls._memory_cache.pop(k, None)

    @classmethod
    def clear_org(cls, organization_id: str) -> None:
        """Evicts all cache entries for an organization."""
        prefix = f"rec:{organization_id}:"
        keys_to_delete = [k for k in cls._memory_cache if k.startswith(prefix)]
        for k in keys_to_delete:
            cls._memory_cache.pop(k, None)
