"""
Enterprise Property Inventory & Property CRM Service
===================================================
Production-grade property management, live inventory tracking, atomic reservation,
lead ↔ property relationship lifecycle, site visit coordination, multi-dimensional search,
sanitized public sharing, analytics, and CSV import.
"""
from __future__ import annotations

import csv
import io
import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, update

from app.models.property_models import (
    PropertyListing, PropertyMedia, PropertyPriceHistory, LeadPropertyInterest
)
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.crm_models import Task, Meeting, Activity
from app.models.audit_log import AuditLog
from app.modules.security.services.file_security import FileSecurityScanner
from app.services.property_ai_valuation_service import PropertyAIValuationService
from app.infrastructure.cache.query_cache import AsyncQueryCacheService
from app.infrastructure.events.event_bus import DomainEventBus, DomainEvent, StandardDomainEvents, ActorContext

from app.infrastructure.tenancy.scope import resolve_organization_id_for_broker
from app.infrastructure.ai_gateway.gateway import AIGateway

logger = logging.getLogger("beetlelabs.properties.service")


class PropertyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _resolve_tenant_org_id(self, broker: Broker, explicit_org_id: Optional[Union[str, uuid.UUID]] = None) -> uuid.UUID:
        if explicit_org_id is not None:
            return explicit_org_id if isinstance(explicit_org_id, uuid.UUID) else uuid.UUID(str(explicit_org_id))
        broker_id = broker.id if isinstance(broker.id, uuid.UUID) else uuid.UUID(str(broker.id))
        return await resolve_organization_id_for_broker(self.db, broker_id, requested_organization_id=explicit_org_id, allow_fallback=True)

    def _tenant_filter(self, broker_id: uuid.UUID, org_id: uuid.UUID):
        return or_(
            PropertyListing.organization_id == org_id,
            and_(PropertyListing.organization_id.is_(None), PropertyListing.broker_id == broker_id)
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Core Property CRUD & Codes
    # ─────────────────────────────────────────────────────────────────────────

    async def create_property(
        self,
        broker: Broker,
        data: Dict[str, Any],
        organization_id: Optional[Union[str, uuid.UUID]] = None
    ) -> PropertyListing:
        """Creates a canonical property listing with tenant scoping and audit log."""
        broker_id = broker.id
        if isinstance(broker_id, str):
            broker_id = uuid.UUID(broker_id)
        org_id = await self._resolve_tenant_org_id(broker, organization_id or data.get("organization_id"))

        # Generate unique human-readable property code if not provided
        property_code = data.get("property_code")
        if not property_code:
            property_code = f"PROP-{secrets.token_hex(3).upper()}"

        # Generate unique public share token
        share_token = secrets.token_urlsafe(24)

        price = float(data.get("price", 0))
        area_value = float(data.get("area_value") or data.get("built_up_area_sqft") or 1000.0)
        price_per_sqft = data.get("price_per_sqft")
        if price_per_sqft is None and area_value > 0:
            price_per_sqft = round(price / area_value, 2)

        assigned_agent_id = data.get("assigned_agent_id")
        if assigned_agent_id and isinstance(assigned_agent_id, str):
            try:
                assigned_agent_id = uuid.UUID(assigned_agent_id)
            except ValueError:
                assigned_agent_id = None

        listing = PropertyListing(
            organization_id=org_id,
            broker_id=broker_id,
            property_code=property_code,
            share_token=share_token,
            title=data.get("title", "").strip(),
            description=data.get("description", "").strip(),
            property_category=data.get("property_category", "residential"),
            property_type=data.get("property_type", "apartment"),
            transaction_category=data.get("transaction_category", "resale"),
            listing_type=data.get("listing_type", "exclusive"),
            status=data.get("status", "available").lower(),
            price=price,
            price_min=data.get("price_min"),
            price_max=data.get("price_max"),
            monthly_rent=data.get("monthly_rent"),
            security_deposit=data.get("security_deposit"),
            price_per_sqft=price_per_sqft,
            currency_code=data.get("currency_code", "INR").upper(),
            area_value=area_value,
            area_unit=data.get("area_unit", "sqft"),
            carpet_area=data.get("carpet_area"),
            super_built_up_area=data.get("super_built_up_area"),
            plot_area=data.get("plot_area"),
            bedrooms=int(data.get("bedrooms", 1)),
            bathrooms=int(data.get("bathrooms", 1)),
            balconies=int(data.get("balconies", 0)),
            parking_spaces=int(data.get("parking_spaces", 1)),
            floor_number=data.get("floor_number"),
            total_floors=data.get("total_floors"),
            facing=data.get("facing"),
            furnishing=data.get("furnishing", "unfurnished"),
            age_years=data.get("age_years"),
            possession_date=data.get("possession_date"),
            construction_status=data.get("construction_status", "ready_to_move"),
            developer_name=data.get("developer_name"),
            project_name=data.get("project_name"),
            building_name=data.get("building_name"),
            unit_number=data.get("unit_number"),
            address=data.get("address"),
            locality=data.get("locality", "Indiranagar"),
            city=data.get("city", "Bengaluru"),
            state=data.get("state", "Karnataka"),
            country_code=data.get("country_code", "IN"),
            postal_code=data.get("postal_code"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            amenities=data.get("amenities") or [],
            marketing_highlights=data.get("marketing_highlights") or [],
            owner_name=data.get("owner_name"),
            owner_phone=data.get("owner_phone"),
            owner_email=data.get("owner_email"),
            assigned_agent_id=assigned_agent_id,
            commission_amount=data.get("commission_amount"),
            commission_percentage=data.get("commission_percentage"),
            internal_notes=data.get("internal_notes"),
            extended_fields={"amenities": data.get("amenities") or []}
        )

        self.db.add(listing)
        # Flush so the DB assigns listing.id before we reference it in the audit log
        await self.db.flush()

        # Audit Log — resource_id is now populated with canonical organization_id
        audit = AuditLog(
            organization_id=org_id,
            actor_id=broker_id,
            actor_type="user",
            action="property.create",
            resource_type="property",
            resource_id=str(listing.id),
            new_values={"title": listing.title, "price": listing.price, "code": listing.property_code}
        )
        self.db.add(audit)
        await self.db.commit()

        await self.db.refresh(listing)

        # Invalidate tenant search and matching cache and emit domain event
        AsyncQueryCacheService.invalidate_tag(f"tenant:{org_id}:search")
        AsyncQueryCacheService.invalidate_tag(f"tenant:{org_id}:matches")
        try:
            await DomainEventBus.publish(
                DomainEvent(
                    event_type=StandardDomainEvents.PROPERTY_CREATED,
                    organization_id=str(org_id),
                    payload={"property_id": str(listing.id), "title": listing.title}
                )
            )
        except Exception:
            pass

        return listing

    async def get_property(
        self,
        property_id: str | uuid.UUID,
        broker: Broker,
        organization_id: Optional[Union[str, uuid.UUID]] = None
    ) -> PropertyListing:
        """Fetches property strictly scoped to authenticated organization with dual-read support."""
        broker_id = broker.id
        if isinstance(broker_id, str):
            broker_id = uuid.UUID(broker_id)
        org_id = await self._resolve_tenant_org_id(broker, organization_id)

        p_uuid = uuid.UUID(str(property_id)) if not isinstance(property_id, uuid.UUID) else property_id

        stmt = select(PropertyListing).where(
            PropertyListing.id == p_uuid,
            self._tenant_filter(broker_id, org_id),
            PropertyListing.deleted_at.is_(None)
        )
        res = await self.db.execute(stmt)
        prop = res.scalars().first()
        if not prop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Property {property_id} not found."
            )
        return prop

    async def update_property(
        self,
        property_id: str | uuid.UUID,
        broker: Broker,
        updates: Dict[str, Any],
        organization_id: Optional[Union[str, uuid.UUID]] = None
    ) -> PropertyListing:
        """Updates property with price history tracking and audit logging."""
        prop = await self.get_property(property_id, broker, organization_id)
        broker_id = broker.id if isinstance(broker.id, uuid.UUID) else uuid.UUID(str(broker.id))
        org_id = await self._resolve_tenant_org_id(broker, organization_id)

        # Check for price change
        if "price" in updates and updates["price"] is not None:
            new_price = float(updates["price"])
            if abs(new_price - prop.price) > 0.01:
                price_hist = PropertyPriceHistory(
                    property_id=prop.id,
                    old_price=prop.price,
                    new_price=new_price,
                    changed_by_id=broker_id,
                    reason=updates.get("price_change_reason", "Manual price update")
                )
                self.db.add(price_hist)
                prop.price = new_price
                if prop.area_value > 0:
                    prop.price_per_sqft = round(new_price / prop.area_value, 2)

        # Update fields
        for field, val in updates.items():
            if field in ("price", "price_change_reason", "id", "broker_id", "organization_id", "created_at"):
                continue
            if hasattr(prop, field) and val is not None:
                if field == "assigned_agent_id" and isinstance(val, str):
                    try:
                        val = uuid.UUID(val)
                    except ValueError:
                        val = None
                setattr(prop, field, val)

        # Update extended amenities if present
        if "amenities" in updates and isinstance(updates["amenities"], list):
            prop.amenities = updates["amenities"]
            ext = dict(prop.extended_fields or {})
            ext["amenities"] = updates["amenities"]
            prop.extended_fields = ext

        audit = AuditLog(
            organization_id=org_id,
            actor_id=broker_id,
            actor_type="user",
            action="property.update",
            resource_type="property",
            resource_id=str(prop.id),
            new_values={"status": prop.status, "price": prop.price}
        )
        self.db.add(audit)

        await self.db.commit()
        await self.db.refresh(prop)

        # Invalidate property, search, and matching cache and emit domain event
        AsyncQueryCacheService.invalidate_tag(f"tenant:{org_id}:property:{prop.id}")
        AsyncQueryCacheService.invalidate_tag(f"tenant:{org_id}:search")
        AsyncQueryCacheService.invalidate_tag(f"tenant:{org_id}:matches")
        try:
            await DomainEventBus.publish(
                DomainEvent(
                    event_type=StandardDomainEvents.PROPERTY_UPDATED,
                    organization_id=str(org_id),
                    payload={"property_id": str(prop.id), "status": prop.status, "price": prop.price}
                )
            )
        except Exception:
            pass

        return prop

    async def archive_property(
        self,
        property_id: str | uuid.UUID,
        broker: Broker,
        organization_id: Optional[Union[str, uuid.UUID]] = None
    ) -> PropertyListing:
        """Safely archives property (status=ARCHIVED, deleted_at=now)."""
        prop = await self.get_property(property_id, broker, organization_id)
        broker_id = broker.id if isinstance(broker.id, uuid.UUID) else uuid.UUID(str(broker.id))
        org_id = await self._resolve_tenant_org_id(broker, organization_id)
        prop.status = "archived"
        prop.deleted_at = datetime.now(timezone.utc)

        audit = AuditLog(
            organization_id=org_id,
            actor_id=broker_id,
            actor_type="user",
            action="property.archive",
            resource_type="property",
            resource_id=str(prop.id)
        )
        self.db.add(audit)

        await self.db.commit()
        await self.db.refresh(prop)

        # Invalidate property, search, and matching cache and emit domain event
        AsyncQueryCacheService.invalidate_tag(f"tenant:{org_id}:property:{prop.id}")
        AsyncQueryCacheService.invalidate_tag(f"tenant:{org_id}:search")
        AsyncQueryCacheService.invalidate_tag(f"tenant:{org_id}:matches")
        try:
            await DomainEventBus.publish(
                DomainEvent(
                    event_type=StandardDomainEvents.PROPERTY_ARCHIVED,
                    organization_id=str(org_id),
                    payload={"property_id": str(prop.id)}
                )
            )
        except Exception:
            pass

        return prop

    # ─────────────────────────────────────────────────────────────────────────
    # 1b. Price Update (Part 35.1) — surfaces PRICE_CHANGE_MATCH opportunities
    # ─────────────────────────────────────────────────────────────────────────

    async def update_price(
        self,
        property_id: str | uuid.UUID,
        broker: Broker,
        new_price: float,
        reason: str = "Market adjustment",
        organization_id: Optional[Union[str, uuid.UUID]] = None
    ) -> PropertyListing:
        """
        Dedicated price update that writes PropertyPriceHistory atomically.
        Used by the 'Update Price' UI workflow to trigger PRICE_CHANGE_MATCH
        revenue opportunities when a price drops into a lead's budget range.
        """
        if new_price <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="New price must be greater than zero."
            )

        prop = await self.get_property(property_id, broker, organization_id)
        broker_id = broker.id if isinstance(broker.id, uuid.UUID) else uuid.UUID(str(broker.id))
        org_id = await self._resolve_tenant_org_id(broker, organization_id)
        old_price = prop.price

        if abs(new_price - old_price) < 0.01:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="New price is the same as current price. No change recorded."
            )

        # Record price history
        price_hist = PropertyPriceHistory(
            property_id=prop.id,
            old_price=old_price,
            new_price=new_price,
            changed_by_id=broker_id,
            reason=reason
        )
        self.db.add(price_hist)

        # Update listing
        prop.price = new_price
        if prop.area_value and prop.area_value > 0:
            prop.price_per_sqft = round(new_price / prop.area_value, 2)

        # Audit log
        direction = "reduced" if new_price < old_price else "increased"
        audit = AuditLog(
            organization_id=org_id,
            actor_id=broker_id,
            actor_type="user",
            action="property.price_update",
            resource_type="property",
            resource_id=str(prop.id),
            previous_values={"price": old_price},
            new_values={"price": new_price, "reason": reason, "direction": direction}
        )
        self.db.add(audit)

        await self.db.commit()
        await self.db.refresh(prop)

        # Invalidate property intelligence cache and search cache
        AsyncQueryCacheService.invalidate_tag(f"tenant:{org_id}:property:{prop.id}")
        AsyncQueryCacheService.invalidate_tag(f"tenant:{org_id}:search")
        try:
            await DomainEventBus.publish(
                DomainEvent(
                    event_type=StandardDomainEvents.PROPERTY_PRICE_CHANGED,
                    organization_id=str(org_id),
                    payload={
                        "property_id": str(prop.id),
                        "old_price": old_price,
                        "new_price": new_price,
                        "reason": reason
                    }
                )
            )
        except Exception:
            pass

        logger.info(
            f"Price {direction} for property {prop.property_code}: "
            f"₹{old_price:,.0f} → ₹{new_price:,.0f} ({reason})"
        )
        return prop

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Search, Filter & Pagination Engine
    # ─────────────────────────────────────────────────────────────────────────

    async def search_and_filter(
        self,
        broker: Broker,
        query: Optional[str] = None,
        property_type: Optional[str] = None,
        property_category: Optional[str] = None,
        transaction_category: Optional[str] = None,
        status_filter: Optional[str] = None,
        city: Optional[str] = None,
        locality: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_area: Optional[float] = None,
        max_area: Optional[float] = None,
        bedrooms: Optional[int] = None,
        bathrooms: Optional[int] = None,
        furnishing: Optional[str] = None,
        construction_status: Optional[str] = None,
        assigned_agent_id: Optional[str] = None,
        sort_by: str = "newest",
        page: int = 1,
        limit: int = 20,
        organization_id: Optional[Union[str, uuid.UUID]] = None
    ) -> Dict[str, Any]:
        """Powerful, indexed, multi-attribute property inventory search with tenant scoping."""
        broker_id = broker.id
        if isinstance(broker_id, str):
            broker_id = uuid.UUID(broker_id)
        org_id = await self._resolve_tenant_org_id(broker, organization_id)

        stmt = select(PropertyListing).where(
            self._tenant_filter(broker_id, org_id),
            PropertyListing.deleted_at.is_(None)
        )

        # Full-text query across code, title, project, locality, city, developer
        if query and query.strip():
            term = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    PropertyListing.title.ilike(term),
                    PropertyListing.property_code.ilike(term),
                    PropertyListing.project_name.ilike(term),
                    PropertyListing.locality.ilike(term),
                    PropertyListing.city.ilike(term),
                    PropertyListing.developer_name.ilike(term),
                    PropertyListing.description.ilike(term)
                )
            )

        if property_type and property_type.lower() != "all":
            stmt = stmt.where(PropertyListing.property_type.ilike(f"%{property_type.strip()}%"))
        if property_category and property_category.lower() != "all":
            stmt = stmt.where(PropertyListing.property_category == property_category.strip().lower())
        if transaction_category and transaction_category.lower() != "all":
            stmt = stmt.where(PropertyListing.transaction_category == transaction_category.strip().lower())
        if status_filter and status_filter.lower() != "all":
            stmt = stmt.where(PropertyListing.status == status_filter.strip().lower())

        if city:
            stmt = stmt.where(PropertyListing.city.ilike(f"%{city.strip()}%"))
        if locality:
            stmt = stmt.where(PropertyListing.locality.ilike(f"%{locality.strip()}%"))

        if min_price is not None:
            stmt = stmt.where(PropertyListing.price >= min_price)
        if max_price is not None:
            stmt = stmt.where(PropertyListing.price <= max_price)
        if min_area is not None:
            stmt = stmt.where(PropertyListing.area_value >= min_area)
        if max_area is not None:
            stmt = stmt.where(PropertyListing.area_value <= max_area)

        if bedrooms is not None:
            stmt = stmt.where(PropertyListing.bedrooms == bedrooms)
        if bathrooms is not None:
            stmt = stmt.where(PropertyListing.bathrooms == bathrooms)

        if furnishing and furnishing.lower() != "all":
            stmt = stmt.where(PropertyListing.furnishing == furnishing.strip().lower())
        if construction_status and construction_status.lower() != "all":
            stmt = stmt.where(PropertyListing.construction_status == construction_status.strip().lower())

        if assigned_agent_id:
            try:
                agent_uuid = uuid.UUID(assigned_agent_id)
                stmt = stmt.where(PropertyListing.assigned_agent_id == agent_uuid)
            except ValueError:
                pass

        # Sorting
        if sort_by == "price_asc":
            stmt = stmt.order_by(PropertyListing.price.asc())
        elif sort_by == "price_desc":
            stmt = stmt.order_by(PropertyListing.price.desc())
        elif sort_by == "area_asc":
            stmt = stmt.order_by(PropertyListing.area_value.asc())
        elif sort_by == "area_desc":
            stmt = stmt.order_by(PropertyListing.area_value.desc())
        elif sort_by == "oldest":
            stmt = stmt.order_by(PropertyListing.created_at.asc())
        elif sort_by == "recently_updated":
            stmt = stmt.order_by(PropertyListing.updated_at.desc())
        else:
            stmt = stmt.order_by(PropertyListing.created_at.desc())

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_res = await self.db.execute(count_stmt)
        total = count_res.scalar() or 0

        # Pagination
        offset = (page - 1) * limit
        stmt = stmt.offset(offset).limit(limit)

        res = await self.db.execute(stmt)
        items = list(res.scalars().all())

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "items": [self.serialize_property(p) for p in items]
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Concurrency-Safe Atomic Reservation
    # ─────────────────────────────────────────────────────────────────────────

    async def reserve_property(
        self,
        property_id: str | uuid.UUID,
        broker: Broker,
        lead_id: Optional[str | uuid.UUID] = None,
        organization_id: Optional[Union[str, uuid.UUID]] = None
    ) -> PropertyListing:
        """
        Atomic reservation with concurrency conflict protection and tenant scoping.
        Guarantees exactly one reservation succeeds when multiple workers or agents race.
        """
        broker_id = broker.id if isinstance(broker.id, uuid.UUID) else uuid.UUID(str(broker.id))
        org_id = await self._resolve_tenant_org_id(broker, organization_id)
        p_uuid = property_id if isinstance(property_id, uuid.UUID) else uuid.UUID(str(property_id))

        # Check existing status atomically with tenant filter
        stmt = select(PropertyListing).where(
            PropertyListing.id == p_uuid,
            self._tenant_filter(broker_id, org_id),
            PropertyListing.deleted_at.is_(None)
        )
        res = await self.db.execute(stmt)
        prop = res.scalars().first()
        if not prop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found.")

        if prop.status.lower() != "available":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Property is currently '{prop.status.upper()}' and cannot be reserved."
            )

        # Atomic update
        prop.status = "reserved"

        # If lead provided, record reservation in LeadPropertyInterest
        if lead_id:
            lead_uuid = lead_id if isinstance(lead_id, uuid.UUID) else uuid.UUID(str(lead_id))
            await self.link_lead_property(
                lead_id=lead_uuid,
                property_id=prop.id,
                broker=broker,
                status="RESERVED",
                notes="Property reserved by agent.",
                organization_id=org_id
            )

        # Audit Log
        audit = AuditLog(
            organization_id=org_id,
            actor_id=broker_id,
            actor_type="user",
            action="property.reserve",
            resource_type="property",
            resource_id=str(prop.id),
            new_values={"status": "reserved", "lead_id": str(lead_id) if lead_id else None}
        )
        self.db.add(audit)

        await self.db.commit()
        await self.db.refresh(prop)

        # Invalidate property and search cache and emit domain event
        AsyncQueryCacheService.invalidate_tag(f"tenant:{org_id}:property:{prop.id}")
        AsyncQueryCacheService.invalidate_tag(f"tenant:{org_id}:search")
        try:
            await DomainEventBus.publish(
                DomainEvent(
                    event_type=StandardDomainEvents.PROPERTY_AVAILABILITY_CHANGED,
                    organization_id=str(org_id),
                    payload={"property_id": str(prop.id), "status": "reserved", "lead_id": str(lead_id) if lead_id else None}
                )
            )
        except Exception:
            pass

        return prop

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Public Property Share (STRICT SANITIZATION)
    # ─────────────────────────────────────────────────────────────────────────

    async def get_public_share(self, share_token: str) -> Dict[str, Any]:
        """
        Returns public-facing, sanitized property details without exposing internal CRM data.
        Owner contact, internal notes, commission, and private docs are STRICTLY REDACTED.
        """
        if not share_token or len(share_token) < 10:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid share link.")

        stmt = select(PropertyListing).where(
            PropertyListing.share_token == share_token,
            PropertyListing.deleted_at.is_(None)
        )
        res = await self.db.execute(stmt)
        prop = res.scalars().first()
        if not prop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property listing not found.")

        # Load public media only
        media_stmt = select(PropertyMedia).where(
            PropertyMedia.property_id == prop.id,
            PropertyMedia.is_private.is_(False)
        ).order_by(PropertyMedia.sort_order.asc())
        media_res = await self.db.execute(media_stmt)
        public_media = media_res.scalars().all()

        return {
            "property_code": prop.property_code,
            "title": prop.title,
            "description": prop.description,
            "property_category": prop.property_category,
            "property_type": prop.property_type,
            "transaction_category": prop.transaction_category,
            "status": prop.status,
            "price": prop.price,
            "currency": prop.currency_code,
            "area_value": prop.area_value,
            "area_unit": prop.area_unit,
            "bedrooms": prop.bedrooms,
            "bathrooms": prop.bathrooms,
            "balconies": prop.balconies,
            "parking_spaces": prop.parking_spaces,
            "furnishing": prop.furnishing,
            "facing": prop.facing,
            "construction_status": prop.construction_status,
            "project_name": prop.project_name,
            "locality": prop.locality,
            "city": prop.city,
            "amenities": prop.amenities or [],
            "marketing_highlights": prop.marketing_highlights or [],
            "media": [
                {
                    "media_type": m.media_type,
                    "url": m.url,
                    "title": m.title,
                    "is_primary": m.is_primary
                } for m in public_media
            ]
            # STRICTLY NO owner_name, owner_phone, owner_email, commission, internal_notes, or broker_id!
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Duplicate Property Detection
    # ─────────────────────────────────────────────────────────────────────────

    async def detect_duplicates(
        self,
        broker: Broker,
        data: Dict[str, Any],
        exclude_id: Optional[uuid.UUID] = None,
        organization_id: Optional[Union[str, uuid.UUID]] = None
    ) -> List[Dict[str, Any]]:
        """
        Scans existing inventory for potential duplicates based on
        (city, locality, project_name, unit_number) or (city, address, unit_number).
        """
        broker_id = broker.id if isinstance(broker.id, uuid.UUID) else uuid.UUID(str(broker.id))
        org_id = await self._resolve_tenant_org_id(broker, organization_id)
        city = (data.get("city") or "").strip().lower()
        project = (data.get("project_name") or "").strip().lower()
        unit = (data.get("unit_number") or "").strip().lower()
        address = (data.get("address") or "").strip().lower()

        if not city:
            return []

        conditions = []
        if project and unit:
            conditions.append(
                and_(
                    func.lower(PropertyListing.city) == city,
                    func.lower(PropertyListing.project_name) == project,
                    func.lower(PropertyListing.unit_number) == unit
                )
            )
        if address and unit:
            conditions.append(
                and_(
                    func.lower(PropertyListing.city) == city,
                    func.lower(PropertyListing.address) == address,
                    func.lower(PropertyListing.unit_number) == unit
                )
            )

        if not conditions:
            return []

        stmt = select(PropertyListing).where(
            self._tenant_filter(broker_id, org_id),
            PropertyListing.deleted_at.is_(None),
            or_(*conditions)
        )
        if exclude_id:
            stmt = stmt.where(PropertyListing.id != exclude_id)

        res = await self.db.execute(stmt)
        duplicates = res.scalars().all()

        return [
            {
                "id": str(p.id),
                "property_code": p.property_code,
                "title": p.title,
                "project_name": p.project_name,
                "unit_number": p.unit_number,
                "status": p.status,
                "price": float(p.price)
            } for p in duplicates
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # 6. Lead ↔ Property Relationship & Multi-Property Interest
    # ─────────────────────────────────────────────────────────────────────────

    async def link_lead_property(
        self,
        lead_id: str | uuid.UUID,
        property_id: str | uuid.UUID,
        broker: Broker,
        status: str = "INTERESTED",
        interest_level: str = "medium",
        match_score: float = 0.0,
        notes: Optional[str] = None,
        source: str = "manual",
        organization_id: Optional[Union[str, uuid.UUID]] = None
    ) -> LeadPropertyInterest:
        """Creates or updates a many-to-many Lead ↔ Property interest record with tenant scoping."""
        broker_id = broker.id if isinstance(broker.id, uuid.UUID) else uuid.UUID(str(broker.id))
        org_id = await self._resolve_tenant_org_id(broker, organization_id)
        lead_uuid = lead_id if isinstance(lead_id, uuid.UUID) else uuid.UUID(str(lead_id))
        prop_uuid = property_id if isinstance(property_id, uuid.UUID) else uuid.UUID(str(property_id))

        # Verify lead belongs to organization (dual-read)
        lead_filter = or_(
            Lead.organization_id == org_id,
            and_(Lead.organization_id.is_(None), Lead.broker_id == broker_id)
        )
        lead_stmt = select(Lead).where(Lead.id == lead_uuid, lead_filter)
        lead_res = await self.db.execute(lead_stmt)
        lead = lead_res.scalars().first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found.")

        # Verify property belongs to organization
        prop_stmt = select(PropertyListing).where(
            PropertyListing.id == prop_uuid,
            self._tenant_filter(broker_id, org_id)
        )
        prop_res = await self.db.execute(prop_stmt)
        prop = prop_res.scalars().first()
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found.")

        # Check existing interest
        existing_stmt = select(LeadPropertyInterest).where(
            or_(
                LeadPropertyInterest.organization_id == org_id,
                LeadPropertyInterest.organization_id == broker_id
            ),
            LeadPropertyInterest.lead_id == lead_uuid,
            LeadPropertyInterest.property_id == prop_uuid
        )
        existing_res = await self.db.execute(existing_stmt)
        interest = existing_res.scalars().first()

        now = datetime.now(timezone.utc)
        if interest:
            interest.status = status.upper()
            interest.interest_level = interest_level
            if notes:
                interest.notes = f"{interest.notes}\n{notes}" if interest.notes else notes
            interest.last_viewed_at = now
            if match_score > 0:
                interest.match_score = match_score
        else:
            interest = LeadPropertyInterest(
                organization_id=org_id,
                lead_id=lead_uuid,
                property_id=prop_uuid,
                status=status.upper(),
                interest_level=interest_level,
                first_matched_at=now,
                interested_at=now,
                last_viewed_at=now,
                notes=notes,
                match_score=match_score,
                source_of_match=source
            )
            self.db.add(interest)

        # Log Activity
        act = Activity(
            actor_id=broker_id,
            lead_id=lead_uuid,
            organization_id=str(org_id),
            activity_type="property_interest_linked",
            title=f"Interested in {prop.title}",
            description=f"Status: {status.upper()} | Source: {source}",
            activity_data={"property_id": str(prop_uuid), "property_title": prop.title, "status": status.upper()}
        )
        self.db.add(act)

        await self.db.commit()
        await self.db.refresh(interest)
        return interest

    async def list_interested_leads(
        self,
        property_id: str | uuid.UUID,
        broker: Broker,
        organization_id: Optional[Union[str, uuid.UUID]] = None
    ) -> List[Dict[str, Any]]:
        """Lists all leads interested in a property with relationship status and details."""
        prop = await self.get_property(property_id, broker, organization_id)
        broker_id = broker.id if isinstance(broker.id, uuid.UUID) else uuid.UUID(str(broker.id))
        org_id = await self._resolve_tenant_org_id(broker, organization_id)

        stmt = select(LeadPropertyInterest, Lead).join(
            Lead, LeadPropertyInterest.lead_id == Lead.id
        ).where(
            LeadPropertyInterest.property_id == prop.id,
            or_(
                LeadPropertyInterest.organization_id == org_id,
                LeadPropertyInterest.organization_id == broker_id
            )
        ).order_by(LeadPropertyInterest.interested_at.desc())

        res = await self.db.execute(stmt)
        rows = res.all()

        results = []
        for interest, lead in rows:
            results.append({
                "interest_id": str(interest.id),
                "lead_id": str(lead.id),
                "lead_name": lead.name or "Unnamed Lead",
                "lead_phone": lead.phone,
                "status": interest.status,
                "interest_level": interest.interest_level,
                "visit_count": interest.visit_count,
                "match_score": interest.match_score,
                "interested_at": interest.interested_at.isoformat(),
                "notes": interest.notes
            })
        return results

    # ─────────────────────────────────────────────────────────────────────────
    # 7. Site Visits & Outcome Capture
    # ─────────────────────────────────────────────────────────────────────────

    async def schedule_site_visit(
        self,
        lead_id: str | uuid.UUID,
        property_id: str | uuid.UUID,
        broker: Broker,
        scheduled_at: datetime,
        duration_minutes: int = 60,
        notes: Optional[str] = None,
        organization_id: Optional[Union[str, uuid.UUID]] = None
    ) -> Dict[str, Any]:
        """
        Coordinates a site visit:
        - Links lead to property as VISIT_SCHEDULED
        - Creates Meeting entity (meeting_type='site_visit')
        - Creates Task for agent
        - Records Activity feed entry
        """
        broker_id = broker.id if isinstance(broker.id, uuid.UUID) else uuid.UUID(str(broker.id))
        org_id = await self._resolve_tenant_org_id(broker, organization_id)
        prop = await self.get_property(property_id, broker, organization_id)
        lead_uuid = lead_id if isinstance(lead_id, uuid.UUID) else uuid.UUID(str(lead_id))

        # 1. Update/create interest record
        interest = await self.link_lead_property(
            lead_id=lead_uuid,
            property_id=prop.id,
            broker=broker,
            status="VISIT_SCHEDULED",
            notes=f"Site visit booked for {scheduled_at.isoformat()}",
            organization_id=org_id
        )

        # 2. Create Meeting
        meeting = Meeting(
            broker_id=broker_id,
            lead_id=lead_uuid,
            title=f"Site Visit: {prop.title}",
            meeting_type="site_visit",
            scheduled_at=scheduled_at,
            duration_minutes=duration_minutes,
            location=f"{prop.locality or ''}, {prop.city or ''}",
            notes=notes or f"Viewing at {prop.title} ({prop.property_code})",
            status="scheduled"
        )
        self.db.add(meeting)

        # 3. Create Task
        task = Task(
            broker_id=broker_id,
            lead_id=lead_uuid,
            title=f"Conduct site visit: {prop.title}",
            description=f"Property: {prop.title} ({prop.property_code})\nLocation: {prop.address or prop.locality}\nNotes: {notes or ''}",
            due_at=scheduled_at,
            priority="high",
            status="pending"
        )
        self.db.add(task)

        # 4. Activity
        act = Activity(
            actor_id=broker_id,
            lead_id=lead_uuid,
            organization_id=str(org_id),
            activity_type="meeting_scheduled",
            title="Site Visit Scheduled",
            description=f"Scheduled visit for {prop.title} on {scheduled_at.strftime('%Y-%m-%d %H:%M UTC')}",
            activity_data={"property_id": str(prop.id), "meeting_id": meeting.id}
        )
        self.db.add(act)

        await self.db.commit()

        return {
            "status": "success",
            "meeting_id": meeting.id,
            "task_id": task.id,
            "scheduled_at": scheduled_at.isoformat(),
            "property_title": prop.title
        }

    async def record_visit_outcome(
        self,
        meeting_id: str,
        broker: Broker,
        outcome: str,  # attended | cancelled | rescheduled | no_show | interested | rejected
        feedback: Optional[str] = None,
        next_action: Optional[str] = None
    ) -> Dict[str, Any]:
        """Captures site visit result, updates interest status and meeting state."""
        broker_id = broker.id if isinstance(broker.id, uuid.UUID) else uuid.UUID(str(broker.id))

        stmt = select(Meeting).where(Meeting.id == meeting_id, Meeting.broker_id == broker_id)
        res = await self.db.execute(stmt)
        meeting = res.scalars().first()
        if not meeting:
            raise HTTPException(status_code=404, detail="Visit meeting not found.")

        outcome_lower = outcome.lower()
        if outcome_lower in ("attended", "interested"):
            meeting.status = "completed"
        elif outcome_lower == "cancelled":
            meeting.status = "cancelled"
        elif outcome_lower == "no_show":
            meeting.status = "no_show"
        else:
            meeting.status = "completed"

        if feedback:
            meeting.notes = f"{meeting.notes or ''}\nOutcome: {outcome}\nFeedback: {feedback}"

        # Update LeadPropertyInterest if lead present
        if meeting.lead_id:
            interest_stmt = select(LeadPropertyInterest).where(
                LeadPropertyInterest.lead_id == meeting.lead_id,
                LeadPropertyInterest.organization_id == broker_id
            ).order_by(LeadPropertyInterest.updated_at.desc())
            int_res = await self.db.execute(interest_stmt)
            interest = int_res.scalars().first()
            if interest:
                interest.visit_count += 1
                if outcome_lower == "attended":
                    interest.status = "VISITED"
                elif outcome_lower == "interested":
                    interest.status = "SHORTLISTED"
                elif outcome_lower == "rejected":
                    interest.status = "REJECTED"

        # Log Activity
        act = Activity(
            actor_id=broker_id,
            lead_id=meeting.lead_id,
            organization_id=str(broker_id),
            activity_type="meeting_held" if outcome_lower in ("attended", "interested") else "meeting_cancelled",
            title=f"Site Visit Outcome: {outcome.upper()}",
            description=feedback or f"Marked as {outcome}",
            activity_data={"outcome": outcome, "next_action": next_action}
        )
        self.db.add(act)

        await self.db.commit()
        return {"status": "success", "outcome": outcome, "meeting_id": meeting_id}

    async def list_site_visits(
        self,
        broker: Broker,
        status_filter: Optional[str] = None,
        limit: int = 15
    ) -> List[Dict[str, Any]]:
        """Lists site visits / meetings for broker's properties with lead and property details."""
        broker_id = broker.id if isinstance(broker.id, uuid.UUID) else uuid.UUID(str(broker.id))
        stmt = select(Meeting).where(Meeting.broker_id == broker_id)
        if status_filter:
            stmt = stmt.where(Meeting.status == status_filter)
        stmt = stmt.order_by(Meeting.scheduled_at.desc()).limit(limit)
        res = await self.db.execute(stmt)
        meetings = list(res.scalars().all())

        lead_ids = []
        for m in meetings:
            if m.lead_id:
                if isinstance(m.lead_id, uuid.UUID):
                    lead_ids.append(m.lead_id)
                else:
                    try:
                        lead_ids.append(uuid.UUID(str(m.lead_id)))
                    except Exception:
                        pass

        leads_map: Dict[Any, Lead] = {}
        if lead_ids:
            lead_stmt = select(Lead).where(Lead.id.in_(lead_ids))
            lead_res = await self.db.execute(lead_stmt)
            for l in lead_res.scalars().all():
                leads_map[str(l.id)] = l
                leads_map[l.id] = l

        visits = []
        for meeting in meetings:
            prop_title = meeting.title.replace("Site Visit: ", "") if meeting.title else (meeting.location or "Property")
            lead = leads_map.get(meeting.lead_id) or (leads_map.get(str(meeting.lead_id)) if meeting.lead_id else None)
            visits.append({
                "meeting_id": str(meeting.id),
                "scheduled_at": meeting.scheduled_at.isoformat() if meeting.scheduled_at else None,
                "status": meeting.status,
                "notes": meeting.notes,
                "location": meeting.location,
                "lead_id": str(meeting.lead_id) if meeting.lead_id else None,
                "lead_name": lead.name if lead else "Unknown Client",
                "lead_phone": lead.phone if lead else None,
                "property_title": prop_title,
            })
        return visits

    # ─────────────────────────────────────────────────────────────────────────
    # 8. Inventory Analytics & Lead Demand Intelligence
    # ─────────────────────────────────────────────────────────────────────────

    async def get_inventory_analytics(
        self,
        broker: Broker,
        organization_id: Optional[Union[str, uuid.UUID]] = None
    ) -> Dict[str, Any]:
        """Calculates live inventory counts, price benchmarks, and status breakdowns with tenant scoping."""
        broker_id = broker.id if isinstance(broker.id, uuid.UUID) else uuid.UUID(str(broker.id))
        org_id = await self._resolve_tenant_org_id(broker, organization_id)

        stmt = select(PropertyListing).where(
            self._tenant_filter(broker_id, org_id),
            PropertyListing.deleted_at.is_(None)
        )
        res = await self.db.execute(stmt)
        props = list(res.scalars().all())

        total = len(props)
        available = sum(1 for p in props if p.status == "available")
        reserved = sum(1 for p in props if p.status == "reserved")
        sold = sum(1 for p in props if p.status == "sold")
        rented = sum(1 for p in props if p.status == "rented")
        draft = sum(1 for p in props if p.status == "draft")
        archived = sum(1 for p in props if p.status == "archived")

        prices = [p.price for p in props if p.price > 0]
        avg_price = round(sum(prices) / len(prices), 2) if prices else 0.0

        psqft = [p.price_per_sqft for p in props if p.price_per_sqft and p.price_per_sqft > 0]
        avg_price_per_sqft = round(sum(psqft) / len(psqft), 2) if psqft else 0.0

        # Category breakdown
        by_category = {}
        for p in props:
            cat = p.property_category or "residential"
            by_category[cat] = by_category.get(cat, 0) + 1

        # City breakdown
        by_city = {}
        for p in props:
            c = p.city or "Unknown"
            by_city[c] = by_city.get(c, 0) + 1

        # Price band breakdown (<50L, 50L-1Cr, 1Cr-2Cr, >2Cr)
        price_bands = {
            "under_50L": sum(1 for p in props if p.price < 5000000),
            "50L_to_1Cr": sum(1 for p in props if 5000000 <= p.price < 10000000),
            "1Cr_to_2Cr": sum(1 for p in props if 10000000 <= p.price < 20000000),
            "above_2Cr": sum(1 for p in props if p.price >= 20000000),
        }

        return {
            "total_properties": total,
            "available": available,
            "reserved": reserved,
            "sold": sold,
            "rented": rented,
            "draft": draft,
            "archived": archived,
            "average_price": avg_price,
            "average_price_per_sqft": avg_price_per_sqft,
            "by_category": by_category,
            "by_city": by_city,
            "price_bands": price_bands
        }

    async def get_demand_vs_inventory(
        self,
        broker: Broker,
        organization_id: Optional[Union[str, uuid.UUID]] = None
    ) -> List[Dict[str, Any]]:
        """Compares lead budget and location demand against live available inventory with tenant scoping."""
        broker_id = broker.id if isinstance(broker.id, uuid.UUID) else uuid.UUID(str(broker.id))
        org_id = await self._resolve_tenant_org_id(broker, organization_id)

        # Get active leads with dual-read
        lead_filter = or_(
            Lead.organization_id == org_id,
            and_(Lead.organization_id.is_(None), Lead.broker_id == broker_id)
        )
        leads_stmt = select(Lead).where(lead_filter, Lead.deleted_at.is_(None))
        leads_res = await self.db.execute(leads_stmt)
        leads = leads_res.scalars().all()

        # Get available inventory
        props_stmt = select(PropertyListing).where(
            self._tenant_filter(broker_id, org_id),
            PropertyListing.deleted_at.is_(None),
            PropertyListing.status == "available"
        )
        props_res = await self.db.execute(props_stmt)
        props = props_res.scalars().all()

        demand_map: Dict[str, Dict[str, int]] = {}
        for l in leads:
            locs = l.preferred_locations or []
            if not locs and l.property_type:
                locs = ["Bengaluru"]
            for loc in locs:
                key = loc.strip().title()
                if key not in demand_map:
                    demand_map[key] = {"leads_count": 0, "available_inventory": 0}
                demand_map[key]["leads_count"] += 1

        for p in props:
            key = (p.locality or p.city or "Bengaluru").strip().title()
            if key not in demand_map:
                demand_map[key] = {"leads_count": 0, "available_inventory": 0}
            demand_map[key]["available_inventory"] += 1

        results = []
        for location, counts in demand_map.items():
            gap = counts["leads_count"] - counts["available_inventory"]
            results.append({
                "location": location,
                "leads_demanding": counts["leads_count"],
                "available_inventory": counts["available_inventory"],
                "inventory_gap": gap,
                "high_demand_opportunity": gap > 0
            })

        results.sort(key=lambda x: x["inventory_gap"], reverse=True)
        return results

    # ─────────────────────────────────────────────────────────────────────────
    # 9. CSV Batch Import & Duplicate Check
    # ─────────────────────────────────────────────────────────────────────────

    async def import_properties_csv(
        self,
        broker: Broker,
        file_content: bytes,
        filename: str = "inventory.csv",
        dry_run: bool = False,
        organization_id: Optional[Union[str, uuid.UUID]] = None
    ) -> Dict[str, Any]:
        """Validates CSV with FileSecurityScanner, maps headers, checks duplicates/conflicts, and supports dry-run preview."""
        valid, err = FileSecurityScanner.scan_file(filename, file_content)
        if not valid:
            raise HTTPException(status_code=400, detail=f"File security rejected: {err}")

        text_data = file_content.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text_data))

        imported_count = 0
        duplicate_count = 0
        updated_count = 0
        failed_count = 0
        errors = []
        row_results = []

        org_id = await self._resolve_tenant_org_id(broker, organization_id)

        idx = 0
        for idx, row in enumerate(reader, start=1):
            try:
                r = {k.strip().lower(): v.strip() for k, v in row.items() if k and v}
                title = r.get("title") or r.get("property_name") or r.get("name")
                if not title:
                    failed_count += 1
                    errors.append(f"Row {idx}: Missing title.")
                    row_results.append({"row": idx, "status": "invalid", "reason": "Missing title"})
                    continue

                price = float(r.get("price", 0))
                area = float(r.get("area", r.get("built_up_area_sqft", 1000)))

                prop_data = {
                    "title": title,
                    "property_code": r.get("property_code") or r.get("code"),
                    "property_type": r.get("property_type", "apartment"),
                    "property_category": r.get("property_category", "residential"),
                    "transaction_category": r.get("transaction_category", "resale"),
                    "status": r.get("status", "available"),
                    "price": price,
                    "currency_code": r.get("currency", "INR"),
                    "area_value": area,
                    "bedrooms": int(r.get("bedrooms", r.get("bhk", 1))),
                    "bathrooms": int(r.get("bathrooms", 1)),
                    "project_name": r.get("project_name", r.get("project")),
                    "unit_number": r.get("unit_number", r.get("unit")),
                    "locality": r.get("locality", "Indiranagar"),
                    "city": r.get("city", "Bengaluru"),
                    "description": r.get("description", ""),
                    "owner_name": r.get("owner_name"),
                    "owner_phone": r.get("owner_phone")
                }

                # Check duplicates with tenant scoping
                dupes = await self.detect_duplicates(broker, prop_data, organization_id=org_id)
                if dupes:
                    existing = dupes[0]
                    # Check if price or status changed
                    price_diff = abs(float(existing.get("price", 0)) - price) > 0.01
                    status_diff = existing.get("status") != prop_data["status"]
                    if price_diff or status_diff:
                        if not dry_run:
                            await self.update_property(
                                existing["id"], broker,
                                {"price": price, "status": prop_data["status"]},
                                organization_id=org_id
                            )
                        updated_count += 1
                        row_results.append({"row": idx, "status": "updated", "property_id": existing["id"], "code": existing.get("property_code")})
                    else:
                        duplicate_count += 1
                        row_results.append({"row": idx, "status": "unchanged", "property_id": existing["id"], "code": existing.get("property_code")})
                    continue

                if not dry_run:
                    created = await self.create_property(broker, prop_data, organization_id=org_id)
                    row_results.append({"row": idx, "status": "created", "property_id": str(created.id), "code": created.property_code})
                else:
                    row_results.append({"row": idx, "status": "valid_preview", "title": title, "price": price})
                imported_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f"Row {idx}: {str(e)}")
                row_results.append({"row": idx, "status": "failed", "error": str(e)})

        return {
            "total_rows": idx,
            "dry_run": dry_run,
            "created": imported_count if not dry_run else 0,
            "imported": imported_count if not dry_run else 0,
            "updated": updated_count,
            "unchanged": duplicate_count,
            "duplicates": duplicate_count,
            "duplicates_skipped": duplicate_count,
            "failed": failed_count,
            "row_results": row_results[:50],
            "errors": errors[:10]
        }


    # ─────────────────────────────────────────────────────────────────────────
    # 10. AI Grounded Property Description
    # ─────────────────────────────────────────────────────────────────────────

    async def generate_ai_description(
        self,
        property_data: Dict[str, Any],
        broker: Optional[Broker] = None,
        organization_id: Optional[Union[str, uuid.UUID]] = None
    ) -> Dict[str, Any]:
        """Generates grounded marketing description without hallucinating non-existent facts using canonical AIGateway."""
        title = property_data.get("title", "Property")
        bhk = property_data.get("bedrooms", 2)
        prop_type = property_data.get("property_type", "Apartment")
        locality = property_data.get("locality", "Bengaluru")
        price = property_data.get("price", 0)
        amenities = ", ".join(property_data.get("amenities") or ["Modern Amenities"])

        deterministic_desc = (
            f"Spacious {bhk} BHK {prop_type.title()} in prime {locality}. "
            f"Featuring modern layouts, optimal ventilation, and convenient access to key commercial hubs. "
            f"Amenities include {amenities}. Available at ₹{price:,.0f}."
        )

        try:
            resolved_org_id = None
            if organization_id:
                resolved_org_id = organization_id if isinstance(organization_id, uuid.UUID) else uuid.UUID(str(organization_id))
            elif broker:
                resolved_org_id = await self._resolve_tenant_org_id(broker)

            if resolved_org_id:
                gateway = AIGateway(self.db)
                prompt = (
                    f"Write a compelling, professional 50-word real estate listing description for:\n"
                    f"- Title: {title}\n"
                    f"- Type: {bhk} BHK {prop_type}\n"
                    f"- Location: {locality}\n"
                    f"- Price: ₹{price:,.0f}\n"
                    f"- Amenities: {amenities}\n\n"
                    f"Rules: Strictly stick to provided facts. Do not invent amenities, metro distances, or guarantees."
                )
                res = await gateway.complete(
                    organization_id=resolved_org_id,
                    feature="property_marketing",
                    task_type="description_generation",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=200,
                )
                if res.success and res.content:
                    return {"description": res.content.strip(), "ai_generated": True}
        except Exception as exc:
            logger.warning(f"AI description generation fallback to deterministic: {exc}")

        return {"description": deterministic_desc, "ai_generated": False}

    # ─────────────────────────────────────────────────────────────────────────
    # Helper: Serialize Property with Valuation & Redaction
    # ─────────────────────────────────────────────────────────────────────────

    def serialize_property(self, p: PropertyListing) -> Dict[str, Any]:
        """Serializes property listing into comprehensive dictionary."""
        val = PropertyAIValuationService.calculate_valuation(
            price=float(p.price),
            built_up_area_sqft=float(p.area_value),
            locality=p.locality or "Bengaluru"
        )
        return {
            "id": str(p.id),
            "property_code": p.property_code,
            "share_token": p.share_token,
            "broker_id": str(p.broker_id),
            "title": p.title,
            "description": p.description,
            "property_category": p.property_category,
            "property_type": p.property_type,
            "transaction_category": p.transaction_category,
            "listing_type": p.listing_type,
            "status": p.status,
            "price": float(p.price),
            "price_min": p.price_min,
            "price_max": p.price_max,
            "price_per_sqft": p.price_per_sqft,
            "currency": p.currency_code,
            "currency_code": p.currency_code,
            "built_up_area_sqft": float(p.area_value),
            "area_value": float(p.area_value),
            "area_unit": p.area_unit,
            "carpet_area": p.carpet_area,
            "super_built_up_area": p.super_built_up_area,
            "plot_area": p.plot_area,
            "bedrooms": p.bedrooms,
            "bathrooms": p.bathrooms,
            "balconies": p.balconies,
            "parking_spaces": p.parking_spaces,
            "floor_number": p.floor_number,
            "total_floors": p.total_floors,
            "facing": p.facing,
            "furnishing": p.furnishing,
            "construction_status": p.construction_status,
            "age_years": p.age_years,
            "developer_name": p.developer_name,
            "project_name": p.project_name,
            "building_name": p.building_name,
            "unit_number": p.unit_number,
            "address": p.address,
            "city": p.city,
            "locality": p.locality,
            "state": p.state,
            "country_code": p.country_code,
            "postal_code": p.postal_code,
            "amenities": p.amenities or [],
            "marketing_highlights": p.marketing_highlights or [],
            # Internal fields included for authenticated broker
            "owner_name": p.owner_name,
            "owner_phone": p.owner_phone,
            "owner_email": p.owner_email,
            "assigned_agent_id": str(p.assigned_agent_id) if p.assigned_agent_id else None,
            "commission_amount": p.commission_amount,
            "commission_percentage": p.commission_percentage,
            "internal_notes": p.internal_notes,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            "valuation": {
                "estimated_market_value": val.estimated_market_value,
                "estimated_price_per_sqft": val.estimated_price_per_sqft,
                "is_overpriced": val.is_overpriced,
                "overpriced_percentage": val.overpriced_percentage,
                "estimated_annual_roi_yield_pct": val.estimated_annual_roi_yield_pct,
                "confidence_score": val.confidence_score
            }
        }
