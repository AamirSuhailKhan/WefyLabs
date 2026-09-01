from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Request, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.common.response import APIResponse, create_success_response
from app.modules.ingestion.dto.canonical_lead_dto import IngestionRequestDTO, IngestionResponseDTO
from app.modules.ingestion.pipeline.ingestion_pipeline import LeadIngestionPipeline
from app.modules.ingestion.service.batch_importer_service import BatchImporterService
from app.modules.ingestion.service.dlq_service import DeadLetterQueueService
from app.modules.ingestion.connectors.connector_factory import CONNECTOR_REGISTRY

router = APIRouter(prefix="/v1/ingest", tags=["Universal Lead Ingestion Engine"])


@router.post("/lead", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def submit_lead(
    dto: IngestionRequestDTO,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Submits a single lead from any source into the ingestion pipeline."""
    org_id = str(getattr(current_broker, "organization_id", "") or str(current_broker.id))
    pipeline = LeadIngestionPipeline(db)
    result = await pipeline.ingest_lead(
        source=dto.source,
        raw_payload=dto.payload,
        organization_id=org_id,
        user_id=str(current_broker.id),
        idempotency_key=dto.idempotency_key or request.headers.get("X-Idempotency-Key"),
        headers=dict(request.headers),
    )
    return create_success_response(data=result.model_dump(), request_id=result.ingestion_id)


@router.post("/webhook/{connector_id}", response_model=APIResponse)
async def receive_webhook_lead(
    connector_id: str,
    raw_payload: dict,
    request: Request,
    source: str = Query(default="webhook"),
    org_id: str = Query(default="global"),
    db: AsyncSession = Depends(get_db),
):
    """Public webhook receiver endpoint for external integrations (Meta, Google, Zapier)."""
    pipeline = LeadIngestionPipeline(db)
    result = await pipeline.ingest_lead(
        source=source,
        raw_payload=raw_payload,
        organization_id=org_id,
        headers=dict(request.headers),
    )
    return create_success_response(data=result.model_dump(), request_id=result.ingestion_id)


@router.post("/import-file", response_model=APIResponse, status_code=status.HTTP_202_ACCEPTED)
async def import_lead_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Uploads CSV / Excel file for high-throughput batch lead ingestion."""
    org_id = str(getattr(current_broker, "organization_id", "") or str(current_broker.id))
    content = await file.read()
    svc = BatchImporterService(db)
    batch = await svc.create_batch_job(
        organization_id=org_id,
        user_id=str(current_broker.id),
        filename=file.filename or "import.csv",
        content=content,
    )
    return create_success_response(data={
        "batch_id": batch.id,
        "filename": batch.filename,
        "total_records": batch.total_records,
        "processed_records": batch.processed_records,
        "failed_records": batch.failed_records,
        "status": batch.status,
    })


@router.get("/imports", response_model=APIResponse)
async def list_import_batches(
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = str(getattr(current_broker, "organization_id", "") or str(current_broker.id))
    svc = BatchImporterService(db)
    batches = await svc.list_batches(organization_id=org_id, limit=limit)
    return create_success_response(data=[
        {
            "id": b.id,
            "filename": b.filename,
            "total_records": b.total_records,
            "processed_records": b.processed_records,
            "failed_records": b.failed_records,
            "duplicate_records": b.duplicate_records,
            "status": b.status,
            "started_at": b.started_at,
            "completed_at": b.completed_at,
        } for b in batches
    ])


@router.get("/imports/{batch_id}/items", response_model=APIResponse)
async def list_batch_items(
    batch_id: str,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    svc = BatchImporterService(db)
    items = await svc.get_batch_items(batch_id=batch_id, limit=limit)
    return create_success_response(data=[
        {
            "id": i.id,
            "row_index": i.row_index,
            "status": i.status,
            "error_message": i.error_message,
            "lead_id": i.lead_id,
            "raw_data": i.raw_data,
        } for i in items
    ])


@router.get("/dlq", response_model=APIResponse)
async def list_dlq_failed_items(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = str(getattr(current_broker, "organization_id", "") or str(current_broker.id))
    svc = DeadLetterQueueService(db)
    items = await svc.list_failed_items(organization_id=org_id, limit=limit)
    return create_success_response(data=[
        {
            "id": i.id,
            "batch_id": i.batch_id,
            "row_index": i.row_index,
            "error_message": i.error_message,
            "raw_data": i.raw_data,
        } for i in items
    ])


@router.post("/dlq/{item_id}/replay", response_model=APIResponse)
async def replay_dlq_item(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    svc = DeadLetterQueueService(db)
    res = await svc.replay_failed_item(item_id)
    return create_success_response(data=res.model_dump())


@router.get("/connectors", response_model=APIResponse)
async def list_registered_connectors(current_broker=Depends(get_current_broker)):
    """Returns all supported source connector adapters."""
    connectors = [
        {"source": k, "adapter": v.__name__} for k, v in CONNECTOR_REGISTRY.items()
    ]
    return create_success_response(data=connectors)
