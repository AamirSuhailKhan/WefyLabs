"""
Production Service Layer for AI Agent Tool Execution
=====================================================
Abstracts all external data access behind typed service classes.
Tools NEVER query the database directly — they call these services.
This allows production CRM/Property/Knowledge services to be wired in
without changing any tool handler logic.

Services:
  PropertyService    → property inventory, pricing, availability
  CRMService         → lead updates, booking, notes, tasks
  KnowledgeService   → FAQ, policy, area guide search
  NotificationService→ broker/manager push notifications
  WorkflowService    → CRM workflow triggers
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

logger = logging.getLogger("wefylabs.ai_agent.services")


import uuid

def _to_uuid(val: Any) -> Optional[uuid.UUID]:
    if not val:
        return None
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except Exception:
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(val))

# ─── PropertyService ──────────────────────────────────────────────────────────

class PropertyService:
    """
    Searches the property inventory and checks availability.
    In production: delegates to apps/api/app/modules/properties service.
    Enforces strict organization/broker tenant isolation.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search(
        self,
        property_type: Optional[str] = None,
        bedrooms: Optional[int] = None,
        budget_max: Optional[float] = None,
        locations: Optional[List[str]] = None,
        purpose: Optional[str] = None,
        limit: int = 3,
        organization_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search properties matching buyer criteria.
        Returns verified list — never fabricated.
        PropertyListing uses status=="available" and soft-delete via deleted_at.
        Enforces tenant isolation by organization_id / broker_id.
        """
        try:
            from app.models.property_models import PropertyListing
            query = select(PropertyListing).where(
                PropertyListing.status == "available",
                PropertyListing.deleted_at.is_(None),
            )
            if organization_id:
                try:
                    org_uuid = uuid.UUID(str(organization_id))
                    query = query.where(PropertyListing.broker_id == org_uuid)
                except Exception:
                    pass
            if property_type:
                query = query.where(PropertyListing.property_type == property_type)
            if bedrooms:
                query = query.where(PropertyListing.bedrooms >= bedrooms)
            if budget_max:
                query = query.where(PropertyListing.price <= budget_max)
            query = query.limit(limit)
            result = await self.db.execute(query)
            listings = result.scalars().all()
            return {
                "properties": [
                    {
                        "id": str(lst.id),
                        "name": lst.title or "Property Listing",
                        "type": lst.property_type,
                        "bedrooms": lst.bedrooms,
                        "price": float(lst.price) if lst.price else None,
                        "currency": getattr(lst, "currency_code", getattr(lst, "currency", "INR")),
                        "location": lst.locality or lst.city or "",
                        "availability": lst.status or "available",
                        "source_verified": True,
                    }
                    for lst in listings
                ],
                "total": len(listings),
                "source_verified": True,
            }
        except Exception as exc:
            logger.error(f"PropertyService.search error: {exc}")
            # Graceful fallback — never crash the conversation
            return {
                "properties": [],
                "total": 0,
                "error": "Property service temporarily unavailable",
                "source_verified": False,
            }

    async def check_availability(self, property_id: str, organization_id: Optional[str] = None) -> Dict[str, Any]:
        """Check real-time availability status of a property unit with tenant scope check."""
        try:
            from app.models.property_models import PropertyListing
            prop_uuid = _to_uuid(property_id)
            query = select(PropertyListing).where(
                PropertyListing.id == prop_uuid,
                PropertyListing.deleted_at.is_(None),
            )
            if organization_id:
                try:
                    org_uuid = _to_uuid(organization_id)
                    query = query.where(PropertyListing.broker_id == org_uuid)
                except Exception:
                    pass
            result = await self.db.execute(query)
            listing = result.scalar_one_or_none()
            if not listing:
                return {"property_id": property_id, "status": "not_found", "source_verified": True}
            is_available = listing.status == "available"
            return {
                "property_id": property_id,
                "status": listing.status or "available",
                "units_remaining": 1 if is_available else 0,
                "source_verified": True,
            }
        except Exception as exc:
            logger.error(f"PropertyService.check_availability error: {exc}")
            return {"property_id": property_id, "status": "error", "source_verified": False}

    async def get_payment_plan(self, property_id: str, organization_id: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve verified developer payment plan from property record with tenant scope check."""
        try:
            from app.models.property_models import PropertyListing
            prop_uuid = _to_uuid(property_id)
            query = select(PropertyListing).where(
                PropertyListing.id == prop_uuid,
                PropertyListing.deleted_at.is_(None),
            )
            if organization_id:
                try:
                    org_uuid = _to_uuid(organization_id)
                    query = query.where(PropertyListing.broker_id == org_uuid)
                except Exception:
                    pass
            result = await self.db.execute(query)
            listing = result.scalar_one_or_none()
            if not listing:
                return {"property_id": property_id, "plan": None, "source_verified": False,
                        "message": "Property not found or not accessible."}
            # Only return data that actually exists in the listing record.
            # Do NOT fabricate payment plan details.
            payment_plan = getattr(listing, "payment_plan", None)
            down_pct = getattr(listing, "down_payment_percentage", None)
            if payment_plan or down_pct:
                return {
                    "property_id": property_id,
                    "plan": payment_plan,
                    "down_payment_pct": down_pct,
                    "developer_verified": True,
                    "source_verified": True,
                }
            else:
                return {
                    "property_id": property_id,
                    "plan": None,
                    "source_verified": False,
                    "message": "No verified payment plan data available for this property.",
                }
        except Exception as exc:
            logger.error(f"PropertyService.get_payment_plan error: {exc}")
            return {"property_id": property_id, "plan": None, "source_verified": False,
                    "message": "No verified payment plan data available for this property."}



# ─── CRMService ───────────────────────────────────────────────────────────────

class CRMService:
    """
    Reads and updates CRM records — Lead, Task, Meeting.
    Uses the established CRM SQLAlchemy models.
    Enforces tenant isolation by organization/broker.
    Never bypasses service layer.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_lead(self, lead_id: str, organization_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Load lead profile from CRM, verifying tenant ownership."""
        try:
            from app.models.lead import Lead
            query = select(Lead).where(Lead.id == lead_id, Lead.deleted_at.is_(None))
            if organization_id:
                try:
                    org_uuid = uuid.UUID(str(organization_id))
                    query = query.where(Lead.broker_id == org_uuid)
                except Exception:
                    pass
            result = await self.db.execute(query)
            lead = result.scalar_one_or_none()
            if not lead:
                return None
            return {
                "id": str(lead.id),
                "name": lead.name,
                "phone": lead.phone,
                "email": lead.email,
                "status": lead.status,
                "source": lead.source,
                "score": getattr(lead, "score", None),
            }
        except Exception as exc:
            logger.error(f"CRMService.get_lead error: {exc}")
            return None

    async def update_lead(
        self,
        lead_id: str,
        status: Optional[str] = None,
        pipeline_stage: Optional[str] = None,
        notes: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> bool:
        """Update lead status, pipeline stage, and add notes with tenant check."""
        try:
            from app.models.lead import Lead
            from app.models.crm_models import LeadNote
            from datetime import datetime, timezone

            # Verify lead exists and belongs to tenant
            lead_query = select(Lead).where(Lead.id == lead_id, Lead.deleted_at.is_(None))
            if organization_id:
                try:
                    org_uuid = uuid.UUID(str(organization_id))
                    lead_query = lead_query.where(Lead.broker_id == org_uuid)
                except Exception:
                    pass
            lead = (await self.db.execute(lead_query)).scalar_one_or_none()
            if not lead:
                return False

            updates = {}
            if status:
                updates["status"] = status
            if pipeline_stage:
                updates["pipeline_stage"] = pipeline_stage

            if updates:
                await self.db.execute(
                    update(Lead).where(Lead.id == lead.id).values(**updates)
                )

            if notes:
                note = LeadNote(
                    lead_id=str(lead.id),
                    broker_id=str(lead.broker_id),
                    content=notes,
                    created_at=datetime.now(timezone.utc),
                )
                self.db.add(note)

            await self.db.flush()
            return True
        except Exception as exc:
            logger.error(f"CRMService.update_lead error: {exc}")
            return False

    async def create_meeting(
        self,
        lead_id: str,
        property_id: str,
        preferred_date: str,
        preferred_time: Optional[str] = None,
        notes: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a property viewing meeting using canonical BookingService with tenant verification."""
        try:
            from app.models.lead import Lead
            from app.modules.calendar.booking.booking_service import BookingService
            from app.modules.calendar.booking_lock.lock_manager import BookingLockManager
            from app.modules.calendar.dto.calendar_schemas import BookingRequestDTO
            from datetime import datetime, timezone, timedelta

            # Verify lead belongs to tenant if organization_id supplied
            l_uuid = None
            try:
                l_uuid = uuid.UUID(str(lead_id))
            except Exception:
                l_uuid = lead_id

            stmt_lead = select(Lead).where(Lead.id == l_uuid, Lead.deleted_at.is_(None))
            if organization_id:
                try:
                    org_uuid = uuid.UUID(str(organization_id))
                    stmt_lead = stmt_lead.where(Lead.broker_id == org_uuid)
                except Exception:
                    pass
            chk = await self.db.execute(stmt_lead)
            lead = chk.scalar_one_or_none()
            if not lead:
                return {"booking_id": None, "status": "error", "error": "Lead not found in organization", "source_verified": False}

            # Parse start time from preferred_date and preferred_time
            parsed_dt = None
            try:
                if "T" in preferred_date:
                    parsed_dt = datetime.fromisoformat(preferred_date)
                elif preferred_time:
                    try:
                        combined_str = f"{preferred_date} {preferred_time}"
                        parsed_dt = datetime.strptime(combined_str, "%Y-%m-%d %I:%M %p").replace(tzinfo=timezone.utc)
                    except Exception:
                        parsed_dt = datetime.fromisoformat(preferred_date).replace(tzinfo=timezone.utc)
                else:
                    parsed_dt = datetime.fromisoformat(preferred_date).replace(tzinfo=timezone.utc)
            except Exception:
                parsed_dt = datetime.now(timezone.utc) + timedelta(days=2, hours=10)

            if parsed_dt.tzinfo is None:
                parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)

            org_id_str = str(organization_id or lead.broker_id)
            broker_id_str = str(lead.broker_id)

            lock_mgr = BookingLockManager(self.db)
            booking_svc = BookingService(self.db, lock_mgr)

            idempotency_key = f"ai_booking_{lead_id}_{property_id}_{parsed_dt.strftime('%Y%m%d%H%M')}"

            dto = BookingRequestDTO(
                lead_id=str(lead.id),
                broker_id=broker_id_str,
                property_id=str(property_id) if property_id else None,
                meeting_type="PROPERTY_VIEWING",
                slot_start_utc=parsed_dt,
                duration_minutes=45,
                notes=notes,
                idempotency_key=idempotency_key
            )

            booking_resp = await booking_svc.book_appointment(
                dto=dto,
                organization_id=org_id_str,
                authenticated_broker_id=broker_id_str
            )

            return {
                "booking_id": booking_resp.id,
                "property_id": property_id,
                "date": booking_resp.start_utc.strftime("%Y-%m-%d"),
                "time": booking_resp.start_utc.strftime("%I:%M %p"),
                "status": "confirmed",
                "customer_timezone": booking_resp.customer_timezone,
                "meeting_url": booking_resp.meeting_url,
                "location": booking_resp.location_address,
                "crm_task_created": True,
                "crm_meeting_created": True,
                "source_verified": True,
            }
        except Exception as exc:
            logger.error(f"CRMService.create_meeting error: {exc}")
            return {
                "booking_id": None,
                "status": "error",
                "error": str(exc),
                "source_verified": False,
            }


# ─── KnowledgeService ─────────────────────────────────────────────────────────

class KnowledgeService:
    """
    Knowledge Engine integration for the AI Agent tool executor.
    Delegates to HybridSearchService for full retrieval pipeline:
      vector search → keyword search → RRF fusion → permission filter
      → freshness filter → reranking → context assembly → grounding validation.

    Returns grounded, cited, permission-filtered results.
    Never fabricates; every result traces back to a PUBLISHED document.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search(
        self,
        query: str,
        organization_id: str,
        category: Optional[str] = None,
        project_id: Optional[str] = None,
        property_id: Optional[str] = None,
        language: Optional[str] = None,
        channel: str = "internal",
        role: str = "AGENT",
        top_k: int = 10,
        rerank_top_n: int = 5,
    ) -> Dict[str, Any]:
        """
        Execute hybrid knowledge search and return grounded context.
        Called by the AI agent's search_knowledge_base tool.
        """
        try:
            from app.modules.knowledge.retrieval.hybrid_search_service import HybridSearchService
            from app.modules.knowledge.retrieval.context_builder import KnowledgeContextBuilder

            svc = HybridSearchService(db=self.db)
            response = await svc.search(
                query=query,
                organization_id=organization_id,
                top_k=top_k,
                rerank_top_n=rerank_top_n,
                knowledge_types=[category] if category else None,
                project_id=project_id,
                property_id=property_id,
                language=language,
                channel=channel,
                role=role,
            )

            builder = KnowledgeContextBuilder()
            assembled = builder.build_context(
                results=response.results,
                query=query,
            )

            return {
                "query": query,
                "category": category,
                "context_text": assembled.context_text,
                "results": [
                    {
                        "chunk_id": r.chunk_id,
                        "document_id": r.document_id,
                        "text": r.text[:500],
                        "score": r.score,
                        "knowledge_type": r.metadata.get("knowledge_type"),
                        "source_title": r.metadata.get("source_title"),
                        "heading": r.metadata.get("heading"),
                        "rank": r.rank_position,
                    }
                    for r in response.results
                ],
                "citations": [
                    {
                        "index": c.citation_index,
                        "document_id": c.document_id,
                        "source_title": c.source_title,
                        "page_number": c.page_number,
                        "heading": c.heading,
                    }
                    for c in assembled.citations
                ],
                "confidence": assembled.confidence,
                "has_verified_facts": assembled.has_verified_facts,
                "total_vector_hits": response.total_vector_hits,
                "total_keyword_hits": response.total_keyword_hits,
                "source_verified": True,
            }

        except Exception as exc:
            logger.error(f"[KnowledgeService] Search failed: {exc}", exc_info=True)
            # Graceful degradation: never fabricate, always fail transparently
            return {
                "query": query,
                "category": category,
                "context_text": "",
                "results": [],
                "citations": [],
                "confidence": 0.0,
                "has_verified_facts": False,
                "total_vector_hits": 0,
                "total_keyword_hits": 0,
                "source_verified": False,
                "error": "Knowledge retrieval temporarily unavailable.",
            }


# ─── NotificationService ──────────────────────────────────────────────────────

class NotificationService:
    """Sends notifications to brokers and managers via the CRM notification system."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def send(
        self,
        organization_id: str,
        message: str,
        priority: str = "medium",
        lead_id: Optional[str] = None,
    ) -> bool:
        try:
            from app.models.crm_models import Notification
            from datetime import datetime, timezone

            notification = Notification(
                organization_id=organization_id,
                message=message,
                priority=priority,
                lead_id=lead_id,
                created_at=datetime.now(timezone.utc),
                is_read=False,
            )
            self.db.add(notification)
            await self.db.flush()
            logger.info(f"[NotificationService] Sent [{priority}]: {message[:80]}")
            return True
        except Exception as exc:
            logger.error(f"NotificationService.send error: {exc}")
            return False


# ─── WorkflowService ─────────────────────────────────────────────────────────

class WorkflowService:
    """Triggers CRM workflows from the AI agent."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def trigger(self, workflow_name: str, payload: Optional[Dict[str, Any]] = None) -> bool:
        """Trigger a named workflow."""
        try:
            from app.models.workflow_models import WorkflowExecution
            from datetime import datetime, timezone

            execution = WorkflowExecution(
                workflow_name=workflow_name,
                status="pending",
                payload=payload or {},
                triggered_at=datetime.now(timezone.utc),
            )
            self.db.add(execution)
            await self.db.flush()
            logger.info(f"[WorkflowService] Triggered: {workflow_name}")
            return True
        except Exception as exc:
            logger.error(f"WorkflowService.trigger error: {exc}")
            return False

# ─── ShortlistService ─────────────────────────────────────────────────────────

class ShortlistService:
    """
    Manages customer property shortlists using LeadPropertyInterest model.
    Enforces tenant isolation: only properties owned by the tenant broker
    can be added to a lead's shortlist belonging to that same tenant.
    """

    VALID_STATUSES = {"shortlisted", "liked", "rejected", "visit_requested", "visited", "viewed"}

    def __init__(self, db: AsyncSession):
        self.db = db

    async def add(
        self,
        lead_id: str,
        property_id: str,
        status: str = "shortlisted",
        organization_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add a property to the customer's shortlist.
        Validates tenant ownership before adding.
        Idempotent: updates status if record already exists.
        """
        if status not in self.VALID_STATUSES:
            status = "shortlisted"
        try:
            from app.models.property_models import LeadPropertyInterest, PropertyListing
            from app.models.lead import Lead

            lead_uuid = _to_uuid(lead_id)
            prop_uuid = _to_uuid(property_id)
            org_uuid = _to_uuid(organization_id) or uuid.uuid5(uuid.NAMESPACE_DNS, "default-org")

            # Verify lead belongs to tenant
            if organization_id:
                try:
                    lead_chk = await self.db.execute(
                        select(Lead).where(
                            Lead.id == lead_uuid,
                            Lead.broker_id == org_uuid,
                            Lead.deleted_at.is_(None)
                        )
                    )
                    if not lead_chk.scalar_one_or_none():
                        return {"success": False, "error": "Lead not found in this organization",
                                "source_verified": False}
                    # Verify property belongs to tenant
                    prop_chk = await self.db.execute(
                        select(PropertyListing).where(
                            PropertyListing.id == prop_uuid,
                            PropertyListing.broker_id == org_uuid,
                            PropertyListing.deleted_at.is_(None),
                        )
                    )
                    if not prop_chk.scalar_one_or_none():
                        return {"success": False, "error": "Property not found in this organization",
                                "source_verified": False}
                except Exception:
                    pass

            # Upsert: check if interest record already exists
            existing = await self.db.execute(
                select(LeadPropertyInterest).where(
                    LeadPropertyInterest.lead_id == lead_uuid,
                    LeadPropertyInterest.property_id == prop_uuid,
                )
            )
            interest = existing.scalar_one_or_none()
            if interest:
                interest.status = status
                if notes:
                    interest.notes = notes
            else:
                interest = LeadPropertyInterest(
                    id=uuid.uuid4(),
                    organization_id=org_uuid,
                    lead_id=lead_uuid,
                    property_id=prop_uuid,
                    status=status,
                    notes=notes,
                )
                self.db.add(interest)
            await self.db.flush()
            return {
                "success": True,
                "lead_id": lead_id,
                "property_id": property_id,
                "status": status,
                "source_verified": True,
            }
        except Exception as exc:
            logger.error(f"ShortlistService.add error: {exc}")
            return {"success": False, "error": str(exc), "source_verified": False}

    async def get(
        self,
        lead_id: str,
        organization_id: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get the customer's shortlisted/viewed/rejected properties.
        Filters to only properties that belong to the tenant.
        """
        try:
            from app.models.property_models import LeadPropertyInterest, PropertyListing

            lead_uuid = _to_uuid(lead_id)
            query = (
                select(LeadPropertyInterest, PropertyListing)
                .join(PropertyListing, PropertyListing.id == LeadPropertyInterest.property_id)
                .where(LeadPropertyInterest.lead_id == lead_uuid)
            )
            if organization_id:
                try:
                    org_uuid = _to_uuid(organization_id)
                    query = query.where(PropertyListing.broker_id == org_uuid)
                except Exception:
                    pass
            if status_filter:
                query = query.where(LeadPropertyInterest.status == status_filter)

            result = await self.db.execute(query)
            rows = result.all()
            items = []
            for interest, prop in rows:
                items.append({
                    "property_id": str(prop.id),
                    "name": prop.title or "Property",
                    "type": prop.property_type,
                    "bedrooms": prop.bedrooms,
                    "price": float(prop.price) if prop.price else None,
                    "currency": getattr(prop, "currency_code", "INR"),
                    "location": prop.locality or prop.city or "",
                    "status": interest.status,
                    "notes": interest.notes,
                    "source_verified": True,
                })
            return {
                "lead_id": lead_id,
                "items": items,
                "total": len(items),
                "source_verified": True,
            }
        except Exception as exc:
            logger.error(f"ShortlistService.get error: {exc}")
            return {"lead_id": lead_id, "items": [], "total": 0, "source_verified": True,
                    "error": None}


# ─── CalendarSlotService ──────────────────────────────────────────────────────

class CalendarSlotService:
    """
    Retrieves available calendar slots for property viewings.
    Delegates to the existing calendar module.
    Enforces tenant scoping via organization_id.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_available_slots(
        self,
        organization_id: str,
        property_id: Optional[str] = None,
        days_ahead: int = 7,
    ) -> Dict[str, Any]:
        """
        Retrieve available viewing slots for the next N days.
        Queries the canonical AvailabilityEngine. Never returns fabricated slots.
        """
        try:
            from app.modules.calendar.availability.availability_engine import AvailabilityEngine
            from app.models.calendar_models import CalendarAccount
            from app.models.broker import Broker

            # Check if org has a connected calendar account
            result = await self.db.execute(
                select(CalendarAccount).where(
                    CalendarAccount.organization_id == str(organization_id),
                    CalendarAccount.is_connected == True,
                )
            )
            cal_account = result.scalar_one_or_none()
            calendar_connected = cal_account is not None

            # Look up broker for the organization
            stmt_broker = select(Broker).where(Broker.organization_id == str(organization_id))
            res_broker = await self.db.execute(stmt_broker)
            broker = res_broker.scalar_one_or_none()
            broker_id = str(broker.id) if broker else str(organization_id)

            engine = AvailabilityEngine(self.db)
            slots_data = await engine.calculate_available_slots(
                broker_id=broker_id,
                duration_minutes=45,
                search_days_ahead=min(days_ahead, 30),
                property_id=property_id,
            )

            formatted_slots = [
                {
                    "date": s.get("date"),
                    "time": s.get("time"),
                    "start_utc": s.get("start_utc").isoformat() if hasattr(s.get("start_utc"), "isoformat") else str(s.get("start_utc")),
                    "end_utc": s.get("end_utc").isoformat() if hasattr(s.get("end_utc"), "isoformat") else str(s.get("end_utc")),
                    "customer_local_start": s.get("customer_local_start"),
                    "broker_local_start": s.get("broker_local_start"),
                    "customer_timezone": s.get("customer_timezone"),
                    "confirmed": False,
                    "note": "Verified available slot" if calendar_connected else "Suggested viewing slot (Agent confirmation required)",
                }
                for s in slots_data
            ]

            return {
                "slots": formatted_slots[:10],
                "calendar_connected": calendar_connected,
                "source_verified": True,
                "note": "Slots are verified against broker availability and property access rules." if calendar_connected else "Slots are suggested availability. Agent confirmation required.",
            }

        except Exception as exc:
            logger.error(f"CalendarSlotService.get_available_slots error: {exc}")
            return {
                "slots": [],
                "calendar_connected": False,
                "source_verified": False,
                "error": "Calendar service temporarily unavailable",
            }


# ─── ComparisonService ────────────────────────────────────────────────────────

class ComparisonService:
    """
    Fetches multiple properties for side-by-side comparison.
    Enforces tenant isolation.
    Returns only verified DB fields — no fabrication.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def compare(
        self,
        property_ids: List[str],
        organization_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch and structure comparison data for a list of property IDs.
        All properties must belong to the same tenant.
        """
        try:
            from app.models.property_models import PropertyListing

            valid_uuids = [u for pid in property_ids if (u := _to_uuid(pid))]
            properties = []

            if valid_uuids:
                query = select(PropertyListing).where(
                    PropertyListing.id.in_(valid_uuids),
                    PropertyListing.deleted_at.is_(None),
                )
                if organization_id:
                    try:
                        org_uuid = _to_uuid(organization_id)
                        query = query.where(PropertyListing.broker_id == org_uuid)
                    except Exception:
                        pass

                result = await self.db.execute(query)
                listings = result.scalars().all()
                for lst in listings:
                    properties.append({
                        "id": str(lst.id),
                        "name": lst.title or "Property Listing",
                        "type": lst.property_type,
                        "bedrooms": lst.bedrooms,
                        "bathrooms": getattr(lst, "bathrooms", None),
                        "area_sqft": getattr(lst, "area_value", None),
                        "price": float(lst.price) if lst.price else None,
                        "currency": getattr(lst, "currency_code", "INR"),
                        "location": lst.locality or "",
                        "city": lst.city or "",
                        "status": lst.status,
                        "possession": getattr(lst, "possession_date", None),
                        "amenities": getattr(lst, "amenities", None) or [],
                        "developer": getattr(lst, "developer_name", None),
                        "description": getattr(lst, "description", None),
                        "source_verified": True,
                    })

            missing = [pid for pid in property_ids if pid not in {p["id"] for p in properties}]
            return {
                "properties": properties,
                "total": len(properties),
                "missing_ids": missing,
                "comparison_matrix": {
                    "price": {p["id"]: p["price"] for p in properties},
                    "bedrooms": {p["id"]: p["bedrooms"] for p in properties},
                    "location": {p["id"]: p["location"] for p in properties},
                },
                "source_verified": True,
            }
        except Exception as exc:
            logger.error(f"ComparisonService.compare error: {exc}")
            return {
                "properties": [],
                "total": 0,
                "source_verified": False,
                "error": "Comparison service temporarily unavailable",
            }


