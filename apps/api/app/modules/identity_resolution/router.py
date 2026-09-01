"""
Identity Resolution REST API Router
=====================================
Endpoints:
    POST   /api/v1/identity/resolve/{lead_id}         # Trigger resolution pipeline
    GET    /api/v1/identity/profile/{identity_id}     # Fetch full identity profile + linked leads
    GET    /api/v1/identity/candidates/{lead_id}      # List duplicate candidates for a lead
    POST   /api/v1/identity/merge                     # Manual merge execution
    POST   /api/v1/identity/merge/{op_id}/undo        # Undo a merge operation
    POST   /api/v1/identity/merge/simulate            # Dry-run merge simulation
    GET    /api/v1/identity/review/queue              # List manual review items
    POST   /api/v1/identity/review/{review_id}/action # Submit reviewer decision
    GET    /api/v1/identity/search                    # Search identities by phone/email/alias
    GET    /api/v1/identity/metrics                   # Monitor stats
"""
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.identity_models import (
    Identity, DuplicateCandidate, MergeOperation, ManualReview, IdentityLink, IdentityAlias
)
from app.modules.identity_resolution.service import IdentityResolutionService
from app.modules.identity_resolution.merge_engine.merge_executor import MergeExecutor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/identity", tags=["Identity Resolution"])


# ─── Request/Response DTOs ────────────────────────────────────────────────────

class ResolveLeadRequest(BaseModel):
    lead_data: Dict[str, Any] = Field(..., description="Canonical lead dict")
    organization_id: str

class ManualMergeRequest(BaseModel):
    source_identity_id: str
    target_identity_id: str
    organization_id: str
    actor_id: Optional[str] = None

class MergeSimulateRequest(BaseModel):
    source_identity_id: str
    target_identity_id: str
    confidence: float = 0.90

class ReviewActionRequest(BaseModel):
    reviewer_id: str
    decision: str  # merge | ignore | defer
    reviewer_notes: Optional[str] = None
    reviewer_confidence: Optional[float] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/resolve/{lead_id}", summary="Trigger Identity Resolution Pipeline")
async def resolve_lead(
    lead_id: str,
    request: ResolveLeadRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trigger the full identity resolution pipeline for an incoming lead."""
    try:
        service = IdentityResolutionService(db=db)
        lead_data = dict(request.lead_data)
        lead_data["id"] = lead_id
        result = await service.resolve_lead(lead_data, request.organization_id)
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(f"[IDENTITY_ROUTER] resolve_lead failed for {lead_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profile/{identity_id}", summary="Fetch Identity Profile")
async def get_identity_profile(
    identity_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch full identity profile including all linked leads and aliases."""
    service = IdentityResolutionService(db=db)
    profile = await service.get_identity_profile(identity_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Identity {identity_id} not found")
    return {"status": "success", "identity": profile}


@router.get("/candidates/{lead_id}", summary="List Duplicate Candidates for a Lead")
async def get_candidates(
    lead_id: str,
    organization_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """List all duplicate candidate evaluations for a given lead."""
    result = await db.execute(
        select(DuplicateCandidate)
        .where(
            DuplicateCandidate.lead_id == lead_id,
            DuplicateCandidate.organization_id == organization_id,
        )
        .order_by(DuplicateCandidate.overall_confidence.desc())
    )
    candidates = result.scalars().all()
    return {
        "lead_id": lead_id,
        "count": len(candidates),
        "candidates": [
            {
                "id": c.id,
                "candidate_identity_id": c.candidate_identity_id,
                "confidence": c.overall_confidence,
                "decision": c.decision,
                "matched_fields": c.matched_fields,
                "reason": c.reason,
                "status": c.status,
                "algorithms_used": c.algorithms_used,
            }
            for c in candidates
        ],
    }


@router.post("/merge", summary="Execute Manual Merge")
async def manual_merge(
    request: ManualMergeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Execute a manual identity merge."""
    try:
        executor = MergeExecutor(db)
        result = await executor.execute_merge(
            source_identity_id=request.source_identity_id,
            target_identity_id=request.target_identity_id,
            organization_id=request.organization_id,
            merge_confidence=1.0,
            merge_type="manual",
            actor_id=request.actor_id,
        )
        return {"status": "success", "merge": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[IDENTITY_ROUTER] manual_merge failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/merge/{op_id}/undo", summary="Undo a Merge Operation")
async def undo_merge(
    op_id: str,
    undone_by: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Undo a completed merge, restoring both identities to pre-merge state."""
    try:
        service = IdentityResolutionService(db=db)
        result = await service.undo_merge(op_id, undone_by)
        return {"status": "success", "undo": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/merge/simulate", summary="Dry-Run Merge Simulation")
async def simulate_merge(
    request: MergeSimulateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Simulate a merge without executing it. Shows conflicts and field copies."""
    try:
        service = IdentityResolutionService(db=db)
        simulation = await service.simulate_merge(
            request.source_identity_id,
            request.target_identity_id,
            request.confidence,
        )
        return {"status": "success", "simulation": simulation}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/review/queue", summary="List Manual Review Queue")
async def get_review_queue(
    organization_id: str = Query(...),
    assigned_to: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List pending manual review items for an organization."""
    from app.modules.identity_resolution.manual_review.review_service import ReviewService
    review_svc = ReviewService(db)
    reviews = await review_svc.list_pending(organization_id, assigned_to, limit)
    return {
        "count": len(reviews),
        "reviews": [
            {
                "id": r.id,
                "lead_id": r.lead_id,
                "candidate_identity_id": r.candidate_identity_id,
                "ai_confidence": r.ai_confidence,
                "ai_recommendation": r.ai_recommendation,
                "ai_explanation": r.ai_explanation,
                "similarity_breakdown": r.similarity_breakdown,
                "priority": r.priority,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r in reviews
        ],
    }


@router.post("/review/{review_id}/action", summary="Submit Reviewer Decision")
async def submit_review_action(
    review_id: str,
    request: ReviewActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit a reviewer decision (merge/ignore/defer) and execute the resulting action."""
    from app.modules.identity_resolution.manual_review.review_service import ReviewService
    review_svc = ReviewService(db)
    try:
        result = await review_svc.submit_decision(
            review_id=review_id,
            reviewer_id=request.reviewer_id,
            decision=request.decision,
            reviewer_notes=request.reviewer_notes,
            reviewer_confidence=request.reviewer_confidence,
        )
        # If decision is merge, execute the merge
        if result["decision"] == "merge":
            executor = MergeExecutor(db)
            # In production, load identity IDs from review record
            # Here we return next_action for the UI to trigger
            result["next_action"] = "execute_merge"

        return {"status": "success", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/search", summary="Search Identities by Phone, Email, or Alias")
async def search_identities(
    organization_id: str = Query(...),
    phone: Optional[str] = Query(default=None),
    email: Optional[str] = Query(default=None),
    name: Optional[str] = Query(default=None),
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Search identities by primary contact or historical alias.
    Searches both primary fields and the alias registry.
    """
    from sqlalchemy import or_
    results = []

    # Search aliases
    alias_clauses = []
    if phone:
        import re
        digits = re.sub(r"\D", "", phone)
        normalized = f"+{digits}" if digits else phone
        alias_clauses.append(IdentityAlias.alias_value_normalized == normalized)
    if email:
        alias_clauses.append(IdentityAlias.alias_value_normalized == email.strip().lower())
    if name:
        alias_clauses.append(IdentityAlias.alias_value_normalized.ilike(f"%{name.lower()}%"))

    if alias_clauses:
        alias_stmt = (
            select(IdentityAlias.identity_id)
            .where(
                IdentityAlias.organization_id == organization_id,
                or_(*alias_clauses),
            )
            .distinct()
            .limit(limit)
        )
        alias_result = await db.execute(alias_stmt)
        identity_ids = [row[0] for row in alias_result.fetchall()]

        if identity_ids:
            id_stmt = (
                select(Identity)
                .where(
                    Identity.id.in_(identity_ids),
                    Identity.is_merged == False,
                )
                .limit(limit)
            )
            id_result = await db.execute(id_stmt)
            for ident in id_result.scalars().all():
                results.append({
                    "id": ident.id,
                    "primary_email": ident.primary_email,
                    "primary_phone_e164": ident.primary_phone_e164,
                    "primary_name": ident.primary_name,
                    "lead_count": ident.lead_count,
                    "health_score": ident.health_score,
                    "first_source": ident.first_source,
                })

    return {"count": len(results), "identities": results}


@router.get("/metrics", summary="Identity Resolution Metrics")
async def get_metrics(
    organization_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get identity resolution monitoring metrics for an organization."""
    total_identities = await db.scalar(
        select(func.count()).select_from(Identity).where(
            Identity.organization_id == organization_id,
            Identity.is_merged == False,
        )
    )
    merged_identities = await db.scalar(
        select(func.count()).select_from(Identity).where(
            Identity.organization_id == organization_id,
            Identity.is_merged == True,
        )
    )
    pending_reviews = await db.scalar(
        select(func.count()).select_from(ManualReview).where(
            ManualReview.organization_id == organization_id,
            ManualReview.status == "pending",
        )
    )
    auto_merges = await db.scalar(
        select(func.count()).select_from(MergeOperation).where(
            MergeOperation.organization_id == organization_id,
            MergeOperation.merge_type == "auto",
            MergeOperation.status == "completed",
        )
    )

    return {
        "organization_id": organization_id,
        "total_identities": total_identities or 0,
        "merged_identities": merged_identities or 0,
        "pending_manual_reviews": pending_reviews or 0,
        "auto_merges_completed": auto_merges or 0,
        "duplicate_rate": round(
            (merged_identities or 0) / max((total_identities or 1) + (merged_identities or 0), 1), 4
        ),
    }
