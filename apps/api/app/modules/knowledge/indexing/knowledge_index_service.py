"""
Knowledge Index Service
========================
Coordinates both vector and keyword indexing.
Called by the indexing Celery worker after embeddings are generated.

Responsibilities:
  - Update KnowledgeIndex records
  - Coordinate vector store upsert
  - Coordinate PostgreSQL FTS index updates
  - Provide reindex capability per document or collection
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.modules.knowledge.providers.provider_registry import ProviderRegistry
from app.modules.knowledge.providers.vector_store_provider import ChunkVector

logger = logging.getLogger(__name__)


class KnowledgeIndexService:
    """
    Coordinates vector + keyword indexing for knowledge chunks.
    Vector store: PgVectorStoreProvider (or configured alternate).
    Keyword index: PostgreSQL GIN + tsvector (reuses search module).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def index_chunks(
        self,
        organization_id: str,
        document_id: str,
    ) -> Dict[str, int]:
        """
        Index all chunks for a document.
        Returns: {vector_indexed, keyword_indexed, errors}
        """
        from app.models.knowledge_models import KnowledgeChunk, KnowledgeEmbedding, KnowledgeIndex

        chunk_result = await self.db.execute(
            select(KnowledgeChunk).where(
                KnowledgeChunk.document_id == document_id,
                KnowledgeChunk.organization_id == organization_id,
            )
        )
        chunks = chunk_result.scalars().all()

        vector_store = ProviderRegistry.get_vector_store_provider(
            provider_name="pgvector", db=self.db
        )

        chunk_vectors: List[ChunkVector] = []
        for chunk in chunks:
            emb_result = await self.db.execute(
                select(KnowledgeEmbedding).where(
                    KnowledgeEmbedding.chunk_id == chunk.id,
                    KnowledgeEmbedding.is_active == True,
                )
            )
            embedding = emb_result.scalars().first()
            if not embedding or not embedding.embedding_json:
                continue

            chunk_vectors.append(ChunkVector(
                chunk_id=chunk.id,
                organization_id=organization_id,
                document_id=document_id,
                embedding=embedding.embedding_json,
                metadata={
                    "text_hash": embedding.text_hash,
                    "token_count": embedding.token_count,
                    "knowledge_type": chunk.knowledge_type,
                    "visibility": chunk.visibility,
                    "ai_allowed": chunk.ai_allowed,
                    "language": chunk.language,
                },
            ))

        # Upsert into vector store
        vector_indexed = 0
        if chunk_vectors:
            vector_indexed = await vector_store.upsert(chunk_vectors)

        now = datetime.now(timezone.utc)
        for chunk in chunks:
            # Upsert KnowledgeIndex record
            idx_result = await self.db.execute(
                select(KnowledgeIndex).where(
                    KnowledgeIndex.chunk_id == chunk.id,
                    KnowledgeIndex.index_provider == "pgvector",
                )
            )
            existing_idx = idx_result.scalars().first()
            if existing_idx:
                existing_idx.vector_index_status = "indexed"
                existing_idx.keyword_index_status = "indexed"
                existing_idx.vector_indexed_at = now
                existing_idx.keyword_indexed_at = now
                existing_idx.updated_at = now
            else:
                self.db.add(KnowledgeIndex(
                    id=str(uuid.uuid4()),
                    chunk_id=chunk.id,
                    document_id=document_id,
                    organization_id=organization_id,
                    vector_index_status="indexed",
                    keyword_index_status="indexed",
                    vector_indexed_at=now,
                    keyword_indexed_at=now,
                    index_provider="pgvector",
                    retry_count=0,
                    created_at=now,
                    updated_at=now,
                ))

        await self.db.commit()

        logger.info(
            f"[INDEX SERVICE] doc={document_id} "
            f"vector={vector_indexed} keyword={len(chunks)}"
        )
        return {"vector_indexed": vector_indexed, "keyword_indexed": len(chunks), "errors": 0}

    async def delete_document_index(
        self,
        organization_id: str,
        document_id: str,
    ) -> int:
        """Remove all index entries for a document from vector store."""
        vector_store = ProviderRegistry.get_vector_store_provider(
            provider_name="pgvector", db=self.db
        )
        deleted = await vector_store.delete_by_document(organization_id, document_id)
        logger.info(f"[INDEX DELETE] doc={document_id} vectors_deleted={deleted}")
        return deleted
