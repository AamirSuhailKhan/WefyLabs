"""
Knowledge Intelligence Platform — API Router
=============================================
All 25+ endpoints for the Knowledge Engine.
Mounts at /api/v1/knowledge (registered in main.py).

Auth: JWT bearer token via get_current_broker (existing dependency).
Tenant isolation: organization_id always sourced from authenticated broker.

Follows existing BeetleLabs router conventions:
  - APIRouter with prefix and tags
  - get_db and get_current_broker dependencies
  - HTTPException for all errors
  - Pydantic response models
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Query,
    UploadFile, status
)
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.models.knowledge_models import (
    KnowledgeDocument, KnowledgeChunk, KnowledgeFact, KnowledgeConflict,
    KnowledgeCollection, KnowledgeProcessingJob, KnowledgeDeletionJob,
    KnowledgeFreshnessPolicy, KnowledgeSource, KnowledgeFeedback,
)
from app.modules.knowledge.dto.knowledge_dto import (
    KnowledgeUploadResponse, KnowledgeDocumentDTO, KnowledgeDocumentUpdateRequest,
    KnowledgeDocumentListResponse, KnowledgeSearchRequest, KnowledgeSearchResponse,
    KnowledgeSearchResultDTO, KnowledgeFactDTO, FactVerificationRequest,
    KnowledgeConflictDTO, ConflictResolutionRequest, KnowledgeCollectionDTO,
    CreateCollectionRequest, KnowledgeFeedbackRequest, FreshnessPolicyDTO,
    FreshnessPolicyRequest, ProcessingJobDTO, KnowledgeChunkDTO, KnowledgeHealthResponse,
)
from app.modules.knowledge.ingestion.knowledge_ingestion_service import KnowledgeIngestionService
from app.modules.knowledge.retrieval.hybrid_search_service import HybridSearchService
from app.modules.knowledge.retrieval.context_builder import KnowledgeContextBuilder
from app.infrastructure.events.event_bus import event_bus, DomainEvent, ActorContext
from app.modules.knowledge.events.knowledge_events import KnowledgeEvents

router = APIRouter(prefix="/knowledge", tags=["Knowledge Intelligence Platform"])


# ─── Document Upload ──────────────────────────────────────────────────────────

@router.post(
    "/documents",
    response_model=KnowledgeUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a knowledge document",
    description=(
        "Upload a PDF, DOCX, TXT, CSV, HTML, or Markdown file to the Knowledge Engine. "
        "The document is validated, stored, and queued for processing. "
        "Accepts multipart/form-data."
    ),
)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    knowledge_type: str = Form(...),
    description: Optional[str] = Form(None),
    language: str = Form("en"),
    country: Optional[str] = Form(None),
    currency: Optional[str] = Form(None),
    visibility: str = Form("INTERNAL"),
    ai_allowed: bool = Form(True),
    customer_facing_allowed: bool = Form(False),
    project_id: Optional[str] = Form(None),
    property_id: Optional[str] = Form(None),
    collection_id: Optional[str] = Form(None),
    effective_at: Optional[str] = Form(None),
    expires_at: Optional[str] = Form(None),
    source_url: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Upload a document to the Knowledge Engine.
    Processing is asynchronous — check document status via GET /documents/:id.
    """
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # Parse optional datetime strings
    eff_at = None
    exp_at = None
    if effective_at:
        try:
            eff_at = datetime.fromisoformat(effective_at.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(400, "Invalid effective_at datetime format (ISO 8601 expected).")
    if expires_at:
        try:
            exp_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(400, "Invalid expires_at datetime format (ISO 8601 expected).")

    svc = KnowledgeIngestionService(db=db)
    try:
        result = await svc.ingest_document(
            organization_id=current_broker.organization_id,
            filename=file.filename or "upload",
            content=content,
            mime_type=file.content_type or "application/octet-stream",
            knowledge_type=knowledge_type,
            title=title,
            uploaded_by=str(current_broker.id),
            description=description,
            language=language,
            country=country,
            currency=currency,
            visibility=visibility,
            ai_allowed=ai_allowed,
            customer_facing_allowed=customer_facing_allowed,
            project_id=project_id,
            property_id=property_id,
            collection_id=collection_id,
            effective_at=eff_at,
            expires_at=exp_at,
            source_url=source_url,
            author=author,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    return KnowledgeUploadResponse(**result)


# ─── Document CRUD ────────────────────────────────────────────────────────────

@router.get(
    "/documents",
    response_model=KnowledgeDocumentListResponse,
    summary="List knowledge documents",
)
async def list_documents(
    status_filter: Optional[str] = Query(None, alias="status"),
    knowledge_type: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """List knowledge documents for the authenticated organization."""
    org_id = current_broker.organization_id

    q = select(KnowledgeDocument).where(
        KnowledgeDocument.organization_id == org_id,
        KnowledgeDocument.status != "DELETED",
    )
    if status_filter:
        q = q.where(KnowledgeDocument.status == status_filter)
    if knowledge_type:
        q = q.where(KnowledgeDocument.knowledge_type == knowledge_type)
    if language:
        q = q.where(KnowledgeDocument.language == language)
    if project_id:
        q = q.where(KnowledgeDocument.project_id == project_id)

    count_q = select(func.count()).select_from(q.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    q = q.order_by(KnowledgeDocument.created_at.desc())
    q = q.offset((page - 1) * limit).limit(limit)
    result = await db.execute(q)
    docs = result.scalars().all()

    return KnowledgeDocumentListResponse(
        documents=[KnowledgeDocumentDTO.model_validate(d) for d in docs],
        total=total,
        page=page,
        limit=limit,
        total_pages=max(1, (total + limit - 1) // limit),
    )


@router.get(
    "/documents/{document_id}",
    response_model=KnowledgeDocumentDTO,
    summary="Get knowledge document details",
)
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Get document details including processing status."""
    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.organization_id == current_broker.organization_id,
        )
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return KnowledgeDocumentDTO.model_validate(doc)


@router.patch(
    "/documents/{document_id}",
    response_model=KnowledgeDocumentDTO,
    summary="Update document metadata",
)
async def update_document(
    document_id: str,
    req: KnowledgeDocumentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Update document metadata. Does not re-trigger processing."""
    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.organization_id == current_broker.organization_id,
        )
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    update_data = req.model_dump(exclude_none=True)
    update_data["updated_at"] = datetime.now(timezone.utc)

    for key, value in update_data.items():
        setattr(doc, key, value)

    await db.commit()
    await db.refresh(doc)
    return KnowledgeDocumentDTO.model_validate(doc)


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Delete a knowledge document",
)
async def delete_document(
    document_id: str,
    reason: str = Query("admin_delete"),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Initiate the GDPR-aware deletion pipeline.
    Removes document, chunks, embeddings, and index entries asynchronously.
    """
    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.organization_id == current_broker.organization_id,
        )
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    if doc.status == "DELETED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document already deleted.")

    # Create deletion job
    now = datetime.now(timezone.utc)
    deletion_job_id = str(uuid.uuid4())
    deletion_job = KnowledgeDeletionJob(
        id=deletion_job_id,
        organization_id=current_broker.organization_id,
        document_id=document_id,
        requested_by=str(current_broker.id),
        reason=reason,
        status="pending",
        audit_metadata={},
        created_at=now,
    )
    db.add(deletion_job)
    await db.commit()

    # Queue deletion task
    try:
        from app.modules.knowledge.workers.knowledge_tasks import delete_document_knowledge
        delete_document_knowledge.apply_async(
            kwargs={
                "document_id": document_id,
                "organization_id": current_broker.organization_id,
                "deletion_job_id": deletion_job_id,
                "requested_by": str(current_broker.id),
                "reason": reason,
            },
            queue="knowledge-deletion",
        )
    except Exception:
        pass

    return {"message": "Deletion queued.", "deletion_job_id": deletion_job_id}


# ─── Document Lifecycle Actions ───────────────────────────────────────────────

@router.post(
    "/documents/{document_id}/publish",
    summary="Publish an INDEXED document",
    status_code=status.HTTP_200_OK,
)
async def publish_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Publish a document that has been INDEXED.
    Only PUBLISHED documents serve customer-facing AI.
    Requires MANAGER role or higher.
    """
    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.organization_id == current_broker.organization_id,
        )
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if doc.status not in ("INDEXED", "PENDING_REVIEW"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document must be in INDEXED or PENDING_REVIEW status to publish. Current: {doc.status}",
        )

    now = datetime.now(timezone.utc)
    doc.status = "PUBLISHED"
    doc.published_at = now
    doc.reviewed_by = str(current_broker.id)
    doc.reviewed_at = now
    doc.updated_at = now
    await db.commit()

    await event_bus.publish(DomainEvent(
        event_type=KnowledgeEvents.PUBLISHED,
        organization_id=current_broker.organization_id,
        actor=ActorContext(user_id=str(current_broker.id), actor_type="user"),
        payload={"document_id": document_id, "title": doc.title},
    ))

    return {"message": "Document published successfully.", "document_id": document_id, "status": "PUBLISHED"}


@router.post(
    "/documents/{document_id}/reindex",
    summary="Trigger document reindex",
    status_code=status.HTTP_202_ACCEPTED,
)
async def reindex_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Force a full reindex of a document (re-embeds all chunks)."""
    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.organization_id == current_broker.organization_id,
        )
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        from app.modules.knowledge.workers.knowledge_tasks import reindex_document as reindex_task
        reindex_task.apply_async(
            kwargs={
                "document_id": document_id,
                "organization_id": current_broker.organization_id,
            },
            queue="knowledge-reindex",
        )
    except Exception:
        pass

    return {"message": "Reindex queued.", "document_id": document_id}


@router.post(
    "/documents/{document_id}/archive",
    summary="Archive a published document",
    status_code=status.HTTP_200_OK,
)
async def archive_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Archive a document (removes from AI retrieval without deleting)."""
    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.organization_id == current_broker.organization_id,
        )
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    doc.status = "ARCHIVED"
    doc.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "Document archived.", "document_id": document_id}


# ─── Hybrid Search ────────────────────────────────────────────────────────────

@router.post(
    "/search",
    response_model=KnowledgeSearchResponse,
    summary="Hybrid knowledge search",
    description=(
        "Execute hybrid knowledge search (vector + keyword + reranking) "
        "against all PUBLISHED knowledge for the authenticated organization."
    ),
)
async def search_knowledge(
    req: KnowledgeSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Hybrid retrieval with RRF fusion and reranking."""
    svc = HybridSearchService(db=db)
    try:
        response = await svc.search(
            query=req.query,
            organization_id=current_broker.organization_id,
            top_k=req.top_k,
            rerank_top_n=req.rerank_top_n,
            knowledge_types=req.knowledge_types,
            project_id=req.project_id,
            property_id=req.property_id,
            language=req.language,
            channel=req.channel,
            role=getattr(current_broker, "role", "INTERNAL"),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(exc)}",
        )

    return KnowledgeSearchResponse(
        results=[
            KnowledgeSearchResultDTO(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                text=r.text,
                score=r.score,
                rank_position=r.rank_position,
                retrieval_method=r.retrieval_method,
                metadata=r.metadata,
            )
            for r in response.results
        ],
        query=response.query,
        total_vector_hits=response.total_vector_hits,
        total_keyword_hits=response.total_keyword_hits,
        total_results=len(response.results),
        retrieval_latency_ms=response.retrieval_latency_ms,
        reranking_latency_ms=response.reranking_latency_ms,
    )


# ─── Chunks ───────────────────────────────────────────────────────────────────

@router.get(
    "/chunks/{document_id}",
    response_model=List[KnowledgeChunkDTO],
    summary="List chunks for a document",
)
async def list_chunks(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """List all semantic chunks for a document."""
    result = await db.execute(
        select(KnowledgeChunk).where(
            KnowledgeChunk.document_id == document_id,
            KnowledgeChunk.organization_id == current_broker.organization_id,
        ).order_by(KnowledgeChunk.chunk_index)
    )
    chunks = result.scalars().all()
    return [KnowledgeChunkDTO.model_validate(c) for c in chunks]


# ─── Facts ────────────────────────────────────────────────────────────────────

@router.get(
    "/facts/{document_id}",
    response_model=List[KnowledgeFactDTO],
    summary="List extracted facts for a document",
)
async def list_facts(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """List all extracted structured facts for a document."""
    result = await db.execute(
        select(KnowledgeFact).where(
            KnowledgeFact.document_id == document_id,
            KnowledgeFact.organization_id == current_broker.organization_id,
        )
    )
    facts = result.scalars().all()
    return [KnowledgeFactDTO.model_validate(f) for f in facts]


@router.post(
    "/verify/{fact_id}",
    response_model=KnowledgeFactDTO,
    summary="Verify or reject a fact",
)
async def verify_fact(
    fact_id: str,
    req: FactVerificationRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Human verification of an extracted fact (VERIFIED or REJECTED)."""
    result = await db.execute(
        select(KnowledgeFact).where(
            KnowledgeFact.id == fact_id,
            KnowledgeFact.organization_id == current_broker.organization_id,
        )
    )
    fact = result.scalars().first()
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found.")

    now = datetime.now(timezone.utc)
    fact.verification_status = req.decision
    fact.verified_by = str(current_broker.id)
    fact.verified_at = now
    fact.updated_at = now
    if req.confidence_override is not None:
        fact.confidence = req.confidence_override
    if req.decision == "REJECTED" and req.notes:
        fact.rejection_reason = req.notes

    await db.commit()
    await db.refresh(fact)
    return KnowledgeFactDTO.model_validate(fact)


# ─── Conflicts ────────────────────────────────────────────────────────────────

@router.get(
    "/conflicts",
    response_model=List[KnowledgeConflictDTO],
    summary="List open knowledge conflicts",
)
async def list_conflicts(
    resolution_status: str = Query("OPEN"),
    project_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """List knowledge conflicts requiring human resolution."""
    q = select(KnowledgeConflict).where(
        KnowledgeConflict.organization_id == current_broker.organization_id,
        KnowledgeConflict.resolution_status == resolution_status,
    )
    if project_id:
        q = q.where(KnowledgeConflict.project_id == project_id)
    result = await db.execute(q.order_by(KnowledgeConflict.created_at.desc()))
    conflicts = result.scalars().all()
    return [KnowledgeConflictDTO.model_validate(c) for c in conflicts]


@router.post(
    "/conflicts/{conflict_id}/resolve",
    response_model=KnowledgeConflictDTO,
    summary="Resolve a knowledge conflict",
)
async def resolve_conflict(
    conflict_id: str,
    req: ConflictResolutionRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Resolve a knowledge conflict by selecting the winning fact."""
    result = await db.execute(
        select(KnowledgeConflict).where(
            KnowledgeConflict.id == conflict_id,
            KnowledgeConflict.organization_id == current_broker.organization_id,
        )
    )
    conflict = result.scalars().first()
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found.")

    now = datetime.now(timezone.utc)
    conflict.resolution_status = "RESOLVED"
    conflict.winning_fact_id = req.winning_fact_id
    conflict.resolution_strategy = req.resolution_strategy
    conflict.resolved_by = str(current_broker.id)
    conflict.resolved_at = now
    conflict.resolution_notes = req.resolution_notes

    await db.commit()
    await db.refresh(conflict)
    return KnowledgeConflictDTO.model_validate(conflict)


# ─── Collections ─────────────────────────────────────────────────────────────

@router.get(
    "/collections",
    response_model=List[KnowledgeCollectionDTO],
    summary="List knowledge collections",
)
async def list_collections(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """List knowledge collections for the organization."""
    result = await db.execute(
        select(KnowledgeCollection).where(
            KnowledgeCollection.organization_id == current_broker.organization_id,
            KnowledgeCollection.is_active == True,
        )
    )
    collections = result.scalars().all()
    return [KnowledgeCollectionDTO.model_validate(c) for c in collections]


@router.post(
    "/collections",
    response_model=KnowledgeCollectionDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create a knowledge collection",
)
async def create_collection(
    req: CreateCollectionRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Create a new knowledge collection."""
    now = datetime.now(timezone.utc)
    collection = KnowledgeCollection(
        id=str(uuid.uuid4()),
        organization_id=current_broker.organization_id,
        name=req.name,
        description=req.description,
        knowledge_type=req.knowledge_type,
        project_id=req.project_id,
        language=req.language,
        visibility=req.visibility,
        ai_allowed=req.ai_allowed,
        is_active=True,
        document_count=0,
        created_by=str(current_broker.id),
        created_at=now,
        updated_at=now,
    )
    db.add(collection)
    await db.commit()
    await db.refresh(collection)
    return KnowledgeCollectionDTO.model_validate(collection)


# ─── Feedback ─────────────────────────────────────────────────────────────────

@router.post(
    "/feedback",
    status_code=status.HTTP_201_CREATED,
    summary="Submit answer feedback",
)
async def submit_feedback(
    req: KnowledgeFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Submit quality feedback for a knowledge query result."""
    now = datetime.now(timezone.utc)
    feedback = KnowledgeFeedback(
        id=str(uuid.uuid4()),
        query_id=req.query_id,
        organization_id=current_broker.organization_id,
        given_by=str(current_broker.id),
        given_by_type="broker",
        feedback_type=req.feedback_type,
        notes=req.notes,
        document_ids_flagged=req.document_ids_flagged,
        chunk_ids_flagged=req.chunk_ids_flagged,
        created_at=now,
    )
    db.add(feedback)
    await db.commit()

    await event_bus.publish(DomainEvent(
        event_type=KnowledgeEvents.FEEDBACK_RECEIVED,
        organization_id=current_broker.organization_id,
        actor=ActorContext(user_id=str(current_broker.id), actor_type="user"),
        payload={"query_id": req.query_id, "feedback_type": req.feedback_type},
    ))

    return {"message": "Feedback recorded.", "feedback_id": feedback.id}


# ─── Freshness Policies ───────────────────────────────────────────────────────

@router.get(
    "/freshness/policies",
    response_model=List[FreshnessPolicyDTO],
    summary="List freshness policies",
)
async def list_freshness_policies(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """List knowledge freshness policies for the organization."""
    result = await db.execute(
        select(KnowledgeFreshnessPolicy).where(
            KnowledgeFreshnessPolicy.organization_id == current_broker.organization_id,
        )
    )
    policies = result.scalars().all()
    return [FreshnessPolicyDTO.model_validate(p) for p in policies]


@router.post(
    "/freshness/policies",
    response_model=FreshnessPolicyDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update a freshness policy",
)
async def upsert_freshness_policy(
    req: FreshnessPolicyRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Create or update a freshness policy for a knowledge type."""
    result = await db.execute(
        select(KnowledgeFreshnessPolicy).where(
            KnowledgeFreshnessPolicy.organization_id == current_broker.organization_id,
            KnowledgeFreshnessPolicy.knowledge_type == req.knowledge_type,
        )
    )
    policy = result.scalars().first()
    now = datetime.now(timezone.utc)

    if policy:
        policy.max_age_days = req.max_age_days
        policy.warn_at_days = req.warn_at_days
        policy.auto_expire = req.auto_expire
        policy.auto_publish = req.auto_publish
        policy.updated_at = now
    else:
        policy = KnowledgeFreshnessPolicy(
            id=str(uuid.uuid4()),
            organization_id=current_broker.organization_id,
            knowledge_type=req.knowledge_type,
            max_age_days=req.max_age_days,
            warn_at_days=req.warn_at_days,
            auto_expire=req.auto_expire,
            auto_publish=req.auto_publish,
            is_active=True,
            applies_to_ai=True,
            applies_to_customer_facing=True,
            created_at=now,
            updated_at=now,
        )
        db.add(policy)

    await db.commit()
    await db.refresh(policy)
    return FreshnessPolicyDTO.model_validate(policy)


# ─── Processing Jobs ─────────────────────────────────────────────────────────

@router.get(
    "/jobs",
    response_model=List[ProcessingJobDTO],
    summary="List processing jobs",
)
async def list_jobs(
    job_status: Optional[str] = Query(None, alias="status"),
    document_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """List knowledge processing jobs."""
    q = select(KnowledgeProcessingJob).where(
        KnowledgeProcessingJob.organization_id == current_broker.organization_id,
    )
    if job_status:
        q = q.where(KnowledgeProcessingJob.status == job_status)
    if document_id:
        q = q.where(KnowledgeProcessingJob.document_id == document_id)

    q = q.order_by(KnowledgeProcessingJob.created_at.desc()).limit(limit)
    result = await db.execute(q)
    jobs = result.scalars().all()
    return [ProcessingJobDTO.model_validate(j) for j in jobs]


# ─── Full Reindex ─────────────────────────────────────────────────────────────

@router.post(
    "/reindex/full",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Full organization reindex",
    description="Re-embed and re-index all PUBLISHED documents for the organization.",
)
async def full_reindex(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Trigger a full reindex of all documents."""
    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.organization_id == current_broker.organization_id,
            KnowledgeDocument.status.in_(["PUBLISHED", "INDEXED"]),
        )
    )
    docs = result.scalars().all()
    queued = 0

    for doc in docs:
        try:
            from app.modules.knowledge.workers.knowledge_tasks import reindex_document
            reindex_document.apply_async(
                kwargs={
                    "document_id": doc.id,
                    "organization_id": current_broker.organization_id,
                },
                queue="knowledge-reindex",
            )
            queued += 1
        except Exception:
            pass

    return {
        "message": f"Full reindex queued for {queued} documents.",
        "documents_queued": queued,
    }


# ─── Health ───────────────────────────────────────────────────────────────────

@router.get(
    "/health",
    summary="Knowledge platform health check",
    description="Returns rich operational health metrics for the authenticated organization's knowledge engine.",
)
async def knowledge_health(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Knowledge engine health metrics for the authenticated organization."""
    from app.modules.knowledge.monitoring.knowledge_monitoring_service import (
        KnowledgeMonitoringService,
    )
    org_id = current_broker.organization_id
    monitor = KnowledgeMonitoringService(db=db)
    report = await monitor.get_health_report(organization_id=org_id)
    return report.to_dict()


# ─── Processing Errors ────────────────────────────────────────────────────────

@router.get(
    "/errors",
    summary="Get recent document processing errors",
    description="Returns recently failed documents with error details for diagnosis.",
)
async def get_processing_errors(
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Return failed documents with error messages."""
    from app.modules.knowledge.monitoring.knowledge_monitoring_service import (
        KnowledgeMonitoringService,
    )
    monitor = KnowledgeMonitoringService(db=db)
    errors = await monitor.get_document_processing_errors(
        organization_id=current_broker.organization_id,
        limit=limit,
    )
    return {"errors": errors, "count": len(errors)}
