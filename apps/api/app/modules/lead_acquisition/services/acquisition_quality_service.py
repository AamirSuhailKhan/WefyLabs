"""
Part 21.1 — Acquisition Quality Score Service
===============================================
Computes a separate Acquisition Quality Score (0.0 – 1.0) for each prospect.

Distinct from:
  - Lead Score (qualification/hot-warm-cold)
  - Qualification Score (AI-assessed intent)
  - Conversion Propensity (predicted close probability)

Acquisition Quality evaluates:
  - Source reliability (known vs unknown source)
  - Data completeness (phone, email, name, budget)
  - Contact validity (E.164 phone, valid email format)
  - Consent quality (GRANTED vs UNKNOWN vs DENIED)
  - Freshness (time since event)
  - Identity confidence (dedup match strength)

Score is stored on LeadProspect.acquisition_quality_score.
"""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.models.acquisition_models import LeadProspect, ConsentStatus


def compute_acquisition_quality_score(prospect: LeadProspect) -> float:
    """
    Compute acquisition quality score.

    Returns float 0.0 – 1.0. Higher = better quality acquisition.
    """
    score = 0.0
    weights = {
        "source_reliability": 0.15,
        "contact_completeness": 0.30,
        "contact_validity": 0.20,
        "consent_quality": 0.15,
        "freshness": 0.10,
        "identity_confidence": 0.10,
    }

    # 1. Source reliability
    source_score = 0.7 if prospect.source_id else 0.3
    # Known channel = slightly higher
    if prospect.source_id:
        source_score = 0.9
    score += weights["source_reliability"] * source_score

    # 2. Contact completeness
    completeness = 0.0
    completeness_factors = [
        bool(prospect.phone_e164),      # E.164 phone: high weight
        bool(prospect.email),            # Email present
        bool(prospect.name),             # Name present
        bool(prospect.budget_min or prospect.budget_max),  # Budget
        bool(prospect.currency),         # Currency with budget
        bool(prospect.property_type),    # Property interest
        bool(prospect.transaction_type), # Transaction type
        bool(prospect.country),          # Country
    ]
    weights_inner = [0.25, 0.20, 0.10, 0.15, 0.05, 0.10, 0.10, 0.05]
    for factor, w in zip(completeness_factors, weights_inner):
        if factor:
            completeness += w
    score += weights["contact_completeness"] * completeness

    # 3. Contact validity
    validity = 0.0
    if prospect.phone_e164 and prospect.phone_e164.startswith("+"):
        validity += 0.6
    if prospect.email and "@" in prospect.email:
        validity += 0.4
    score += weights["contact_validity"] * min(validity, 1.0)

    # 4. Consent quality
    consent_score = 0.0
    if prospect.consent_status == ConsentStatus.GRANTED:
        consent_score = 1.0
        if prospect.email_consent or prospect.whatsapp_consent:
            consent_score = 1.0
    elif prospect.consent_status == ConsentStatus.UNKNOWN:
        consent_score = 0.4  # Neutral — not denied, not confirmed
    elif prospect.consent_status == "DENIED":
        consent_score = 0.0  # Denied = lowest quality
    score += weights["consent_quality"] * consent_score

    # 5. Freshness (decay over time)
    freshness = 1.0
    if prospect.created_at:
        age_seconds = (datetime.now(timezone.utc) - prospect.created_at).total_seconds()
        age_hours = age_seconds / 3600
        if age_hours > 24:
            freshness = max(0.5, 1.0 - (age_hours - 24) / (24 * 30))  # decay over 30 days
    score += weights["freshness"] * freshness

    # 6. Identity confidence
    id_conf = float(prospect.identity_confidence or 0.5)
    score += weights["identity_confidence"] * id_conf

    return round(min(max(score, 0.0), 1.0), 4)


async def score_and_save(prospect: LeadProspect, db) -> float:
    """Compute and persist acquisition quality score."""
    score = compute_acquisition_quality_score(prospect)
    prospect.acquisition_quality_score = Decimal(str(score))
    await db.flush()
    return score
