"""
Identity Resolution Service — Main Pipeline Orchestrator
=========================================================
Pipeline:
    lead_data → Candidate Search → Similarity Engine → Business Rules →
    Confidence Engine → Decision Engine → Identity Graph → DB + Events

Decisions:
    ≥ 0.95  → Auto Merge → IdentityLink + MergeCompleted event
    0.85-0.95 → Manual Review Queue → ManualReviewCreated event
    < 0.85  → New Identity → IdentityCreated event
"""
import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.identity_models import (
    Identity, IdentityLink, DuplicateCandidate, SimilarityScore, ManualReview
)
from app.modules.identity_resolution.candidate_search.candidate_finder import CandidateFinder
from app.modules.identity_resolution.similarity_engine.similarity_engine import SimilarityEngine
from app.modules.identity_resolution.matching_rules.rule_engine import RuleEngine
from app.modules.identity_resolution.confidence.confidence_engine import ConfidenceEngine
from app.modules.identity_resolution.decision_engine.decision_engine import DecisionEngine
from app.modules.identity_resolution.merge_engine.merge_executor import MergeExecutor
from app.modules.identity_resolution.merge_engine.merge_simulator import MergeSimulator
from app.modules.identity_resolution.merge_engine.merge_reverter import MergeReverter
from app.modules.identity_resolution.identity_graph.identity_graph import IdentityGraph
from app.modules.identity_resolution.manual_review.review_service import ReviewService
from app.modules.identity_resolution.events.event_publisher import IdentityEventPublisher
from app.modules.identity_resolution.events.identity_events import (
    IdentityCreated, DuplicateDetected, MergeSuggested,
    MergeCompleted, MergeReverted, ManualReviewCreated
)
from app.modules.identity_resolution.cache.identity_cache import IdentityCache

logger = logging.getLogger(__name__)


class IdentityResolutionService:
    """
    Enterprise Identity Resolution Pipeline Orchestrator.

    Responsibilities:
    - Orchestrate full pipeline from lead data to identity assignment
    - Manage auto-merge, manual review, and new identity creation
    - Delegate to specialized engines (similarity, confidence, decision, merge)
    - Publish domain events
    - Maintain audit trail
    """

    def __init__(self, db: AsyncSession, redis_client: Optional[Any] = None):
        self.db = db
        self.similarity_engine = SimilarityEngine()
        self.confidence_engine = ConfidenceEngine()
        self.decision_engine = DecisionEngine()
        self.rule_engine = RuleEngine()
        self.candidate_finder = CandidateFinder(db)
        self.identity_graph = IdentityGraph(db)
        self.merge_executor = MergeExecutor(db)
        self.merge_simulator = MergeSimulator()
        self.merge_reverter = MergeReverter(db)
        self.review_service = ReviewService(db)
        self.event_publisher = IdentityEventPublisher(redis_client)
        self.cache = IdentityCache(redis_client)

    async def resolve_lead(
        self,
        lead_data: Dict[str, Any],
        organization_id: str,
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Main entry point: resolve a lead's identity.

        Args:
            lead_data: Canonical lead dict (id, phone, email, name, whatsapp, source, etc.)
            organization_id: Tenant isolation key
            actor_id: Optional user who triggered this (null = system/event-driven)

        Returns:
            {
                "decision": "new_identity" | "auto_merge" | "manual_review",
                "identity_id": "...",
                "confidence": 0.94,
                "candidates_evaluated": 3,
                "processing_time_ms": 42,
            }
        """
        start_time = time.time()
        lead_id = str(lead_data.get("id") or "")
        logger.info(f"[IDENTITY_RESOLUTION] Resolving lead {lead_id} for org {organization_id}")

        # ── Step 1: Find candidate identities ────────────────────────────────
        candidates = await self.candidate_finder.find_candidates(lead_data, organization_id)
        logger.info(f"[IDENTITY_RESOLUTION] Found {len(candidates)} candidates for lead {lead_id}")

        # ── Step 2: Score each candidate ──────────────────────────────────────
        scored_candidates: List[tuple] = []
        for candidate in candidates:
            sim_result = self.similarity_engine.compute(lead_data, candidate)
            confidence = self.confidence_engine.compute(sim_result)
            scored_candidates.append((candidate, confidence, sim_result))

        # ── Step 3: Pick best match, apply decision engine ────────────────────
        if scored_candidates:
            scored_candidates.sort(key=lambda x: x[1], reverse=True)
            best_candidate, best_confidence, best_sim = scored_candidates[0]
        else:
            best_candidate, best_confidence, best_sim = None, 0.0, {}

        decision_result = self.decision_engine.decide_best(
            [(c, conf) for c, conf, _ in scored_candidates]
        )

        # ── Step 4: Apply business rules ─────────────────────────────────────
        if best_candidate:
            decision_result = self.rule_engine.apply(decision_result, lead_data, best_candidate)

        decision = decision_result["decision"]
        confidence = decision_result["confidence"]

        # ── Step 5: Execute decision ──────────────────────────────────────────
        result_identity_id: Optional[str] = None
        candidate_id: Optional[str] = None

        if decision == "new_identity" or not best_candidate:
            # Create new identity
            identity = await self.identity_graph.create_identity(lead_data, organization_id)
            result_identity_id = identity.id

            await self.event_publisher.publish(IdentityCreated(
                identity_id=identity.id,
                organization_id=organization_id,
                lead_id=lead_id,
                source=lead_data.get("source"),
                phone=lead_data.get("phone"),
                email=lead_data.get("email"),
                health_score=identity.health_score,
            ))

        elif decision == "auto_merge":
            # Persist candidate record
            candidate_db = await self._persist_candidate(
                lead_id, best_candidate["id"], organization_id,
                confidence, decision, best_sim
            )
            candidate_id = candidate_db.id

            # Link lead to existing identity
            await self.identity_graph.link_lead_to_identity(
                identity_id=best_candidate["id"],
                lead_data=lead_data,
                organization_id=organization_id,
                confidence=confidence,
                matched_fields=best_sim.get("matched_fields", []),
                link_method="auto_merge",
            )
            result_identity_id = best_candidate["id"]

            explanation = self.confidence_engine.build_explanation(best_sim, confidence, decision)

            await self.event_publisher.publish(DuplicateDetected(
                lead_id=lead_id,
                candidate_identity_id=best_candidate["id"],
                organization_id=organization_id,
                confidence=confidence,
                decision=decision,
                matched_fields=best_sim.get("matched_fields", []),
                reason=explanation,
            ))

            await self.event_publisher.publish(MergeCompleted(
                merge_operation_id=candidate_db.id,
                source_identity_id=lead_id,
                target_identity_id=best_candidate["id"],
                organization_id=organization_id,
                merge_type="auto",
                confidence=confidence,
                fields_merged=best_sim.get("matched_fields", []),
            ))

        elif decision == "manual_review":
            # Persist candidate, create manual review
            candidate_db = await self._persist_candidate(
                lead_id, best_candidate["id"], organization_id,
                confidence, "manual_review", best_sim
            )
            candidate_id = candidate_db.id

            explanation = self.confidence_engine.build_explanation(best_sim, confidence, decision)

            # Create new identity first (will link after review decision)
            identity = await self.identity_graph.create_identity(lead_data, organization_id)
            result_identity_id = identity.id

            # Create manual review item
            review = await self.review_service.create_review(
                candidate=candidate_db,
                ai_explanation=explanation,
                organization_id=organization_id,
            )

            await self.event_publisher.publish(ManualReviewCreated(
                review_id=review.id,
                lead_id=lead_id,
                candidate_identity_id=best_candidate["id"],
                organization_id=organization_id,
                confidence=confidence,
                ai_recommendation=review.ai_recommendation,
            ))

            await self.event_publisher.publish(MergeSuggested(
                lead_id=lead_id,
                candidate_identity_id=best_candidate["id"],
                organization_id=organization_id,
                confidence=confidence,
                review_id=review.id,
                ai_recommendation=review.ai_recommendation,
            ))

        await self.db.commit()

        processing_ms = round((time.time() - start_time) * 1000, 1)
        logger.info(
            f"[IDENTITY_RESOLUTION] Lead {lead_id} → {decision} "
            f"identity={result_identity_id} (conf={confidence:.2%}, {processing_ms}ms)"
        )

        return {
            "decision": decision,
            "identity_id": result_identity_id,
            "confidence": confidence,
            "candidates_evaluated": len(candidates),
            "candidate_id": candidate_id,
            "matched_fields": best_sim.get("matched_fields", []) if best_sim else [],
            "per_field_scores": best_sim.get("per_field_scores", {}) if best_sim else {},
            "algorithms_used": best_sim.get("algorithms_used", []) if best_sim else [],
            "reason": best_sim.get("reason", "") if best_sim else "",
            "processing_time_ms": processing_ms,
        }

    async def get_identity_profile(self, identity_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full identity profile including all linked leads."""
        cached = await self.cache.get_identity(identity_id)
        if cached:
            return cached

        result = await self.db.execute(select(Identity).where(Identity.id == identity_id))
        identity = result.scalar_one_or_none()
        if not identity:
            return None

        links_result = await self.db.execute(
            select(IdentityLink).where(
                IdentityLink.identity_id == identity_id,
                IdentityLink.is_active == True
            )
        )
        links = links_result.scalars().all()

        profile = {
            "id": identity.id,
            "organization_id": identity.organization_id,
            "primary_email": identity.primary_email,
            "primary_phone_e164": identity.primary_phone_e164,
            "primary_name": identity.primary_name,
            "primary_whatsapp": identity.primary_whatsapp,
            "primary_telegram": identity.primary_telegram,
            "location_profile": identity.location_profile,
            "financial_profile": identity.financial_profile,
            "health_score": identity.health_score,
            "completeness_score": identity.completeness_score,
            "verification_status": identity.verification_status,
            "first_source": identity.first_source,
            "lead_count": identity.lead_count,
            "is_merged": identity.is_merged,
            "merged_into_id": identity.merged_into_id,
            "first_seen_at": identity.first_seen_at.isoformat() if identity.first_seen_at else None,
            "linked_leads": [
                {"lead_id": l.lead_id, "source": l.source, "confidence": l.link_confidence}
                for l in links
            ],
        }

        await self.cache.set_identity(identity_id, profile)
        return profile

    async def simulate_merge(
        self,
        source_identity_id: str,
        target_identity_id: str,
        confidence: float = 0.90,
    ) -> Dict[str, Any]:
        """Dry-run merge simulation — no DB writes."""
        source_profile = await self.get_identity_profile(source_identity_id)
        target_profile = await self.get_identity_profile(target_identity_id)
        if not source_profile or not target_profile:
            raise ValueError("One or both identities not found.")
        return self.merge_simulator.simulate(source_profile, target_profile, confidence)

    async def undo_merge(
        self,
        merge_operation_id: str,
        undone_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Undo a completed merge operation."""
        result = await self.merge_reverter.undo_merge(merge_operation_id, undone_by)
        await self.event_publisher.publish(MergeReverted(
            merge_operation_id=merge_operation_id,
            source_identity_id=result["source_identity_id"],
            target_identity_id=result["target_identity_id"],
            organization_id="",  # Will be populated from MergeOperation in production
            undone_by=undone_by,
        ))
        return result

    async def _persist_candidate(
        self,
        lead_id: str,
        candidate_identity_id: str,
        organization_id: str,
        confidence: float,
        decision: str,
        sim_result: Dict[str, Any],
    ) -> DuplicateCandidate:
        """Persist a DuplicateCandidate record and its per-field SimilarityScore rows."""
        candidate = DuplicateCandidate(
            lead_id=lead_id,
            candidate_identity_id=candidate_identity_id,
            organization_id=organization_id,
            overall_confidence=confidence,
            decision=decision,
            matched_fields=sim_result.get("matched_fields", []),
            per_field_scores=sim_result.get("per_field_scores", {}),
            weights_used=sim_result.get("weights_used", {}),
            algorithms_used=sim_result.get("algorithms_used", []),
            reason=sim_result.get("reason", ""),
            status="pending",
        )
        self.db.add(candidate)
        await self.db.flush()

        # Persist per-field SimilarityScore rows
        for score_data in sim_result.get("similarity_scores", []):
            self.db.add(SimilarityScore(
                candidate_id=candidate.id,
                organization_id=organization_id,
                field_name=score_data["field_name"],
                value_a=score_data.get("value_a"),
                value_b=score_data.get("value_b"),
                score=score_data["score"],
                weight=score_data["weight"],
                algorithm=score_data["algorithm"],
                weighted_contribution=score_data["weighted_contribution"],
            ))

        return candidate
