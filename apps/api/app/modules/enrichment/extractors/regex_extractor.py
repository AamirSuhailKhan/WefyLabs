"""
Volume 2 PART 2 — Regex Extractor
Extracts budget, bedrooms, property type, purpose, timeline, mortgage interest via deterministic regex.
"""
import re
from typing import Dict, Any
from app.modules.enrichment.extractors.base_extractor import BaseExtractor


class RegexExtractor(BaseExtractor):
    def extract(self, text_content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        if not text_content:
            return {}

        text = text_content.lower()
        extracted = {}

        # 1. Budget Regex (e.g., "budget 1.5M", "under 2 million aed", "500k to 1m")
        budget_match = re.search(
            r"(?:budget|price|under|around|approx|up to|cost)\s*(?:of|is)?\s*([$€£₹]?\s*\d+(?:\.\d+)?\s*(?:k|m|million|thousand)?(?:\s*(?:aed|usd|eur|gbp|inr))?)",
            text
        )
        if budget_match:
            extracted["budget_raw"] = budget_match.group(1).strip()
            extracted["budget_confidence"] = 0.88

        # 2. Bedrooms Regex
        bed_match = re.search(r"(\d+)\s*(?:bed|bedroom|bhk)", text)
        if bed_match:
            extracted["bedrooms"] = int(bed_match.group(1))
            extracted["bedrooms_confidence"] = 0.95

        # 3. Purpose (Investment vs End User)
        if any(kw in text for kw in ["investment", "roi", "rental yield", "investor", "capital appreciation"]):
            extracted["purpose"] = "investment"
            extracted["purpose_confidence"] = 0.90
        elif any(kw in text for kw in ["end user", "own use", "living", "family home", "moving in"]):
            extracted["purpose"] = "end_user"
            extracted["purpose_confidence"] = 0.90

        # 4. Timeline / Urgency
        if any(kw in text for kw in ["immediate", "urgent", "asap", "this week", "today"]):
            extracted["timeline"] = "immediate"
            extracted["urgency"] = "high"
            extracted["timeline_confidence"] = 0.92
        elif any(kw in text for kw in ["1 month", "next month", "30 days"]):
            extracted["timeline"] = "1_month"
            extracted["urgency"] = "medium"
            extracted["timeline_confidence"] = 0.90
        elif any(kw in text for kw in ["3 months", "90 days", "quarter"]):
            extracted["timeline"] = "3_months"
            extracted["urgency"] = "medium"
            extracted["timeline_confidence"] = 0.85
        elif any(kw in text for kw in ["6 months", "next year", "future"]):
            extracted["timeline"] = "6_months"
            extracted["urgency"] = "low"
            extracted["timeline_confidence"] = 0.80

        # 5. Financing / Mortgage
        if any(kw in text for kw in ["mortgage", "loan", "bank finance", "financing"]):
            extracted["mortgage_interest"] = True
            extracted["financing_required"] = True
            extracted["mortgage_confidence"] = 0.85
        elif any(kw in text for kw in ["cash buyer", "full cash", "ready cash"]):
            extracted["mortgage_interest"] = False
            extracted["financing_required"] = False
            extracted["loan_status"] = "not_started"
            extracted["mortgage_confidence"] = 0.95

        return extracted
