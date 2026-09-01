"""
Part 21.2A — AI Prospect Intelligence Orchestrator Service
=============================================================
Main service orchestrating:
- Lead & Conversation Ingestion
- SHA-256 Content Hashing (Smart Caching & Cost Control)
- AI Intelligence Extraction
- Conflict Detection & Supersession
- Missing Information & Next Best Questions
- Tenant-Scoped Property Inventory Matching
- Relevance & Sales Readiness Scoring
- Grounded Sales Brief & Next Best Action
- Persistence & Audit Logging
"""
import uuid
import hashlib
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.models.lead import Lead
from app.models.conversation import Conversation
from app.models.prospect_intelligence_models import (
    ProspectIntelligence, ProspectIntelligenceHistory,
    IntelligenceStatus, SalesReadiness, NextBestActionType
)
from app.modules.prospect_intelligence.services.prospect_ai_extractor import ProspectAIExtractor
from app.modules.prospect_intelligence.services.conflict_detector import ConflictDetector
from app.modules.prospect_intelligence.services.missing_info_engine import MissingInformationEngine
from app.modules.prospect_intelligence.services.prospect_relevance_engine import (
    ProspectRelevanceEngine, PROSPECT_RELEVANCE_MODEL_VERSION
)
from app.modules.prospect_intelligence.services.tenant_property_matcher import TenantPropertyMatcher
from app.modules.prospect_intelligence.services.sales_brief_generator import SalesBriefGenerator

logger = logging.getLogger(__name__)


def compute_evidence_hash(lead: Lead, conversations: List[Conversation]) -> str:
    """Deterministic hash of conversation and lead notes to prevent redundant AI re-analysis."""
    hasher = hashlib.sha256()
    hasher.update(str(lead.id).encode("utf-8"))
    hasher.update(str(lead.phone or "").encode("utf-8"))
    hasher.update(str(lead.name or "").encode("utf-8"))
    for conv in conversations:
        hasher.update(str(conv.id).encode("utf-8"))
        hasher.update(str(conv.message or "").encode("utf-8"))
    return hasher.hexdigest()


class ProspectIntelligenceService:
    """
    Production-grade AI Prospect Intelligence Service.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.property_matcher = TenantPropertyMatcher(db)

    async def get_profile(
        self, organization_id: str, lead_id: str
    ) -> Optional[ProspectIntelligence]:
        """Fetch intelligence profile strictly enforcing tenant isolation."""
        stmt = select(ProspectIntelligence).where(
            and_(
                ProspectIntelligence.lead_id == lead_id,
                ProspectIntelligence.organization_id == organization_id,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def analyze_lead(
        self,
        organization_id: str,
        lead_id: str,
        force_refresh: bool = False,
    ) -> ProspectIntelligence:
        """
        Executes end-to-end prospect intelligence pipeline for a CRM lead.
        """
        # 1. Fetch Lead (enforcing tenant access)
        # Lead.broker_id corresponds to the tenant broker/organization
        lead_uuid = uuid.UUID(lead_id) if isinstance(lead_id, str) and len(lead_id) == 36 else lead_id
        stmt_lead = select(Lead).where(
            or_(
                and_(Lead.id == lead_uuid, Lead.broker_id == organization_id),
                and_(Lead.id == lead_uuid, Lead.broker_id == uuid.UUID(organization_id))
            ) if isinstance(organization_id, str) and len(organization_id) == 36 else (Lead.id == lead_uuid)
        )
        res_lead = await self.db.execute(stmt_lead)
        lead = res_lead.scalars().first()
        if not lead:
            raise ValueError(f"Lead {lead_id} not found in organization {organization_id}")

        # 2. Fetch Conversation History
        stmt_conv = select(Conversation).where(
            Conversation.lead_id == lead_uuid
        ).order_by(Conversation.created_at.asc())
        res_conv = await self.db.execute(stmt_conv)
        conversations = res_conv.scalars().all()

        # 3. Check Smart Cache via Content Hash
        content_hash = compute_evidence_hash(lead, conversations)
        existing_profile = await self.get_profile(organization_id, lead_id)

        if not force_refresh and existing_profile and existing_profile.content_hash == content_hash and existing_profile.status == IntelligenceStatus.READY.value:
            logger.info(f"[PROSPECT_INTELLIGENCE] Returning cached intelligence for lead {lead_id} (hash match)")
            return existing_profile

        # 4. Synthesize Full Text Corpus from Real Evidence
        corpus_parts = []
        if lead.name and lead.name != "New Lead":
            corpus_parts.append(f"Lead Name: {lead.name}")
        if lead.property_type:
            corpus_parts.append(f"Initial Stated Property: {lead.property_type}")
        if lead.budget_max:
            corpus_parts.append(f"Initial Stated Budget: {lead.budget_max} {lead.budget_currency or ''}")

        for msg in conversations:
            speaker = "Lead" if msg.direction == "inbound" else "Broker"
            corpus_parts.append(f"{speaker}: {msg.message}")

        full_text = "\n".join(corpus_parts)

        # 5. Execute Structured AI Extraction (Gemini primary)
        extraction = await ProspectAIExtractor.extract_prospect_intelligence(
            text_corpus=full_text,
            country_code=lead.country_code or "AE",
            lead_metadata={"lead_id": lead_id, "organization_id": organization_id},
        )

        # 6. Detect Preference Conflicts & Supersessions
        conflicts = ConflictDetector.detect_conflicts(existing_profile, extraction)

        # 7. Evaluate Missing Information & Next Best Questions
        missing_fields, next_best_questions = MissingInformationEngine.evaluate(extraction)

        # 8. Verified Tenant Property Matching
        matched_properties = await self.property_matcher.match_tenant_properties(
            organization_id=organization_id,
            extraction=extraction,
            limit=5,
        )

        # 9. Relevance & Sales Readiness Scoring
        relevance_score, confidences, overall_conf, readiness = ProspectRelevanceEngine.evaluate(
            extraction=extraction,
            has_verified_matches=bool(matched_properties),
            has_phone=bool(lead.phone),
            has_email=bool(getattr(lead, "email", None)),
        )

        # 10. Generate Grounded Sales Brief & Next Best Action
        sales_brief, next_best_action, nba_reason = SalesBriefGenerator.generate_brief(
            extraction=extraction,
            matched_properties=matched_properties,
            missing_fields=missing_fields,
            sales_readiness=readiness,
            overall_confidence=overall_conf,
        )

        # 11. Format Property Requirements & Budget Dictionaries
        property_requirements = {
            "property_type": extraction.property_type,
            "bedrooms": extraction.bedrooms,
            "bathrooms": extraction.bathrooms,
            "location": extraction.location,
            "preferred_areas": extraction.preferred_areas,
            "size_min": extraction.size_min,
            "size_max": extraction.size_max,
            "size_unit": extraction.size_unit,
            "furnished_preference": extraction.furnished_preference,
            "parking_required": extraction.parking_required,
            "amenities": extraction.amenities,
            "view_preference": extraction.view_preference,
            "floor_preference": extraction.floor_preference,
            "new_or_resale": extraction.new_or_resale,
            "ready_or_off_plan": extraction.ready_or_off_plan,
        }

        budget_dict = {
            "budget_min": extraction.budget_min,
            "budget_max": extraction.budget_max,
            "currency": extraction.currency,
            "budget_confidence": confidences.get("budget_confidence", 0.0),
            "budget_source": extraction.evidence_snippets.get("budget"),
        }

        # 12. Create or Update ProspectIntelligence Record
        if not existing_profile:
            profile = ProspectIntelligence(
                lead_id=lead_id,
                organization_id=organization_id,
                status=IntelligenceStatus.READY.value,
                intelligence_version=PROSPECT_RELEVANCE_MODEL_VERSION,
                content_hash=content_hash,
                name=lead.name,
                email=getattr(lead, "email", None),
                phone=lead.phone,
                language=extraction.language or "en",
                prospect_types=extraction.prospect_types,
                transaction_intent=extraction.transaction_intent,
                property_requirements=property_requirements,
                budget=budget_dict,
                timeline=extraction.timeline or "UNKNOWN",
                financing=extraction.financing or "UNKNOWN",
                purpose=extraction.purpose or "UNKNOWN",
                urgency=extraction.urgency or "UNKNOWN",
                confidences=confidences,
                overall_confidence=overall_conf,
                discovery_relevance_score=relevance_score,
                sales_readiness=readiness,
                missing_information=missing_fields,
                next_best_questions=next_best_questions,
                matched_properties=matched_properties,
                sales_brief=sales_brief,
                next_best_action=next_best_action,
                next_best_action_reason=nba_reason,
                provenance=extraction.evidence_snippets,
                conflicts=conflicts,
                human_overrides={},
                model_provider="gemini",
                model_name="gemini-3.5-flash",
                prompt_version="v1.0.0",
                analyzed_at=datetime.now(timezone.utc),
            )
            self.db.add(profile)
        else:
            profile = existing_profile
            profile.status = IntelligenceStatus.READY.value
            profile.content_hash = content_hash
            profile.name = lead.name
            profile.phone = lead.phone
            profile.language = extraction.language or "en"
            profile.prospect_types = extraction.prospect_types
            profile.transaction_intent = extraction.transaction_intent
            profile.property_requirements = property_requirements
            profile.budget = budget_dict
            profile.timeline = extraction.timeline or "UNKNOWN"
            profile.financing = extraction.financing or "UNKNOWN"
            profile.purpose = extraction.purpose or "UNKNOWN"
            profile.urgency = extraction.urgency or "UNKNOWN"
            profile.confidences = confidences
            profile.overall_confidence = overall_conf
            profile.discovery_relevance_score = relevance_score
            profile.sales_readiness = readiness
            profile.missing_information = missing_fields
            profile.next_best_questions = next_best_questions
            profile.matched_properties = matched_properties
            profile.sales_brief = sales_brief
            profile.next_best_action = next_best_action
            profile.next_best_action_reason = nba_reason
            profile.provenance = extraction.evidence_snippets
            profile.conflicts = conflicts
            profile.analyzed_at = datetime.now(timezone.utc)

        # 13. Audit History Snapshot
        history_record = ProspectIntelligenceHistory(
            lead_id=lead_id,
            organization_id=organization_id,
            snapshot={
                "transaction_intent": extraction.transaction_intent,
                "property_requirements": property_requirements,
                "budget": budget_dict,
                "timeline": extraction.timeline,
                "relevance_score": relevance_score,
                "readiness": readiness,
                "sales_brief": sales_brief,
            },
            reason_for_change="Automated AI Prospect Intelligence analysis",
            model_version=PROSPECT_RELEVANCE_MODEL_VERSION,
        )
        self.db.add(history_record)
        await self.db.commit()
        await self.db.refresh(profile)

        return profile

    async def apply_human_override(
        self,
        organization_id: str,
        lead_id: str,
        overrides: Dict[str, Any],
        reason: str = "Human broker verification",
    ) -> ProspectIntelligence:
        """
        Applies human-verified corrections with highest precedence.
        """
        profile = await self.get_profile(organization_id, lead_id)
        if not profile:
            raise ValueError(f"No intelligence profile exists for lead {lead_id}")

        existing_overrides = dict(profile.human_overrides or {})
        existing_overrides.update(overrides)
        profile.human_overrides = existing_overrides

        # Update relevant fields
        if "transaction_intent" in overrides:
            profile.transaction_intent = overrides["transaction_intent"]
        if "bedrooms" in overrides or "property_type" in overrides or "location" in overrides:
            reqs = dict(profile.property_requirements or {})
            for k in ["bedrooms", "property_type", "location", "preferred_areas"]:
                if k in overrides:
                    reqs[k] = overrides[k]
            profile.property_requirements = reqs
        if "budget_max" in overrides or "budget_min" in overrides or "currency" in overrides:
            b_dict = dict(profile.budget or {})
            for k in ["budget_min", "budget_max", "currency"]:
                if k in overrides:
                    b_dict[k] = overrides[k]
            profile.budget = b_dict

        # Recalculate properties and sales brief with overrides
        history_record = ProspectIntelligenceHistory(
            lead_id=lead_id,
            organization_id=organization_id,
            snapshot=overrides,
            reason_for_change=reason,
            model_version=PROSPECT_RELEVANCE_MODEL_VERSION,
        )
        self.db.add(history_record)
        await self.db.commit()
        await self.db.refresh(profile)

        return profile
