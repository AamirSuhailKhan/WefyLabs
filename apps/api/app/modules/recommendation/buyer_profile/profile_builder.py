"""
Buyer Profile Builder & Synthesis Engine
========================================
Synthesizes explicit CRM fields, AI Lead Intelligence, conversation transcripts,
and notes into a unified canonical BuyerProfile entity with evidence tracking.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.lead import Lead
from app.models.lead_intelligence_models import LeadIntelligenceProfile
from app.models.recommendation_models import BuyerProfile, BuyerPreference, BuyerConstraint, BuyerPreferenceEvidence
from app.modules.recommendation.scoring.FX_converter import FXConverter

logger = logging.getLogger(__name__)

class BuyerProfileBuilder:
    """
    Constructs and persists canonical Buyer Profile objects.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.fx_converter = FXConverter()

    async def get_or_create_profile(self, lead_id: str, organization_id: str, broker_id: str) -> BuyerProfile:
        """
        Loads existing BuyerProfile or initializes a new profile from Lead entity.
        """
        stmt = select(BuyerProfile).where(BuyerProfile.lead_id == lead_id)
        result = await self.db.execute(stmt)
        profile = result.scalar_one_or_none()

        if profile:
            return profile

        # Fetch underlying Lead record
        lead_stmt = select(Lead).where(Lead.id == lead_id)
        lead_res = await self.db.execute(lead_stmt)
        lead = lead_res.scalar_one_or_none()

        if not lead:
            raise ValueError(f"Lead ID '{lead_id}' not found.")

        # Extract budget fields
        max_budget = float(lead.budget_max or lead.budget_min or 5000000)
        min_budget = float(lead.budget_min or 0)
        target_budget = (max_budget + min_budget) / 2.0 if min_budget > 0 else max_budget

        # Default Currency by Lead Location / Org
        currency = "AED"
        if lead.preferred_locations:
            loc_lower = [l.lower() for l in lead.preferred_locations]
            if any(l in loc_lower for l in ["indiranagar", "koramangala", "whitefield", "mumbai", "bangalore", "bengaluru"]):
                currency = "INR"

        profile = BuyerProfile(
            lead_id=str(lead.id),
            broker_id=str(lead.broker_id),
            organization_id=organization_id,
            country="India" if currency == "INR" else "UAE",
            currency=currency,
            target_budget=target_budget,
            max_budget=max_budget,
            min_budget=min_budget,
            budget_flexibility_pct=10.0,
            purchase_purpose="end_user" if lead.transaction_type == "buy" else "investment",
            property_types=[lead.property_type] if lead.property_type else ["apartment"],
            min_bedrooms=self._parse_min_beds(lead.property_type),
            max_bedrooms=self._parse_max_beds(lead.property_type),
            preferred_locations=lead.preferred_locations or [],
            possession_timeline=lead.timeline or "immediate",
            profile_completeness_pct=75.0,
            raw_extracted_features={
                "source": lead.source,
                "score": lead.score,
                "loan_status": lead.loan_status,
            }
        )

        self.db.add(profile)
        await self.db.commit()
        await self.db.refresh(profile)

        # Create default initial evidence
        await self._attach_evidence(
            profile_id=profile.id,
            preference_key="max_budget",
            source_type="crm_field",
            snippet=f"Lead budget_max: {max_budget} {currency}",
            confidence=1.0
        )

        return profile

    def _parse_min_beds(self, prop_type: Optional[str]) -> int:
        if not prop_type:
            return 1
        pt = prop_type.lower()
        if "1bhk" in pt: return 1
        if "2bhk" in pt: return 2
        if "3bhk" in pt: return 3
        if "villa" in pt: return 3
        return 1

    def _parse_max_beds(self, prop_type: Optional[str]) -> int:
        if not prop_type:
            return 4
        pt = prop_type.lower()
        if "1bhk" in pt: return 1
        if "2bhk" in pt: return 2
        if "3bhk" in pt: return 3
        if "villa" in pt: return 5
        return 4

    async def _attach_evidence(
        self, profile_id: str, preference_key: str, source_type: str, snippet: str, confidence: float
    ):
        evidence = BuyerPreferenceEvidence(
            buyer_profile_id=profile_id,
            preference_key=preference_key,
            source_type=source_type,
            snippet=snippet,
            confidence=confidence
        )
        self.db.add(evidence)
        await self.db.commit()
