"""
Part 21.2 — Discovery Candidate Service
=========================================
State machine and lifecycle manager for DiscoveryCandidate entities.

Lifecycle Transitions:
  DISCOVERED → EVIDENCE_VALIDATION → NORMALIZING → IDENTITY_MATCH →
  DUPLICATE | RELEVANT | IRRELEVANT → COMPLIANCE_REVIEW → REVIEW_REQUIRED | READY →
  IMPORTED | REJECTED | FAILED
"""
from __future__ import annotations
import uuid
import logging
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.discovery_models import (
    DiscoveryCandidate, CandidateStatus, ComplianceStatus
)
from app.models.acquisition_models import SourceAttribution, DuplicateMatchStatus
from app.models.lead import Lead
from app.modules.lead_acquisition.services.normalization_service import (
    normalize_phone, normalize_email, normalize_name, normalize_budget, normalize_currency
)
from app.modules.discovery.connectors.base_provider import DiscoveredRecord
from app.modules.discovery.service.evidence_signal_service import EvidenceSignalService
from app.modules.discovery.service.discovery_relevance_service import DiscoveryRelevanceService, DISCOVERY_MODEL_VERSION
from app.modules.discovery.service.discovery_duplicate_service import DiscoveryDuplicateService
from app.modules.discovery.service.discovery_compliance_service import DiscoveryComplianceService

logger = logging.getLogger(__name__)


class DiscoveryCandidateService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.evidence_service = EvidenceSignalService(db)
        self.duplicate_service = DiscoveryDuplicateService(db)

    async def create_candidate_from_record(
        self,
        organization_id: str,
        discovery_run_id: Optional[str],
        source_id: Optional[str],
        record: DiscoveredRecord,
    ) -> DiscoveryCandidate:
        """Create candidate entity and attach factual evidence records."""
        # 1. Normalize contact fields
        phone_e164, _ = normalize_phone(record.phone)
        email_norm, _ = normalize_email(record.email)
        name_norm = normalize_name(record.name)
        bmin_dec, _ = normalize_budget(record.budget_min, record.currency)
        bmax_dec, curr_norm = normalize_budget(record.budget_max, record.currency)

        contact_info = {
            "name": name_norm,
            "email": email_norm,
            "phone": record.phone,
            "phone_e164": phone_e164,
        }

        normalized_data = {
            "name": name_norm,
            "email": email_norm,
            "phone": phone_e164 or record.phone,
            "property_type": record.property_type,
            "transaction_type": record.transaction_type or "BUY",
            "lead_intent": record.lead_intent or "BUYER",
            "budget_min": float(bmin_dec) if bmin_dec is not None else None,
            "budget_max": float(bmax_dec) if bmax_dec is not None else None,
            "currency": curr_norm or record.currency,
            "city": record.city,
            "country": record.country,
            "timeline": record.timeline,
            "message": record.message,
        }

        candidate = DiscoveryCandidate(
            organization_id=organization_id,
            discovery_run_id=discovery_run_id,
            source_id=source_id,
            external_id=record.external_id,
            source_url=record.source_url,
            display_name=name_norm or (f"Prospect {phone_e164[-4:]}" if phone_e164 else "Discovered Prospect"),
            contact_information=contact_info,
            raw_reference=record.external_id,
            normalized_data=normalized_data,
            observed_at=record.observed_at,
            source_created_at=record.source_created_at,
            retrieved_at=datetime.now(timezone.utc),
            status=CandidateStatus.DISCOVERED,
            compliance_status=ComplianceStatus.UNKNOWN,
            duplicate_status="UNKNOWN",
            relevance_model_version=DISCOVERY_MODEL_VERSION,
        )
        self.db.add(candidate)
        await self.db.flush()

        # 2. Record Factual Evidence
        for ev in record.evidence_items:
            await self.evidence_service.record_evidence(
                organization_id=organization_id,
                candidate_id=candidate.id,
                source_id=source_id,
                field_name=ev.get("field_name", "provider_record"),
                value_reference=str(ev.get("value_reference", "")),
                source_timestamp=record.source_created_at,
                confidence=ev.get("confidence", 1.0),
                provenance=ev.get("provenance"),
            )

        # 3. Record Structured Signals
        for sig in record.signals:
            await self.evidence_service.record_signal(
                organization_id=organization_id,
                candidate_id=candidate.id,
                signal_type=sig.get("signal_type", "PROPERTY_INQUIRY"),
                source=sig.get("source", "provider"),
                observed_at=record.observed_at,
                strength=sig.get("strength", 1.0),
                confidence=sig.get("confidence", 1.0),
                signal_payload=sig.get("signal_payload"),
            )

        await self.db.flush()
        return candidate

    async def process_candidate_pipeline(
        self, organization_id: str, candidate: DiscoveryCandidate, campaign=None
    ) -> DiscoveryCandidate:
        """
        Execute full candidate qualification state machine:
          EVIDENCE_VALIDATION → NORMALIZING → IDENTITY_MATCH → RELEVANCE_EVALUATION → COMPLIANCE → READY
        """
        # Step 1: Evidence Validation
        candidate.status = CandidateStatus.EVIDENCE_VALIDATION
        evidence_list = await self.evidence_service.get_candidate_evidence(organization_id, candidate.id)
        if not evidence_list:
            candidate.status = CandidateStatus.REJECTED
            candidate.rejection_reason = "No factual source evidence found"
            await self.db.flush()
            return candidate

        # Step 2: Normalization
        candidate.status = CandidateStatus.NORMALIZING

        # Step 3: Identity & Duplicate Matching
        candidate.status = CandidateStatus.IDENTITY_MATCH
        dup_status, matched_lead_id, conflicts = await self.duplicate_service.check_duplicate(organization_id, candidate)
        candidate.duplicate_status = dup_status
        candidate.matched_lead_id = matched_lead_id

        if dup_status in (DuplicateMatchStatus.EXACT_MATCH, DuplicateMatchStatus.HIGH_CONFIDENCE_MATCH):
            candidate.status = CandidateStatus.DUPLICATE
            await self.db.flush()
            return candidate

        # Step 4: Relevance & Confidence Evaluation
        signals = await self.evidence_service.get_candidate_signals(organization_id, candidate.id)
        max_str = max([s.strength for s in signals], default=1.0)
        scores = DiscoveryRelevanceService.evaluate_candidate(
            candidate, campaign=campaign, signals_count=len(signals), max_signal_strength=max_str
        )

        candidate.evidence_confidence = scores["evidence_confidence"]
        candidate.identity_confidence = scores["identity_confidence"]
        candidate.intent_confidence = scores["intent_confidence"]
        candidate.freshness_score = scores["freshness_score"]
        candidate.relevance_score = scores["relevance_score"]

        # Step 5: Compliance Check
        comp_status, comp_reason = DiscoveryComplianceService.evaluate_compliance(
            candidate, country_code=campaign.country_code if campaign else None
        )
        candidate.compliance_status = comp_status

        # Step 6: Determine Final State
        threshold = campaign.intent_threshold if campaign else 0.70
        min_conf = campaign.minimum_confidence if campaign else 0.60

        if candidate.relevance_score < threshold:
            candidate.status = CandidateStatus.IRRELEVANT
        elif candidate.identity_confidence < min_conf:
            candidate.status = CandidateStatus.REVIEW_REQUIRED
            candidate.review_reason = "Low identity confidence — contact information incomplete"
        elif comp_status == ComplianceStatus.REVIEW_REQUIRED:
            candidate.status = CandidateStatus.REVIEW_REQUIRED
            candidate.review_reason = comp_reason
        elif comp_status == ComplianceStatus.BLOCKED:
            candidate.status = CandidateStatus.REJECTED
            candidate.rejection_reason = comp_reason or "Compliance blocked"
        else:
            candidate.status = CandidateStatus.READY

        await self.db.flush()
        return candidate

    async def import_candidate_as_lead(
        self,
        organization_id: str,
        candidate: DiscoveryCandidate,
        broker_uuid: uuid.UUID,
        override_name: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Lead:
        """
        Import a READY candidate as a canonical CRM Lead with complete attribution.
        """
        if candidate.status not in (CandidateStatus.READY, CandidateStatus.DUPLICATE, CandidateStatus.REVIEW_REQUIRED):
            raise ValueError(f"Cannot import candidate in status '{candidate.status}'. Must be READY or REVIEW_REQUIRED.")

        norm = candidate.normalized_data or {}
        contact = candidate.contact_information or {}

        phone = contact.get("phone_e164") or contact.get("phone") or norm.get("phone")
        if not phone:
            raise ValueError("Cannot create CRM Lead without a phone number.")

        final_name = override_name or candidate.display_name or norm.get("name") or "Discovered Lead"

        lead = Lead(
            broker_id=broker_uuid,
            phone=str(phone),
            name=final_name,
            source="manual",
            score="pending",
            property_type=norm.get("property_type"),
            transaction_type=norm.get("transaction_type", "BUY"),
            preferred_locations=[norm["city"]] if norm.get("city") else [],
            budget_min=int(norm["budget_min"]) if norm.get("budget_min") is not None else None,
            budget_max=int(norm["budget_max"]) if norm.get("budget_max") is not None else None,
            budget_currency=norm.get("currency"),
            country_code=norm.get("country"),
            status="pending",
            pipeline_stage="new",
        )
        self.db.add(lead)
        await self.db.flush()

        # Add Source Attribution
        attribution = SourceAttribution(
            organization_id=organization_id,
            lead_id=str(lead.id),
            source_id=candidate.source_id,
            channel="API",
            provider="discovery_engine",
            external_id=candidate.external_id,
            first_touch_at=candidate.observed_at or candidate.created_at,
            last_touch_at=datetime.now(timezone.utc),
        )
        self.db.add(attribution)

        candidate.canonical_lead_id = str(lead.id)
        candidate.status = CandidateStatus.IMPORTED
        await self.db.commit()
        await self.db.refresh(lead)
        logger.info(f"[DISCOVERY_CANDIDATE] Imported candidate {candidate.id} → Lead {lead.id}")
        return lead

    async def reject_candidate(self, candidate: DiscoveryCandidate, reason: str) -> DiscoveryCandidate:
        candidate.status = CandidateStatus.REJECTED
        candidate.rejection_reason = reason[:255]
        candidate.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        return candidate

    async def get_candidate(self, organization_id: str, candidate_id: str) -> Optional[DiscoveryCandidate]:
        stmt = select(DiscoveryCandidate).where(
            and_(DiscoveryCandidate.id == candidate_id, DiscoveryCandidate.organization_id == organization_id)
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def list_candidates(
        self,
        organization_id: str,
        run_id: Optional[str] = None,
        source_id: Optional[str] = None,
        status: Optional[str] = None,
        min_relevance: Optional[float] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[DiscoveryCandidate]:
        conditions = [DiscoveryCandidate.organization_id == organization_id]
        if run_id:
            conditions.append(DiscoveryCandidate.discovery_run_id == run_id)
        if source_id:
            conditions.append(DiscoveryCandidate.source_id == source_id)
        if status:
            conditions.append(DiscoveryCandidate.status == status)
        if min_relevance is not None:
            conditions.append(DiscoveryCandidate.relevance_score >= min_relevance)

        stmt = (
            select(DiscoveryCandidate)
            .where(and_(*conditions))
            .order_by(DiscoveryCandidate.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.db.execute(stmt)).scalars().all())
