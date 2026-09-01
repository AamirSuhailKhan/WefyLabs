"""
Feature Extractor — Feature Engine for AI Lead Intelligence Platform
=====================================================================
Extracts 30+ signals across CRM data, AI Enrichment profiles, Identity Graph,
Activities, Meetings, Tasks, and Communications.
Output feature vector is passed to RulesEngine, ML Engine, and persisted in DB.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone


class FeatureExtractor:
    """
    Extracts numerical, categorical, and boolean feature vectors from raw & enriched lead objects.
    """

    def extract_features(
        self,
        lead_dto: Dict[str, Any],
        enrichment_profile: Optional[Dict[str, Any]] = None,
        identity_profile: Optional[Dict[str, Any]] = None,
        activity_stats: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Main extraction routine. Converts input entities into a normalized FeatureVector dictionary.
        """
        enrichment = enrichment_profile or {}
        identity = identity_profile or {}
        stats = activity_stats or {}

        # Basic identity & contact availability
        has_phone = bool(lead_dto.get("phone") or identity.get("primary_phone_e164"))
        has_email = bool(lead_dto.get("email") or identity.get("primary_email"))
        has_name = bool(lead_dto.get("name") or identity.get("primary_name"))
        has_whatsapp = bool(lead_dto.get("whatsapp") or identity.get("primary_whatsapp"))

        # Budget calculation (canonical AED)
        budget = (
            lead_dto.get("budget_max") or
            lead_dto.get("budget_min") or
            (enrichment.get("financial_profile") or {}).get("amount_canonical_aed") or
            0.0
        )

        # Property & Transaction specifications
        property_type = lead_dto.get("property_type") or (enrichment.get("property_interest") or {}).get("unit_type") or "unknown"
        transaction_type = lead_dto.get("transaction_type") or (enrichment.get("intent_profile") or {}).get("transaction_type") or "buy"
        timeline = lead_dto.get("timeline") or (enrichment.get("intent_profile") or {}).get("timeline") or "unknown"
        loan_status = lead_dto.get("loan_status") or (enrichment.get("financial_profile") or {}).get("financing") or "not_started"

        # Quality & Confidence metrics
        quality_score = float(enrichment.get("overall_quality_score") or 50.0)
        quality_tier = enrichment.get("quality_tier") or "cold"
        field_completion = float(enrichment.get("field_completion_rate") or 0.5)

        # Activity & Engagement metrics
        activity_count = int(stats.get("activity_count") or 0)
        meeting_count = int(stats.get("meeting_count") or 0)
        task_count = int(stats.get("task_count") or 0)
        note_count = int(stats.get("note_count") or len(lead_dto.get("notes") or []))

        # Time deltas
        created_at_str = lead_dto.get("created_at")
        lead_age_days = 0.0
        if created_at_str:
            try:
                dt = datetime.fromisoformat(str(created_at_str).replace("Z", "+00:00"))
                lead_age_days = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0)
            except Exception:
                pass

        # Inferred flags
        has_viewing_booked = meeting_count > 0 or "viewing" in str(lead_dto.get("pipeline_stage") or "").lower()
        has_mortgage = loan_status in ("pre_approved", "in_process", "cash_buyer")
        is_repeat_buyer = int(identity.get("lead_count") or 1) > 1

        feature_vector = {
            # Contact signals
            "has_phone": has_phone,
            "has_email": has_email,
            "has_name": has_name,
            "has_whatsapp": has_whatsapp,

            # Financial signals
            "budget_aed": float(budget),
            "is_high_value": float(budget) >= 3_000_000,
            "is_luxury": float(budget) >= 5_000_000,

            # Requirement signals
            "property_type": property_type,
            "transaction_type": transaction_type,
            "timeline": timeline,
            "loan_status": loan_status,

            # Intent & Urgency proxies
            "is_immediate": timeline in ("immediate", "1_month"),
            "has_mortgage_preapproval": loan_status == "pre_approved",
            "is_cash_buyer": loan_status == "cash_buyer",

            # Quality & Enrichment
            "quality_score": quality_score,
            "quality_tier": quality_tier,
            "field_completion_rate": field_completion,

            # Engagement
            "activity_count": activity_count,
            "meeting_count": meeting_count,
            "task_count": task_count,
            "note_count": note_count,
            "has_viewing_booked": has_viewing_booked,

            # Identity & History
            "is_repeat_buyer": is_repeat_buyer,
            "identity_lead_count": int(identity.get("lead_count") or 1),
            "lead_age_days": round(lead_age_days, 1),
            "source": lead_dto.get("source") or "manual",
        }

        return feature_vector
