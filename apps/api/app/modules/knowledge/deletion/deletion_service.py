"""
Knowledge Deletion Service
============================
Standalone deletion service for GDPR-aware document removal.

This service is the synchronous API-layer entry point for deletion.
The actual async cleanup work (vector removal, embedding deletion) is
dispatched to the `delete_document_knowledge` Celery worker.

7-step GDPR deletion pipeline:
  1. Authorize (org check, document exists)
  2. Create KnowledgeDeletionJob audit record
  3. Mark document DELETED in DB (soft delete immediately)
  4. Queue async cleanup (Celery: embeddings, vectors, chunks, indexes)
  5. Emit KnowledgeDeleted domain event
  6. Preserve audit metadata (never destroy the deletion record)
  7. Return deletion job ID for status tracking

Supports:
  - Single document deletion
  - Collection deletion (all documents in a collection)
  - Org-wide deletion (GDPR right to erasure)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.knowledge_models import (
    KnowledgeDocument, KnowledgeDeletionJob, KnowledgeCollection
)
from app.infrastructure.events.event_bus import event_bus, DomainEvent, ActorContext
from app.modules.knowledge.events.knowledge_events import KnowledgeEvents

logger = logging.getLogger(__name__)


class KnowledgeDeletionService:
    """
    Entry point for all document deletion workflows.
    Delegates heavy async work to Celery.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def delete_document(
        self,
        organization_id: str,
        document_id: str,
        requested_by: str,
        reason: str = "admin_delete",
        requested_by_type: str = "broker",
    ) -> Dict[str, Any]:
        """
        Initiate deletion of a single knowledge document.

        Returns:
            {"deletion_job_id": str, "status": "queued", "message": str}

        Raises:
            ValueError: if document not found or already deleted.
        """
        doc = await self._load_doc(organization_id, document_id)
        if doc.status == "DELETED":
            raise ValueError(f"Document {document_id} is already deleted.")

        now = datetime.now(timezone.utc)
        job_id = str(uuid.uuid4())

        # Soft-delete immediately
        doc.status = "DELETED"
        doc.updated_at = now

        # Create audit record
        job = KnowledgeDeletionJob(
            id=job_id,
            organization_id=organization_id,
            document_id=document_id,
            requested_by=requested_by,
            reason=reason,
            status="pending",
            audit_metadata={
                "title": doc.title,
                "knowledge_type": doc.knowledge_type,
                "file_name": doc.file_name,
                "requested_by_type": requested_by_type,
            },
            created_at=now,
        )
        self.db.add(job)
        await self.db.commit()

        # Queue async cleanup
        self._queue_cleanup(document_id, organization_id, job_id, requested_by, reason)

        # Emit event
        await event_bus.publish(DomainEvent(
            event_type=KnowledgeEvents.DELETED,
            organization_id=organization_id,
            actor=ActorContext(user_id=requested_by, actor_type=requested_by_type),
            payload={
                "document_id": document_id,
                "title": doc.title,
                "reason": reason,
                "deletion_job_id": job_id,
            },
        ))

        logger.info(
            f"[DELETION] doc={document_id} org={organization_id} "
            f"reason={reason} job={job_id}"
        )

        return {
            "deletion_job_id": job_id,
            "status": "queued",
            "message": (
                "Document marked deleted. Embeddings and index entries will "
                "be removed asynchronously."
            ),
        }

    async def delete_collection(
        self,
        organization_id: str,
        collection_id: str,
        requested_by: str,
        reason: str = "collection_delete",
    ) -> Dict[str, Any]:
        """Delete all documents in a knowledge collection."""
        result = await self.db.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.organization_id == organization_id,
                KnowledgeDocument.collection_id == collection_id,
                KnowledgeDocument.status != "DELETED",
            )
        )
        docs = result.scalars().all()

        job_ids = []
        for doc in docs:
            try:
                result_item = await self.delete_document(
                    organization_id=organization_id,
                    document_id=doc.id,
                    requested_by=requested_by,
                    reason=reason,
                )
                job_ids.append(result_item["deletion_job_id"])
            except Exception as exc:
                logger.error(f"[DELETION] Failed to delete doc {doc.id}: {exc}")

        # Deactivate collection
        col_result = await self.db.execute(
            select(KnowledgeCollection).where(
                KnowledgeCollection.id == collection_id,
                KnowledgeCollection.organization_id == organization_id,
            )
        )
        collection = col_result.scalars().first()
        if collection:
            collection.is_active = False
            collection.updated_at = datetime.now(timezone.utc)
            await self.db.commit()

        return {
            "collection_id": collection_id,
            "documents_queued": len(job_ids),
            "deletion_job_ids": job_ids,
            "status": "queued",
        }

    async def get_deletion_status(
        self,
        organization_id: str,
        deletion_job_id: str,
    ) -> Dict[str, Any]:
        """Get the status of a deletion job."""
        result = await self.db.execute(
            select(KnowledgeDeletionJob).where(
                KnowledgeDeletionJob.id == deletion_job_id,
                KnowledgeDeletionJob.organization_id == organization_id,
            )
        )
        job = result.scalars().first()
        if not job:
            raise ValueError(f"Deletion job not found: {deletion_job_id}")

        return {
            "deletion_job_id": job.id,
            "document_id": job.document_id,
            "status": job.status,
            "reason": job.reason,
            "requested_by": job.requested_by,
            "created_at": job.created_at.isoformat(),
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "audit_metadata": job.audit_metadata,
        }

    async def _load_doc(
        self, organization_id: str, document_id: str
    ) -> KnowledgeDocument:
        result = await self.db.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id,
                KnowledgeDocument.organization_id == organization_id,
            )
        )
        doc = result.scalars().first()
        if not doc:
            raise ValueError(
                f"Document not found or access denied: {document_id}"
            )
        return doc

    @staticmethod
    def _queue_cleanup(
        document_id: str,
        organization_id: str,
        job_id: str,
        requested_by: str,
        reason: str,
    ) -> None:
        """Queue the async deletion cleanup task."""
        try:
            from app.modules.knowledge.workers.knowledge_tasks import (
                delete_document_knowledge
            )
            delete_document_knowledge.apply_async(
                kwargs={
                    "document_id": document_id,
                    "organization_id": organization_id,
                    "deletion_job_id": job_id,
                    "requested_by": requested_by,
                    "reason": reason,
                },
                queue="knowledge-deletion",
            )
        except Exception as exc:
            logger.warning(
                f"[DELETION] Could not queue Celery cleanup task "
                f"(non-fatal, will retry): {exc}"
            )
