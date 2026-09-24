"""
Part 19 — Supply Side Inventory OS: FastAPI Router
===================================================
Endpoints for Developers, Projects, Units, Price Books, Channel Partners.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional, List, Any, Dict

from fastapi import APIRouter, Depends, Query, Path, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, or_

from app.database import get_db
from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.inventory_models import (
    RealEstateDeveloper, RealEstateProject, ProjectUnit, ProjectUnitStatusLog,
    ChannelPartner, ChannelPartnerProjectAgreement, ChannelPartnerCommission,
)
from app.modules.inventory.service import (
    DeveloperService, ProjectService, UnitService,
    PriceBookService, ChannelPartnerService, InventorySnapshotService,
)

inventory_router = APIRouter(prefix="/inventory", tags=["Part 19 — Supply Side Inventory OS"])
router = inventory_router


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _org(broker: Broker) -> uuid.UUID:
    oid = broker.organization_id or broker.id
    return uuid.UUID(str(oid)) if isinstance(oid, str) else oid

def _bid(broker: Broker) -> uuid.UUID:
    return uuid.UUID(str(broker.id)) if isinstance(broker.id, str) else broker.id


# ===========================================================================
# Developers
# ===========================================================================

@inventory_router.post("/developers", status_code=201, summary="Register a real estate developer")
async def create_developer(
    data: Dict[str, Any] = Body(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = DeveloperService(db)
    dev = await svc.create_developer(_org(broker), _bid(broker), data)
    await db.commit()
    return {
        "id": str(dev.id),
        "developer_code": dev.developer_code,
        "legal_name": dev.legal_name,
        "status": dev.status,
    }


@inventory_router.get("/developers", summary="List developers")
async def list_developers(
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = DeveloperService(db)
    items, total = await svc.list_developers(_org(broker), status=status, limit=limit, offset=offset)
    return {
        "total": total,
        "items": [{"id": str(d.id), "developer_code": d.developer_code, "legal_name": d.legal_name, "status": d.status, "city": d.city} for d in items],
    }


@inventory_router.get("/developers/{developer_id}", summary="Get developer")
async def get_developer(
    developer_id: uuid.UUID = Path(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    dev = await DeveloperService(db).get_developer(_org(broker), developer_id)
    return {
        "id": str(dev.id), "developer_code": dev.developer_code,
        "legal_name": dev.legal_name, "trade_name": dev.trade_name,
        "status": dev.status, "city": dev.city, "rera_number": dev.rera_number,
        "rating": float(dev.rating) if dev.rating else None,
        "total_projects": dev.total_projects, "completed_projects": dev.completed_projects,
    }


@inventory_router.patch("/developers/{developer_id}", summary="Update developer")
async def update_developer(
    developer_id: uuid.UUID = Path(...),
    data: Dict[str, Any] = Body(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    dev = await DeveloperService(db).update_developer(_org(broker), developer_id, data)
    await db.commit()
    return {"id": str(dev.id), "status": dev.status, "updated": True}


# ===========================================================================
# Projects
# ===========================================================================

@inventory_router.post("/projects", status_code=201, summary="Create a real estate project")
async def create_project(
    data: Dict[str, Any] = Body(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = ProjectService(db)
    proj = await svc.create_project(_org(broker), _bid(broker), data)
    await db.commit()
    return {
        "id": str(proj.id),
        "project_code": proj.project_code,
        "project_name": proj.project_name,
        "status": proj.status,
    }


@inventory_router.get("/projects", summary="List projects")
async def list_projects(
    status: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    project_type: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = ProjectService(db)
    items, total = await svc.list_projects(_org(broker), status=status, city=city, project_type=project_type, limit=limit, offset=offset)
    return {
        "total": total,
        "items": [{
            "id": str(p.id), "project_code": p.project_code,
            "project_name": p.project_name, "status": p.status,
            "city": p.city, "project_type": p.project_type,
            "available_units": p.available_units, "total_units": p.total_units,
            "price_min": float(p.price_min) if p.price_min else None,
        } for p in items],
    }


@inventory_router.get("/projects/{project_id}", summary="Get project details")
async def get_project(
    project_id: uuid.UUID = Path(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    proj = await ProjectService(db).get_project(_org(broker), project_id)
    return {
        "id": str(proj.id),
        "project_code": proj.project_code,
        "project_name": proj.project_name,
        "description": proj.description,
        "project_type": proj.project_type,
        "transaction_type": proj.transaction_type,
        "status": proj.status,
        "locality": proj.locality, "city": proj.city, "state": proj.state,
        "rera_number": proj.rera_number,
        "price_min": float(proj.price_min) if proj.price_min else None,
        "price_max": float(proj.price_max) if proj.price_max else None,
        "total_units": proj.total_units,
        "available_units": proj.available_units,
        "sold_units": proj.sold_units,
        "reserved_units": proj.reserved_units,
        "amenities": proj.amenities or [],
        "unit_configs": proj.unit_configs or [],
    }


# ===========================================================================
# Units
# ===========================================================================

@inventory_router.post("/projects/{project_id}/units", status_code=201, summary="Add a unit to a project")
async def create_unit(
    project_id: uuid.UUID = Path(...),
    data: Dict[str, Any] = Body(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    data["project_id"] = project_id
    svc = UnitService(db)
    unit = await svc.create_unit(_org(broker), _bid(broker), data)
    await db.commit()
    return {
        "id": str(unit.id),
        "unit_code": unit.unit_code,
        "unit_type": unit.unit_type,
        "inventory_status": unit.inventory_status,
        "total_price": float(unit.total_price) if unit.total_price else None,
    }


@inventory_router.get("/projects/{project_id}/units", summary="List units in a project")
async def list_units(
    project_id: uuid.UUID = Path(...),
    inventory_status: Optional[str] = Query(None),
    unit_type: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = UnitService(db)
    items, total = await svc.list_units(_org(broker), project_id, inventory_status=inventory_status, unit_type=unit_type, limit=limit, offset=offset)
    return {
        "total": total,
        "items": [{
            "id": str(u.id), "unit_code": u.unit_code,
            "unit_number": u.unit_number, "unit_type": u.unit_type,
            "floor_number": u.floor_number, "facing": u.facing,
            "carpet_area": float(u.carpet_area) if u.carpet_area else None,
            "bedrooms": u.bedrooms, "bathrooms": u.bathrooms,
            "base_price": float(u.base_price) if u.base_price else None,
            "total_price": float(u.total_price) if u.total_price else None,
            "inventory_status": u.inventory_status,
        } for u in items],
    }


@inventory_router.post("/units/{unit_id}/transition", summary="Transition unit inventory status")
async def transition_unit_status(
    unit_id: uuid.UUID = Path(...),
    data: Dict[str, Any] = Body(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = UnitService(db)
    unit = await svc.transition_status(
        org_id=_org(broker),
        unit_id=unit_id,
        to_status=data["to_status"],
        reason=data.get("reason"),
        actor_id=_bid(broker),
        actor_type="user",
        deal_id=uuid.UUID(data["deal_id"]) if data.get("deal_id") else None,
        idempotency_key=data.get("idempotency_key"),
        reservation_ttl_hours=data.get("reservation_ttl_hours", 48),
        channel_partner_id=uuid.UUID(data["channel_partner_id"]) if data.get("channel_partner_id") else None,
    )
    # Materialize snapshot
    snap_svc = InventorySnapshotService(db)
    await snap_svc.materialize_snapshot(_org(broker), unit.project_id)
    # Update project counters
    await ProjectService(db).update_project_inventory_counters(unit.project_id)
    await db.commit()
    return {
        "unit_id": str(unit.id),
        "unit_code": unit.unit_code,
        "inventory_status": unit.inventory_status,
        "message": f"Unit transitioned to {unit.inventory_status}",
    }


@inventory_router.get("/projects/{project_id}/availability", summary="Get latest inventory availability snapshot")
async def get_availability_snapshot(
    project_id: uuid.UUID = Path(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    snap = await InventorySnapshotService(db).get_latest_snapshot(_org(broker), project_id)
    if not snap:
        raise HTTPException(status_code=404, detail="No snapshot found for this project. Add units first.")
    return {
        "project_id": str(snap.project_id),
        "snapshot_at": snap.snapshot_at.isoformat(),
        "total_units": snap.total_units,
        "available_units": snap.available_units,
        "reserved_units": snap.reserved_units,
        "booked_units": snap.booked_units,
        "sold_units": snap.sold_units,
        "blocked_units": snap.blocked_units,
        "under_offer_units": snap.under_offer_units,
        "by_unit_type": snap.by_unit_type,
        "price_range_available": snap.price_range_available,
    }


# ===========================================================================
# Price Books
# ===========================================================================

@inventory_router.post("/projects/{project_id}/price-books", status_code=201, summary="Create a price book")
async def create_price_book(
    project_id: uuid.UUID = Path(...),
    data: Dict[str, Any] = Body(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    data["project_id"] = project_id
    pb = await PriceBookService(db).create_price_book(_org(broker), data)
    await db.commit()
    return {"id": str(pb.id), "version": pb.version, "status": pb.status}


@inventory_router.post("/price-books/{price_book_id}/publish", summary="Publish a price book (supersedes active)")
async def publish_price_book(
    price_book_id: uuid.UUID = Path(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    pb = await PriceBookService(db).publish_price_book(_org(broker), price_book_id, publisher_id=_bid(broker))
    await db.commit()
    return {"id": str(pb.id), "version": pb.version, "status": pb.status, "published_at": pb.published_at.isoformat() if pb.published_at else None}


@inventory_router.post("/price-books/{price_book_id}/entries", status_code=201, summary="Add a price entry to a price book")
async def add_price_entry(
    price_book_id: uuid.UUID = Path(...),
    data: Dict[str, Any] = Body(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    entry = await PriceBookService(db).add_entry(price_book_id, data)
    await db.commit()
    return {"id": str(entry.id), "base_price": float(entry.base_price)}


# ===========================================================================
# Channel Partners
# ===========================================================================

@inventory_router.post("/channel-partners", status_code=201, summary="Register a channel partner")
async def register_channel_partner(
    data: Dict[str, Any] = Body(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    cp = await ChannelPartnerService(db).register_channel_partner(_org(broker), _bid(broker), data)
    await db.commit()
    return {"id": str(cp.id), "cp_code": cp.cp_code, "status": cp.status}


@inventory_router.get("/channel-partners", summary="List channel partners")
async def list_channel_partners(
    status: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = ChannelPartnerService(db)
    items, total = await svc.list_channel_partners(_org(broker), status=status, tier=tier, limit=limit, offset=offset)
    return {
        "total": total,
        "items": [{"id": str(c.id), "cp_code": c.cp_code, "contact_name": c.contact_name, "email": c.email, "status": c.status, "tier": c.tier, "kyc_verified": c.kyc_verified} for c in items],
    }


@inventory_router.post("/channel-partners/{cp_id}/kyc-verify", summary="Mark channel partner KYC verified")
async def verify_kyc(
    cp_id: uuid.UUID = Path(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    cp = await ChannelPartnerService(db).verify_kyc(_org(broker), cp_id)
    await db.commit()
    return {"id": str(cp.id), "status": cp.status, "kyc_verified": cp.kyc_verified}


@inventory_router.post("/channel-partners/{cp_id}/project-agreements", status_code=201, summary="Create CP-project agreement")
async def create_agreement(
    cp_id: uuid.UUID = Path(...),
    data: Dict[str, Any] = Body(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    project_id = uuid.UUID(data.pop("project_id"))
    agreement = await ChannelPartnerService(db).create_project_agreement(_org(broker), cp_id, project_id, data)
    await db.commit()
    return {"id": str(agreement.id), "project_id": str(project_id), "is_active": agreement.is_active}


@inventory_router.post("/channel-partners/{cp_id}/commissions", status_code=201, summary="Record CP commission for a closed deal")
async def record_commission(
    cp_id: uuid.UUID = Path(...),
    data: Dict[str, Any] = Body(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    comm = await ChannelPartnerService(db).record_commission(_org(broker), cp_id, data)
    await db.commit()
    return {
        "id": str(comm.id),
        "commission_amount": float(comm.commission_amount),
        "payment_status": comm.payment_status,
    }


# ===========================================================================
# Dashboard & Analytics
# ===========================================================================

@inventory_router.get("/dashboard", summary="Supply Command Center dashboard KPIs")
async def get_inventory_dashboard(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(broker)
    projects_res = (await db.execute(
        select(
            func.count(RealEstateProject.id).label("total_projects"),
            func.sum(RealEstateProject.total_units).label("total_units"),
            func.sum(RealEstateProject.available_units).label("available_units"),
            func.sum(RealEstateProject.reserved_units).label("reserved_units"),
            func.sum(RealEstateProject.sold_units).label("sold_units"),
        ).where(
            and_(RealEstateProject.organization_id == org_id,
                 RealEstateProject.deleted_at.is_(None))
        )
    )).one_or_none()

    value_res = (await db.execute(
        select(
            func.sum(ProjectUnit.total_price).label("total_inventory_value"),
            func.avg(ProjectUnit.price_per_sqft).label("avg_price_per_sqft"),
        ).where(
            and_(ProjectUnit.organization_id == org_id,
                 ProjectUnit.deleted_at.is_(None))
        )
    )).one_or_none()

    cp_count = (await db.execute(
        select(func.count(ChannelPartner.id)).where(
            and_(ChannelPartner.organization_id == org_id,
                 ChannelPartner.deleted_at.is_(None))
        )
    )).scalar() or 0

    return {
        "total_projects": (projects_res.total_projects or 0) if projects_res else 0,
        "total_units": (projects_res.total_units or 0) if projects_res else 0,
        "available_units": (projects_res.available_units or 0) if projects_res else 0,
        "reserved_units": (projects_res.reserved_units or 0) if projects_res else 0,
        "sold_units": (projects_res.sold_units or 0) if projects_res else 0,
        "total_inventory_value": float(value_res.total_inventory_value) if (value_res and value_res.total_inventory_value) else 0.0,
        "avg_price_per_sqft": float(value_res.avg_price_per_sqft) if (value_res and value_res.avg_price_per_sqft) else 0.0,
        "active_channel_partners": cp_count,
    }


# ===========================================================================
# Unit Detail & Search
# ===========================================================================

@inventory_router.get("/units/{unit_id}", summary="Get unit details and status history")
async def get_unit_details(
    unit_id: uuid.UUID = Path(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(broker)
    svc = UnitService(db)
    unit = await svc.get_unit(org_id, unit_id)

    logs_res = (await db.execute(
        select(ProjectUnitStatusLog).where(
            and_(ProjectUnitStatusLog.unit_id == unit_id,
                 ProjectUnitStatusLog.organization_id == org_id)
        ).order_by(ProjectUnitStatusLog.created_at.desc()).limit(20)
    )).scalars().all()

    return {
        "id": str(unit.id),
        "unit_code": unit.unit_code,
        "unit_number": unit.unit_number,
        "unit_type": unit.unit_type,
        "project_id": str(unit.project_id),
        "floor_number": unit.floor_number,
        "facing": unit.facing,
        "carpet_area": float(unit.carpet_area) if unit.carpet_area else None,
        "built_up_area": float(unit.built_up_area) if unit.built_up_area else None,
        "super_built_up_area": float(unit.super_built_up_area) if unit.super_built_up_area else None,
        "bedrooms": unit.bedrooms,
        "bathrooms": unit.bathrooms,
        "base_price": float(unit.base_price) if unit.base_price else None,
        "price_per_sqft": float(unit.price_per_sqft) if unit.price_per_sqft else None,
        "total_price": float(unit.total_price) if unit.total_price else None,
        "inventory_status": unit.inventory_status,
        "reserved_by_deal_id": str(unit.reserved_by_deal_id) if unit.reserved_by_deal_id else None,
        "reservation_expires_at": unit.reservation_expires_at.isoformat() if unit.reservation_expires_at else None,
        "status_history": [
            {
                "previous_status": log.previous_status,
                "new_status": log.new_status,
                "reason": log.reason,
                "changed_by_type": log.changed_by_type,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs_res
        ],
    }


@inventory_router.get("/search", summary="Multi-faceted search for available inventory")
async def search_inventory(
    city: Optional[str] = Query(None),
    project_type: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    bedrooms: Optional[int] = Query(None),
    inventory_status: Optional[str] = Query("available"),
    limit: int = Query(50, le=100),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(broker)
    q = select(ProjectUnit, RealEstateProject).join(
        RealEstateProject, RealEstateProject.id == ProjectUnit.project_id
    ).where(
        and_(
            ProjectUnit.organization_id == org_id,
            ProjectUnit.deleted_at.is_(None),
            RealEstateProject.deleted_at.is_(None),
        )
    )
    if inventory_status:
        q = q.where(ProjectUnit.inventory_status == inventory_status)
    if bedrooms is not None:
        q = q.where(ProjectUnit.bedrooms == bedrooms)
    if min_price is not None:
        q = q.where(ProjectUnit.total_price >= Decimal(str(min_price)))
    if max_price is not None:
        q = q.where(ProjectUnit.total_price <= Decimal(str(max_price)))
    if city:
        q = q.where(RealEstateProject.city.ilike(f"%{city}%"))
    if project_type:
        q = q.where(RealEstateProject.project_type == project_type)

    results = (await db.execute(q.limit(limit))).all()
    return {
        "count": len(results),
        "items": [
            {
                "unit_id": str(u.id),
                "unit_code": u.unit_code,
                "unit_number": u.unit_number,
                "unit_type": u.unit_type,
                "bedrooms": u.bedrooms,
                "carpet_area": float(u.carpet_area) if u.carpet_area else None,
                "total_price": float(u.total_price) if u.total_price else None,
                "inventory_status": u.inventory_status,
                "project_id": str(p.id),
                "project_name": p.project_name,
                "city": p.city,
            }
            for u, p in results
        ],
    }


# ===========================================================================
# Channel Partner Detail, Leads & Portal
# ===========================================================================

@inventory_router.get("/channel-partners/{cp_id}", summary="Get channel partner profile and agreements")
async def get_channel_partner_detail(
    cp_id: uuid.UUID = Path(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(broker)
    cp = await ChannelPartnerService(db).get_channel_partner(org_id, cp_id)
    agreements_res = (await db.execute(
        select(ChannelPartnerProjectAgreement).where(
            and_(ChannelPartnerProjectAgreement.channel_partner_id == cp_id,
                 ChannelPartnerProjectAgreement.organization_id == org_id,
                 ChannelPartnerProjectAgreement.deleted_at.is_(None))
        )
    )).scalars().all()

    commissions_res = (await db.execute(
        select(ChannelPartnerCommission).where(
            and_(ChannelPartnerCommission.channel_partner_id == cp_id,
                 ChannelPartnerCommission.organization_id == org_id,
                 ChannelPartnerCommission.deleted_at.is_(None))
        )
    )).scalars().all()

    return {
        "id": str(cp.id),
        "cp_code": cp.cp_code,
        "firm_name": cp.firm_name,
        "contact_name": cp.contact_name,
        "email": cp.email,
        "phone": cp.phone,
        "tier": cp.tier,
        "status": cp.status,
        "kyc_verified": cp.kyc_verified,
        "rera_number": cp.rera_number,
        "default_commission_pct": float(cp.default_commission_pct) if cp.default_commission_pct else None,
        "agreements": [
            {
                "id": str(a.id),
                "project_id": str(a.project_id),
                "commission_pct": float(a.commission_pct) if a.commission_pct else None,
                "is_active": a.is_active,
                "is_exclusive": a.is_exclusive,
            }
            for a in agreements_res
        ],
        "commissions": [
            {
                "id": str(c.id),
                "deal_id": str(c.deal_id) if c.deal_id else None,
                "commission_amount": float(c.commission_amount),
                "payment_status": c.payment_status,
                "transaction_value": float(c.transaction_value),
            }
            for c in commissions_res
        ],
    }


@inventory_router.post("/channel-partners/{cp_id}/leads", status_code=201, summary="Register partner lead with attribution")
async def register_partner_lead(
    cp_id: uuid.UUID = Path(...),
    data: Dict[str, Any] = Body(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(broker)
    cp = await ChannelPartnerService(db).get_channel_partner(org_id, cp_id)
    if cp.status not in ("active", "kyc_verified"):
        raise HTTPException(status_code=400, detail=f"Channel partner is not authorized (status={cp.status})")

    phone = (data.get("phone") or "").strip()
    email = (data.get("email") or "").strip().lower()
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required for partner lead registration")

    # Check duplicate lead for this broker
    existing = (await db.execute(
        select(Lead).where(
            and_(
                Lead.broker_id == _bid(broker),
                or_(Lead.phone == phone, (Lead.email == email if email else False)),
                Lead.deleted_at.is_(None),
            )
        )
    )).scalars().first()

    if existing:
        return {
            "duplicate_detected": True,
            "lead_id": str(existing.id),
            "attribution": "existing_customer",
            "message": "Lead already exists in CRM. Existing attribution preserved.",
            "first_touch_source": existing.source,
        }

    new_lead = Lead(
        broker_id=_bid(broker),
        name=data.get("name"),
        phone=phone,
        email=email or None,
        source="channel_partner",
        budget_min=int(data.get("budget_min")) if data.get("budget_min") else None,
        budget_max=int(data.get("budget_max")) if data.get("budget_max") else None,
        property_type=data.get("property_type"),
        notes=[{
            "channel_partner_id": str(cp.id),
            "channel_partner_code": cp.cp_code,
            "project_interest_id": data.get("project_id"),
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "attribution_type": "FIRST_TOUCH",
        }],
        status="pending",
        pipeline_stage="new",
    )
    db.add(new_lead)
    await db.flush()
    await db.commit()

    return {
        "duplicate_detected": False,
        "lead_id": str(new_lead.id),
        "attribution": "channel_partner",
        "channel_partner_code": cp.cp_code,
        "message": "Partner lead registered and attributed successfully.",
    }


@inventory_router.get("/channel-partners/{cp_id}/portal", summary="Channel partner workspace portal data")
async def get_channel_partner_portal(
    cp_id: uuid.UUID = Path(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(broker)
    cp = await ChannelPartnerService(db).get_channel_partner(org_id, cp_id)
    agreements = (await db.execute(
        select(ChannelPartnerProjectAgreement, RealEstateProject).join(
            RealEstateProject, RealEstateProject.id == ChannelPartnerProjectAgreement.project_id
        ).where(
            and_(ChannelPartnerProjectAgreement.channel_partner_id == cp_id,
                 ChannelPartnerProjectAgreement.is_active == True,
                 ChannelPartnerProjectAgreement.organization_id == org_id)
        )
    )).all()

    leads = (await db.execute(
        select(Lead).where(
            and_(Lead.broker_id == _bid(broker),
                 Lead.source == "channel_partner",
                 Lead.deleted_at.is_(None))
        ).limit(50)
    )).scalars().all()

    commissions = (await db.execute(
        select(ChannelPartnerCommission).where(
            and_(ChannelPartnerCommission.channel_partner_id == cp_id,
                 ChannelPartnerCommission.organization_id == org_id)
        )
    )).scalars().all()

    total_commission = sum((c.commission_amount for c in commissions), Decimal("0"))

    return {
        "partner": {
            "id": str(cp.id),
            "firm_name": cp.firm_name,
            "contact_name": cp.contact_name,
            "cp_code": cp.cp_code,
            "tier": cp.tier,
            "status": cp.status,
            "kyc_verified": cp.kyc_verified,
        },
        "authorized_projects": [
            {
                "project_id": str(p.id),
                "project_name": p.project_name,
                "project_code": p.project_code,
                "city": p.city,
                "available_units": p.available_units,
                "commission_pct": float(a.commission_pct) if a.commission_pct else None,
            }
            for a, p in agreements
        ],
        "leads_count": len(leads),
        "total_commission_earned": float(total_commission),
        "commissions_count": len(commissions),
    }

