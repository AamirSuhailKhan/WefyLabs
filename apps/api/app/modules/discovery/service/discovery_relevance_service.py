"""
Part 21.2 — Discovery Relevance Scoring Service
=================================================
Calculates the Discovery Relevance Score (0.0 – 1.0) for real estate prospects.

Model Version: "v1.0-real-estate-discovery"

Maintains 4 distinct confidence metrics (NEVER collapses them into one):
  1. evidence_confidence  — Reliability of concrete source evidence
  2. identity_confidence  — Strength of contact resolution & deduplication
  3. intent_confidence    — Strength and clarity of buying/selling intent
  4. discovery_relevance  — Overall campaign match score

Features:
  - Intent Evidence & Signal Strength (25%)
  - Property & Location Match (25%)
  - Budget & Timeline Match (20%)
  - Contact Completeness & Validity (15%)
  - Freshness Decay (15%)
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from app.models.discovery_models import DiscoveryCandidate, DiscoveryCampaign

logger = logging.getLogger(__name__)

DISCOVERY_MODEL_VERSION = "v1.0-real-estate-discovery"


class DiscoveryRelevanceService:
    @staticmethod
    def compute_freshness(observed_at: Optional[datetime]) -> float:
        """
        Calculate freshness score with exponential decay.
        1.0 for < 24 hours old.
        Decays smoothly to 0.4 at 30 days, 0.1 at 90 days.
        """
        if not observed_at:
            return 0.5

        now = datetime.now(timezone.utc)
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)

        age_seconds = max((now - observed_at).total_seconds(), 0)
        age_hours = age_seconds / 3600.0

        if age_hours <= 24:
            return 1.0
        elif age_hours <= 720:  # Up to 30 days
            return round(max(0.4, 1.0 - (age_hours - 24) * (0.6 / 696)), 4)
        else:  # Beyond 30 days
            return round(max(0.1, 0.4 - (age_hours - 720) * (0.3 / 1440)), 4)

    @classmethod
    def evaluate_candidate(
        cls,
        candidate: DiscoveryCandidate,
        campaign: Optional[DiscoveryCampaign] = None,
        signals_count: int = 1,
        max_signal_strength: float = 1.0,
    ) -> Dict[str, float]:
        """
        Evaluate all 4 confidence and relevance dimensions.

        Returns:
            {
                "evidence_confidence": float,
                "identity_confidence": float,
                "intent_confidence": float,
                "freshness_score": float,
                "relevance_score": float,
            }
        """
        norm = candidate.normalized_data or {}
        contact = candidate.contact_information or {}

        # 1. Freshness Score
        freshness = cls.compute_freshness(candidate.observed_at or candidate.source_created_at)

        # 2. Evidence Confidence
        # Higher if verified provider external ID and source reference exist
        evidence_conf = 0.5
        if candidate.external_id:
            evidence_conf += 0.3
        if candidate.source_url:
            evidence_conf += 0.1
        if candidate.raw_reference:
            evidence_conf += 0.1
        evidence_conf = min(evidence_conf, 1.0)

        # 3. Identity Confidence
        # E.164 phone + verified email = high; only partial name = low
        identity_conf = 0.2
        phone = contact.get("phone_e164") or contact.get("phone") or norm.get("phone")
        email = contact.get("email") or norm.get("email")
        name = candidate.display_name or norm.get("name")

        if phone:
            identity_conf += 0.4
            if str(phone).startswith("+"):
                identity_conf += 0.1
        if email and "@" in str(email):
            identity_conf += 0.3
        if name:
            identity_conf += 0.1
        identity_conf = min(identity_conf, 1.0)

        # 4. Intent Confidence
        intent_conf = 0.5
        lead_intent = norm.get("lead_intent") or norm.get("intent")
        if lead_intent in ("BUYER", "INVESTOR", "SELLER", "TENANT"):
            intent_conf += 0.3
        if norm.get("property_type"):
            intent_conf += 0.1
        if norm.get("timeline"):
            intent_conf += 0.1
        intent_conf = min(intent_conf * max_signal_strength, 1.0)

        # 5. Discovery Relevance Score against Campaign
        # Criteria match
        relevance = 0.0

        # Component A: Intent & Signals (Weight: 0.25)
        relevance += 0.25 * (intent_conf * min(signals_count, 3) / 3.0)

        # Component B: Property & Location Match (Weight: 0.25)
        loc_score = 0.5  # Neutral default if no campaign
        if campaign:
            loc_match = False
            prop_match = False
            cand_city = norm.get("city")
            cand_prop = norm.get("property_type")

            if campaign.cities and cand_city:
                if any(str(c).lower() in str(cand_city).lower() for c in campaign.cities):
                    loc_match = True
            elif not campaign.cities:
                loc_match = True

            if campaign.property_types and cand_prop:
                if any(str(p).lower() in str(cand_prop).lower() for p in campaign.property_types):
                    prop_match = True
            elif not campaign.property_types:
                prop_match = True

            loc_score = (1.0 if loc_match else 0.2) * 0.5 + (1.0 if prop_match else 0.2) * 0.5
        relevance += 0.25 * loc_score

        # Component C: Budget & Timeline Match (Weight: 0.20)
        budget_score = 0.6
        cand_bmax = norm.get("budget_max")
        cand_bmin = norm.get("budget_min")
        if campaign and (campaign.budget_min or campaign.budget_max):
            if cand_bmax or cand_bmin:
                budget_score = 0.9  # Expressed budget that fits context
            else:
                budget_score = 0.4
        relevance += 0.20 * budget_score

        # Component D: Contact Completeness & Identity (Weight: 0.15)
        relevance += 0.15 * identity_conf

        # Component E: Freshness (Weight: 0.15)
        relevance += 0.15 * freshness

        final_relevance = round(min(max(relevance, 0.0), 1.0), 4)

        return {
            "evidence_confidence": round(evidence_conf, 4),
            "identity_confidence": round(identity_conf, 4),
            "intent_confidence": round(intent_conf, 4),
            "freshness_score": round(freshness, 4),
            "relevance_score": final_relevance,
        }
