"""
Provider Registry
=================
Central DI registry for all Knowledge Engine providers.
Provider selection is database-driven via KnowledgeProvider config.
Defaults:
  - Embedding: Google Gemini (text-embedding-004)
  - OCR: Local Tesseract OCR (open-source)
  - Vector Store: pgvector
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from app.modules.knowledge.providers.embedding_provider import (
    EmbeddingProvider, get_embedding_provider
)
from app.modules.knowledge.providers.vector_store_provider import (
    VectorStoreProvider, PgVectorStoreProvider, MockVectorStoreProvider
)
from app.modules.knowledge.providers.document_parser import get_parser, DocumentParser
from app.modules.knowledge.providers.ocr_provider import (
    OCRProvider, get_ocr_provider
)
from app.modules.knowledge.providers.reranker_provider import (
    RerankerProvider, get_reranker_provider
)

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    Resolves provider instances from KnowledgeProvider database config.
    Caches resolved providers to avoid repeated DB lookups.
    """

    @staticmethod
    async def get_embedding_provider(
        organization_id: str,
        db=None,
    ) -> EmbeddingProvider:
        """
        Resolve embedding provider for an organization.
        Falls back to Gemini or mock if no provider is configured in DB.
        """
        if db is not None:
            try:
                from sqlalchemy import text
                result = await db.execute(
                    text(
                        "SELECT provider_name, model_name, api_key_encrypted, config "
                        "FROM knowledge_providers "
                        "WHERE (organization_id = :org_id OR organization_id IS NULL) "
                        "AND provider_type = 'embedding' "
                        "AND is_active = TRUE AND is_default = TRUE "
                        "ORDER BY CASE WHEN organization_id = :org_id THEN 0 ELSE 1 END "
                        "LIMIT 1"
                    ),
                    {"org_id": organization_id},
                )
                row = result.fetchone()
                if row:
                    api_key = None
                    if row.api_key_encrypted:
                        try:
                            from app.modules.security.services.crypto_service import CryptoService
                            api_key = CryptoService.decrypt(row.api_key_encrypted)
                        except Exception:
                            pass
                    return get_embedding_provider(
                        provider_name=row.provider_name,
                        api_key=api_key,
                        model=row.model_name,
                    )
            except Exception as exc:
                logger.warning(f"[PROVIDER REGISTRY] Embedding lookup failed: {exc}")

        # Fallback: check Gemini environment key
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key and not gemini_key.startswith("AIzaSy_placeholder"):
            return get_embedding_provider("gemini", api_key=gemini_key)

        return get_embedding_provider("mock")

    @staticmethod
    def get_vector_store_provider(
        provider_name: str = "pgvector",
        db=None,
    ) -> VectorStoreProvider:
        """Resolve vector store provider. PgVector is the default."""
        if provider_name == "pgvector" and db is not None:
            return PgVectorStoreProvider(db=db)
        return MockVectorStoreProvider()

    @staticmethod
    async def get_ocr_provider(
        organization_id: str,
        db=None,
    ) -> OCRProvider:
        """Resolve OCR provider for an organization. Defaults to local Tesseract OCR."""
        if db is not None:
            try:
                from sqlalchemy import text
                result = await db.execute(
                    text(
                        "SELECT provider_name, config FROM knowledge_providers "
                        "WHERE (organization_id = :org_id OR organization_id IS NULL) "
                        "AND provider_type = 'ocr' AND is_active = TRUE "
                        "LIMIT 1"
                    ),
                    {"org_id": organization_id},
                )
                row = result.fetchone()
                if row:
                    cfg = row.config if isinstance(row.config, dict) else {}
                    return get_ocr_provider(row.provider_name, config=cfg)
            except Exception as exc:
                logger.warning(f"[PROVIDER REGISTRY] OCR lookup failed: {exc}")

        default_provider = os.getenv("KNOWLEDGE_OCR_PROVIDER", "tesseract")
        return get_ocr_provider(default_provider)

    @staticmethod
    async def get_reranker_provider(
        organization_id: str,
        db=None,
    ) -> RerankerProvider:
        """Resolve reranker provider for an organization."""
        if db is None:
            return get_reranker_provider("score_boost")
        try:
            from sqlalchemy import text
            result = await db.execute(
                text(
                    "SELECT provider_name, api_key_encrypted, config "
                    "FROM knowledge_providers "
                    "WHERE (organization_id = :org_id OR organization_id IS NULL) "
                    "AND provider_type = 'reranker' AND is_active = TRUE "
                    "LIMIT 1"
                ),
                {"org_id": organization_id},
            )
            row = result.fetchone()
            if row:
                api_key = None
                if row.api_key_encrypted:
                    try:
                        from app.modules.security.services.crypto_service import CryptoService
                        api_key = CryptoService.decrypt(row.api_key_encrypted)
                    except Exception:
                        pass
                return get_reranker_provider(row.provider_name, api_key=api_key)
        except Exception as exc:
            logger.warning(f"[PROVIDER REGISTRY] Reranker lookup failed: {exc}")
        return get_reranker_provider("score_boost")
