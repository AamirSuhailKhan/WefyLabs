"""
Part 21.7 — Appointment & Viewing Intent Detector
=================================================
Extracts viewing and appointment scheduling intent:
- Viewing Request
- Viewing Confirmation
- Viewing Reschedule
- Viewing Cancellation
- Preferred Date / Day
- Preferred Time Window

NON-NEGOTIABLE INVARIANT:
Never claims calendar booking unless Google Calendar / Scheduling service
actually confirms availability and creates the event.
"""
from __future__ import annotations

import re
import logging
from typing import Optional

from app.modules.conversation_intelligence.taxonomies import AppointmentIntentType
from app.modules.conversation_intelligence.dto import AppointmentIntentDTO

logger = logging.getLogger(__name__)

DAYS_OF_WEEK = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "tomorrow", "this weekend", "today"]


class AppointmentDetector:
    """Extracts viewing appointments and customer timing preferences."""

    @staticmethod
    def detect_appointment_intent(text: str) -> AppointmentIntentDTO:
        if not text or not text.strip():
            return AppointmentIntentDTO(intent_type=AppointmentIntentType.NONE)

        lowered = text.lower()
        intent_type = AppointmentIntentType.NONE
        preferred_date: Optional[str] = None
        preferred_time: Optional[str] = None
        evidence_snippets = []

        # 1. Cancellation
        if re.search(r"(cannot\s+make\s+it|can'?t\s+make\s+it|cancel\s+(the\s+)?(viewing|visit|appointment|meeting)|won'?t\s+be\s+able\s+to\s+come)", lowered):
            intent_type = AppointmentIntentType.CANCELLATION
            evidence_snippets.append("Viewing cancellation")

        # 2. Reschedule
        elif re.search(r"(reschedule|postpone|change\s+the\s+day|different\s+time|another\s+day|move\s+to\s+next\s+week)", lowered):
            intent_type = AppointmentIntentType.RESCHEDULE
            evidence_snippets.append("Viewing reschedule")

        # 3. Confirmation
        elif re.search(r"(works\s+for\s+me|see\s+you\s+(then|there|at)|confirm(ed)?|i'?ll\s+be\s+there|perfect\s+time|booked)", lowered) and any(
            t in lowered for t in ["saturday", "sunday", "tomorrow", "pm", "am", "clock", "morning", "afternoon", "evening", "weekend"]
        ):
            intent_type = AppointmentIntentType.CONFIRMATION
            evidence_snippets.append("Viewing confirmation")

        # 4. Request
        elif re.search(r"(visit|view|viewing|tour|see\s+the\s+(property|apartment|villa|unit|place)|schedule\s+a\s+(visit|viewing))", lowered):
            intent_type = AppointmentIntentType.REQUEST
            evidence_snippets.append("Viewing request")

        elif any(day in lowered for day in DAYS_OF_WEEK) and any(kw in lowered for kw in ["come", "visit", "see", "meet", "free", "available"]):
            intent_type = AppointmentIntentType.REQUEST
            evidence_snippets.append("Day/time availability preference")

        # Extract Preferred Day
        for day in DAYS_OF_WEEK:
            if day in lowered:
                preferred_date = day.capitalize()
                evidence_snippets.append(f"Day: {preferred_date}")
                break

        # Extract Preferred Time
        time_match = re.search(r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)|\d{1,2}\s*o'?clock|morning|afternoon|evening)", lowered)
        if time_match:
            preferred_time = time_match.group(0).strip()
            evidence_snippets.append(f"Time: {preferred_time}")

        confidence = 0.90 if intent_type != AppointmentIntentType.NONE else 0.0

        return AppointmentIntentDTO(
            intent_type=intent_type,
            preferred_date=preferred_date,
            preferred_time=preferred_time,
            evidence="; ".join(evidence_snippets) if evidence_snippets else None,
            confidence=confidence,
            calendar_verified=False,  # Truthful: unverified until calendar API check
        )
