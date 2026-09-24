"""
Part 19 — Supply Side Inventory Service
========================================
Core business logic for the supply-side OS:
  - Developer CRUD
  - Project CRUD + status lifecycle
  - Phase / Building / Floor / Unit hierarchy management
  - Atomic unit reservation (with idempotency and distributed locking)
  - Unit status state machine enforcement
  - Price book versioning and publication
  - Channel partner registration, KYC, and project agreements
  - CP commission ledger
  - Inventory availability snapshot materialization

Design rules (from Part 17/18 precedent):
  - No autonomous financial mutations.
  - All state changes write an OutboxEvent atomically.
  - All state changes write an append-only status log.
  - Decimal arithmetic only (never float).
  - Tenant isolation enforced on every query via organization_id.
  - Resource-level locks via Redis (or in-process fallback) for reservations.
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_models import (
    RealEstateDeveloper, RealEstateProject, ProjectPhase, ProjectBuilding,
    ProjectFloor, ProjectUnit, ProjectUnitStatusLog, ProjectPriceBook,
    PriceBookEntry, ProjectMedia, ChannelPartner, ChannelPartnerProjectAgreement,
    ChannelPartnerCommission, InventoryAvailabilitySnapshot,
    UnitInventoryStatus, DeveloperStatus, ProjectStatus, PriceBookStatus,
    ChannelPartnerStatus, ChannelPartnerTier,
)
from app.infrastructure.outbox.outbox_service import OutboxService
from app.models.outbox_models import OutboxEvent
from app.common.redis.distributed_lock import RedisDistributedLock

logger = logging.getLogger("wefylabs.inventory.service")

# ---------------------------------------------------------------------------
# Helper: generate human-readable codes
# ---------------------------------------------------------------------------

def _generate_code(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(3).upper()}"


# ---------------------------------------------------------------------------
# 1. DeveloperService
# ---------------------------------------------------------------------------

class DeveloperService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_developer(self, organization_id: uuid.UUID, broker_id: uuid.UUID, data: Dict[str, Any]) -> RealEstateDeveloper:
        code = data.get("developer_code") or _generate_code("DEV")
        dev = RealEstateDeveloper(
            organization_id=organization_id,
            broker_id=broker_id,
            developer_code=code,
            legal_name=data["legal_name"],
            trade_name=data.get("trade_name"),
            logo_url=data.get("logo_url"),
            rera_number=data.get("rera_number"),
            gst_number=data.get("gst_number"),
            pan_number=data.get("pan_number"),
            cin_number=data.get("cin_number"),
            primary_email=data.get("primary_email"),
            primary_phone=data.get("primary_phone"),
            website_url=data.get("website_url"),
            address=data.get("address"),
            city=data.get("city"),
            state=data.get("state"),
            country_code=data.get("country_code", "IN"),
            years_in_business=data.get("years_in_business"),
            status=DeveloperStatus.ACTIVE,
            notes=data.get("notes"),
            extended_fields=data.get("extended_fields"),
        )
        self.db.add(dev)
        await self.db.flush()
        logger.info(f"[Developer] Created {dev.developer_code} org={organization_id}")
        return dev

    async def get_developer(self, org_id: uuid.UUID, developer_id: uuid.UUID) -> RealEstateDeveloper:
        result = await self.db.execute(
            select(RealEstateDeveloper).where(
                and_(RealEstateDeveloper.id == developer_id,
                     RealEstateDeveloper.organization_id == org_id,
                     RealEstateDeveloper.deleted_at.is_(None))
            )
        )
        dev = result.scalar_one_or_none()
        if not dev:
            raise HTTPException(status_code=404, detail="Developer not found")
        return dev

    async def list_developers(self, org_id: uuid.UUID, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> Tuple[List[RealEstateDeveloper], int]:
        q = select(RealEstateDeveloper).where(
            and_(RealEstateDeveloper.organization_id == org_id,
                 RealEstateDeveloper.deleted_at.is_(None))
        )
        if status:
            q = q.where(RealEstateDeveloper.status == status)
        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0
        items = (await self.db.execute(q.order_by(RealEstateDeveloper.legal_name).offset(offset).limit(limit))).scalars().all()
        return list(items), total

    async def update_developer(self, org_id: uuid.UUID, developer_id: uuid.UUID, data: Dict[str, Any]) -> RealEstateDeveloper:
        dev = await self.get_developer(org_id, developer_id)
        allowed = ["legal_name", "trade_name", "logo_url", "rera_number", "gst_number",
                   "pan_number", "cin_number", "primary_email", "primary_phone", "website_url",
                   "address", "city", "state", "country_code", "years_in_business", "status",
                   "notes", "extended_fields", "rating"]
        for k, v in data.items():
            if k in allowed and v is not None:
                setattr(dev, k, v)
        dev.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return dev


# ---------------------------------------------------------------------------
# 2. ProjectService
# ---------------------------------------------------------------------------

class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_project(self, organization_id: uuid.UUID, broker_id: uuid.UUID, data: Dict[str, Any]) -> RealEstateProject:
        code = data.get("project_code") or _generate_code("PRJ")
        project = RealEstateProject(
            organization_id=organization_id,
            broker_id=broker_id,
            developer_id=data.get("developer_id"),
            project_code=code,
            project_name=data["project_name"],
            slug=data.get("slug"),
            tagline=data.get("tagline"),
            description=data.get("description"),
            hero_image_url=data.get("hero_image_url"),
            brochure_url=data.get("brochure_url"),
            project_type=data.get("project_type", "residential"),
            transaction_type=data.get("transaction_type", "primary_sale"),
            status=data.get("status", ProjectStatus.ANNOUNCED),
            rera_number=data.get("rera_number"),
            address=data.get("address"),
            micro_market=data.get("micro_market"),
            locality=data.get("locality"),
            city=data.get("city"),
            state=data.get("state"),
            country_code=data.get("country_code", "IN"),
            postal_code=data.get("postal_code"),
            latitude=Decimal(str(data["latitude"])) if data.get("latitude") else None,
            longitude=Decimal(str(data["longitude"])) if data.get("longitude") else None,
            price_min=Decimal(str(data["price_min"])) if data.get("price_min") else None,
            price_max=Decimal(str(data["price_max"])) if data.get("price_max") else None,
            currency=data.get("currency", "INR"),
            cp_commission_pct=Decimal(str(data["cp_commission_pct"])) if data.get("cp_commission_pct") else None,
            amenities=data.get("amenities", []),
            highlights=data.get("highlights", []),
            unit_configs=data.get("unit_configs", []),
            area_range=data.get("area_range"),
            notes=data.get("notes"),
            extended_fields=data.get("extended_fields"),
        )
        self.db.add(project)
        await self.db.flush()
        logger.info(f"[Project] Created {project.project_code} org={organization_id}")
        return project

    async def get_project(self, org_id: uuid.UUID, project_id: uuid.UUID) -> RealEstateProject:
        result = await self.db.execute(
            select(RealEstateProject).where(
                and_(RealEstateProject.id == project_id,
                     RealEstateProject.organization_id == org_id,
                     RealEstateProject.deleted_at.is_(None))
            )
        )
        proj = result.scalar_one_or_none()
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")
        return proj

    async def list_projects(
        self, org_id: uuid.UUID, status: Optional[str] = None,
        city: Optional[str] = None, project_type: Optional[str] = None,
        limit: int = 50, offset: int = 0
    ) -> Tuple[List[RealEstateProject], int]:
        q = select(RealEstateProject).where(
            and_(RealEstateProject.organization_id == org_id,
                 RealEstateProject.deleted_at.is_(None))
        )
        if status:
            q = q.where(RealEstateProject.status == status)
        if city:
            q = q.where(RealEstateProject.city.ilike(f"%{city}%"))
        if project_type:
            q = q.where(RealEstateProject.project_type == project_type)
        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0
        items = (await self.db.execute(q.order_by(RealEstateProject.project_name).offset(offset).limit(limit))).scalars().all()
        return list(items), total

    async def update_project_inventory_counters(self, project_id: uuid.UUID) -> None:
        """Recompute and update denormalized unit counters on the project."""
        counts = (await self.db.execute(
            select(
                ProjectUnit.inventory_status,
                func.count(ProjectUnit.id).label("cnt")
            ).where(
                and_(ProjectUnit.project_id == project_id,
                     ProjectUnit.deleted_at.is_(None))
            ).group_by(ProjectUnit.inventory_status)
        )).all()
        totals: Dict[str, int] = {row.inventory_status: row.cnt for row in counts}
        total = sum(totals.values())
        await self.db.execute(
            update(RealEstateProject)
            .where(RealEstateProject.id == project_id)
            .values(
                total_units=total,
                available_units=totals.get(UnitInventoryStatus.AVAILABLE, 0),
                sold_units=totals.get(UnitInventoryStatus.SOLD, 0),
                reserved_units=totals.get(UnitInventoryStatus.RESERVED, 0),
                updated_at=datetime.now(timezone.utc),
            )
        )


# ---------------------------------------------------------------------------
# 3. UnitService (core inventory state machine)
# ---------------------------------------------------------------------------

class UnitService:
    def __init__(self, db: AsyncSession, outbox: Optional[OutboxService] = None):
        self.db = db
        self.outbox = outbox

    async def create_unit(self, organization_id: uuid.UUID, broker_id: uuid.UUID, data: Dict[str, Any]) -> ProjectUnit:
        code = data.get("unit_code") or _generate_code("UNIT")
        unit = ProjectUnit(
            organization_id=organization_id,
            broker_id=broker_id,
            project_id=data["project_id"],
            phase_id=data.get("phase_id"),
            building_id=data.get("building_id"),
            floor_id=data.get("floor_id"),
            property_listing_id=data.get("property_listing_id"),
            unit_code=code,
            unit_number=data["unit_number"],
            unit_type=data["unit_type"],
            floor_number=data.get("floor_number"),
            facing=data.get("facing"),
            carpet_area=Decimal(str(data["carpet_area"])) if data.get("carpet_area") else None,
            built_up_area=Decimal(str(data["built_up_area"])) if data.get("built_up_area") else None,
            super_built_up_area=Decimal(str(data["super_built_up_area"])) if data.get("super_built_up_area") else None,
            area_unit=data.get("area_unit", "sqft"),
            bedrooms=data.get("bedrooms", 0),
            bathrooms=data.get("bathrooms", 0),
            balconies=data.get("balconies", 0),
            parking_slots=data.get("parking_slots", 0),
            base_price=Decimal(str(data["base_price"])) if data.get("base_price") else None,
            price_per_sqft=Decimal(str(data["price_per_sqft"])) if data.get("price_per_sqft") else None,
            floor_rise_amount=Decimal(str(data["floor_rise_amount"])) if data.get("floor_rise_amount") else None,
            amenity_charges=Decimal(str(data["amenity_charges"])) if data.get("amenity_charges") else None,
            parking_charges=Decimal(str(data["parking_charges"])) if data.get("parking_charges") else None,
            total_price=Decimal(str(data["total_price"])) if data.get("total_price") else None,
            currency=data.get("currency", "INR"),
            inventory_status=UnitInventoryStatus.AVAILABLE,
            notes=data.get("notes"),
            extended_fields=data.get("extended_fields"),
        )
        self.db.add(unit)
        await self.db.flush()
        # Write initial status log
        await self._write_status_log(unit, previous=None, new=UnitInventoryStatus.AVAILABLE, reason="unit_created", actor_type="system")
        logger.info(f"[Unit] Created {unit.unit_code} project={data['project_id']}")
        return unit

    async def get_unit(self, org_id: uuid.UUID, unit_id: uuid.UUID) -> ProjectUnit:
        result = await self.db.execute(
            select(ProjectUnit).where(
                and_(ProjectUnit.id == unit_id,
                     ProjectUnit.organization_id == org_id,
                     ProjectUnit.deleted_at.is_(None))
            )
        )
        unit = result.scalar_one_or_none()
        if not unit:
            raise HTTPException(status_code=404, detail="Unit not found")
        return unit

    async def list_units(
        self, org_id: uuid.UUID, project_id: uuid.UUID,
        inventory_status: Optional[str] = None,
        unit_type: Optional[str] = None,
        limit: int = 100, offset: int = 0
    ) -> Tuple[List[ProjectUnit], int]:
        q = select(ProjectUnit).where(
            and_(ProjectUnit.organization_id == org_id,
                 ProjectUnit.project_id == project_id,
                 ProjectUnit.deleted_at.is_(None))
        )
        if inventory_status:
            q = q.where(ProjectUnit.inventory_status == inventory_status)
        if unit_type:
            q = q.where(ProjectUnit.unit_type == unit_type)
        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0
        items = (await self.db.execute(q.order_by(ProjectUnit.floor_number, ProjectUnit.unit_number).offset(offset).limit(limit))).scalars().all()
        return list(items), total

    async def transition_status(
        self,
        org_id: uuid.UUID,
        unit_id: uuid.UUID,
        to_status: str,
        reason: Optional[str] = None,
        actor_id: Optional[uuid.UUID] = None,
        actor_type: str = "user",
        deal_id: Optional[uuid.UUID] = None,
        idempotency_key: Optional[str] = None,
        reservation_ttl_hours: int = 48,
        channel_partner_id: Optional[uuid.UUID] = None,
    ) -> ProjectUnit:
        """
        Atomically transition a unit's inventory_status.
        Validates the state machine, writes a status log, and emits an OutboxEvent.
        """
        unit = await self.get_unit(org_id, unit_id)
        from_status = unit.inventory_status

        # 1. Idempotency guard for reservation
        if to_status == UnitInventoryStatus.RESERVED and idempotency_key:
            if unit.last_reservation_idempotency_key == idempotency_key:
                logger.info(f"[Unit] Idempotent reservation replay key={idempotency_key}")
                return unit

        # 2. Concurrency lock for reservation
        lock_token = None
        lock_name = None
        if to_status == UnitInventoryStatus.RESERVED:
            lock_name = f"inventory:unit:{unit_id}:reservation"
            acquired, lock_token = RedisDistributedLock.acquire(lock_name, ttl_seconds=30)
            if not acquired:
                raise HTTPException(
                    status_code=409,
                    detail=f"Unit {unit.unit_code} is currently undergoing a concurrent reservation."
                )

        try:
            if not UnitInventoryStatus.can_transition(from_status, to_status):
                raise HTTPException(
                    status_code=409,
                    detail=f"Cannot transition unit from '{from_status}' to '{to_status}'"
                )

            now = datetime.now(timezone.utc)
            unit.inventory_status = to_status

            if to_status == UnitInventoryStatus.RESERVED:
                unit.reserved_by_deal_id = deal_id
                unit.reserved_at = now
                unit.reservation_expires_at = now + timedelta(hours=reservation_ttl_hours)
                unit.last_reservation_idempotency_key = idempotency_key
                if channel_partner_id:
                    unit.channel_partner_id = channel_partner_id
            elif to_status == UnitInventoryStatus.BOOKED:
                unit.booked_by_deal_id = deal_id
                unit.booked_at = now
            elif to_status == UnitInventoryStatus.SOLD:
                unit.sold_at = now
            elif to_status == UnitInventoryStatus.AVAILABLE:
                # Release from reservation/return
                unit.reserved_by_deal_id = None
                unit.reserved_at = None
                unit.reservation_expires_at = None

            unit.updated_at = now

            # Write status log (append-only)
            log_entry = await self._write_status_log(
                unit, previous=from_status, new=to_status,
                reason=reason, actor_id=actor_id, actor_type=actor_type, deal_id=deal_id
            )

            # Write outbox event (transactional outbox pattern)
            try:
                await OutboxService.record_event(
                    self.db,
                    tenant_id=str(org_id),
                    event_type=f"inventory.unit.{to_status}",
                    aggregate_type="unit",
                    aggregate_id=str(unit.id),
                    payload={
                        "unit_id": str(unit.id),
                        "unit_code": unit.unit_code,
                        "project_id": str(unit.project_id),
                        "from_status": from_status,
                        "to_status": to_status,
                        "deal_id": str(deal_id) if deal_id else None,
                        "reason": reason,
                        "actor_id": str(actor_id) if actor_id else None,
                        "organization_id": str(org_id),
                    },
                    idempotency_key=f"inv_{unit.id}_{to_status}_{now.timestamp()}",
                )
            except Exception as e:
                logger.warning(f"[Unit] Outbox record_event: {e}")

            await self.db.flush()
            logger.info(f"[Unit] {unit.unit_code} {from_status}->{to_status} deal={deal_id}")
            return unit
        finally:
            if lock_name and lock_token:
                RedisDistributedLock.release(lock_name, lock_token)

    async def _write_status_log(
        self, unit: ProjectUnit, previous: Optional[str], new: str,
        reason: Optional[str] = None, actor_id: Optional[uuid.UUID] = None,
        actor_type: str = "system", deal_id: Optional[uuid.UUID] = None,
    ) -> ProjectUnitStatusLog:
        log = ProjectUnitStatusLog(
            unit_id=unit.id,
            organization_id=unit.organization_id,
            previous_status=previous,
            new_status=new,
            reason=reason,
            changed_by_id=actor_id,
            changed_by_type=actor_type,
            deal_id=deal_id,
        )
        self.db.add(log)
        return log


# ---------------------------------------------------------------------------
# 4. PriceBookService
# ---------------------------------------------------------------------------

class PriceBookService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_price_book(self, org_id: uuid.UUID, data: Dict[str, Any]) -> ProjectPriceBook:
        """Creates a new DRAFT price book for a project."""
        # Find the next version number
        max_version = (await self.db.execute(
            select(func.max(ProjectPriceBook.version)).where(
                ProjectPriceBook.project_id == data["project_id"]
            )
        )).scalar() or 0
        version = max_version + 1

        pb = ProjectPriceBook(
            organization_id=org_id,
            project_id=data["project_id"],
            version=version,
            title=data.get("title", f"Price Book v{version}"),
            effective_from=data["effective_from"],
            effective_until=data.get("effective_until"),
            status=PriceBookStatus.DRAFT,
            base_price_floor=Decimal(str(data["base_price_floor"])) if data.get("base_price_floor") else None,
            floor_rise_per_floor=Decimal(str(data["floor_rise_per_floor"])) if data.get("floor_rise_per_floor") else None,
            currency=data.get("currency", "INR"),
            notes=data.get("notes"),
        )
        self.db.add(pb)
        await self.db.flush()
        return pb

    async def publish_price_book(self, org_id: uuid.UUID, price_book_id: uuid.UUID, publisher_id: Optional[uuid.UUID] = None) -> ProjectPriceBook:
        """
        Publish a DRAFT price book. Supersedes any previously ACTIVE price book
        for the same project.
        """
        result = await self.db.execute(
            select(ProjectPriceBook).where(
                and_(ProjectPriceBook.id == price_book_id,
                     ProjectPriceBook.organization_id == org_id,
                     ProjectPriceBook.deleted_at.is_(None))
            )
        )
        pb = result.scalar_one_or_none()
        if not pb:
            raise HTTPException(status_code=404, detail="Price book not found")
        if pb.status != PriceBookStatus.DRAFT:
            raise HTTPException(status_code=409, detail=f"Cannot publish a price book with status '{pb.status}'")

        now = datetime.now(timezone.utc)

        # Supersede any currently ACTIVE price books for this project
        await self.db.execute(
            update(ProjectPriceBook)
            .where(and_(ProjectPriceBook.project_id == pb.project_id,
                        ProjectPriceBook.status == PriceBookStatus.ACTIVE,
                        ProjectPriceBook.deleted_at.is_(None)))
            .values(status=PriceBookStatus.SUPERSEDED, updated_at=now)
        )

        pb.status = PriceBookStatus.ACTIVE
        pb.published_by_id = publisher_id
        pb.published_at = now
        pb.updated_at = now
        await self.db.flush()
        logger.info(f"[PriceBook] Published v{pb.version} project={pb.project_id}")
        return pb

    async def add_entry(self, price_book_id: uuid.UUID, data: Dict[str, Any]) -> PriceBookEntry:
        entry = PriceBookEntry(
            price_book_id=price_book_id,
            unit_id=data.get("unit_id"),
            unit_type=data.get("unit_type"),
            floor_number=data.get("floor_number"),
            base_price=Decimal(str(data["base_price"])),
            price_per_sqft=Decimal(str(data["price_per_sqft"])) if data.get("price_per_sqft") else None,
            floor_rise_amount=Decimal(str(data["floor_rise_amount"])) if data.get("floor_rise_amount") else None,
            parking_charges=Decimal(str(data["parking_charges"])) if data.get("parking_charges") else None,
            other_charges=Decimal(str(data["other_charges"])) if data.get("other_charges") else None,
            total_price=Decimal(str(data["total_price"])) if data.get("total_price") else None,
            notes=data.get("notes"),
        )
        self.db.add(entry)
        await self.db.flush()
        return entry


# ---------------------------------------------------------------------------
# 5. ChannelPartnerService
# ---------------------------------------------------------------------------

class ChannelPartnerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_channel_partner(self, org_id: uuid.UUID, broker_id: uuid.UUID, data: Dict[str, Any]) -> ChannelPartner:
        code = data.get("cp_code") or _generate_code("CP")
        cp = ChannelPartner(
            organization_id=org_id,
            broker_id=broker_id,
            cp_code=code,
            firm_name=data.get("firm_name"),
            contact_name=data["contact_name"],
            email=data.get("email"),
            phone=data.get("phone"),
            whatsapp_number=data.get("whatsapp_number"),
            rera_number=data.get("rera_number"),
            pan_number=data.get("pan_number"),
            gst_number=data.get("gst_number"),
            city=data.get("city"),
            state=data.get("state"),
            country_code=data.get("country_code", "IN"),
            tier=data.get("tier", ChannelPartnerTier.STANDARD),
            status=ChannelPartnerStatus.PENDING_KYC,
            default_commission_pct=Decimal(str(data["default_commission_pct"])) if data.get("default_commission_pct") else None,
            notes=data.get("notes"),
            extended_fields=data.get("extended_fields"),
        )
        self.db.add(cp)
        await self.db.flush()
        logger.info(f"[ChannelPartner] Registered {cp.cp_code} org={org_id}")
        return cp

    async def get_channel_partner(self, org_id: uuid.UUID, cp_id: uuid.UUID) -> ChannelPartner:
        result = await self.db.execute(
            select(ChannelPartner).where(
                and_(ChannelPartner.id == cp_id,
                     ChannelPartner.organization_id == org_id,
                     ChannelPartner.deleted_at.is_(None))
            )
        )
        cp = result.scalar_one_or_none()
        if not cp:
            raise HTTPException(status_code=404, detail="Channel partner not found")
        return cp

    async def list_channel_partners(
        self, org_id: uuid.UUID, status: Optional[str] = None,
        tier: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> Tuple[List[ChannelPartner], int]:
        q = select(ChannelPartner).where(
            and_(ChannelPartner.organization_id == org_id,
                 ChannelPartner.deleted_at.is_(None))
        )
        if status:
            q = q.where(ChannelPartner.status == status)
        if tier:
            q = q.where(ChannelPartner.tier == tier)
        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0
        items = (await self.db.execute(q.order_by(ChannelPartner.contact_name).offset(offset).limit(limit))).scalars().all()
        return list(items), total

    async def verify_kyc(self, org_id: uuid.UUID, cp_id: uuid.UUID) -> ChannelPartner:
        cp = await self.get_channel_partner(org_id, cp_id)
        now = datetime.now(timezone.utc)
        cp.status = ChannelPartnerStatus.KYC_VERIFIED
        cp.kyc_verified = True
        cp.kyc_verified_at = now
        cp.updated_at = now
        await self.db.flush()
        return cp

    async def create_project_agreement(
        self, org_id: uuid.UUID, cp_id: uuid.UUID,
        project_id: uuid.UUID, data: Dict[str, Any]
    ) -> ChannelPartnerProjectAgreement:
        # Check for existing active agreement
        existing = (await self.db.execute(
            select(ChannelPartnerProjectAgreement).where(
                and_(ChannelPartnerProjectAgreement.channel_partner_id == cp_id,
                     ChannelPartnerProjectAgreement.project_id == project_id,
                     ChannelPartnerProjectAgreement.deleted_at.is_(None))
            )
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Agreement already exists for this CP-Project pair")

        agreement = ChannelPartnerProjectAgreement(
            organization_id=org_id,
            channel_partner_id=cp_id,
            project_id=project_id,
            is_active=True,
            valid_from=data["valid_from"],
            valid_until=data.get("valid_until"),
            commission_pct=Decimal(str(data["commission_pct"])) if data.get("commission_pct") else None,
            brokerage_fee=Decimal(str(data["brokerage_fee"])) if data.get("brokerage_fee") else None,
            commission_slabs=data.get("commission_slabs", []),
            is_exclusive=data.get("is_exclusive", False),
            document_url=data.get("document_url"),
            notes=data.get("notes"),
        )
        self.db.add(agreement)
        await self.db.flush()
        return agreement

    async def record_commission(
        self, org_id: uuid.UUID, cp_id: uuid.UUID, data: Dict[str, Any]
    ) -> ChannelPartnerCommission:
        comm = ChannelPartnerCommission(
            organization_id=org_id,
            channel_partner_id=cp_id,
            deal_id=data.get("deal_id"),
            unit_id=data.get("unit_id"),
            project_id=data.get("project_id"),
            transaction_value=Decimal(str(data["transaction_value"])),
            commission_pct=Decimal(str(data["commission_pct"])),
            commission_amount=Decimal(str(data["commission_amount"])),
            gst_amount=Decimal(str(data["gst_amount"])) if data.get("gst_amount") else None,
            tds_amount=Decimal(str(data["tds_amount"])) if data.get("tds_amount") else None,
            net_payable=Decimal(str(data["net_payable"])) if data.get("net_payable") else None,
            currency=data.get("currency", "INR"),
            payment_status="pending",
            due_date=data.get("due_date"),
            notes=data.get("notes"),
        )
        self.db.add(comm)
        await self.db.flush()
        return comm


# ---------------------------------------------------------------------------
# 6. InventorySnapshotService
# ---------------------------------------------------------------------------

class InventorySnapshotService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def materialize_snapshot(self, org_id: uuid.UUID, project_id: uuid.UUID) -> InventoryAvailabilitySnapshot:
        """
        Build and persist a fresh InventoryAvailabilitySnapshot for a project.
        This is called after any unit status transition.
        """
        # Aggregate by status
        rows = (await self.db.execute(
            select(
                ProjectUnit.inventory_status,
                func.count(ProjectUnit.id).label("cnt")
            ).where(
                and_(ProjectUnit.project_id == project_id,
                     ProjectUnit.deleted_at.is_(None))
            ).group_by(ProjectUnit.inventory_status)
        )).all()
        status_map = {r.inventory_status: r.cnt for r in rows}
        total = sum(status_map.values())

        # Aggregate by unit_type
        type_rows = (await self.db.execute(
            select(
                ProjectUnit.unit_type,
                ProjectUnit.inventory_status,
                func.count(ProjectUnit.id).label("cnt")
            ).where(
                and_(ProjectUnit.project_id == project_id,
                     ProjectUnit.deleted_at.is_(None))
            ).group_by(ProjectUnit.unit_type, ProjectUnit.inventory_status)
        )).all()
        by_type: Dict = {}
        for r in type_rows:
            by_type.setdefault(r.unit_type, {})[r.inventory_status] = r.cnt

        # Price range of available units
        price_row = (await self.db.execute(
            select(
                func.min(ProjectUnit.total_price).label("min_p"),
                func.max(ProjectUnit.total_price).label("max_p"),
            ).where(
                and_(ProjectUnit.project_id == project_id,
                     ProjectUnit.inventory_status == UnitInventoryStatus.AVAILABLE,
                     ProjectUnit.deleted_at.is_(None))
            )
        )).one_or_none()
        price_range = None
        if price_row and price_row.min_p is not None:
            price_range = {
                "min": float(price_row.min_p),
                "max": float(price_row.max_p),
                "currency": "INR",  # TODO: pull from project
            }

        snapshot = InventoryAvailabilitySnapshot(
            organization_id=org_id,
            project_id=project_id,
            snapshot_at=datetime.now(timezone.utc),
            total_units=total,
            available_units=status_map.get(UnitInventoryStatus.AVAILABLE, 0),
            reserved_units=status_map.get(UnitInventoryStatus.RESERVED, 0),
            booked_units=status_map.get(UnitInventoryStatus.BOOKED, 0),
            sold_units=status_map.get(UnitInventoryStatus.SOLD, 0),
            blocked_units=status_map.get(UnitInventoryStatus.BLOCKED, 0),
            under_offer_units=status_map.get(UnitInventoryStatus.UNDER_OFFER, 0),
            by_unit_type=by_type,
            price_range_available=price_range,
        )
        self.db.add(snapshot)
        await self.db.flush()
        return snapshot

    async def get_latest_snapshot(self, org_id: uuid.UUID, project_id: uuid.UUID) -> Optional[InventoryAvailabilitySnapshot]:
        result = await self.db.execute(
            select(InventoryAvailabilitySnapshot).where(
                and_(InventoryAvailabilitySnapshot.project_id == project_id,
                     InventoryAvailabilitySnapshot.organization_id == org_id)
            ).order_by(InventoryAvailabilitySnapshot.snapshot_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()
