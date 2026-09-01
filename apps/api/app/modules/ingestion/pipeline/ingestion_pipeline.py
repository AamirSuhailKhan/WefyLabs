"""
Universal Lead Ingestion Pipeline
=================================
Central unified lifecycle engine for ALL incoming leads across BeetleLabs:
  Source -> Connector -> Normalization -> Deduplication -> Persistence -> Timeline -> Audit -> Domain Events
"""
import time
import uuid
import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.lead import Lead
from app.models.ingestion_models import OriginalPayload, IngestionLog
from app.models.infrastructure_models import TimelineEvent
from app.modules.ingestion.connectors.connector_factory import get_connector
from app.modules.ingestion.dto.canonical_lead_dto import CanonicalLeadDTO, IngestionResponseDTO
from app.infrastructure.events.event_bus import event_bus, DomainEvent, StandardDomainEvents, ActorContext
from app.modules.audit.service.audit_service import AuditLogService
from app.modules.audit.dto.audit_dto import AuditCreateDTO

logger = logging.getLogger(__name__)


class LeadIngestionPipeline:
    """
    Unified Ingestion Engine.
    Executes source validation, canonical normalization, deduplication,
    CRM persistence, original payload archiving, and domain event dispatch.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit_service = AuditLogService(db)

    async def ingest_lead(
        self,
        source: str,
        raw_payload: Dict[str, Any],
        organization_id: str,
        user_id: str = "system",
        idempotency_key: Optional[str] = None,
        headers: Optional[Dict[str, Any]] = None,
    ) -> IngestionResponseDTO:
        start_time = time.time()
        ingestion_id = f"ing_{uuid.uuid4().hex[:12]}"

        # 1. Idempotency Check
        idem_key = idempotency_key or self._generate_payload_hash(raw_payload)
        existing_log = await self._check_idempotency(organization_id, idem_key)
        if existing_log and existing_log.status == "success":
            latency_ms = round((time.time() - start_time) * 1000, 2)
            logger.info(f"[INGESTION DUP] Idempotent request detected key='{idem_key}' LeadID={existing_log.lead_id}")
            return IngestionResponseDTO(
                ingestion_id=ingestion_id,
                status="duplicate",
                lead_id=existing_log.lead_id,
                source=source,
                latency_ms=latency_ms,
                message="Idempotent lead ingestion. Existing lead returned.",
            )

        # 2. Preserve Original Payload (Audit/Compliance)
        await self._archive_original_payload(
            ingestion_id=ingestion_id,
            organization_id=organization_id,
            source=source,
            raw_payload=raw_payload,
            headers=headers,
        )

        # 3. Resolve Connector & Normalize
        connector = get_connector(source)
        if not connector.validate_raw(raw_payload):
            latency_ms = round((time.time() - start_time) * 1000, 2)
            await self._log_ingestion(ingestion_id, organization_id, source, "rejected", idem_key, latency_ms, "Invalid payload structure.")
            return IngestionResponseDTO(
                ingestion_id=ingestion_id,
                status="rejected",
                source=source,
                latency_ms=latency_ms,
                message="Payload validation failed. Missing required fields.",
            )

        try:
            canonical: CanonicalLeadDTO = connector.parse_to_canonical(raw_payload)
        except Exception as exc:
            latency_ms = round((time.time() - start_time) * 1000, 2)
            await self._log_ingestion(ingestion_id, organization_id, source, "rejected", idem_key, latency_ms, str(exc))
            return IngestionResponseDTO(
                ingestion_id=ingestion_id, status="rejected", source=source, latency_ms=latency_ms, message=f"Normalization error: {exc}"
            )

        # 4. Deduplication & Persistence
        lead, is_new = await self._persist_lead(canonical, organization_id)

        # 5. Record Timeline & Audit Log
        await self._record_timeline(lead, source, is_new)
        await self.audit_service.log(AuditCreateDTO(
            action="lead.ingested",
            resource_type="lead",
            resource_id=str(lead.id),
            actor_id=user_id if user_id != "system" else None,
            actor_type="system" if user_id == "system" else "user",
            organization_id=organization_id,
            changes={"source": source, "is_new": is_new, "ingestion_id": ingestion_id},
            request_id=ingestion_id,
        ))

        latency_ms = round((time.time() - start_time) * 1000, 2)
        await self._log_ingestion(ingestion_id, organization_id, source, "success", idem_key, latency_ms, lead_id=str(lead.id))

        # 6. Publish Domain Event
        await event_bus.publish(DomainEvent(
            event_type=StandardDomainEvents.LEAD_CREATED if is_new else StandardDomainEvents.LEAD_UPDATED,
            organization_id=organization_id,
            actor=ActorContext(user_id=user_id, actor_type="system"),
            correlation_id=ingestion_id,
            payload={
                "lead_id": str(lead.id),
                "name": lead.name,
                "phone": lead.phone,
                "source": source,
                "is_new": is_new,
                "ingestion_id": ingestion_id,
            }
        ))

        logger.info(f"[INGESTION SUCCESS] {source} -> Lead {lead.id} ({'NEW' if is_new else 'UPDATED'}) | {latency_ms}ms")
        return IngestionResponseDTO(
            ingestion_id=ingestion_id,
            status="ingested" if is_new else "updated",
            lead_id=str(lead.id),
            source=source,
            latency_ms=latency_ms,
            message=f"Lead successfully ingested and persistent (Lead ID: {lead.id}).",
        )

    async def _persist_lead(self, dto: CanonicalLeadDTO, organization_id: str) -> Tuple[Lead, bool]:
        """Finds existing lead by broker/phone or creates a new Lead entity."""
        try:
            org_uuid = uuid.UUID(organization_id)
        except Exception:
            org_uuid = uuid.uuid4()

        # Check existing lead by phone
        stmt = select(Lead).where(Lead.broker_id == org_uuid, Lead.phone == dto.phone, Lead.deleted_at.is_(None))
        lead = (await self.db.execute(stmt)).scalars().first()

        if lead:
            if dto.name and lead.name != dto.name: lead.name = dto.name
            if dto.property_type: lead.property_type = dto.property_type
            if dto.notes:
                current_notes = list(lead.notes or [])
                current_notes.append({"text": dto.notes[0], "added_at": datetime.now(timezone.utc).isoformat()})
                lead.notes = current_notes
            lead.updated_at = datetime.now(timezone.utc)
            await self.db.commit()
            return lead, False
        else:
            notes_payload = [{"text": n, "added_at": datetime.now(timezone.utc).isoformat()} for n in dto.notes]
            lead = Lead(
                broker_id=org_uuid,
                phone=dto.phone,
                name=dto.name,
                source=dto.source if dto.source in ('whatsapp_forward', 'facebook', 'google', 'manual') else 'manual',
                score="pending",
                property_type=dto.property_type if dto.property_type in ('1bhk', '2bhk', '3bhk', 'villa', 'plot') else None,
                preferred_locations=[dto.city] if dto.city else [],
                notes=notes_payload,
                status="pending",
                pipeline_stage="new",
            )
            self.db.add(lead)
            await self.db.commit()
            await self.db.refresh(lead)
            return lead, True

    async def _archive_original_payload(
        self, ingestion_id: str, organization_id: str, source: str, raw_payload: Dict, headers: Optional[Dict]
    ) -> None:
        archive = OriginalPayload(
            ingestion_id=ingestion_id,
            organization_id=organization_id,
            source=source,
            raw_payload_json=raw_payload,
            headers_json=headers or {},
        )
        self.db.add(archive)
        await self.db.flush()

    async def _record_timeline(self, lead: Lead, source: str, is_new: bool) -> None:
        event = TimelineEvent(
            organization_id=str(lead.broker_id),
            resource_type="lead",
            resource_id=str(lead.id),
            event_type="lead.created" if is_new else "lead.updated",
            actor_id="system",
            actor_type="system",
            title=f"Lead {'Received' if is_new else 'Updated'} via {source.title()}",
            body=f"Canonical lead ingested from source '{source}'.",
            event_metadata={"source": source, "phone": lead.phone},
        )
        self.db.add(event)
        await self.db.flush()

    async def _log_ingestion(
        self, ingestion_id: str, organization_id: str, source: str, status: str,
        idempotency_key: str, latency_ms: float, error_details: Optional[str] = None, lead_id: Optional[str] = None
    ) -> None:
        log = IngestionLog(
            ingestion_id=ingestion_id,
            organization_id=organization_id,
            source=source,
            idempotency_key=idempotency_key,
            status=status,
            lead_id=lead_id,
            latency_ms=latency_ms,
            error_details=error_details,
        )
        self.db.add(log)
        await self.db.commit()

    def _generate_payload_hash(self, payload: Dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    async def _check_idempotency(self, organization_id: str, key: str) -> Optional[IngestionLog]:
        stmt = select(IngestionLog).where(IngestionLog.organization_id == organization_id, IngestionLog.idempotency_key == key)
        return (await self.db.execute(stmt)).scalars().first()
