"""
Part 21.2 — Real-Estate Lead Discovery Engine Router
=====================================================
FastAPI endpoints for AI Lead Discovery campaigns, runs, candidate review, and sources.

Security Rules:
  - organization_id from authenticated JWT broker context ONLY.
  - Strict tenant isolation across sources, campaigns, runs, candidates, and evidence.
  - Rate limiting & PII protection.
"""
from __future__ import annotations
import uuid
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.database import get_db
from app.dependencies import get_current_broker
from app.common.response import APIResponse, create_success_response
from app.models.discovery_models import (
    DiscoverySource, DiscoveryCampaign, DiscoveryRun, DiscoveryCandidate,
    DiscoveryCampaignStatus, DiscoveryRunStatus, CandidateStatus, ProviderStatus
)
from app.modules.discovery.dto.discovery_dto import (
    DiscoverySourceCreateDTO, DiscoverySourceUpdateDTO, DiscoverySourceResponseDTO,
    DiscoveryCampaignCreateDTO, DiscoveryCampaignUpdateDTO, DiscoveryCampaignResponseDTO,
    DiscoveryRunCreateDTO, DiscoveryRunResponseDTO,
    DiscoveryCandidateResponseDTO, CandidateApproveDTO, CandidateRejectDTO,
    DiscoveryEvidenceDTO, DiscoverySignalDTO, ProviderStatusDTO, DiscoveryDashboardMetricsDTO
)
from app.modules.discovery.service.discovery_source_service import DiscoverySourceService
from app.modules.discovery.service.discovery_campaign_service import DiscoveryCampaignService
from app.modules.discovery.service.discovery_run_service import DiscoveryRunService
from app.modules.discovery.service.discovery_candidate_service import DiscoveryCandidateService
from app.modules.discovery.service.evidence_signal_service import EvidenceSignalService
from app.modules.discovery.service.property_matching_service import PropertyMatchingService
from app.modules.discovery.connectors.provider_registry import DiscoveryProviderRegistry, get_discovery_provider
from app.modules.discovery.metrics.discovery_metrics import record_discovery_run, record_candidate_processed

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/discovery", tags=["AI Lead Discovery Engine"])


def _get_org_id(broker) -> str:
    org_id = getattr(broker, "organization_id", None)
    return str(org_id) if org_id else str(broker.id)


def _get_broker_uuid(broker) -> uuid.UUID:
    b_id = getattr(broker, "id", None)
    if isinstance(b_id, uuid.UUID):
        return b_id
    return uuid.UUID(str(b_id))


# ─── Sources ─────────────────────────────────────────────────────────────────

@router.post("/sources", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def create_discovery_source(
    dto: DiscoverySourceCreateDTO,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = _get_org_id(current_broker)
    svc = DiscoverySourceService(db)
    source = await svc.create_source(org_id, dto)
    return create_success_response(data=DiscoverySourceResponseDTO.model_validate(source).model_dump())


@router.get("/sources", response_model=APIResponse)
async def list_discovery_sources(
    provider: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = _get_org_id(current_broker)
    svc = DiscoverySourceService(db)
    sources = await svc.list_sources(org_id, provider=provider, source_type=source_type, status=status_filter)
    return create_success_response(data=[
        DiscoverySourceResponseDTO.model_validate(s).model_dump() for s in sources
    ])


@router.get("/sources/{source_id}", response_model=APIResponse)
async def get_discovery_source(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = _get_org_id(current_broker)
    svc = DiscoverySourceService(db)
    source = await svc.get_source(org_id, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Discovery source not found")
    return create_success_response(data=DiscoverySourceResponseDTO.model_validate(source).model_dump())


@router.put("/sources/{source_id}", response_model=APIResponse)
async def update_discovery_source(
    source_id: str,
    dto: DiscoverySourceUpdateDTO,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = _get_org_id(current_broker)
    svc = DiscoverySourceService(db)
    source = await svc.update_source(org_id, source_id, dto)
    if not source:
        raise HTTPException(status_code=404, detail="Discovery source not found")
    return create_success_response(data=DiscoverySourceResponseDTO.model_validate(source).model_dump())


# ─── Campaigns ───────────────────────────────────────────────────────────────

@router.post("/campaigns", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def create_discovery_campaign(
    dto: DiscoveryCampaignCreateDTO,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = _get_org_id(current_broker)
    svc = DiscoveryCampaignService(db)
    campaign = await svc.create_campaign(org_id, dto)
    return create_success_response(data=DiscoveryCampaignResponseDTO.model_validate(campaign).model_dump())


@router.get("/campaigns", response_model=APIResponse)
async def list_discovery_campaigns(
    status_filter: Optional[str] = Query(None, alias="status"),
    country_code: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = _get_org_id(current_broker)
    svc = DiscoveryCampaignService(db)
    campaigns = await svc.list_campaigns(org_id, status=status_filter, country_code=country_code)
    return create_success_response(data=[
        DiscoveryCampaignResponseDTO.model_validate(c).model_dump() for c in campaigns
    ])


@router.get("/campaigns/{campaign_id}", response_model=APIResponse)
async def get_discovery_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = _get_org_id(current_broker)
    svc = DiscoveryCampaignService(db)
    campaign = await svc.get_campaign(org_id, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Discovery campaign not found")
    return create_success_response(data=DiscoveryCampaignResponseDTO.model_validate(campaign).model_dump())


@router.put("/campaigns/{campaign_id}", response_model=APIResponse)
async def update_discovery_campaign(
    campaign_id: str,
    dto: DiscoveryCampaignUpdateDTO,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = _get_org_id(current_broker)
    svc = DiscoveryCampaignService(db)
    campaign = await svc.update_campaign(org_id, campaign_id, dto)
    if not campaign:
        raise HTTPException(status_code=404, detail="Discovery campaign not found")
    return create_success_response(data=DiscoveryCampaignResponseDTO.model_validate(campaign).model_dump())


@router.post("/campaigns/{campaign_id}/run", response_model=APIResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_discovery_campaign(
    campaign_id: str,
    dto: Optional[DiscoveryRunCreateDTO] = None,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Trigger an execution run of an AI discovery campaign."""
    org_id = _get_org_id(current_broker)
    camp_svc = DiscoveryCampaignService(db)
    campaign = await camp_svc.get_campaign(org_id, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Discovery campaign not found")

    run_svc = DiscoveryRunService(db)
    run = await run_svc.create_run(org_id, campaign, dto)
    record_discovery_run(org_id, "QUEUED")

    # Dispatch to Celery background worker
    try:
        from app.modules.discovery.workers.discovery_tasks import execute_discovery_run_task
        if callable(getattr(execute_discovery_run_task, "apply_async", None)):
            execute_discovery_run_task.apply_async(args=[org_id, run.id], countdown=1)
    except Exception as exc:
        logger.debug(f"[DISCOVERY] Async task dispatch skipped: {exc}")

    return create_success_response(data=DiscoveryRunResponseDTO.model_validate(run).model_dump())


@router.post("/campaigns/{campaign_id}/pause", response_model=APIResponse)
async def pause_discovery_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = _get_org_id(current_broker)
    svc = DiscoveryCampaignService(db)
    campaign = await svc.set_campaign_status(org_id, campaign_id, DiscoveryCampaignStatus.PAUSED)
    if not campaign:
        raise HTTPException(status_code=404, detail="Discovery campaign not found")
    return create_success_response(data=DiscoveryCampaignResponseDTO.model_validate(campaign).model_dump())


@router.post("/campaigns/{campaign_id}/resume", response_model=APIResponse)
async def resume_discovery_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = _get_org_id(current_broker)
    svc = DiscoveryCampaignService(db)
    campaign = await svc.set_campaign_status(org_id, campaign_id, DiscoveryCampaignStatus.ACTIVE)
    if not campaign:
        raise HTTPException(status_code=404, detail="Discovery campaign not found")
    return create_success_response(data=DiscoveryCampaignResponseDTO.model_validate(campaign).model_dump())


# ─── Discovery Runs ───────────────────────────────────────────────────────────

@router.get("/runs", response_model=APIResponse)
async def list_discovery_runs(
    campaign_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = _get_org_id(current_broker)
    svc = DiscoveryRunService(db)
    runs = await svc.list_runs(org_id, campaign_id=campaign_id, status=status_filter, limit=limit, offset=offset)
    return create_success_response(data=[
        DiscoveryRunResponseDTO.model_validate(r).model_dump() for r in runs
    ])


@router.get("/runs/{run_id}", response_model=APIResponse)
async def get_discovery_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = _get_org_id(current_broker)
    svc = DiscoveryRunService(db)
    run = await svc.get_run(org_id, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Discovery run not found")
    return create_success_response(data=DiscoveryRunResponseDTO.model_validate(run).model_dump())


# ─── Candidates ──────────────────────────────────────────────────────────────

@router.get("/candidates", response_model=APIResponse)
async def list_discovery_candidates(
    run_id: Optional[str] = Query(None),
    source_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    min_relevance: Optional[float] = Query(None, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = _get_org_id(current_broker)
    svc = DiscoveryCandidateService(db)
    candidates = await svc.list_candidates(
        org_id, run_id=run_id, source_id=source_id, status=status_filter,
        min_relevance=min_relevance, limit=limit, offset=offset
    )
    return create_success_response(data=[
        DiscoveryCandidateResponseDTO.model_validate(c).model_dump() for c in candidates
    ])


@router.get("/candidates/{candidate_id}", response_model=APIResponse)
async def get_discovery_candidate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = _get_org_id(current_broker)
    svc = DiscoveryCandidateService(db)
    cand = await svc.get_candidate(org_id, candidate_id)
    if not cand:
        raise HTTPException(status_code=404, detail="Discovery candidate not found")
    return create_success_response(data=DiscoveryCandidateResponseDTO.model_validate(cand).model_dump())


@router.get("/candidates/{candidate_id}/evidence", response_model=APIResponse)
async def get_candidate_evidence(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = _get_org_id(current_broker)
    cand_svc = DiscoveryCandidateService(db)
    cand = await cand_svc.get_candidate(org_id, candidate_id)
    if not cand:
        raise HTTPException(status_code=404, detail="Discovery candidate not found")

    ev_svc = EvidenceSignalService(db)
    evidence_list = await ev_svc.get_candidate_evidence(org_id, candidate_id)
    return create_success_response(data=[
        DiscoveryEvidenceDTO.model_validate(e).model_dump() for e in evidence_list
    ])


@router.get("/candidates/{candidate_id}/signals", response_model=APIResponse)
async def get_candidate_signals(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = _get_org_id(current_broker)
    cand_svc = DiscoveryCandidateService(db)
    cand = await cand_svc.get_candidate(org_id, candidate_id)
    if not cand:
        raise HTTPException(status_code=404, detail="Discovery candidate not found")

    ev_svc = EvidenceSignalService(db)
    signals = await ev_svc.get_candidate_signals(org_id, candidate_id)
    return create_success_response(data=[
        DiscoverySignalDTO.model_validate(s).model_dump() for s in signals
    ])


@router.get("/candidates/{candidate_id}/matched-properties", response_model=APIResponse)
async def get_candidate_matched_properties(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = _get_org_id(current_broker)
    cand_svc = DiscoveryCandidateService(db)
    cand = await cand_svc.get_candidate(org_id, candidate_id)
    if not cand:
        raise HTTPException(status_code=404, detail="Discovery candidate not found")

    prop_svc = PropertyMatchingService(db)
    matches = await prop_svc.match_candidate_properties(org_id, cand)
    return create_success_response(data={"candidate_id": candidate_id, "matched_properties": matches})


@router.post("/candidates/{candidate_id}/approve", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def approve_candidate(
    candidate_id: str,
    dto: CandidateApproveDTO,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Approve and import candidate as a canonical CRM Lead with attribution."""
    org_id = _get_org_id(current_broker)
    cand_svc = DiscoveryCandidateService(db)
    cand = await cand_svc.get_candidate(org_id, candidate_id)
    if not cand:
        raise HTTPException(status_code=404, detail="Discovery candidate not found")

    broker_uuid = _get_broker_uuid(current_broker)
    try:
        lead = await cand_svc.import_candidate_as_lead(
            organization_id=org_id,
            candidate=cand,
            broker_uuid=broker_uuid,
            override_name=dto.override_name,
            notes=dto.notes,
        )
        record_candidate_processed(org_id, "IMPORTED")
        return create_success_response(data={
            "candidate_id": candidate_id,
            "lead_id": str(lead.id),
            "status": "IMPORTED",
            "message": "Candidate successfully imported into CRM pipeline.",
        })
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))


@router.post("/candidates/{candidate_id}/reject", response_model=APIResponse)
async def reject_candidate(
    candidate_id: str,
    dto: CandidateRejectDTO,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    org_id = _get_org_id(current_broker)
    cand_svc = DiscoveryCandidateService(db)
    cand = await cand_svc.get_candidate(org_id, candidate_id)
    if not cand:
        raise HTTPException(status_code=404, detail="Discovery candidate not found")

    await cand_svc.reject_candidate(cand, dto.reason)
    record_candidate_processed(org_id, "REJECTED")
    return create_success_response(data={
        "candidate_id": candidate_id,
        "status": "REJECTED",
        "reason": dto.reason,
    })


# ─── Providers Status ─────────────────────────────────────────────────────────

@router.get("/providers/status", response_model=APIResponse)
async def get_providers_status(
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """List status of all authorized discovery providers."""
    org_id = _get_org_id(current_broker)
    source_svc = DiscoverySourceService(db)
    sources = await source_svc.list_sources(org_id)

    providers = DiscoveryProviderRegistry.list_providers()
    statuses = []
    for p in providers:
        matching_sources = [s for s in sources if s.provider == p.provider_name]
        is_live = any(s.status == ProviderStatus.CONNECTED for s in matching_sources)
        st = ProviderStatus.CONNECTED if is_live else (
            matching_sources[0].status if matching_sources else ProviderStatus.CONFIGURATION_REQUIRED
        )
        statuses.append(ProviderStatusDTO(
            provider=p.provider_name,
            status=st,
            is_live=is_live,
            configured_sources=len(matching_sources),
            note="Configuration required in Discovery Sources" if st == ProviderStatus.CONFIGURATION_REQUIRED else None,
        ).model_dump())

    return create_success_response(data=statuses)


# ─── Dashboard Metrics ────────────────────────────────────────────────────────

@router.get("/metrics/dashboard", response_model=APIResponse)
async def get_discovery_dashboard_metrics(
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Aggregate real discovery statistics from database (NO fake data)."""
    org_id = _get_org_id(current_broker)

    # 1. Total Candidates by status
    stmt_c = (
        select(DiscoveryCandidate.status, func.count(DiscoveryCandidate.id))
        .where(DiscoveryCandidate.organization_id == org_id)
        .group_by(DiscoveryCandidate.status)
    )
    status_counts = dict((await db.execute(stmt_c)).all())

    total = sum(status_counts.values())
    high_intent = status_counts.get(CandidateStatus.READY, 0) + status_counts.get(CandidateStatus.IMPORTED, 0)
    duplicates = status_counts.get(CandidateStatus.DUPLICATE, 0)
    rejected = status_counts.get(CandidateStatus.REJECTED, 0) + status_counts.get(CandidateStatus.IRRELEVANT, 0)
    imported = status_counts.get(CandidateStatus.IMPORTED, 0)

    # 2. Campaigns
    stmt_camp = (
        select(func.count(DiscoveryCampaign.id))
        .where(and_(DiscoveryCampaign.organization_id == org_id, DiscoveryCampaign.status == DiscoveryCampaignStatus.ACTIVE))
    )
    active_campaigns = (await db.execute(stmt_camp)).scalar() or 0

    # 3. Runs
    stmt_runs = (
        select(func.count(DiscoveryRun.id))
        .where(and_(DiscoveryRun.organization_id == org_id, DiscoveryRun.status == DiscoveryRunStatus.COMPLETED))
    )
    completed_runs = (await db.execute(stmt_runs)).scalar() or 0

    # 4. Average Relevance Score
    stmt_avg = (
        select(func.avg(DiscoveryCandidate.relevance_score))
        .where(and_(DiscoveryCandidate.organization_id == org_id, DiscoveryCandidate.relevance_score.isnot(None)))
    )
    avg_score = float((await db.execute(stmt_avg)).scalar() or 0.0)

    # 5. Source distribution
    stmt_src = (
        select(DiscoverySource.provider, func.count(DiscoveryCandidate.id))
        .join(DiscoveryCandidate, DiscoveryCandidate.source_id == DiscoverySource.id)
        .where(DiscoveryCandidate.organization_id == org_id)
        .group_by(DiscoverySource.provider)
    )
    src_dist = dict((await db.execute(stmt_src)).all())

    metrics_dto = DiscoveryDashboardMetricsDTO(
        total_discovered_candidates=total,
        high_intent_prospects=high_intent,
        duplicates_detected=duplicates,
        rejected_candidates=rejected,
        imported_leads=imported,
        active_campaigns=active_campaigns,
        completed_runs=completed_runs,
        average_relevance_score=round(avg_score, 4),
        source_distribution=src_dist,
    )
    return create_success_response(data=metrics_dto.model_dump())
