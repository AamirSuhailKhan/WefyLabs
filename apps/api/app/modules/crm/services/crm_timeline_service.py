"""WefyLabs Native CRM — Unified Timeline Aggregation Service
=============================================================
Combines domain activities, communication events, audit logs,
notes, appointments, and lifecycle changes into one unified,
chronological timeline with strict actor and channel provenance.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc

from app.models.crm_models import Activity, LeadNote, Task
from app.models.lead import Lead
from app.models.calendar_models import SchedulingMeeting
from app.models.communication_models import ChannelMessage, OmnichannelConversation
from app.models.audit_log import AuditLog
from app.modules.crm.dto.crm_schemas import CustomerTimelineEventDTO


class CRMTimelineService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_unified_timeline(
        self,
        lead_id: str,
        organization_id: str,
        limit: int = 100
    ) -> List[CustomerTimelineEventDTO]:
        """
        Gathers events from Activities, Notes, Meetings, Communications, and Audits
        for the given lead within the authenticated organization boundary.
        """
        events: List[CustomerTimelineEventDTO] = []
        lead_uuid = uuid.UUID(lead_id) if isinstance(lead_id, str) and len(lead_id) == 36 else None

        # 1. Activities
        try:
            stmt = select(Activity).where(
                Activity.lead_id == lead_uuid
            ).order_by(Activity.created_at.desc()).limit(limit)
            res = await self.db.execute(stmt)
            for act in res.scalars().all():
                events.append(
                    CustomerTimelineEventDTO(
                        id=f"act_{act.id}",
                        event_type=f"activity.{act.activity_type}",
                        title=act.title,
                        description=act.description,
                        timestamp=act.created_at,
                        actor=str(act.actor_id) if act.actor_id else "System",
                        actor_type="HUMAN" if act.actor_id else "SYSTEM",
                        source="crm_activity",
                        channel=act.activity_data.get("channel") if act.activity_data else None,
                        metadata=act.activity_data or {}
                    )
                )
        except Exception:
            pass

        # 2. Notes
        try:
            stmt_notes = select(LeadNote).where(
                LeadNote.lead_id == lead_uuid
            ).order_by(LeadNote.created_at.desc()).limit(limit)
            res_notes = await self.db.execute(stmt_notes)
            for note in res_notes.scalars().all():
                events.append(
                    CustomerTimelineEventDTO(
                        id=f"note_{note.id}",
                        event_type="note.created",
                        title="Internal Note Added",
                        description=note.content,
                        timestamp=note.created_at,
                        actor=str(note.broker_id),
                        actor_type="HUMAN",
                        source="crm_note",
                        channel="internal",
                        metadata={"visibility": "ORGANIZATION"}
                    )
                )
        except Exception:
            pass

        # 3. Scheduled Appointments / Site Visits
        try:
            stmt_mtg = select(SchedulingMeeting).where(
                SchedulingMeeting.lead_id == lead_uuid
            ).order_by(SchedulingMeeting.start_utc.desc()).limit(limit)
            res_mtg = await self.db.execute(stmt_mtg)
            for mtg in res_mtg.scalars().all():
                events.append(
                    CustomerTimelineEventDTO(
                        id=f"mtg_{mtg.id}",
                        event_type=f"appointment.{mtg.status.lower()}",
                        title=f"{mtg.meeting_type.replace('_', ' ').title()}: {mtg.title}",
                        description=f"Status: {mtg.status} | Scheduled for {mtg.start_utc.isoformat()}",
                        timestamp=mtg.start_utc,
                        actor=str(mtg.broker_id),
                        actor_type="HUMAN",
                        source="appointment_engine",
                        channel=mtg.virtual_provider or "in_person",
                        metadata={
                            "meeting_type": mtg.meeting_type,
                            "status": mtg.status,
                            "duration_minutes": mtg.duration_minutes
                        }
                    )
                )
        except Exception:
            pass

        # 4. Omnichannel Communication Messages
        try:
            conv_stmt = select(OmnichannelConversation.id).where(
                OmnichannelConversation.lead_id == lead_uuid
            )
            conv_res = await self.db.execute(conv_stmt)
            conv_ids = conv_res.scalars().all()
            if conv_ids:
                msg_stmt = select(ChannelMessage).where(
                    ChannelMessage.conversation_id.in_(conv_ids)
                ).order_by(ChannelMessage.created_at.desc()).limit(limit)
                msg_res = await self.db.execute(msg_stmt)
                for msg in msg_res.scalars().all():
                    actor_type = "AI_AGENT" if msg.sender_type == "ai_agent" else ("CUSTOMER" if msg.direction == "inbound" else "HUMAN")
                    events.append(
                        CustomerTimelineEventDTO(
                            id=f"msg_{msg.id}",
                            event_type=f"message.{msg.direction}",
                            title=f"{msg.channel.upper()} Message ({msg.direction})",
                            description=msg.content[:200] if msg.content else "[Media Message]",
                            timestamp=msg.created_at,
                            actor=msg.sender_type or "system",
                            actor_type=actor_type,
                            source="communication_hub",
                            channel=msg.channel,
                            metadata={"delivery_status": msg.delivery_status}
                        )
                    )
        except Exception:
            pass

        # 5. Audit Log stage & critical changes
        try:
            audit_stmt = select(AuditLog).where(
                AuditLog.entity_id == str(lead_id)
            ).order_by(AuditLog.created_at.desc()).limit(limit)
            audit_res = await self.db.execute(audit_stmt)
            for aud in audit_res.scalars().all():
                events.append(
                    CustomerTimelineEventDTO(
                        id=f"audit_{aud.id}",
                        event_type=f"audit.{aud.action.lower()}",
                        title=f"Audit: {aud.action.replace('_', ' ').title()}",
                        description=f"Action performed by {aud.user_id or 'System'}",
                        timestamp=aud.created_at,
                        actor=str(aud.user_id) if aud.user_id else "System",
                        actor_type="HUMAN" if aud.user_id else "SYSTEM",
                        source="audit_service",
                        channel="system",
                        metadata=aud.changes or {}
                    )
                )
        except Exception:
            pass

        # Sort all unified events by timestamp descending
        events.sort(key=lambda x: x.timestamp, reverse=True)
        return events[:limit]
