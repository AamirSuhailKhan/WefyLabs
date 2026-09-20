"""
Appointment & Viewing Booking Service
=====================================
Orchestrates atomic appointment creation, external calendar synchronization,
distributed slot holding, virtual meeting link generation, and reminder scheduling.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.calendar_models import Meeting, Viewing, MeetingReminder
from app.models.lead import Lead
from app.models.broker import Broker
from app.models.property_models import PropertyListing
from app.modules.calendar.booking_lock.lock_manager import BookingLockManager
from app.modules.calendar.providers.provider_interface import CalendarProvider, MockCalendarProvider
from app.modules.calendar.providers.calendar_provider_factory import resolve_calendar_provider
from app.modules.calendar.dto.calendar_schemas import BookingRequestDTO, BookingResponseDTO
from app.modules.global_.timezones.timezone_service import TimezoneService, TimezoneContext

logger = logging.getLogger(__name__)

class BookingService:
    """
    Manages booking execution with collision locking and multi-channel confirmations.
    """

    def __init__(self, db: AsyncSession, lock_manager: BookingLockManager, provider: Optional[CalendarProvider] = None):
        self.db = db
        self.lock_manager = lock_manager
        self.provider = resolve_calendar_provider(provider)

    async def book_appointment(
        self,
        dto: BookingRequestDTO,
        organization_id: str,
        authenticated_broker_id: str
    ) -> BookingResponseDTO:
        """
        Idempotently books a meeting or property viewing.
        """
        hold_id: Optional[str] = None
        # 1. Check Idempotency Key
        if dto.idempotency_key:
            stmt_idem = select(Meeting).where(Meeting.idempotency_key == dto.idempotency_key)
            res_idem = await self.db.execute(stmt_idem)
            existing = res_idem.scalar_one_or_none()
            if existing:
                logger.info(f"[BOOKING] Idempotent hit: Returning existing Meeting {existing.id}.")
                return BookingResponseDTO.model_validate(existing)

        # 2. Fetch Lead & Broker Details
        try:
            l_pk = uuid.UUID(str(dto.lead_id))
        except Exception:
            l_pk = dto.lead_id

        stmt_lead = select(Lead).where(Lead.id == l_pk)
        res_lead = await self.db.execute(stmt_lead)
        lead = res_lead.scalar_one_or_none()
        if not lead:
            raise ValueError(f"Lead ID '{dto.lead_id}' not found.")

        # Tenant Isolation: Ensure lead belongs to the authenticated tenant organization
        lead_org = getattr(lead, "organization_id", None) or str(lead.broker_id)
        if organization_id and lead_org and str(lead_org) != str(organization_id):
            raise ValueError(f"Lead '{dto.lead_id}' does not belong to organization '{organization_id}'.")

        broker_id = dto.broker_id or str(lead.broker_id) or authenticated_broker_id

        slot_start = dto.slot_start_utc
        slot_end = slot_start + timedelta(minutes=dto.duration_minutes)

        # 3. Acquire Distributed Hold Lock (5 Mins)
        hold = await self.lock_manager.acquire_hold(
            broker_id=broker_id,
            lead_id=str(lead.id),
            slot_start_utc=slot_start,
            slot_end_utc=slot_end
        )
        if not hold:
            raise ValueError(f"Slot {slot_start.isoformat()} is already held or booked. Please choose another slot.")
        hold_id = hold.id

        # 4. Validate Property Availability if Viewing
        lead_name = lead.name or "Client"
        title = f"{dto.meeting_type.replace('_', ' ').title()}: {lead_name}"
        location_str = dto.location_address or "WefyLabs Real Estate Hub"

        p_pk = None
        if dto.property_id:
            try:
                p_pk = uuid.UUID(str(dto.property_id))
            except Exception:
                p_pk = dto.property_id

            stmt_p = select(PropertyListing).where(PropertyListing.id == p_pk)
            res_p = await self.db.execute(stmt_p)
            prop = res_p.scalar_one_or_none()
            if not prop or prop.status != "available":
                await self.lock_manager.release_hold(hold_id)
                raise ValueError(f"Property '{dto.property_id}' is no longer available for booking.")

            prop_org = getattr(prop, "organization_id", None) or getattr(prop, "broker_id", None)
            if organization_id and prop_org and str(prop_org) != str(organization_id):
                await self.lock_manager.release_hold(hold_id)
                raise ValueError(f"Property '{dto.property_id}' does not belong to organization '{organization_id}'.")

            title = f"Property Viewing: {prop.title} ({lead_name})"
            location_str = f"{prop.locality}, {prop.city}"

        # 4b. Resolve broker's connected calendar account & valid token
        account_email = "broker@wefylabs.com"
        access_token = None
        b_uuid = None
        if broker_id:
            try:
                b_uuid = uuid.UUID(str(broker_id))
            except Exception:
                b_uuid = broker_id

        try:
            from app.models.calendar_models import CalendarAccount
            from app.modules.calendar.auth.token_refresh_service import TokenRefreshService

            stmt_acc = select(CalendarAccount).where(
                CalendarAccount.broker_id == b_uuid,
                CalendarAccount.is_connected == True
            )
            res_acc = await self.db.execute(stmt_acc)
            cal_account = res_acc.scalar_one_or_none()
            if cal_account:
                account_email = cal_account.account_email
                try:
                    access_token = await TokenRefreshService.get_valid_access_token(self.db, cal_account)
                except Exception as exc:
                    logger.warning(f"[BookingService] Token refresh error: {exc}")
        except Exception as exc:
            logger.debug(f"[BookingService] Could not resolve broker account: {exc}")

        # 4c. Create External Calendar Event & Virtual Meeting Link
        ext_result = {}
        try:
            ext_result = await self.provider.create_event(
                account_email=account_email or "broker@wefylabs.com",
                title=title,
                start_utc=slot_start,
                end_utc=slot_end,
                description=dto.notes,
                location=location_str,
                attendee_emails=[f"{lead.phone}@whatsapp.wefylabs.internal"],
                virtual_provider=dto.virtual_provider,
                access_token=access_token
            )
        except Exception as exc:
            if hold_id:
                await self.lock_manager.release_hold(hold_id)
            logger.error(f"[BookingService] Calendar provider failed: {exc}")
            raise ValueError(f"Calendar provider error: {str(exc)}")

        # 5. Determine Timezones
        customer_tz = TimezoneService.resolve(TimezoneContext(
            inferred_timezone=(
                TimezoneService._infer_from_phone(lead.phone) if lead.phone else None
            )
        ))
        broker_tz = TimezoneService.resolve(TimezoneContext(
            inferred_timezone=getattr(lead, 'market_timezone', None)
        ))

        # 6. Persist Meeting Record with atomic rollback on failure
        b_uuid = uuid.UUID(str(broker_id)) if broker_id else None
        l_uuid = uuid.UUID(str(lead.id)) if lead.id else None

        try:
            meeting = Meeting(
                id=str(uuid.uuid4()),
                organization_id=organization_id,
                broker_id=b_uuid,
                lead_id=l_uuid,
                meeting_type=dto.meeting_type,
                title=title,
                description=dto.notes,
                status="CONFIRMED",
                start_utc=slot_start,
                end_utc=slot_end,
                customer_timezone=customer_tz,
                broker_timezone=broker_tz,
                duration_minutes=dto.duration_minutes,
                location_type=dto.location_type,
                location_address=location_str,
                virtual_provider=dto.virtual_provider,
                meeting_url=ext_result.get("meeting_url"),
                external_event_id=ext_result.get("external_event_id"),
                idempotency_key=dto.idempotency_key
            )
            self.db.add(meeting)
            await self.db.commit()
            await self.db.refresh(meeting)

            # 6b. If Property Viewing, create Viewing sub-entity
            if dto.property_id:
                viewing = Viewing(
                    meeting_id=meeting.id,
                    property_id=str(dto.property_id),
                    security_preclearance=True
                )
                self.db.add(viewing)

                # 6c. Update or create LeadPropertyInterest
                from app.models.property_models import LeadPropertyInterest
                try:
                    stmt_int = select(LeadPropertyInterest).where(
                        LeadPropertyInterest.lead_id == l_pk,
                        LeadPropertyInterest.property_id == p_pk
                    )
                    res_int = await self.db.execute(stmt_int)
                    interest = res_int.scalar_one_or_none()
                    if interest:
                        interest.status = "visit_requested"
                        interest.notes = (interest.notes or "") + f"\nVisit booked for {slot_start.isoformat()}"
                    else:
                        new_interest = LeadPropertyInterest(
                            lead_id=l_pk,
                            property_id=p_pk,
                            status="visit_requested",
                            source="appointment_flow",
                            notes=f"Visit booked for {slot_start.isoformat()}"
                        )
                        self.db.add(new_interest)
                except Exception as exc:
                    logger.debug(f"[BOOKING] LeadPropertyInterest update skipped: {exc}")

            # 6d. Record Customer Timeline Activity
            from app.models.crm_models import Activity
            try:
                b_uuid_act = uuid.UUID(str(broker_id)) if broker_id else None
                l_uuid_act = uuid.UUID(str(lead.id)) if lead.id else None
                activity = Activity(
                    organization_id=organization_id,
                    actor_id=b_uuid_act,
                    lead_id=l_uuid_act,
                    activity_type="meeting_booked",
                    title=f"Appointment Confirmed: {title}",
                    description=f"Scheduled for {meeting.start_utc.isoformat()} ({customer_tz})",
                    activity_data={
                        "meeting_id": meeting.id,
                        "meeting_type": meeting.meeting_type,
                        "property_id": str(dto.property_id) if dto.property_id else None,
                        "location": location_str,
                        "meeting_url": meeting.meeting_url,
                    }
                )
                self.db.add(activity)
            except Exception as exc:
                logger.debug(f"[BOOKING] Timeline activity skipped: {exc}")

            # 7. Create Reminders (T-24h, T-2h, T-30m)
            now_utc = datetime.now(timezone.utc)
            for offset in [1440, 120, 30]:
                rem_time = slot_start - timedelta(minutes=offset)
                if rem_time > now_utc:
                    rem = MeetingReminder(
                        meeting_id=meeting.id,
                        offset_minutes=offset,
                        channel="WHATSAPP",
                        scheduled_for_utc=rem_time,
                        is_sent=False
                    )
                    self.db.add(rem)

            # Release hold
            if hold_id:
                await self.lock_manager.release_hold(hold_id)
            await self.db.commit()

        except Exception as db_exc:
            await self.db.rollback()
            if hold_id:
                await self.lock_manager.release_hold(hold_id)
            # Reconcile external event if created
            if ext_result and ext_result.get("external_event_id"):
                try:
                    await self.provider.cancel_event(
                        account_email=account_email,
                        external_event_id=ext_result["external_event_id"],
                        access_token=access_token
                    )
                except Exception as rollback_err:
                    logger.error(f"[BOOKING] External event rollback error: {rollback_err}")
            logger.error(f"[BOOKING] Database persistence error: {db_exc}")
            raise ValueError(f"Failed to persist booking: {str(db_exc)}")

        logger.info(f"[BOOKING] Successfully confirmed Meeting {meeting.id} for Lead {lead.id}.")

        return BookingResponseDTO(
            id=meeting.id,
            organization_id=organization_id,
            broker_id=broker_id,
            lead_id=str(lead.id),
            meeting_type=meeting.meeting_type,
            title=meeting.title,
            status=meeting.status,
            start_utc=meeting.start_utc,
            end_utc=meeting.end_utc,
            customer_timezone=meeting.customer_timezone,
            broker_timezone=meeting.broker_timezone,
            duration_minutes=meeting.duration_minutes,
            location_address=meeting.location_address,
            virtual_provider=meeting.virtual_provider,
            meeting_url=meeting.meeting_url,
            property_id=dto.property_id
        )
