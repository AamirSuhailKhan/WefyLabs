"""
Knowledge Document Ingestion Service
======================================
Handles the entry point of the document ingestion pipeline:
  Upload → Validate → Virus Scan → Store → Create Document Record
  → Create Version → Queue Processing Job → Emit Event

Reuses existing:
  - FileSecurityScanner (MIME, magic bytes, extension, size)
  - AuditLogService (audit trail)
  - DomainEventBus (KnowledgeUploaded event)
  - TimelineEvent (document lifecycle timeline)

Every document gets:
  - Unique document ID
  - Version 1 record
  - SHA-256 checksum
  - Processing job queued
  - Audit log entry

Status: UPLOADED (initial) → processing pipeline takes over.
"""
from __future__ import annotations

import hashlib
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.knowledge_models import (
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    KnowledgeProcessingJob,
    KnowledgeSource,
)
from app.modules.knowledge.ingestion.storage_service import (
    StorageProvider, get_storage_provider
)
from app.modules.security.services.file_security import FileSecurityScanner
from app.infrastructure.events.event_bus import event_bus, DomainEvent, ActorContext
from app.modules.knowledge.events.knowledge_events import KnowledgeEvents

logger = logging.getLogger(__name__)


class KnowledgeIngestionService:
    """
    Document ingestion entry-point service.
    Orchestrates security scanning, storage, DB record creation,
    version management, and pipeline job dispatch.
    """

    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/csv",
        "text/html",
        "text/markdown",
        "text/x-markdown",
        "application/csv",
        "image/jpeg",
        "image/png",
        "image/tiff",
    }

    def __init__(
        self,
        db: AsyncSession,
        storage: Optional[StorageProvider] = None,
    ):
        self.db = db
        self.storage = storage or get_storage_provider(
            "local"  # Override via env: KNOWLEDGE_STORAGE_PROVIDER
        )

    async def ingest_document(
        self,
        organization_id: str,
        filename: str,
        content: bytes,
        mime_type: str,
        knowledge_type: str,
        title: str,
        uploaded_by: str,
        source_id: Optional[str] = None,
        project_id: Optional[str] = None,
        property_id: Optional[str] = None,
        collection_id: Optional[str] = None,
        language: str = "en",
        country: Optional[str] = None,
        currency: Optional[str] = None,
        visibility: str = "INTERNAL",
        ai_allowed: bool = True,
        customer_facing_allowed: bool = False,
        effective_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        description: Optional[str] = None,
        author: Optional[str] = None,
        source_url: Optional[str] = None,
        change_summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ingest a new document into the Knowledge Engine.

        Returns:
            {
                "document_id": str,
                "version_id": str,
                "status": "UPLOADED",
                "job_id": str,
                "message": str,
            }

        Raises:
            ValueError: if security scan fails or MIME type not supported.
        """
        start = time.monotonic()
        doc_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())

        # ── 1. Security Scan (reuses existing FileSecurityScanner) ───────────
        passed, reason = FileSecurityScanner.scan_file(filename, content)
        if not passed:
            logger.warning(
                f"[INGEST] Security scan failed: org={organization_id} "
                f"file={filename} reason={reason}"
            )
            raise ValueError(f"Document rejected by security scanner: {reason}")

        # ── 2. Virus Scan Hook ───────────────────────────────────────────────
        virus_clean = FileSecurityScanner.virus_scan(content)
        if not virus_clean:
            raise ValueError("Document failed virus scan.")

        # ── 3. Validate MIME type ────────────────────────────────────────────
        if mime_type not in self.ALLOWED_MIME_TYPES:
            raise ValueError(
                f"MIME type '{mime_type}' is not supported for knowledge ingestion."
            )

        # ── 4. Compute checksum ──────────────────────────────────────────────
        checksum = hashlib.sha256(content).hexdigest()

        # ── 5. Check for duplicate (same org + same checksum) ────────────────
        existing = await self._find_by_checksum(organization_id, checksum)
        if existing:
            logger.info(
                f"[INGEST] Duplicate document detected: org={organization_id} "
                f"checksum={checksum[:16]} existing_id={existing.id}"
            )
            return {
                "document_id": existing.id,
                "version_id": existing.current_version_id,
                "status": existing.status,
                "job_id": None,
                "message": "Document already exists (duplicate checksum). Existing document returned.",
                "is_duplicate": True,
            }

        # ── 6. Determine version number ──────────────────────────────────────
        # For new documents: version 1. For re-uploads with same title: increment.
        version_number = 1

        # ── 7. Store file ────────────────────────────────────────────────────
        storage_key = self.storage.make_storage_key(
            organization_id, doc_id, version_number, filename
        )
        await self.storage.store(content, storage_key)

        # ── 8. Create KnowledgeDocument record ───────────────────────────────
        now = datetime.now(timezone.utc)
        doc = KnowledgeDocument(
            id=doc_id,
            organization_id=organization_id,
            source_id=source_id,
            project_id=project_id,
            property_id=property_id,
            collection_id=collection_id,
            current_version_id=version_id,
            title=title,
            description=description,
            file_name=filename,
            file_size_bytes=len(content),
            mime_type=mime_type,
            file_type=self._detect_file_type(mime_type, filename),
            storage_key=storage_key,
            storage_provider=self.storage.provider_name,
            checksum_sha256=checksum,
            status="UPLOADED",
            knowledge_type=knowledge_type,
            language=language,
            country=country,
            currency=currency,
            visibility=visibility,
            ai_allowed=ai_allowed,
            customer_facing_allowed=customer_facing_allowed,
            effective_at=effective_at,
            expires_at=expires_at,
            author=author,
            uploaded_by=uploaded_by,
            source_url=source_url,
            created_at=now,
            updated_at=now,
        )
        self.db.add(doc)

        # ── 9. Create version record ─────────────────────────────────────────
        version = KnowledgeDocumentVersion(
            id=version_id,
            document_id=doc_id,
            organization_id=organization_id,
            version_number=version_number,
            checksum_sha256=checksum,
            storage_key=storage_key,
            file_size_bytes=len(content),
            effective_at=effective_at,
            expires_at=expires_at,
            change_summary=change_summary or "Initial upload",
            source_url=source_url,
            created_by=uploaded_by,
            is_active=True,
            previous_version_id=None,
            status="active",
            created_at=now,
        )
        self.db.add(version)

        # ── 10. Create processing job ────────────────────────────────────────
        job_id = str(uuid.uuid4())
        idem_key = f"parse:{doc_id}:v{version_number}"
        job = KnowledgeProcessingJob(
            id=job_id,
            organization_id=organization_id,
            document_id=doc_id,
            job_type="parse",
            status="pending",
            retry_count=0,
            max_retries=3,
            result_summary={},
            idempotency_key=idem_key,
            priority=5,
            created_at=now,
        )
        self.db.add(job)

        await self.db.commit()

        # ── 11. Queue Celery task ─────────────────────────────────────────────
        try:
            from app.modules.knowledge.workers.knowledge_tasks import process_document
            process_document.apply_async(
                kwargs={
                    "document_id": doc_id,
                    "organization_id": organization_id,
                    "job_id": job_id,
                },
                queue="knowledge-parser",
                task_id=job_id,
                countdown=0,
            )
        except Exception as exc:
            # Celery may not be running in test environments
            logger.warning(
                f"[INGEST] Could not queue Celery task (non-fatal): {exc}"
            )

        # ── 12. Emit domain event ────────────────────────────────────────────
        await event_bus.publish(DomainEvent(
            event_type=KnowledgeEvents.UPLOADED,
            organization_id=organization_id,
            actor=ActorContext(user_id=uploaded_by, actor_type="user"),
            payload={
                "document_id": doc_id,
                "version_id": version_id,
                "title": title,
                "knowledge_type": knowledge_type,
                "file_name": filename,
                "file_size_bytes": len(content),
            },
        ))

        latency_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            f"[INGEST SUCCESS] doc={doc_id} org={organization_id} "
            f"type={knowledge_type} {latency_ms}ms"
        )

        return {
            "document_id": doc_id,
            "version_id": version_id,
            "status": "UPLOADED",
            "job_id": job_id,
            "message": "Document uploaded successfully. Processing queued.",
            "is_duplicate": False,
        }

    async def create_new_version(
        self,
        organization_id: str,
        document_id: str,
        filename: str,
        content: bytes,
        mime_type: str,
        uploaded_by: str,
        change_summary: str,
        effective_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Upload a new version of an existing document.
        Archives the current version, creates a new active version.
        """
        # Load existing document
        doc = await self.db.get(KnowledgeDocument, document_id)
        if not doc or doc.organization_id != organization_id:
            raise ValueError("Document not found or access denied.")

        # Security checks
        passed, reason = FileSecurityScanner.scan_file(filename, content)
        if not passed:
            raise ValueError(f"Security scan failed: {reason}")

        checksum = hashlib.sha256(content).hexdigest()
        now = datetime.now(timezone.utc)

        # Get next version number
        result = await self.db.execute(
            select(func.max(KnowledgeDocumentVersion.version_number)).where(
                KnowledgeDocumentVersion.document_id == document_id
            )
        )
        max_version = result.scalar() or 0
        new_version_num = max_version + 1

        # Archive current version
        if doc.current_version_id:
            current = await self.db.get(KnowledgeDocumentVersion, doc.current_version_id)
            if current:
                current.is_active = False
                current.status = "archived"

        # Store new file
        storage_key = self.storage.make_storage_key(
            organization_id, document_id, new_version_num, filename
        )
        await self.storage.store(content, storage_key)

        # Create new version
        new_version_id = str(uuid.uuid4())
        new_version = KnowledgeDocumentVersion(
            id=new_version_id,
            document_id=document_id,
            organization_id=organization_id,
            version_number=new_version_num,
            checksum_sha256=checksum,
            storage_key=storage_key,
            file_size_bytes=len(content),
            effective_at=effective_at,
            expires_at=expires_at,
            change_summary=change_summary,
            created_by=uploaded_by,
            is_active=True,
            previous_version_id=doc.current_version_id,
            status="active",
            created_at=now,
        )
        self.db.add(new_version)

        # Update document
        doc.current_version_id = new_version_id
        doc.checksum_sha256 = checksum
        doc.storage_key = storage_key
        doc.file_size_bytes = len(content)
        doc.status = "UPLOADED"
        doc.updated_at = now
        if effective_at:
            doc.effective_at = effective_at
        if expires_at:
            doc.expires_at = expires_at

        # Queue processing job for new version
        job_id = str(uuid.uuid4())
        job = KnowledgeProcessingJob(
            id=job_id,
            organization_id=organization_id,
            document_id=document_id,
            job_type="parse",
            status="pending",
            retry_count=0,
            max_retries=3,
            result_summary={},
            idempotency_key=f"parse:{document_id}:v{new_version_num}",
            priority=5,
            created_at=now,
        )
        self.db.add(job)
        await self.db.commit()

        await event_bus.publish(DomainEvent(
            event_type=KnowledgeEvents.UPDATED,
            organization_id=organization_id,
            actor=ActorContext(user_id=uploaded_by, actor_type="user"),
            payload={
                "document_id": document_id,
                "version_id": new_version_id,
                "version_number": new_version_num,
                "change_summary": change_summary,
            },
        ))

        logger.info(
            f"[INGEST VERSION] doc={document_id} v{new_version_num} "
            f"org={organization_id}"
        )
        return {
            "document_id": document_id,
            "version_id": new_version_id,
            "version_number": new_version_num,
            "status": "UPLOADED",
            "job_id": job_id,
            "message": f"Version {new_version_num} uploaded successfully. Processing queued.",
        }

    async def _find_by_checksum(
        self, organization_id: str, checksum: str
    ) -> Optional[KnowledgeDocument]:
        """Check if a document with this checksum already exists for this org."""
        result = await self.db.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.organization_id == organization_id,
                KnowledgeDocument.checksum_sha256 == checksum,
                KnowledgeDocument.status != "DELETED",
            )
        )
        return result.scalars().first()

    @staticmethod
    def _detect_file_type(mime_type: str, filename: str) -> str:
        """Map MIME type to short file_type label."""
        _MAP = {
            "application/pdf": "pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
            "text/plain": "txt",
            "text/csv": "csv",
            "text/html": "html",
            "text/markdown": "markdown",
            "text/x-markdown": "markdown",
            "image/jpeg": "image",
            "image/png": "image",
            "image/tiff": "image",
        }
        return _MAP.get(mime_type, "other")
