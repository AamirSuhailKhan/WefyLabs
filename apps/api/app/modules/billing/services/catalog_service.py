"""
WefyLabs Canonical Product & Pricing Catalog Service
=====================================================
Database-driven product catalog supporting:
- Plan tiers (FREE, STARTER, PRO, ENTERPRISE)
- Billing intervals (MONTHLY, ANNUAL)
- Plan versioning with immutability guarantees once subscribed
- Seed catalog initialization and retrieval
- Feature & entitlement definitions
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.billing_models import (
    Plan,
    PlanVersion,
    PlanEntitlement,
    PlanInterval,
    EntitlementType,
    LimitEnforcementPolicy,
)
from app.modules.billing.domain.money import Money

DEFAULT_CATALOG = [
    {
        "code": "free",
        "name": "Free Tier",
        "description": "Essential CRM features for individual solo brokers getting started.",
        "sort_order": 0,
        "versions": [
            {
                "version": 1,
                "interval": PlanInterval.MONTHLY.value,
                "price": Decimal("0.0"),
                "currency": "INR",
                "trial_days": 0,
                "entitlements": [
                    {"key": "team_members", "type": EntitlementType.SEAT_LIMIT.value, "limit": 1},
                    {"key": "ai_messages_per_month", "type": EntitlementType.AI_TOKEN_LIMIT.value, "limit": 25},
                    {"key": "whatsapp_messages_per_month", "type": EntitlementType.MESSAGE_LIMIT.value, "limit": 50},
                    {"key": "active_leads", "type": EntitlementType.LEAD_LIMIT.value, "limit": 50},
                    {"key": "property_inventory", "type": EntitlementType.PROPERTY_LIMIT.value, "limit": 20},
                    {"key": "workflow_executions", "type": EntitlementType.AUTOMATION_LIMIT.value, "limit": 10},
                    {"key": "exports", "type": EntitlementType.EXPORT_LIMIT.value, "limit": 2},
                    {"key": "avm_valuation", "type": EntitlementType.BOOLEAN.value, "bool": False},
                ]
            }
        ]
    },
    {
        "code": "starter",
        "name": "Starter",
        "description": "Growing brokers seeking AI automation and omnichannel WhatsApp messaging.",
        "sort_order": 1,
        "versions": [
            {
                "version": 1,
                "interval": PlanInterval.MONTHLY.value,
                "price": Decimal("2999.00"),
                "currency": "INR",
                "trial_days": 7,
                "entitlements": [
                    {"key": "team_members", "type": EntitlementType.SEAT_LIMIT.value, "limit": 2},
                    {"key": "ai_messages_per_month", "type": EntitlementType.AI_TOKEN_LIMIT.value, "limit": 250},
                    {"key": "whatsapp_messages_per_month", "type": EntitlementType.MESSAGE_LIMIT.value, "limit": 500},
                    {"key": "active_leads", "type": EntitlementType.LEAD_LIMIT.value, "limit": 500},
                    {"key": "property_inventory", "type": EntitlementType.PROPERTY_LIMIT.value, "limit": 150},
                    {"key": "workflow_executions", "type": EntitlementType.AUTOMATION_LIMIT.value, "limit": 100},
                    {"key": "exports", "type": EntitlementType.EXPORT_LIMIT.value, "limit": 20},
                    {"key": "avm_valuation", "type": EntitlementType.BOOLEAN.value, "bool": True},
                ]
            },
            {
                "version": 1,
                "interval": PlanInterval.ANNUAL.value,
                "price": Decimal("29999.00"),
                "currency": "INR",
                "trial_days": 7,
                "entitlements": [
                    {"key": "team_members", "type": EntitlementType.SEAT_LIMIT.value, "limit": 2},
                    {"key": "ai_messages_per_month", "type": EntitlementType.AI_TOKEN_LIMIT.value, "limit": 300},
                    {"key": "whatsapp_messages_per_month", "type": EntitlementType.MESSAGE_LIMIT.value, "limit": 600},
                    {"key": "active_leads", "type": EntitlementType.LEAD_LIMIT.value, "limit": 600},
                    {"key": "property_inventory", "type": EntitlementType.PROPERTY_LIMIT.value, "limit": 200},
                    {"key": "workflow_executions", "type": EntitlementType.AUTOMATION_LIMIT.value, "limit": 150},
                    {"key": "exports", "type": EntitlementType.EXPORT_LIMIT.value, "limit": 30},
                    {"key": "avm_valuation", "type": EntitlementType.BOOLEAN.value, "bool": True},
                ]
            }
        ]
    },
    {
        "code": "pro",
        "name": "Professional",
        "description": "Full-scale brokerage teams requiring high-volume AI qualification and custom pipelines.",
        "sort_order": 2,
        "versions": [
            {
                "version": 1,
                "interval": PlanInterval.MONTHLY.value,
                "price": Decimal("4999.00"),
                "currency": "INR",
                "trial_days": 14,
                "entitlements": [
                    {"key": "team_members", "type": EntitlementType.SEAT_LIMIT.value, "limit": 5},
                    {"key": "ai_messages_per_month", "type": EntitlementType.AI_TOKEN_LIMIT.value, "limit": 1000},
                    {"key": "whatsapp_messages_per_month", "type": EntitlementType.MESSAGE_LIMIT.value, "limit": 2500},
                    {"key": "active_leads", "type": EntitlementType.LEAD_LIMIT.value, "limit": 2500},
                    {"key": "property_inventory", "type": EntitlementType.PROPERTY_LIMIT.value, "limit": 1000},
                    {"key": "workflow_executions", "type": EntitlementType.AUTOMATION_LIMIT.value, "limit": 500},
                    {"key": "exports", "type": EntitlementType.EXPORT_LIMIT.value, "limit": 100},
                    {"key": "avm_valuation", "type": EntitlementType.BOOLEAN.value, "bool": True},
                ]
            },
            {
                "version": 1,
                "interval": PlanInterval.ANNUAL.value,
                "price": Decimal("49999.00"),
                "currency": "INR",
                "trial_days": 14,
                "entitlements": [
                    {"key": "team_members", "type": EntitlementType.SEAT_LIMIT.value, "limit": 5},
                    {"key": "ai_messages_per_month", "type": EntitlementType.AI_TOKEN_LIMIT.value, "limit": 1200},
                    {"key": "whatsapp_messages_per_month", "type": EntitlementType.MESSAGE_LIMIT.value, "limit": 3000},
                    {"key": "active_leads", "type": EntitlementType.LEAD_LIMIT.value, "limit": 3000},
                    {"key": "property_inventory", "type": EntitlementType.PROPERTY_LIMIT.value, "limit": 1500},
                    {"key": "workflow_executions", "type": EntitlementType.AUTOMATION_LIMIT.value, "limit": 750},
                    {"key": "exports", "type": EntitlementType.EXPORT_LIMIT.value, "limit": 150},
                    {"key": "avm_valuation", "type": EntitlementType.BOOLEAN.value, "bool": True},
                ]
            }
        ]
    },
    {
        "code": "enterprise",
        "name": "Enterprise",
        "description": "Unlimited capacity, dedicated WhatsApp numbers, custom AI models, and SLA.",
        "sort_order": 3,
        "versions": [
            {
                "version": 1,
                "interval": PlanInterval.ANNUAL.value,
                "price": Decimal("149999.00"),
                "currency": "INR",
                "trial_days": 30,
                "entitlements": [
                    {"key": "team_members", "type": EntitlementType.UNLIMITED.value, "limit": None},
                    {"key": "ai_messages_per_month", "type": EntitlementType.UNLIMITED.value, "limit": None},
                    {"key": "whatsapp_messages_per_month", "type": EntitlementType.UNLIMITED.value, "limit": None},
                    {"key": "active_leads", "type": EntitlementType.UNLIMITED.value, "limit": None},
                    {"key": "property_inventory", "type": EntitlementType.UNLIMITED.value, "limit": None},
                    {"key": "workflow_executions", "type": EntitlementType.UNLIMITED.value, "limit": None},
                    {"key": "exports", "type": EntitlementType.UNLIMITED.value, "limit": None},
                    {"key": "avm_valuation", "type": EntitlementType.BOOLEAN.value, "bool": True},
                ]
            }
        ]
    }
]


class CatalogService:
    """
    Manages Plan, PlanVersion, and PlanEntitlement database lifecycle.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def ensure_default_catalog_seeded(self) -> None:
        """
        Seeds canonical plans and version 1 entitlements if database is empty.
        """
        stmt = select(Plan).limit(1)
        existing = (await self.db.execute(stmt)).scalars().first()
        if existing:
            return  # Catalog already seeded

        for plan_data in DEFAULT_CATALOG:
            plan = Plan(
                code=plan_data["code"],
                name=plan_data["name"],
                description=plan_data["description"],
                sort_order=plan_data["sort_order"],
                is_active=True,
            )
            self.db.add(plan)
            await self.db.flush()

            for v_data in plan_data["versions"]:
                pv = PlanVersion(
                    plan_id=plan.id,
                    version=v_data["version"],
                    interval=v_data["interval"],
                    price=v_data["price"],
                    currency=v_data["currency"],
                    trial_days=v_data["trial_days"],
                    is_active=True,
                )
                self.db.add(pv)
                await self.db.flush()

                for ent in v_data["entitlements"]:
                    pe = PlanEntitlement(
                        plan_version_id=pv.id,
                        entitlement_key=ent["key"],
                        entitlement_type=ent["type"],
                        limit_value=ent.get("limit"),
                        boolean_value=ent.get("bool", True if ent["type"] == EntitlementType.BOOLEAN.value else None),
                        enforcement_policy=LimitEnforcementPolicy.HARD_LIMIT.value,
                        overage_allowed=False,
                        reset_period="MONTHLY",
                    )
                    self.db.add(pe)

        await self.db.commit()

    async def get_active_catalog(self) -> List[Dict[str, Any]]:
        """
        Returns full public catalog formatted for comparison UI with versions and entitlements.
        """
        stmt = (
            select(Plan)
            .where(Plan.is_active == True)
            .order_by(Plan.sort_order)
            .options(
                selectinload(Plan.versions).selectinload(PlanVersion.entitlements)
            )
        )
        plans = (await self.db.execute(stmt)).scalars().all()

        if not plans:
            await self.ensure_default_catalog_seeded()
            plans = (await self.db.execute(stmt)).scalars().all()

        result = []
        for p in plans:
            versions_list = []
            for v in p.versions:
                if not v.is_active:
                    continue
                entitlements_map = {}
                for e in v.entitlements:
                    entitlements_map[e.entitlement_key] = {
                        "type": e.entitlement_type,
                        "limit": e.limit_value,
                        "boolean_value": e.boolean_value,
                        "enforcement_policy": e.enforcement_policy,
                        "overage_allowed": e.overage_allowed,
                    }
                versions_list.append({
                    "id": str(v.id),
                    "version": v.version,
                    "interval": v.interval,
                    "price": str(v.price),
                    "price_minor": Money(v.price, v.currency).to_minor_units(),
                    "currency": v.currency,
                    "trial_days": v.trial_days,
                    "entitlements": entitlements_map,
                })
            result.append({
                "id": str(p.id),
                "code": p.code,
                "name": p.name,
                "description": p.description,
                "versions": versions_list,
            })
        return result

    async def get_plan_version_by_code(
        self,
        plan_code: str,
        interval: str = PlanInterval.MONTHLY.value,
        version: Optional[int] = None
    ) -> Optional[PlanVersion]:
        """
        Resolves latest or specific active PlanVersion by plan code and interval.
        """
        stmt = (
            select(PlanVersion)
            .join(Plan, PlanVersion.plan_id == Plan.id)
            .where(
                and_(
                    Plan.code == plan_code.lower(),
                    PlanVersion.interval == interval.upper(),
                    PlanVersion.is_active == True,
                )
            )
            .options(selectinload(PlanVersion.entitlements), selectinload(PlanVersion.plan))
            .order_by(desc(PlanVersion.version))
        )
        if version:
            stmt = stmt.where(PlanVersion.version == version)
        return (await self.db.execute(stmt)).scalars().first()
