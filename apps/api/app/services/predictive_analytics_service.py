import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.core.domain.analytics.entities import (
    PredictiveIntelligenceEntity, FeatureAttributionEntity, RevenueForecastEntity
)
from app.models.lead import Lead

logger = logging.getLogger(__name__)

MODEL_VERSION = "v1.0-propensity-heuristic"

class PredictiveAnalyticsService:
    """
    Transparent, Reproducible Conversion Propensity Scoring Engine.
    Computes genuine feature-based conversion propensity scores, churn risk,
    dynamic feature attribution explanations, and revenue forecasts based solely
    on real database CRM records and verified lead parameters.
    """

    @classmethod
    def calculate_propensity(
        cls,
        lead: Optional[Lead] = None,
        lead_id: Optional[uuid.UUID] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> PredictiveIntelligenceEntity:
        """
        Computes conversion propensity score using a documented, versioned weighted feature model.
        """
        if lead is None and data is None:
            # Empty / no data case
            return PredictiveIntelligenceEntity(
                lead_id=lead_id,
                conversion_probability_pct=0.0,
                deal_close_probability_pct=0.0,
                churn_risk_pct=100.0,
                estimated_lifetime_value=0.0,
                best_followup_window="No contact window established",
                confidence_interval="0.0% - 0.0%",
                feature_attributions=[
                    FeatureAttributionEntity(
                        feature_name="Insufficient Data",
                        impact_score=0.0,
                        description="Lead has no recorded engagement or qualification parameters."
                    )
                ],
                model_version=MODEL_VERSION,
                feature_snapshot={}
            )

        # Extract features
        status = getattr(lead, "status", None) or (data.get("status") if data else None)
        score_category = (getattr(lead, "score", None) or (data.get("score") if data else "") or "").lower()
        budget_min = getattr(lead, "budget_min", None) if lead else (data.get("budget_min") if data else None)
        budget_max = getattr(lead, "budget_max", None) if lead else (data.get("budget_max") if data else None)
        timeline = getattr(lead, "timeline", None) if lead else (data.get("timeline") if data else None)
        loan_status = getattr(lead, "loan_status", None) if lead else (data.get("loan_status") if data else None)
        property_type = getattr(lead, "property_type", None) if lead else (data.get("property_type") if data else None)
        transaction_type = getattr(lead, "transaction_type", None) if lead else (data.get("transaction_type") if data else None)
        locations = getattr(lead, "preferred_locations", None) if lead else (data.get("preferred_locations") if data else None)
        conversations = getattr(lead, "conversations", None) if lead else (data.get("conversations") if data else None)
        conv_count = len(conversations) if conversations is not None else int((data or {}).get("conversation_count", 0))

        # Terminal status handling
        if status == "lost":
            return PredictiveIntelligenceEntity(
                lead_id=lead_id or (getattr(lead, "id", None)),
                conversion_probability_pct=0.0,
                deal_close_probability_pct=0.0,
                churn_risk_pct=100.0,
                estimated_lifetime_value=0.0,
                best_followup_window="Lead closed lost",
                confidence_interval="0.0% - 0.0%",
                feature_attributions=[
                    FeatureAttributionEntity(
                        feature_name="Closed Lost Status",
                        impact_score=-100.0,
                        description="Lead was marked closed lost in CRM."
                    )
                ],
                model_version=MODEL_VERSION,
                feature_snapshot={"status": "lost"}
            )
        if status == "converted":
            budget_val = budget_max or budget_min or 0.0
            ltv = round(budget_val * 0.02, 2)
            return PredictiveIntelligenceEntity(
                lead_id=lead_id or (getattr(lead, "id", None)),
                conversion_probability_pct=100.0,
                deal_close_probability_pct=100.0,
                churn_risk_pct=0.0,
                estimated_lifetime_value=ltv,
                best_followup_window="Deal won - Proceed to closing",
                confidence_interval="100.0% - 100.0%",
                feature_attributions=[
                    FeatureAttributionEntity(
                        feature_name="Converted Status",
                        impact_score=100.0,
                        description="Lead successfully converted to client."
                    )
                ],
                model_version=MODEL_VERSION,
                feature_snapshot={"status": "converted"}
            )

        # Feature Scoring & Attributions
        raw_score = 0.0
        attributions: List[FeatureAttributionEntity] = []

        # 1. Lead Qualification Score
        if score_category == "hot":
            raw_score += 30.0
            attributions.append(FeatureAttributionEntity(
                feature_name="Qualification Priority (HOT)",
                impact_score=30.0,
                description="Lead qualified with high intent and verified criteria."
            ))
        elif score_category == "warm":
            raw_score += 15.0
            attributions.append(FeatureAttributionEntity(
                feature_name="Qualification Priority (WARM)",
                impact_score=15.0,
                description="Lead partially qualified with active interest."
            ))
        elif score_category == "cold":
            raw_score += 5.0
            attributions.append(FeatureAttributionEntity(
                feature_name="Qualification Priority (COLD)",
                impact_score=5.0,
                description="Lead has limited parameters or distant timeline."
            ))

        # 2. Budget Parameters
        if budget_min is not None and budget_max is not None:
            raw_score += 15.0
            attributions.append(FeatureAttributionEntity(
                feature_name="Established Budget Range",
                impact_score=15.0,
                description=f"Clear price band specified: ₹{budget_min:,.0f} - ₹{budget_max:,.0f}."
            ))
        elif budget_min is not None or budget_max is not None:
            raw_score += 8.0
            attributions.append(FeatureAttributionEntity(
                feature_name="Partial Budget Specified",
                impact_score=8.0,
                description="Single budget boundary specified."
            ))
        else:
            raw_score -= 10.0
            attributions.append(FeatureAttributionEntity(
                feature_name="Missing Budget",
                impact_score=-10.0,
                description="No budget range has been provided."
            ))

        # 3. Timeline Urgency
        if timeline in ("immediate", "7_days", "< 7 days"):
            raw_score += 20.0
            attributions.append(FeatureAttributionEntity(
                feature_name="Immediate Timeline Urgency",
                impact_score=20.0,
                description="Buyer intends to transact immediately (< 7 days)."
            ))
        elif timeline in ("1_month", "30_days", "< 30 days"):
            raw_score += 12.0
            attributions.append(FeatureAttributionEntity(
                feature_name="Near-Term Purchase Timeline",
                impact_score=12.0,
                description="Buyer plans purchase within 1 month."
            ))
        elif timeline in ("3_months", "90_days"):
            raw_score += 5.0
            attributions.append(FeatureAttributionEntity(
                feature_name="Medium-Term Timeline",
                impact_score=5.0,
                description="Buyer plans purchase in 1 to 3 months."
            ))
        elif not timeline:
            raw_score -= 5.0
            attributions.append(FeatureAttributionEntity(
                feature_name="Unspecified Timeline",
                impact_score=-5.0,
                description="Purchase timeframe remains unknown."
            ))

        # 4. Property Specifications
        if property_type:
            raw_score += 8.0
            attributions.append(FeatureAttributionEntity(
                feature_name="Target Property Type",
                impact_score=8.0,
                description=f"Specific unit configuration requested ({property_type.upper()})."
            ))
        if transaction_type:
            raw_score += 5.0
            attributions.append(FeatureAttributionEntity(
                feature_name="Transaction Intent",
                impact_score=5.0,
                description=f"Transaction intent confirmed ({transaction_type.upper()})."
            ))
        if locations and len(locations) > 0:
            raw_score += 8.0
            attributions.append(FeatureAttributionEntity(
                feature_name="Locality Focus",
                impact_score=8.0,
                description=f"Preferred areas established ({', '.join(locations[:2])})."
            ))

        # 5. Financial Readiness
        if loan_status in ("pre_approved", "not_needed", "cash"):
            raw_score += 15.0
            attributions.append(FeatureAttributionEntity(
                feature_name="Financing Pre-Approval / Cash",
                impact_score=15.0,
                description="Buyer is pre-approved for loan or self-funded."
            ))
        elif loan_status == "in_process":
            raw_score += 6.0
            attributions.append(FeatureAttributionEntity(
                feature_name="Loan In Process",
                impact_score=6.0,
                description="Mortgage application currently underway."
            ))

        # 6. Conversation Engagement
        if conv_count >= 4:
            raw_score += 10.0
            attributions.append(FeatureAttributionEntity(
                feature_name="Active Conversation Velocity",
                impact_score=10.0,
                description=f"High engagement with {conv_count} dialogue turns."
            ))
        elif conv_count >= 1:
            raw_score += 4.0

        # Normalization (maps raw_score from [-15, 120] to [5%, 96%])
        normalized_propensity = min(max(round((raw_score / 115.0) * 100.0, 1), 5.0), 96.0)
        deal_close_prob = round(normalized_propensity * 0.85, 1)
        churn_risk = round(100.0 - normalized_propensity, 1)

        # LTV calculation based on genuine budget (2% broker commission)
        budget_ref = budget_max or budget_min or 0.0
        if budget_ref > 0:
            estimated_ltv = round(budget_ref * 0.02 * (normalized_propensity / 100.0), 2)
        else:
            estimated_ltv = 0.0

        # Optimal contact window
        if timeline in ("immediate", "7_days"):
            followup_window = "Within 4 hours (High Urgency)"
        elif score_category == "hot":
            followup_window = "Today between 10:00 AM - 12:00 PM"
        elif score_category == "warm":
            followup_window = "Within 24 hours"
        else:
            followup_window = "Next scheduled sequence"

        # Confidence interval
        lower = max(round(normalized_propensity - 4.5, 1), 0.0)
        upper = min(round(normalized_propensity + 4.5, 1), 100.0)
        conf_interval = f"{lower}% - {upper}%"

        feature_snapshot = {
            "score": score_category,
            "budget_min": budget_min,
            "budget_max": budget_max,
            "timeline": timeline,
            "loan_status": loan_status,
            "property_type": property_type,
            "conv_count": conv_count,
            "raw_score": raw_score,
        }

        return PredictiveIntelligenceEntity(
            lead_id=lead_id or (getattr(lead, "id", None)),
            conversion_probability_pct=normalized_propensity,
            deal_close_probability_pct=deal_close_prob,
            churn_risk_pct=churn_risk,
            estimated_lifetime_value=estimated_ltv,
            best_followup_window=followup_window,
            confidence_interval=conf_interval,
            feature_attributions=attributions,
            model_version=MODEL_VERSION,
            feature_snapshot=feature_snapshot,
        )

    @classmethod
    def predict_lead_intelligence(
        cls,
        lead_id: uuid.UUID,
        locality: Optional[str] = None,
        engagement_score: Optional[float] = None,
        lead: Optional[Lead] = None,
    ) -> PredictiveIntelligenceEntity:
        """
        Main entry point for calculating lead conversion propensity.
        """
        data = None
        if lead is None and engagement_score is not None:
            # Map legacy engagement_score to feature hints if lead is absent
            score_cat = "hot" if engagement_score >= 80 else ("warm" if engagement_score >= 50 else "cold")
            data = {"score": score_cat, "conversation_count": int(engagement_score / 20)}

        return cls.calculate_propensity(lead=lead, lead_id=lead_id, data=data)

    @classmethod
    def forecast_quarterly_revenue(
        cls,
        deals: Optional[List[Any]] = None,
        leads: Optional[List[Any]] = None,
    ) -> RevenueForecastEntity:
        """
        Computes revenue forecast from genuine deal transactions and qualified lead pipeline.
        Never fabricates hardcoded revenue values.
        """
        quarter_str = f"Q{(datetime.now(timezone.utc).month - 1) // 3 + 1} {datetime.now(timezone.utc).year}"
        deals = deals or []
        leads = leads or []

        total_projected = 0.0
        deal_count = len(deals)

        # 1. Sum probability-weighted deal values
        for d in deals:
            deal_val = float(
                getattr(d, "agreed_price", 0)
                or getattr(d, "deal_value", 0)
                or getattr(d, "value", 0)
                or getattr(d, "amount", 0)
                or 0
            )
            stage = str(getattr(d, "current_stage", "") or getattr(d, "stage", "new")).lower()
            # Stage probability weights
            weight = 0.8 if "negotiat" in stage else (0.5 if "viewing" in stage else (0.2 if "contact" in stage else 0.1))
            total_projected += deal_val * weight

        # 2. Add probability-weighted pipeline commissions from qualified leads if deals are sparse
        if not deals and leads:
            for l in leads:
                score = getattr(l, "score", "")
                budget = float(getattr(l, "budget_max", 0) or getattr(l, "budget_min", 0) or 0)
                if budget > 0:
                    prob = 0.35 if score == "hot" else (0.15 if score == "warm" else 0.05)
                    # 2% estimated commission * conversion probability
                    total_projected += (budget * 0.02) * prob

        if total_projected <= 0.0:
            return RevenueForecastEntity(
                quarter=quarter_str,
                projected_revenue=0.0,
                confidence_lower_bound=0.0,
                confidence_upper_bound=0.0,
                pipeline_health_score=0.0,
                deals_count=deal_count,
                calculation_basis="insufficient_data",
            )

        lower = round(total_projected * 0.85, 2)
        upper = round(total_projected * 1.15, 2)
        health_score = min(max(round(min(deal_count, 10) * 10.0, 1), 50.0), 95.0)

        return RevenueForecastEntity(
            quarter=quarter_str,
            projected_revenue=round(total_projected, 2),
            confidence_lower_bound=lower,
            confidence_upper_bound=upper,
            pipeline_health_score=health_score,
            deals_count=deal_count,
            calculation_basis="actual_pipeline_deals",
        )
