"""
Grounded AI Re-Engagement Service
===================================
Generates personalized, facts-grounded re-engagement messages for inactive leads
using Google Gemini with a safe, deterministic template fallback.
Sanitizes CRM data to protect against prompt injection.
"""

import logging
import re
from typing import Dict, Any, Optional
from app.models.lead import Lead

logger = logging.getLogger(__name__)


class ReengagementService:
    """
    Generates personalized re-engagement suggestions grounded in actual CRM facts.
    """

    @staticmethod
    def _sanitize_untrusted_text(text: Optional[str]) -> str:
        """Sanitizes CRM user text to prevent prompt injection and markup corruption."""
        if not text:
            return ""
        # Strip system instruction tokens and abnormal control characters
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        cleaned = re.sub(r"(?i)(ignore\s+previous\s+instructions|system\s+prompt|send\s+secret)", "[filtered]", cleaned)
        return cleaned[:500].strip()

    @classmethod
    async def generate_reengagement_draft(
        cls,
        lead: Lead,
        days_inactive: int = 14,
        broker_name: str = "your advisor"
    ) -> Dict[str, Any]:
        """
        Creates a grounded re-engagement message draft based on actual CRM facts.
        """
        lead_name = cls._sanitize_untrusted_text(lead.name) or "there"
        prop_type = cls._sanitize_untrusted_text(lead.property_type) or "property"
        location = lead.preferred_locations[0] if (lead.preferred_locations and len(lead.preferred_locations) > 0) else "the area"
        budget = f"{lead.budget_currency or 'AED'} {lead.budget_max:,.0f}" if lead.budget_max else "your target budget"

        # Deterministic Grounded Draft
        deterministic_body = (
            f"Hi {lead_name}, checking in from {broker_name}'s office. "
            f"We recently received new {prop_type} listings in {location} matching {budget}. "
            f"Are you still actively looking, or has your timeline changed? Happy to send details if interested."
        )

        grounded_facts = [
            {"fact": "lead_name", "value": lead_name},
            {"fact": "property_type", "value": prop_type},
            {"fact": "preferred_location", "value": location},
            {"fact": "budget_reference", "value": budget},
            {"fact": "days_inactive", "value": days_inactive}
        ]

        # Try Gemini if settings available, otherwise return deterministic draft
        ai_generated = False
        message_body = deterministic_body

        try:
            from app.config import settings
            api_key = getattr(settings, "GEMINI_API_KEY", None)
            if api_key and api_key != "mock-gemini-key":
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-1.5-flash")

                system_prompt = (
                    "You are a professional real estate assistant. Generate a polite, concise (under 50 words) "
                    "re-engagement message for an inactive client. Strictly use only the provided facts. "
                    "Do NOT invent property features, discounts, or conversations."
                )
                user_prompt = (
                    f"Client Name: {lead_name}\n"
                    f"Interested In: {prop_type} in {location}\n"
                    f"Budget: {budget}\n"
                    f"Days Inactive: {days_inactive}\n"
                    f"Advisor Name: {broker_name}\n\n"
                    "Generate single re-engagement draft:"
                )
                response = await model.generate_content_async(
                    contents=[{"role": "user", "parts": [f"{system_prompt}\n\n{user_prompt}"]}]
                )
                if response and response.text:
                    message_body = response.text.strip()
                    ai_generated = True
        except Exception as exc:
            logger.warning(f"[ReengagementService] Gemini unavailable, using deterministic draft: {exc}")

        return {
            "lead_id": str(lead.id),
            "lead_name": lead_name,
            "days_inactive": days_inactive,
            "message_subject": f"Update regarding {prop_type} options in {location}",
            "message_body": message_body,
            "ai_generated": ai_generated,
            "grounded_facts": grounded_facts,
            "recommended_action": "Review draft and send via WhatsApp/Email or follow up with a quick call."
        }
