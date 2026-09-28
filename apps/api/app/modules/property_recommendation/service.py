"""
Part 21.3 — Property Recommendation Service Orchestrator
=========================================================
End-to-End Orchestrator Pipeline:
  Lead ID + Prospect Intelligence
        ↓
  Requirement Normalizer
        ↓
  Tenant Candidate Retrieval (SQL)
        ↓
  Hard Constraint Filtering
        ↓
  8-Dimensional Compatibility Scoring (v1.0-property-match)
        ↓
  Semantic & Vector Reranking (pgvector)
        ↓
  Diversity Reranker & Role Tagging
        ↓
  Grounded Explanation & Next Best Action Synthesis
        ↓
  Persistence, Smart Caching & Observability Metrics
"""
import time
import uuid
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.models.lead import Lead
from app.models.property_models import PropertyListing
from app.models.prospect_intelligence_models import ProspectIntelligence
from app.models.recommendation_models import (
    Recommendation, RecommendationItem, RecommendationScore,
    RecommendationExplanation, RecommendationFeedback
)
from app.modules.property_recommendation.dto import (
    PropertyRecommendationRequestDTO, PropertyRecommendationResponseDTO,
    PropertyRecommendationItemDTO, ScoreBreakdownDTO, RequirementCoverageDTO,
    PropertyComparisonRequestDTO, PropertyComparisonResponseDTO,
    SimulationRequestDTO, ReverseMatchingResponseDTO, RecommendationFeedbackDTO
)
from app.modules.property_recommendation.requirement_normalizer import RequirementNormalizer
from app.modules.property_recommendation.candidate_retriever import CandidateRetrievalService
from app.modules.property_recommendation.hard_filter import HardConstraintEngine
from app.modules.property_recommendation.compatibility_scorer import (
    CompatibilityScorer, SCORING_MODEL_VERSION
)
from app.modules.property_recommendation.semantic_matcher import SemanticMatcher
from app.modules.property_recommendation.ranking_engine import RankingEngine
from app.modules.property_recommendation.explanation_engine import ExplanationEngine
from app.modules.property_recommendation.recommendation_cache import (
    RecommendationCacheService, compute_recommendation_cache_key
)
from app.modules.property_recommendation.metrics import (
    PROPERTY_RECOMMENDATION_REQUESTS_TOTAL,
    PROPERTY_RECOMMENDATION_GENERATION_DURATION,
    PROPERTY_RECOMMENDATION_NO_MATCH_TOTAL,
    PROPERTY_RECOMMENDATION_ERRORS_TOTAL,
    mask_org_id
)

logger = logging.getLogger(__name__)


class PropertyRecommendationService:
    """
    Enterprise AI Property Recommendation and Matching Engine.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.retriever = CandidateRetrievalService(db)
        self.hard_filter = HardConstraintEngine()
        self.scorer = CompatibilityScorer()
        self.semantic_matcher = SemanticMatcher(db)
        self.ranking_engine = RankingEngine()
        self.explanation_engine = ExplanationEngine()

    async def generate_recommendations(
        self,
        dto: PropertyRecommendationRequestDTO,
        organization_id: str,
        broker_id: Optional[str] = None,
        force_refresh: bool = False,
    ) -> PropertyRecommendationResponseDTO:
        """
        Executes end-to-end property recommendation pipeline.
        """
        start_time = time.time()
        org_hash = mask_org_id(organization_id)
        PROPERTY_RECOMMENDATION_REQUESTS_TOTAL.labels(
            org_hash=org_hash, trigger_type="refresh" if force_refresh else "generate"
        ).inc()

        logger.info(f"[PROPERTY_REC] Generating recommendations for Lead {dto.lead_id} (Org: {organization_id})")

        # ── 1. Fetch Lead (Strict Multi-Tenant Check) ─────────────────────────
        lead_uuid = (
            uuid.UUID(dto.lead_id)
            if isinstance(dto.lead_id, str) and len(dto.lead_id) == 36
            else dto.lead_id
        )
        broker_uuid = (
            uuid.UUID(organization_id)
            if isinstance(organization_id, str) and len(organization_id) == 36
            else organization_id
        )

        if isinstance(broker_uuid, uuid.UUID):
            stmt_lead = select(Lead).where(
                and_(
                    Lead.id == lead_uuid,
                    or_(
                        Lead.organization_id == broker_uuid,
                        Lead.broker_id == broker_uuid,
                    ),
                    Lead.deleted_at.is_(None)
                )
            )
        else:
            stmt_lead = select(Lead).where(Lead.id == lead_uuid, Lead.deleted_at.is_(None))
        res_lead = await self.db.execute(stmt_lead)
        lead = res_lead.scalars().first()
        if not lead:
            PROPERTY_RECOMMENDATION_ERRORS_TOTAL.labels(org_hash=org_hash, error_type="lead_not_found").inc()
            raise ValueError(f"Lead '{dto.lead_id}' not found in organization '{organization_id}'")

        # ── 2. Fetch Prospect Intelligence Profile ────────────────────────────
        stmt_intel = select(ProspectIntelligence).where(
            and_(
                ProspectIntelligence.lead_id == str(dto.lead_id),
                ProspectIntelligence.organization_id == organization_id,
            )
        )
        res_intel = await self.db.execute(stmt_intel)
        intelligence = res_intel.scalars().first()

        # ── 3. Normalize Requirements ─────────────────────────────────────────
        requirements = RequirementNormalizer.normalize(
            lead=lead,
            intelligence=intelligence,
            override_budget=dto.override_budget,
            override_currency=dto.override_currency,
        )

        # ── 4. Retrieve Candidate Listings from Verified Tenant DB ────────────
        raw_candidates, inv_hash = await self.retriever.retrieve_candidates(
            organization_id=organization_id,
            requirements=requirements,
            limit=dto.top_k * 4,
            filter_overpriced=dto.filter_overpriced,
        )

        # Check Cache if not force_refresh
        intel_hash = intelligence.content_hash if intelligence and intelligence.content_hash else "nohash"
        cache_key = compute_recommendation_cache_key(
            organization_id=organization_id,
            lead_id=str(dto.lead_id),
            intel_hash=intel_hash,
            inventory_hash=inv_hash,
            scoring_version=SCORING_MODEL_VERSION,
            top_k=dto.top_k,
        )

        if not force_refresh:
            cached_resp = RecommendationCacheService.get(organization_id, cache_key)
            if cached_resp:
                logger.info(f"[PROPERTY_REC] Returning cached recommendations for lead {dto.lead_id}")
                return cached_resp

        # ── 5. Hard Constraint Filtering ─────────────────────────────────────
        valid_candidates, rejected_log = self.hard_filter.filter_candidates(
            candidates=raw_candidates,
            requirements=requirements,
            flexibility_pct=10.0,
        )

        # ── 6. 8-Dimensional Compatibility Scoring ───────────────────────────
        eval_candidates = valid_candidates if valid_candidates else raw_candidates
        scored_items: List[Dict[str, Any]] = []

        if eval_candidates:
            # Semantic scores
            semantic_map = await self.semantic_matcher.calculate_semantic_scores(
                organization_id=organization_id,
                candidates=eval_candidates,
                requirements=requirements,
            )

            for prop in eval_candidates:
                score, breakdown = self.scorer.calculate_score(prop, requirements)
                # Blend with semantic score if available
                sem_score = semantic_map.get(str(prop.id), 80.0)
                blended_score = round(min(100.0, max(0.0, (score * 0.90) + (sem_score * 0.10))), 1)

                scored_items.append({
                    "property": prop,
                    "match_score": blended_score,
                    "breakdown": breakdown,
                    "semantic_score": sem_score,
                })

        # ── 7. Ranking Engine & Role Assignment ───────────────────────────────
        ranked_items = self.ranking_engine.rerank_and_tag(scored_items, top_k=dto.top_k)

        if not ranked_items:
            PROPERTY_RECOMMENDATION_NO_MATCH_TOTAL.labels(org_hash=org_hash).inc()

        # ── 8. Grounded Explanations & Next Best Action Synthesis ─────────────
        final_item_dtos: List[PropertyRecommendationItemDTO] = []
        for item in ranked_items:
            prop: PropertyListing = item["property"]
            score: float = item["match_score"]
            breakdown: ScoreBreakdownDTO = item["breakdown"]
            rec_type: str = item.get("recommendation_type", "BEST_OVERALL")
            rank_pos: int = item.get("rank_position", 1)

            exp = self.explanation_engine.build_explanation(
                prop=prop,
                requirements=requirements,
                score=score,
                breakdown=breakdown,
                rec_type=rec_type,
            )

            prop_curr = (getattr(prop, "currency_code", None) or getattr(prop, "currency", "AED")).upper()
            item_dto = PropertyRecommendationItemDTO(
                property_id=str(prop.id),
                rank_position=rank_pos,
                recommendation_type=rec_type,
                match_score=score,
                confidence=1.0,
                title=prop.title or f"{prop.property_type.title()} in {prop.city or 'Dubai'}",
                price=float(prop.price or 0.0),
                currency=prop_curr,
                normalized_price_aed=float(prop.price or 0.0),
                built_up_area_sqft=float(getattr(prop, "built_up_area_sqft", None) or getattr(prop, "area_value", 0.0) or 0.0),
                bedrooms=int(getattr(prop, "bedrooms", 1) or 1),
                bathrooms=int(getattr(prop, "bathrooms", 1) or 1),
                city=prop.city,
                locality=prop.locality,
                project_name=prop.project_name,
                building_name=prop.building_name,
                unit_number=prop.unit_number,
                amenities=prop.amenities or [],
                status=prop.status or "available",
                score_breakdown=breakdown,
                requirement_coverage=exp["requirement_coverage"],
                why_matches=exp["why_matches"],
                trade_offs=exp["trade_offs"] if dto.include_tradeoffs else [],
                agent_talking_points=exp["agent_talking_points"] if dto.include_tradeoffs else [],
                suggested_next_action=exp["suggested_next_action"],
                evidence_references={
                    "scoring_version": SCORING_MODEL_VERSION,
                    "evaluated_at": datetime.now(timezone.utc).isoformat(),
                    "inventory_verified": True,
                },
            )
            final_item_dtos.append(item_dto)

        # ── 9. DB Persistence ─────────────────────────────────────────────────
        rec_id = str(uuid.uuid4())
        rec_session = Recommendation(
            id=rec_id,
            lead_id=str(dto.lead_id),
            broker_id=str(broker_id or lead.broker_id),
            organization_id=organization_id,
            buyer_profile_version="v1.0",
            total_candidates_retrieved=len(raw_candidates),
            filtered_candidates_count=len(valid_candidates),
            recommendation_mode="hybrid_matching",
            active_model_version=SCORING_MODEL_VERSION,
        )
        self.db.add(rec_session)

        # Persist top recommendation items
        for item_dto in final_item_dtos:
            db_item = RecommendationItem(
                id=str(uuid.uuid4()),
                recommendation_id=rec_id,
                property_id=item_dto.property_id,
                rank_position=item_dto.rank_position,
                recommendation_type=item_dto.recommendation_type,
                match_score=item_dto.match_score,
                conversion_relevance_score=round(item_dto.match_score * 0.95, 1),
                commercial_priority_score=round(item_dto.match_score * 0.90, 1),
                recommendation_confidence=1.0,
                inventory_verified_at=datetime.now(timezone.utc),
            )
            self.db.add(db_item)

        await self.db.commit()

        duration_ms = int((time.time() - start_time) * 1000)
        PROPERTY_RECOMMENDATION_GENERATION_DURATION.labels(
            org_hash=org_hash, scoring_version=SCORING_MODEL_VERSION
        ).observe(time.time() - start_time)

        response = PropertyRecommendationResponseDTO(
            recommendation_id=rec_id,
            lead_id=str(dto.lead_id),
            organization_id=organization_id,
            scoring_version=SCORING_MODEL_VERSION,
            total_candidates_retrieved=len(raw_candidates),
            filtered_candidates_count=len(valid_candidates),
            recommendation_mode="hybrid_matching",
            execution_duration_ms=duration_ms,
            items=final_item_dtos,
        )

        # Save in Cache
        RecommendationCacheService.set(organization_id, cache_key, response)

        logger.info(
            f"[PROPERTY_REC] Successfully generated {len(final_item_dtos)} recommendations for Lead "
            f"'{dto.lead_id}' in {duration_ms}ms (Session: {rec_id})"
        )

        return response

    async def compare_properties(
        self,
        organization_id: str,
        dto: PropertyComparisonRequestDTO,
    ) -> PropertyComparisonResponseDTO:
        """
        Generates structured side-by-side comparison for target properties within tenant scope.
        """
        p_uuids = []
        for pid in dto.property_ids:
            try:
                p_uuids.append(uuid.UUID(str(pid)))
            except Exception:
                p_uuids.append(pid)

        broker_uuid = (
            uuid.UUID(organization_id)
            if isinstance(organization_id, str) and len(organization_id) == 36
            else organization_id
        )

        stmt = select(PropertyListing).where(
            and_(
                PropertyListing.id.in_(p_uuids),
                PropertyListing.broker_id == broker_uuid,
                PropertyListing.deleted_at.is_(None),
            )
        )
        res = await self.db.execute(stmt)
        listings = list(res.scalars().all())

        comparison_matrix = []
        for prop in listings:
            curr = (getattr(prop, "currency_code", None) or getattr(prop, "currency", "AED")).upper()
            comparison_matrix.append({
                "property_id": str(prop.id),
                "title": prop.title,
                "price": prop.price,
                "currency": curr,
                "built_up_area_sqft": getattr(prop, "built_up_area_sqft", None) or getattr(prop, "area_value", 0.0),
                "bedrooms": prop.bedrooms,
                "bathrooms": prop.bathrooms,
                "city": prop.city,
                "locality": prop.locality,
                "project_name": prop.project_name,
                "amenities": prop.amenities or [],
                "estimated_annual_roi_yield_pct": prop.estimated_annual_roi_yield_pct or 6.5,
                "status": prop.status,
            })

        differences = []
        if len(listings) >= 2:
            p1, p2 = listings[0], listings[1]
            diff_price = abs(p1.price - p2.price)
            differences.append(f"Price difference: {diff_price:,.0f}")
            if p1.bedrooms != p2.bedrooms:
                differences.append(f"Bedroom variation: {p1.bedrooms} BHK vs {p2.bedrooms} BHK")

        return PropertyComparisonResponseDTO(
            lead_id=dto.lead_id,
            compared_count=len(listings),
            properties=comparison_matrix,
            key_differences=differences,
        )

    async def simulate_recommendations(
        self,
        organization_id: str,
        dto: SimulationRequestDTO,
    ) -> PropertyRecommendationResponseDTO:
        """
        Simulates recommendations under shifted conditions (e.g. +10% budget).
        """
        # Fetch lead
        lead_uuid = uuid.UUID(dto.lead_id) if isinstance(dto.lead_id, str) and len(dto.lead_id) == 36 else dto.lead_id
        stmt = select(Lead).where(Lead.id == lead_uuid)
        res = await self.db.execute(stmt)
        lead = res.scalars().first()
        if not lead:
            raise ValueError(f"Lead '{dto.lead_id}' not found.")

        base_budget = float(lead.budget_max or lead.budget_min or 2000000.0)
        sim_budget = base_budget * (1.0 + (dto.budget_delta_pct / 100.0))

        req_dto = PropertyRecommendationRequestDTO(
            lead_id=dto.lead_id,
            top_k=5,
            override_budget=sim_budget,
        )
        return await self.generate_recommendations(req_dto, organization_id=organization_id, force_refresh=True)

    async def reverse_match_leads(
        self,
        organization_id: str,
        property_id: str,
        limit: int = 10,
    ) -> ReverseMatchingResponseDTO:
        """
        Reverse Matching: identifies qualified buyer leads in the CRM most likely to purchase this property.
        """
        broker_uuid = uuid.UUID(organization_id) if isinstance(organization_id, str) and len(organization_id) == 36 else organization_id
        prop_uuid = uuid.UUID(property_id) if isinstance(property_id, str) and len(property_id) == 36 else property_id

        # Verify property belongs to tenant
        stmt_p = select(PropertyListing).where(
            and_(
                PropertyListing.id == prop_uuid,
                PropertyListing.broker_id == broker_uuid,
                PropertyListing.deleted_at.is_(None),
            )
        )
        res_p = await self.db.execute(stmt_p)
        prop = res_p.scalars().first()
        if not prop:
            raise ValueError(f"Property '{property_id}' not found in tenant inventory.")

        # Find active qualified leads in tenant
        stmt_leads = select(Lead).where(
            and_(
                Lead.broker_id == broker_uuid,
                Lead.deleted_at.is_(None),
            )
        ).limit(limit * 3)
        res_leads = await self.db.execute(stmt_leads)
        leads = res_leads.scalars().all()

        matching_leads = []
        for lead in leads:
            req = RequirementNormalizer.normalize(lead=lead)
            score, breakdown = self.scorer.calculate_score(prop, req)
            if score >= 60.0:
                matching_leads.append({
                    "lead_id": str(lead.id),
                    "name": lead.name,
                    "phone": lead.phone,
                    "match_score": score,
                    "budget_max": lead.budget_max,
                    "preferred_property_type": lead.property_type,
                    "status": lead.status,
                })

        matching_leads.sort(key=lambda x: x["match_score"], reverse=True)

        return ReverseMatchingResponseDTO(
            property_id=property_id,
            total_qualified_leads_evaluated=len(leads),
            matching_leads=matching_leads[:limit],
        )

    async def record_feedback(
        self,
        organization_id: str,
        recommendation_id: str,
        lead_id: str,
        dto: RecommendationFeedbackDTO,
    ) -> Dict[str, Any]:
        """
        Records broker or customer feedback on a recommendation.
        """
        feedback = RecommendationFeedback(
            id=str(uuid.uuid4()),
            recommendation_id=recommendation_id,
            property_id=dto.property_id,
            lead_id=lead_id,
            action=dto.action,
            feedback_reason=dto.feedback_reason or dto.override_comment,
            signal_type="EXPLICIT",
        )
        self.db.add(feedback)
        await self.db.commit()

        return {
            "status": "success",
            "message": f"Feedback '{dto.action}' recorded for property {dto.property_id}",
            "recommendation_id": recommendation_id,
        }
