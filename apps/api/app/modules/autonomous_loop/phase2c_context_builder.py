"""
Phase 2C — Real Production Context Builder
===========================================
Builds AgentContextObject from REAL authoritative database records.

REPLACES synthetic context (test fixtures with fake lead data).
NEVER produces synthetic context for production pilot execution.

Every context snapshot includes:
  - Source record IDs
  - Source record timestamps
  - Context freshness
  - Context version
  - Tenant + lead + execution identity

Freshness requirements by action type (Section 11):
  LOW risk (analytics): configurable (default 600s)
  MEDIUM risk (draft): configurable (default 300s)
  HIGH risk (send, schedule): strict (default 120s)
  FINANCIAL_IRREVERSIBLE: strictest (default 60s)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.autonomous_loop.phase2_agent_contracts import AgentContextObject
from app.modules.autonomous_loop.phase2_governance import Phase2ActionType, Phase2RiskClass

logger = logging.getLogger("wefylabs.phase2c.context_builder")

CONTEXT_BUILDER_VERSION = "v2c.1.0"

# Freshness TTL seconds by risk class (configurable via settings)
FRESHNESS_TTL_BY_RISK: Dict[str, int] = {
    Phase2RiskClass.LOW.value: 600,
    Phase2RiskClass.MEDIUM.value: 300,
    Phase2RiskClass.HIGH.value: 120,
    Phase2RiskClass.FINANCIAL_IRREVERSIBLE.value: 60,
}


class ContextBuildError(Exception):
    """Raised when context cannot be built from real data."""
    pass


class Phase2CContextBuilder:
    """
    Builds production AgentContextObject from authoritative DB records.

    This is NOT a factory for test fixtures.
    This class must only be used in production pilot execution paths.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def build(
        self,
        organization_id: str,
        lead_id: str,
        action_risk_class: Phase2RiskClass = Phase2RiskClass.MEDIUM,
    ) -> AgentContextObject:
        """
        Build a real, production AgentContextObject for the given lead.

        Raises:
            ContextBuildError: If lead not found, not in org, or data incomplete.
        """
        # Determine freshness TTL from action risk
        ttl = FRESHNESS_TTL_BY_RISK.get(action_risk_class.value, 300)

        # Step 1: Load lead
        lead = await self._load_lead(organization_id, lead_id)

        # Step 2: Load consent state
        consent = await self._load_consent(lead_id, organization_id)

        # Step 3: Load qualification profile
        qualification = await self._load_qualification(lead_id, organization_id)

        # Step 4: Load property shortlist (latest recommendation)
        property_shortlist = await self._load_property_shortlist(lead_id, organization_id)

        # Step 5: Load recent conversation
        recent_conversation = await self._load_recent_conversation(lead_id, organization_id)

        # Step 6: Load current deal
        current_deal = await self._load_current_deal(lead_id, organization_id)

        # Build context
        ctx = AgentContextObject(
            organization_id=organization_id,
            lead_id=lead_id,
            lead_summary={
                "id": str(lead.get("id", "")),
                "name": lead.get("name", ""),
                "pipeline_stage": lead.get("pipeline_stage", ""),
                "status": lead.get("status", ""),
                "source": lead.get("source", ""),
                "budget": lead.get("budget"),
                "last_activity_at": lead.get("updated_at", "").isoformat() if hasattr(lead.get("updated_at", ""), "isoformat") else str(lead.get("updated_at", "")),
            },
            lead_requirements=lead.get("requirements", {}),
            qualification_profile=qualification,
            property_shortlist=property_shortlist,
            recent_conversation=recent_conversation,
            current_deal=current_deal,
            consent_state=consent,
            policy_summary={
                "context_builder_version": CONTEXT_BUILDER_VERSION,
                "freshness_ttl_seconds": ttl,
                "risk_class": action_risk_class.value,
                "is_production_context": True,
            },
            freshness_ttl_seconds=ttl,
        )

        logger.info(
            f"[CONTEXT_BUILDER] Built real context org={organization_id} lead={lead_id} "
            f"ttl={ttl}s risk={action_risk_class.value}"
        )
        return ctx

    async def _load_lead(self, organization_id: str, lead_id: str) -> Dict[str, Any]:
        """Loads lead from DB with tenant isolation verification."""
        try:
            from app.models.lead import Lead
            from sqlalchemy import or_

            # Canonical type normalization: Lead columns use UUID(as_uuid=True)
            try:
                lead_uuid = uuid.UUID(str(lead_id))
            except (ValueError, TypeError, AttributeError):
                lead_uuid = lead_id

            try:
                org_uuid = uuid.UUID(str(organization_id))
            except (ValueError, TypeError, AttributeError):
                org_uuid = organization_id

            stmt = select(Lead).where(
                and_(
                    Lead.id == lead_uuid,
                    or_(
                        Lead.organization_id == org_uuid,
                        Lead.broker_id == org_uuid,
                    ),
                )
            )
            result = await self.db.execute(stmt)
            lead = result.scalar_one_or_none()
            if lead is None:
                raise ContextBuildError(
                    f"Lead {lead_id} not found for org {organization_id}. "
                    f"Either does not exist or tenant isolation prevents access."
                )
            return {
                "id": str(lead.id),
                "name": getattr(lead, "name", ""),
                "pipeline_stage": getattr(lead, "pipeline_stage", ""),
                "status": getattr(lead, "status", ""),
                "source": getattr(lead, "source", ""),
                "budget": getattr(lead, "budget", None),
                "requirements": getattr(lead, "requirements", {}) or {},
                "updated_at": getattr(lead, "updated_at", None),
            }
        except ContextBuildError:
            raise
        except Exception as exc:
            raise ContextBuildError(f"Failed to load lead {lead_id}: {exc}") from exc

    async def _load_consent(self, lead_id: str, organization_id: str) -> Dict[str, Any]:
        """Loads consent state. Default to BLOCKED if not found (fail-closed)."""
        try:
            async with self.db.begin_nested():
                # Try to load from lead_automation_state (Part 21.8 model)
                from app.modules.autonomous_loop.models import LeadAutomationState
                stmt = select(LeadAutomationState).where(
                    and_(
                        LeadAutomationState.lead_id == lead_id,
                        LeadAutomationState.tenant_id == organization_id,
                    )
                )
                result = await self.db.execute(stmt)
                las = result.scalar_one_or_none()
                if las is None:
                    # No automation state = no consent configured = fail closed
                    return {
                        "has_explicit_opt_in": False,
                        "has_opt_out": True,
                        "is_dnd": True,
                        "source": "missing_automation_state",
                        "fail_closed": True,
                    }
                return {
                    "has_explicit_opt_in": getattr(las, "has_explicit_opt_in", False),
                    "has_opt_out": getattr(las, "has_opt_out", False),
                    "is_dnd": getattr(las, "is_dnd_active", False),
                    "automation_disabled": getattr(las, "automation_disabled", False),
                    "automation_disabled_reason": getattr(las, "automation_disabled_reason", None),
                    "source": "lead_automation_state",
                }
        except Exception as exc:
            logger.warning(f"[CONTEXT_BUILDER] Consent load error lead={lead_id}: {exc}")
            # Fail closed — no consent = no action
            return {
                "has_explicit_opt_in": False,
                "has_opt_out": True,
                "is_dnd": True,
                "source": "error_fail_closed",
                "error": str(exc),
            }

    async def _load_qualification(self, lead_id: str, organization_id: str) -> Optional[Dict[str, Any]]:
        """Loads latest qualification profile."""
        try:
            async with self.db.begin_nested():
                try:
                    from app.models.agent_models import QualificationProfile
                except ImportError:
                    from app.models.qualification_models import QualificationProfile

                stmt = (
                    select(QualificationProfile)
                    .where(and_(
                        QualificationProfile.lead_id == lead_id,
                        QualificationProfile.organization_id == organization_id,
                    ))
                    .order_by(desc(getattr(QualificationProfile, "created_at", QualificationProfile.id)))
                    .limit(1)
                )
                result = await self.db.execute(stmt)
                qp = result.scalar_one_or_none()
                if qp is None:
                    return None
                return {
                    "score": getattr(qp, "score", getattr(qp, "completion_pct", None)),
                    "tier": getattr(qp, "tier", None),
                    "qualified": getattr(qp, "is_qualified", False),
                    "qualification_at": str(getattr(qp, "qualified_at", getattr(qp, "created_at", ""))),
                }
        except Exception as exc:
            logger.warning(f"[CONTEXT_BUILDER] Qualification load error lead={lead_id}: {exc}")
            return None

    async def _load_property_shortlist(self, lead_id: str, organization_id: str) -> List[Dict[str, Any]]:
        """Loads latest property shortlist from recommendation engine."""
        try:
            async with self.db.begin_nested():
                from app.models.recommendation_models import Recommendation, RecommendationItem
                stmt = (
                    select(RecommendationItem)
                    .join(Recommendation, RecommendationItem.recommendation_id == Recommendation.id)
                    .where(and_(
                        Recommendation.lead_id == lead_id,
                        Recommendation.organization_id == organization_id,
                    ))
                    .order_by(desc(RecommendationItem.match_score))
                    .limit(5)
                )
                result = await self.db.execute(stmt)
                items = result.scalars().all()
                if items:
                    return [
                        {
                            "property_id": str(getattr(r, "property_id", "")),
                            "score": getattr(r, "match_score", None),
                            "match_reasons": [getattr(r, "recommendation_type", "BEST_OVERALL")],
                        }
                        for r in items
                    ]
                return []
        except Exception as exc:
            logger.warning(f"[CONTEXT_BUILDER] Property shortlist load error lead={lead_id}: {exc}")
            return []

    async def _load_recent_conversation(self, lead_id: str, organization_id: str) -> List[Dict[str, Any]]:
        """Loads recent conversation history safely with savepoint protection."""
        try:
            async with self.db.begin_nested():
                from app.models.communication_models import ChannelMessage
                stmt = (
                    select(
                        ChannelMessage.direction,
                        ChannelMessage.channel,
                        ChannelMessage.content,
                        ChannelMessage.created_at,
                    )
                    .where(ChannelMessage.lead_id == str(lead_id))
                    .order_by(desc(ChannelMessage.created_at))
                    .limit(10)
                )
                result = await self.db.execute(stmt)
                rows = result.all()
                return [
                    {
                        "direction": r[0] or "",
                        "channel": r[1] or "",
                        "content_preview": (r[2] or "")[:200],
                        "at": str(r[3] or ""),
                    }
                    for r in rows
                ]
        except Exception as exc:
            logger.warning(f"[CONTEXT_BUILDER] Conversation load error lead={lead_id}: {exc}")
            return []

    async def _load_current_deal(self, lead_id: str, organization_id: str) -> Optional[Dict[str, Any]]:
        """Loads active deal state if exists."""
        try:
            async with self.db.begin_nested():
                import uuid as _uuid
                from app.models.deal_models import Deal

                org_val = _uuid.UUID(str(organization_id)) if isinstance(organization_id, str) and len(str(organization_id)) == 36 else organization_id
                lead_val = _uuid.UUID(str(lead_id)) if isinstance(lead_id, str) and len(str(lead_id)) == 36 else lead_id

                stmt = (
                    select(Deal)
                    .where(and_(
                        Deal.lead_id == lead_val,
                        Deal.organization_id == org_val,
                    ))
                    .order_by(desc(Deal.created_at))
                    .limit(1)
                )
                result = await self.db.execute(stmt)
                deal = result.scalar_one_or_none()
                if deal is None:
                    return None
                return {
                    "deal_id": str(getattr(deal, "id", "")),
                    "status": getattr(deal, "status", ""),
                    "stage": getattr(deal, "current_stage", getattr(deal, "stage", "")),
                    "value": getattr(deal, "agreed_price", getattr(deal, "offer_price", getattr(deal, "value", None))),
                }
        except Exception as exc:
            logger.warning(f"[CONTEXT_BUILDER] Deal load error lead={lead_id}: {exc}")
            return None
