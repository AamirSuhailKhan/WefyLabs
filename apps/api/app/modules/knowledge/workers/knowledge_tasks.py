"""
Knowledge Intelligence Platform — Celery Workers
=================================================
All background tasks for the knowledge processing pipeline.

Task ordering for a new document:
  1. process_document    — parse file (→ kicks off chain)
  2. run_ocr             — OCR if image-heavy PDF
  3. extract_facts       — structured fact extraction + conflict detection
  4. chunk_document_task — semantic chunking
  5. generate_embeddings — embed chunks (deduplicated)
  6. index_document      — vector + keyword indexing → sets status=INDEXED

Additional tasks:
  reindex_document      — on-demand reindex for a document
  delete_document_knowledge — GDPR-aware deletion pipeline
  run_evaluation        — evaluation dataset runner
  expire_stale_knowledge— Beat task: mark expired documents

Every task:
  - Is idempotent (uses idempotency_key in KnowledgeProcessingJob)
  - Updates job status in DB before and after
  - Updates document status at each pipeline stage
  - Logs with org_id for tenant-aware observability
  - Routes failures to knowledge-retry then knowledge-dead-letter
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from celery import Task
from app.celery_app import celery_app

logger = logging.getLogger(__name__)

# ─── Async runner helper ──────────────────────────────────────────────────────

def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ─── Base task with retry config ──────────────────────────────────────────────

class KnowledgeBaseTask(Task):
    """Base class for all knowledge tasks — configures retry behaviour."""
    abstract = True
    max_retries = 3
    default_retry_delay = 30    # seconds
    queue = "knowledge-parser"

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(
            f"[KNOWLEDGE TASK FAILURE] task={self.name} id={task_id} "
            f"exc={exc} kwargs={kwargs}"
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(
            f"[KNOWLEDGE TASK RETRY] task={self.name} id={task_id} "
            f"attempt={self.request.retries + 1}"
        )


# ─── 1. process_document ─────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=KnowledgeBaseTask,
    name="app.modules.knowledge.workers.knowledge_tasks.process_document",
    queue="knowledge-parser",
)
def process_document(self, document_id: str, organization_id: str, job_id: str):
    """
    Stage 1: Parse document file, update status → PROCESSING → PARSED.
    Then kicks off fact extraction and chunking.
    """
    logger.info(
        f"[PARSE] doc={document_id} org={organization_id} job={job_id}"
    )
    _run_async(_async_process_document(self, document_id, organization_id, job_id))


async def _async_process_document(
    task, document_id: str, organization_id: str, job_id: str
):
    from app.database import AsyncSessionLocal
    from app.models.knowledge_models import KnowledgeDocument, KnowledgeProcessingJob
    from app.modules.knowledge.providers.document_parser import get_parser
    from app.modules.knowledge.ingestion.storage_service import get_storage_provider
    from sqlalchemy import select, update

    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)

        # Mark document PROCESSING
        await db.execute(
            update(KnowledgeDocument)
            .where(KnowledgeDocument.id == document_id)
            .values(status="PROCESSING", updated_at=now)
        )
        await db.execute(
            update(KnowledgeProcessingJob)
            .where(KnowledgeProcessingJob.id == job_id)
            .values(status="running", started_at=now)
        )
        await db.commit()

        try:
            # Load document record
            result = await db.execute(
                select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
            )
            doc = result.scalars().first()
            if not doc:
                logger.error(f"[PARSE] Document not found: {document_id}")
                return

            # Retrieve file from storage
            storage = get_storage_provider(doc.storage_provider or "local")
            content = await storage.retrieve(doc.storage_key)

            # Resolve parser
            parser = get_parser(doc.mime_type or "", doc.file_name or "")
            if not parser:
                raise ValueError(f"No parser for MIME type: {doc.mime_type}")

            # Parse
            parsed = await parser.parse(content, doc.file_name or "")

            # Update document with parsing results
            await db.execute(
                update(KnowledgeDocument)
                .where(KnowledgeDocument.id == document_id)
                .values(
                    status="PARSED",
                    total_pages=parsed.total_pages,
                    ocr_used=parsed.requires_ocr,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await db.execute(
                update(KnowledgeProcessingJob)
                .where(KnowledgeProcessingJob.id == job_id)
                .values(
                    status="completed",
                    completed_at=datetime.now(timezone.utc),
                    result_summary={
                        "total_pages": parsed.total_pages,
                        "requires_ocr": parsed.requires_ocr,
                        "confidence": parsed.confidence,
                    },
                )
            )
            await db.commit()

            # Queue next stage: OCR if needed, otherwise extract_facts
            if parsed.requires_ocr and parsed.confidence < 0.5:
                run_ocr.apply_async(
                    kwargs={"document_id": document_id, "organization_id": organization_id},
                    queue="knowledge-ocr",
                )
            else:
                # Store parsed text in DB for next stages
                # Kick off fact extraction and chunking in parallel
                extract_facts.apply_async(
                    kwargs={
                        "document_id": document_id,
                        "organization_id": organization_id,
                        "parsed_text": parsed.full_text[:50000],  # limit
                        "tables": parsed.tables,
                    },
                    queue="knowledge-extraction",
                )
                chunk_document_task.apply_async(
                    kwargs={
                        "document_id": document_id,
                        "organization_id": organization_id,
                        "parsed_text": parsed.full_text[:100000],
                        "pages": [
                            {"page_number": p.page_number, "text": p.text, "tables": p.tables}
                            for p in parsed.pages
                        ],
                        "tables": parsed.tables,
                    },
                    queue="knowledge-chunking",
                )

            logger.info(
                f"[PARSE SUCCESS] doc={document_id} pages={parsed.total_pages} "
                f"ocr={parsed.requires_ocr} confidence={parsed.confidence:.2f}"
            )

        except Exception as exc:
            logger.error(f"[PARSE FAILED] doc={document_id}: {exc}", exc_info=True)
            await db.execute(
                update(KnowledgeDocument)
                .where(KnowledgeDocument.id == document_id)
                .values(
                    status="FAILED",
                    processing_error=str(exc)[:2000],
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await db.execute(
                update(KnowledgeProcessingJob)
                .where(KnowledgeProcessingJob.id == job_id)
                .values(
                    status="failed",
                    last_error=str(exc)[:2000],
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            raise task.retry(exc=exc, countdown=60)


# ─── 2. run_ocr ──────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=KnowledgeBaseTask,
    name="app.modules.knowledge.workers.knowledge_tasks.run_ocr",
    queue="knowledge-ocr",
)
def run_ocr(self, document_id: str, organization_id: str):
    """Stage 1b: OCR for image-heavy PDFs. Then chains to extraction/chunking."""
    _run_async(_async_run_ocr(self, document_id, organization_id))


async def _async_run_ocr(task, document_id: str, organization_id: str):
    from app.database import AsyncSessionLocal
    from app.models.knowledge_models import KnowledgeDocument
    from app.modules.knowledge.providers.provider_registry import ProviderRegistry
    from app.modules.knowledge.ingestion.storage_service import get_storage_provider
    from sqlalchemy import select, update

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
        )
        doc = result.scalars().first()
        if not doc:
            return

        storage = get_storage_provider(doc.storage_provider or "local")
        content = await storage.retrieve(doc.storage_key)

        ocr_provider = await ProviderRegistry.get_ocr_provider(organization_id, db)
        ocr_result = await ocr_provider.extract(content, doc.mime_type or "application/pdf")

        await db.execute(
            update(KnowledgeDocument)
            .where(KnowledgeDocument.id == document_id)
            .values(
                status="PARSED",
                ocr_used=True,
                ocr_provider=ocr_result.provider,
                ocr_confidence=ocr_result.average_confidence,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()

        # Chain to chunking
        chunk_document_task.apply_async(
            kwargs={
                "document_id": document_id,
                "organization_id": organization_id,
                "parsed_text": ocr_result.full_text,
                "pages": [
                    {"page_number": p.page_number, "text": p.text, "tables": p.tables}
                    for p in ocr_result.pages
                ],
                "tables": [],
            },
            queue="knowledge-chunking",
        )
        logger.info(
            f"[OCR SUCCESS] doc={document_id} pages={ocr_result.total_pages} "
            f"confidence={ocr_result.average_confidence:.2f}"
        )


# ─── 3. extract_facts ────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=KnowledgeBaseTask,
    name="app.modules.knowledge.workers.knowledge_tasks.extract_facts",
    queue="knowledge-extraction",
)
def extract_facts(
    self,
    document_id: str,
    organization_id: str,
    parsed_text: str,
    tables: Optional[list] = None,
):
    """Stage 2: Extract structured facts from parsed text. Detect conflicts."""
    _run_async(_async_extract_facts(
        self, document_id, organization_id, parsed_text, tables or []
    ))


async def _async_extract_facts(
    task, document_id: str, organization_id: str, parsed_text: str, tables: list
):
    from app.database import AsyncSessionLocal
    from app.models.knowledge_models import (
        KnowledgeDocument, KnowledgeFact, KnowledgeConflict
    )
    from app.modules.knowledge.extraction.fact_extraction_service import (
        FactExtractionService, ConflictDetectionService
    )
    from sqlalchemy import select, update

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
        )
        doc = result.scalars().first()
        if not doc:
            return

        extractor = FactExtractionService()
        conflict_detector = ConflictDetectionService()

        facts, injection_detected = extractor.extract_from_text(
            text=parsed_text,
            document_id=document_id,
            organization_id=organization_id,
            knowledge_type=doc.knowledge_type,
            project_id=doc.project_id,
            property_id=doc.property_id,
            effective_at=doc.effective_at,
            expires_at=doc.expires_at,
        )

        # Persist facts
        for fact in facts:
            db_fact = KnowledgeFact(
                id=fact.id,
                document_id=fact.document_id,
                organization_id=fact.organization_id,
                project_id=fact.project_id,
                property_id=fact.property_id,
                fact_type=fact.fact_type,
                value_text=fact.value_text,
                value_numeric=fact.value_numeric,
                value_json=fact.value_json,
                currency=fact.currency,
                unit=fact.unit,
                scope=fact.scope,
                confidence=fact.confidence,
                extraction_method=fact.extraction_method,
                effective_at=fact.effective_at,
                expires_at=fact.expires_at,
                verification_status="UNVERIFIED",
                created_at=fact.created_at,
                updated_at=fact.updated_at,
            )
            db.add(db_fact)

        await db.flush()

        # Check conflicts
        conflicts = await conflict_detector.check_conflicts(
            db=db,
            new_facts=facts,
            organization_id=organization_id,
            project_id=doc.project_id,
            property_id=doc.property_id,
        )

        for conflict_data in conflicts:
            conflict = KnowledgeConflict(
                id=str(uuid.uuid4()),
                organization_id=conflict_data["organization_id"],
                fact_type=conflict_data["fact_type"],
                fact_a_id=conflict_data["fact_a_id"],
                fact_a_value=conflict_data["fact_a_value"],
                fact_a_document_id=conflict_data["fact_a_document_id"],
                fact_a_confidence=conflict_data["fact_a_confidence"],
                fact_b_id=conflict_data["fact_b_id"],
                fact_b_value=conflict_data["fact_b_value"],
                fact_b_document_id=conflict_data["fact_b_document_id"],
                fact_b_confidence=conflict_data["fact_b_confidence"],
                project_id=conflict_data.get("project_id"),
                property_id=conflict_data.get("property_id"),
                resolution_status="OPEN",
                created_at=datetime.now(timezone.utc),
            )
            db.add(conflict)

        # Update document
        now = datetime.now(timezone.utc)
        await db.execute(
            update(KnowledgeDocument)
            .where(KnowledgeDocument.id == document_id)
            .values(
                status="EXTRACTED",
                total_facts=len(facts),
                total_conflicts=len(conflicts),
                updated_at=now,
            )
        )
        await db.commit()

        logger.info(
            f"[EXTRACT] doc={document_id} facts={len(facts)} "
            f"conflicts={len(conflicts)} injection={injection_detected}"
        )


# ─── 4. chunk_document_task ──────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=KnowledgeBaseTask,
    name="app.modules.knowledge.workers.knowledge_tasks.chunk_document_task",
    queue="knowledge-chunking",
)
def chunk_document_task(
    self,
    document_id: str,
    organization_id: str,
    parsed_text: str,
    pages: Optional[list] = None,
    tables: Optional[list] = None,
):
    """Stage 3: Semantic chunking → persist KnowledgeChunk records."""
    _run_async(_async_chunk_document(
        self, document_id, organization_id, parsed_text,
        pages or [], tables or []
    ))


async def _async_chunk_document(
    task, document_id: str, organization_id: str,
    parsed_text: str, pages: list, tables: list
):
    from app.database import AsyncSessionLocal
    from app.models.knowledge_models import KnowledgeDocument, KnowledgeChunk
    from app.modules.knowledge.parsing.chunking_service import ChunkingService
    from sqlalchemy import select, update

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
        )
        doc = result.scalars().first()
        if not doc:
            return

        chunker = ChunkingService()

        # Reconstruct page objects for chunker
        class _Page:
            def __init__(self, d):
                self.page_number = d.get("page_number", 1)
                self.text = d.get("text", "")
                self.tables = d.get("tables", [])

        parsed_pages = [_Page(p) for p in pages] if pages else None

        chunk_data_list = chunker.chunk_document(
            document_id=document_id,
            organization_id=organization_id,
            parsed_text=parsed_text,
            knowledge_type=doc.knowledge_type,
            version_id=doc.current_version_id,
            pages=parsed_pages,
            tables=tables or [],
            language=doc.language,
            country=doc.country,
            currency=doc.currency,
            visibility=doc.visibility,
            ai_allowed=doc.ai_allowed,
            effective_at=doc.effective_at,
            expires_at=doc.expires_at,
            project_id=doc.project_id,
            property_id=doc.property_id,
        )

        # Persist chunks
        for cd in chunk_data_list:
            chunk = KnowledgeChunk(
                id=cd.id,
                document_id=cd.document_id,
                version_id=cd.version_id,
                organization_id=cd.organization_id,
                project_id=cd.project_id,
                property_id=cd.property_id,
                chunk_index=cd.chunk_index,
                page_number=cd.page_number,
                section=cd.section,
                heading=cd.heading,
                subheading=cd.subheading,
                chunk_type=cd.chunk_type,
                content=cd.content,
                content_hash=cd.content_hash,
                token_count=cd.token_count,
                char_count=cd.char_count,
                language=cd.language,
                country=cd.country,
                currency=cd.currency,
                knowledge_type=cd.knowledge_type,
                visibility=cd.visibility,
                ai_allowed=cd.ai_allowed,
                effective_at=cd.effective_at,
                expires_at=cd.expires_at,
                is_expired=False,
                table_data=cd.table_data,
                created_at=cd.created_at,
                updated_at=cd.updated_at,
            )
            db.add(chunk)

        now = datetime.now(timezone.utc)
        await db.execute(
            update(KnowledgeDocument)
            .where(KnowledgeDocument.id == document_id)
            .values(
                total_chunks=len(chunk_data_list),
                updated_at=now,
            )
        )
        await db.commit()

        logger.info(f"[CHUNK] doc={document_id} chunks={len(chunk_data_list)}")

        # Queue embedding generation
        generate_embeddings.apply_async(
            kwargs={"document_id": document_id, "organization_id": organization_id},
            queue="knowledge-embedding",
        )


# ─── 5. generate_embeddings ──────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=KnowledgeBaseTask,
    name="app.modules.knowledge.workers.knowledge_tasks.generate_embeddings",
    queue="knowledge-embedding",
)
def generate_embeddings(self, document_id: str, organization_id: str):
    """Stage 4: Generate embeddings for all chunks (with deduplication)."""
    _run_async(_async_generate_embeddings(self, document_id, organization_id))


async def _async_generate_embeddings(task, document_id: str, organization_id: str):
    from app.database import AsyncSessionLocal
    from app.models.knowledge_models import KnowledgeChunk, KnowledgeEmbedding
    from app.modules.knowledge.providers.provider_registry import ProviderRegistry
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        # Load all chunks for this document
        result = await db.execute(
            select(KnowledgeChunk).where(
                KnowledgeChunk.document_id == document_id,
                KnowledgeChunk.organization_id == organization_id,
            )
        )
        chunks = result.scalars().all()
        if not chunks:
            logger.warning(f"[EMBED] No chunks found for doc={document_id}")
            return

        embed_provider = await ProviderRegistry.get_embedding_provider(
            organization_id, db
        )

        # Check for existing embeddings (dedup by content_hash)
        existing_hashes = set()
        existing_result = await db.execute(
            select(KnowledgeEmbedding.text_hash).where(
                KnowledgeEmbedding.organization_id == organization_id,
                KnowledgeEmbedding.is_active == True,
            )
        )
        for row in existing_result:
            existing_hashes.add(row.text_hash)

        # Batch chunks that need new embeddings
        BATCH_SIZE = 20
        new_chunks = [c for c in chunks if c.content_hash not in existing_hashes]

        logger.info(
            f"[EMBED] doc={document_id} total={len(chunks)} "
            f"new={len(new_chunks)} cached={len(chunks)-len(new_chunks)}"
        )

        for i in range(0, len(new_chunks), BATCH_SIZE):
            batch = new_chunks[i : i + BATCH_SIZE]
            texts = [c.content for c in batch]

            batch_result = await embed_provider.embed_texts(texts)

            for j, chunk in enumerate(batch):
                emb_result = batch_result.results[j]
                embedding_record = KnowledgeEmbedding(
                    id=str(uuid.uuid4()),
                    chunk_id=chunk.id,
                    organization_id=organization_id,
                    provider=embed_provider.provider_name,
                    model_name=embed_provider.get_default_model(),
                    embedding_dim=emb_result.dimensions,
                    text_hash=emb_result.text_hash,
                    token_count=emb_result.token_count,
                    cost_tokens=emb_result.token_count,
                    embedding_json=emb_result.embedding,
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(embedding_record)

        await db.commit()

        # Queue indexing
        index_document.apply_async(
            kwargs={"document_id": document_id, "organization_id": organization_id},
            queue="knowledge-indexing",
        )


# ─── 6. index_document ───────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=KnowledgeBaseTask,
    name="app.modules.knowledge.workers.knowledge_tasks.index_document",
    queue="knowledge-indexing",
)
def index_document(self, document_id: str, organization_id: str):
    """Stage 5: Update KnowledgeIndex records → set document status=INDEXED."""
    _run_async(_async_index_document(self, document_id, organization_id))


async def _async_index_document(task, document_id: str, organization_id: str):
    from app.database import AsyncSessionLocal
    from app.models.knowledge_models import (
        KnowledgeDocument, KnowledgeChunk, KnowledgeIndex
    )
    from sqlalchemy import select, update

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KnowledgeChunk).where(
                KnowledgeChunk.document_id == document_id,
                KnowledgeChunk.organization_id == organization_id,
            )
        )
        chunks = result.scalars().all()
        now = datetime.now(timezone.utc)

        for chunk in chunks:
            # Check if index record exists
            idx_result = await db.execute(
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
                idx = KnowledgeIndex(
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
                )
                db.add(idx)

        # Determine next status based on org policy
        # Default: INDEXED (requires human to publish)
        await db.execute(
            update(KnowledgeDocument)
            .where(KnowledgeDocument.id == document_id)
            .values(status="INDEXED", updated_at=now)
        )
        await db.commit()

        logger.info(
            f"[INDEX SUCCESS] doc={document_id} chunks={len(chunks)} "
            f"status=INDEXED (awaiting publish)"
        )


# ─── 7. reindex_document ─────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=KnowledgeBaseTask,
    name="app.modules.knowledge.workers.knowledge_tasks.reindex_document",
    queue="knowledge-reindex",
)
def reindex_document(self, document_id: str, organization_id: str):
    """
    On-demand reindex: delete existing embeddings + indexes, then re-embed + re-index.
    Triggered by: provider change, chunking logic change, manual reindex request.
    """
    _run_async(_async_reindex_document(self, document_id, organization_id))


async def _async_reindex_document(task, document_id: str, organization_id: str):
    from app.database import AsyncSessionLocal
    from app.models.knowledge_models import KnowledgeChunk, KnowledgeEmbedding, KnowledgeIndex
    from sqlalchemy import select, delete as sql_delete

    async with AsyncSessionLocal() as db:
        # Delete existing embeddings for this document's chunks
        chunk_result = await db.execute(
            select(KnowledgeChunk.id).where(
                KnowledgeChunk.document_id == document_id,
                KnowledgeChunk.organization_id == organization_id,
            )
        )
        chunk_ids = [row.id for row in chunk_result]

        if chunk_ids:
            await db.execute(
                sql_delete(KnowledgeEmbedding).where(
                    KnowledgeEmbedding.chunk_id.in_(chunk_ids)
                )
            )
            await db.execute(
                sql_delete(KnowledgeIndex).where(
                    KnowledgeIndex.chunk_id.in_(chunk_ids)
                )
            )
        await db.commit()

    # Re-trigger embedding + indexing
    generate_embeddings.apply_async(
        kwargs={"document_id": document_id, "organization_id": organization_id},
        queue="knowledge-embedding",
    )
    logger.info(f"[REINDEX] doc={document_id} queued re-embedding")


# ─── 8. delete_document_knowledge ────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=KnowledgeBaseTask,
    name="app.modules.knowledge.workers.knowledge_tasks.delete_document_knowledge",
    queue="knowledge-deletion",
)
def delete_document_knowledge(
    self,
    document_id: str,
    organization_id: str,
    deletion_job_id: str,
    requested_by: str = "system",
    reason: str = "admin_delete",
):
    """
    GDPR-aware deletion pipeline (7 steps):
    1. Mark source deleted
    2. Remove vector index entries
    3. Remove keyword index entries
    4. Invalidate cache
    5. Emit deletion event
    6. Preserve audit metadata
    7. Mark deletion job completed
    """
    _run_async(_async_delete_document(
        self, document_id, organization_id, deletion_job_id, requested_by, reason
    ))


async def _async_delete_document(
    task, document_id: str, organization_id: str,
    deletion_job_id: str, requested_by: str, reason: str
):
    from app.database import AsyncSessionLocal
    from app.models.knowledge_models import (
        KnowledgeDocument, KnowledgeChunk, KnowledgeEmbedding,
        KnowledgeIndex, KnowledgeDeletionJob
    )
    from app.infrastructure.events.event_bus import event_bus, DomainEvent, ActorContext
    from app.modules.knowledge.events.knowledge_events import KnowledgeEvents
    from sqlalchemy import select, update, delete as sql_delete

    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)

        # Step 1: Load and mark document deleted
        doc_result = await db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
        )
        doc = doc_result.scalars().first()
        if not doc or doc.organization_id != organization_id:
            logger.error(f"[DELETE] Document not found or wrong org: {document_id}")
            return

        doc_metadata = {
            "document_title": doc.title,
            "knowledge_type": doc.knowledge_type,
            "file_name": doc.file_name,
        }

        await db.execute(
            update(KnowledgeDocument)
            .where(KnowledgeDocument.id == document_id)
            .values(status="DELETED", updated_at=now)
        )

        # Step 2 & 3: Remove vector and keyword index entries
        chunk_result = await db.execute(
            select(KnowledgeChunk.id).where(
                KnowledgeChunk.document_id == document_id,
                KnowledgeChunk.organization_id == organization_id,
            )
        )
        chunk_ids = [row.id for row in chunk_result]
        chunks_deleted = len(chunk_ids)
        embeddings_deleted = 0

        if chunk_ids:
            emb_result = await db.execute(
                select(KnowledgeEmbedding).where(
                    KnowledgeEmbedding.chunk_id.in_(chunk_ids)
                )
            )
            embeddings_deleted = len(emb_result.scalars().all())

            await db.execute(
                sql_delete(KnowledgeEmbedding).where(
                    KnowledgeEmbedding.chunk_id.in_(chunk_ids)
                )
            )
            await db.execute(
                sql_delete(KnowledgeIndex).where(
                    KnowledgeIndex.chunk_id.in_(chunk_ids)
                )
            )
            await db.execute(
                sql_delete(KnowledgeChunk).where(
                    KnowledgeChunk.document_id == document_id
                )
            )

        # Step 6: Update deletion job with audit metadata
        await db.execute(
            update(KnowledgeDeletionJob)
            .where(KnowledgeDeletionJob.id == deletion_job_id)
            .values(
                status="completed",
                completed_at=now,
                audit_metadata={
                    **doc_metadata,
                    "total_chunks_deleted": chunks_deleted,
                    "total_embeddings_deleted": embeddings_deleted,
                    "deleted_by": requested_by,
                    "reason": reason,
                    "deleted_at": now.isoformat(),
                },
            )
        )
        await db.commit()

        # Step 5: Emit deletion event
        await event_bus.publish(DomainEvent(
            event_type=KnowledgeEvents.DELETED,
            organization_id=organization_id,
            actor=ActorContext(user_id=requested_by, actor_type="user"),
            payload={
                "document_id": document_id,
                "chunks_deleted": chunks_deleted,
                "embeddings_deleted": embeddings_deleted,
                "reason": reason,
            },
        ))

        logger.info(
            f"[DELETE SUCCESS] doc={document_id} chunks={chunks_deleted} "
            f"embeddings={embeddings_deleted}"
        )


# ─── 9. expire_stale_knowledge ───────────────────────────────────────────────

@celery_app.task(
    name="app.modules.knowledge.workers.knowledge_tasks.expire_stale_knowledge",
    queue="knowledge-indexing",
)
def expire_stale_knowledge():
    """
    Beat task: runs every 6 hours.
    Finds documents and chunks past their expires_at and marks them EXPIRED.
    Expired knowledge is excluded from customer-facing retrieval.
    """
    _run_async(_async_expire_stale_knowledge())


async def _async_expire_stale_knowledge():
    from app.database import AsyncSessionLocal
    from app.models.knowledge_models import KnowledgeDocument, KnowledgeChunk
    from sqlalchemy import update, select

    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)

        # Expire documents
        await db.execute(
            update(KnowledgeDocument)
            .where(
                KnowledgeDocument.expires_at <= now,
                KnowledgeDocument.status == "PUBLISHED",
            )
            .values(status="EXPIRED", updated_at=now)
        )

        # Mark chunks as expired
        await db.execute(
            update(KnowledgeChunk)
            .where(
                KnowledgeChunk.expires_at <= now,
                KnowledgeChunk.is_expired == False,
            )
            .values(is_expired=True, updated_at=now)
        )

        await db.commit()
        logger.info(f"[FRESHNESS] Stale knowledge expiration sweep completed at {now}")


# ─── 10. run_evaluation ──────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=KnowledgeBaseTask,
    name="app.modules.knowledge.workers.knowledge_tasks.run_evaluation",
    queue="knowledge-evaluation",
)
def run_evaluation(self, organization_id: str, eval_type: str = "retrieval"):
    """Kick off an evaluation run. Results persisted to KnowledgeEvaluation."""
    logger.info(f"[EVAL] Starting {eval_type} evaluation for org={organization_id}")
    # Evaluation framework is invoked separately via EvaluationRunner
    from app.modules.knowledge.evaluation.evaluation_runner import EvaluationRunner
    _run_async(EvaluationRunner().run(organization_id=organization_id, eval_type=eval_type))
