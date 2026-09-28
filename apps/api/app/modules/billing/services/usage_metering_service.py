"""
WefyLabs Canonical Usage Metering, Ingestion & Aggregation Service
===================================================================
Features:
- Meter registry (AI_REQUEST, AI_INPUT_TOKEN, AI_OUTPUT_TOKEN, WHATSAPP_MESSAGE, etc.)
- Append-only immutable UsageEvent ledger with strict idempotency deduplication.
- Safe under high concurrency (2, 5, 10, 50, 100 parallel submissions of identical keys).
- Durable rollup aggregation into UsageAggregate by organization & billing period.
- Reconciliation between raw usage events and durable aggregates.
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional, List, Tuple

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.billing_models import (
    UsageMeter,
    UsageEvent,
    UsageAggregate,
    BillingPeriod,
    BillingPeriodStatus,
    MeterAggregationType,
)

logger = logging.getLogger("wefylabs.billing.usage")

CANONICAL_METERS = [
    {
        "code": "AI_REQUEST",
        "name": "AI Copilot & Agent Requests",
        "unit": "requests",
        "aggregation_type": MeterAggregationType.COUNT.value,
        "source_event": "ai_agent.request",
        "is_billable": True,
    },
    {
        "code": "AI_INPUT_TOKEN",
        "name": "AI Prompt / Input Tokens",
        "unit": "tokens",
        "aggregation_type": MeterAggregationType.TOKEN_COUNT.value,
        "source_event": "ai_gateway.input_tokens",
        "is_billable": True,
    },
    {
        "code": "AI_OUTPUT_TOKEN",
        "name": "AI Completion / Output Tokens",
        "unit": "tokens",
        "aggregation_type": MeterAggregationType.TOKEN_COUNT.value,
        "source_event": "ai_gateway.output_tokens",
        "is_billable": True,
    },
    {
        "code": "WHATSAPP_MESSAGE",
        "name": "WhatsApp Outbound / Inbound Messages",
        "unit": "messages",
        "aggregation_type": MeterAggregationType.COUNT.value,
        "source_event": "communication.whatsapp_message",
        "is_billable": True,
    },
    {
        "code": "LEAD_CREATED",
        "name": "Leads Ingested",
        "unit": "leads",
        "aggregation_type": MeterAggregationType.COUNT.value,
        "source_event": "ingestion.lead_created",
        "is_billable": False,
    },
    {
        "code": "DOCUMENT_PROCESSED",
        "name": "Real Estate Documents Processed",
        "unit": "documents",
        "aggregation_type": MeterAggregationType.COUNT.value,
        "source_event": "ocr.document_processed",
        "is_billable": True,
    },
    {
        "code": "WORKFLOW_EXECUTION",
        "name": "Automated Follow-up Workflow Executions",
        "unit": "executions",
        "aggregation_type": MeterAggregationType.COUNT.value,
        "source_event": "workflow.execution",
        "is_billable": True,
    },
    {
        "code": "EXPORT",
        "name": "CRM Data & Report Exports",
        "unit": "exports",
        "aggregation_type": MeterAggregationType.COUNT.value,
        "source_event": "export.generated",
        "is_billable": True,
    },
]


class UsageMeteringService:
    """
    Durable, idempotent usage metering engine.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def ensure_meters_seeded(self) -> None:
        """
        Seeds canonical usage meters if absent.
        """
        for m_data in CANONICAL_METERS:
            stmt = select(UsageMeter).where(UsageMeter.code == m_data["code"])
            existing = (await self.db.execute(stmt)).scalars().first()
            if not existing:
                meter = UsageMeter(
                    code=m_data["code"],
                    name=m_data["name"],
                    unit=m_data["unit"],
                    aggregation_type=m_data["aggregation_type"],
                    source_event=m_data["source_event"],
                    is_billable=m_data["is_billable"],
                    reset_policy="BILLING_PERIOD",
                )
                self.db.add(meter)
        await self.db.commit()

    async def get_meter_by_code(self, meter_code: str) -> Optional[UsageMeter]:
        stmt = select(UsageMeter).where(UsageMeter.code == meter_code.upper())
        meter = (await self.db.execute(stmt)).scalars().first()
        if not meter:
            await self.ensure_meters_seeded()
            meter = (await self.db.execute(stmt)).scalars().first()
        return meter

    async def ingest_usage_event(
        self,
        organization_id: uuid.UUID,
        meter_code: str,
        quantity: Decimal,
        idempotency_key: str,
        event_key: Optional[str] = None,
        source_type: str = "SYSTEM",
        source_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        occurred_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[UsageEvent, bool]:
        """
        Atomically ingests a billable usage event.
        Returns (UsageEvent, is_new: bool).
        Guarantees that duplicate submissions with the same (organization_id, idempotency_key)
        return the existing record and NEVER duplicate consumption.
        """
        now = datetime.now(timezone.utc)
        occurred = occurred_at or now

        # 1. Check if event with same idempotency key already exists for this tenant
        stmt = select(UsageEvent).where(
            and_(
                UsageEvent.organization_id == organization_id,
                UsageEvent.idempotency_key == idempotency_key,
            )
        )
        existing = (await self.db.execute(stmt)).scalars().first()
        if existing:
            logger.info(f"[UsageMetering] Idempotent duplicate event detected: org={organization_id}, key={idempotency_key}")
            return existing, False

        meter = await self.get_meter_by_code(meter_code)
        if not meter:
            raise ValueError(f"Unknown usage meter code: {meter_code}")

        # 2. Find matching open billing period
        stmt_period = select(BillingPeriod).where(
            and_(
                BillingPeriod.organization_id == organization_id,
                BillingPeriod.period_start <= occurred,
                BillingPeriod.period_end > occurred,
                BillingPeriod.status == BillingPeriodStatus.OPEN.value,
            )
        )
        period = (await self.db.execute(stmt_period)).scalars().first()

        event = UsageEvent(
            organization_id=organization_id,
            meter_id=meter.id,
            event_name=meter.source_event,
            event_key=event_key or idempotency_key,
            quantity=quantity,
            unit=meter.unit,
            source_type=source_type,
            source_id=source_id,
            actor_id=actor_id,
            occurred_at=occurred,
            received_at=now,
            billing_period_id=period.id if period else None,
            idempotency_key=idempotency_key,
            metadata_payload=metadata or {},
        )

        try:
            self.db.add(event)
            await self.db.commit()
            await self.db.refresh(event)
            return event, True
        except IntegrityError:
            await self.db.rollback()
            # Concurrent race caught by unique constraint
            existing = (await self.db.execute(stmt)).scalars().first()
            if existing:
                return existing, False
            raise

    async def aggregate_usage(
        self,
        organization_id: uuid.UUID,
        billing_period_id: uuid.UUID
    ) -> List[UsageAggregate]:
        """
        Recomputes durable UsageAggregate records from raw immutable UsageEvents for a period.
        """
        stmt_period = select(BillingPeriod).where(BillingPeriod.id == billing_period_id)
        period = (await self.db.execute(stmt_period)).scalars().first()
        if not period:
            raise ValueError(f"Billing period {billing_period_id} not found.")

        # Group raw events by meter
        stmt_events = (
            select(
                UsageEvent.meter_id,
                func.sum(UsageEvent.quantity).label("total_qty"),
                func.count(UsageEvent.id).label("event_count")
            )
            .where(
                and_(
                    UsageEvent.organization_id == organization_id,
                    UsageEvent.occurred_at >= period.period_start,
                    UsageEvent.occurred_at < period.period_end,
                )
            )
            .group_by(UsageEvent.meter_id)
        )
        grouped = (await self.db.execute(stmt_events)).all()

        aggregates = []
        now = datetime.now(timezone.utc)

        for row in grouped:
            meter_id = row.meter_id
            total_qty = Decimal(str(row.total_qty or 0))

            stmt_meter = select(UsageMeter).where(UsageMeter.id == meter_id)
            meter = (await self.db.execute(stmt_meter)).scalars().first()
            unit = meter.unit if meter else "units"

            # Check existing aggregate
            stmt_agg = select(UsageAggregate).where(
                and_(
                    UsageAggregate.organization_id == organization_id,
                    UsageAggregate.meter_id == meter_id,
                    UsageAggregate.billing_period_id == billing_period_id,
                )
            )
            agg = (await self.db.execute(stmt_agg)).scalars().first()
            if agg:
                agg.quantity = total_qty
                agg.last_aggregated_at = now
            else:
                agg = UsageAggregate(
                    organization_id=organization_id,
                    meter_id=meter_id,
                    billing_period_id=billing_period_id,
                    period_start=period.period_start,
                    period_end=period.period_end,
                    quantity=total_qty,
                    unit=unit,
                    last_aggregated_at=now,
                )
                self.db.add(agg)
            aggregates.append(agg)

        await self.db.commit()
        return aggregates

    async def reconcile_usage(
        self,
        organization_id: uuid.UUID,
        billing_period_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Reconciles raw usage events against aggregates to verify mathematical integrity.
        """
        stmt_agg = select(UsageAggregate).where(
            and_(
                UsageAggregate.organization_id == organization_id,
                UsageAggregate.billing_period_id == billing_period_id,
            )
        )
        aggregates = (await self.db.execute(stmt_agg)).scalars().all()

        discrepancies = []
        for agg in aggregates:
            stmt_sum = select(func.coalesce(func.sum(UsageEvent.quantity), Decimal("0.0"))).where(
                and_(
                    UsageEvent.organization_id == organization_id,
                    UsageEvent.meter_id == agg.meter_id,
                    UsageEvent.occurred_at >= agg.period_start,
                    UsageEvent.occurred_at < agg.period_end,
                )
            )
            raw_sum = (await self.db.execute(stmt_sum)).scalar()
            if raw_sum != agg.quantity:
                discrepancies.append({
                    "meter_id": str(agg.meter_id),
                    "raw_sum": str(raw_sum),
                    "aggregate_quantity": str(agg.quantity),
                    "difference": str(raw_sum - agg.quantity),
                })

        return {
            "organization_id": str(organization_id),
            "billing_period_id": str(billing_period_id),
            "reconciled": len(discrepancies) == 0,
            "discrepancies": discrepancies,
        }
