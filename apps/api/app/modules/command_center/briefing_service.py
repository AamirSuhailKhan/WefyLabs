"""
Part 30 — AI Real-Estate Agent Daily Briefing Service
=====================================================
Generates executive operational morning briefings for real-estate agents.
Principles:
1. Gemini receives ONLY verified structured numerical facts and directives.
2. CRM notes and property text are treated strictly as untrusted data.
3. Deterministic template fallback ensures 100% dashboard uptime without external AI.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from app.modules.command_center.dto import DailyBriefingDTO

logger = logging.getLogger("wefylabs.command_center.briefing")


class CommandCenterBriefingService:
    """
    Synthesizes grounded operational morning briefings.
    """

    @classmethod
    def generate_deterministic_briefing(
        cls,
        broker_name: str,
        critical_count: int,
        overdue_count: int,
        meetings_count: int,
        site_visits_count: int,
        hot_leads_count: int,
        strong_matches_count: int,
        top_directive: Optional[str] = None,
        top_inventory_gap: Optional[str] = None
    ) -> DailyBriefingDTO:
        """
        Builds an explainable, 100% fact-grounded morning briefing without external LLMs.
        """
        now = datetime.now(timezone.utc)
        greeting = f"Good morning, {broker_name or 'Agent'}"
        total_urgent = critical_count + overdue_count

        sentences = []
        if total_urgent > 0:
            sentences.append(f"You have {total_urgent} high-priority operational items requiring immediate attention today.")
        else:
            sentences.append("Your pipeline is in good standing with zero overdue emergencies.")

        if critical_count > 0:
            sentences.append(f"{critical_count} lead(s) require urgent first contact to avoid SLA breaches.")

        if overdue_count > 0:
            sentences.append(f"{overdue_count} client follow-up task(s) are overdue.")

        if site_visits_count > 0 or meetings_count > 0:
            parts = []
            if site_visits_count > 0:
                parts.append(f"{site_visits_count} site visit(s)")
            if meetings_count > 0:
                parts.append(f"{meetings_count} scheduled meeting(s)")
            sentences.append(f"On your schedule today: {' and '.join(parts)}.")

        if strong_matches_count > 0:
            sentences.append(f"{strong_matches_count} qualified buyers have 90+ property compatibility matches ready to present.")

        if top_inventory_gap:
            sentences.append(f"Inventory focus: High demand detected for {top_inventory_gap}.")

        if top_directive:
            sentences.append(f"Top immediate action: {top_directive}.")

        briefing_text = " ".join(sentences)

        highlights = []
        if critical_count > 0:
            highlights.append(f"{critical_count} critical SLA alert(s)")
        if overdue_count > 0:
            highlights.append(f"{overdue_count} overdue follow-up(s)")
        if site_visits_count > 0:
            highlights.append(f"{site_visits_count} site visit(s) today")
        if strong_matches_count > 0:
            highlights.append(f"{strong_matches_count} strong property match(es)")

        return DailyBriefingDTO(
            greeting=greeting,
            briefing_text=briefing_text,
            generated_at=now.isoformat(),
            is_ai_generated=False,
            highlights=highlights
        )

    @classmethod
    async def generate_briefing(
        cls,
        broker_name: str,
        critical_count: int,
        overdue_count: int,
        meetings_count: int,
        site_visits_count: int,
        hot_leads_count: int,
        strong_matches_count: int,
        top_directive: Optional[str] = None,
        top_inventory_gap: Optional[str] = None,
        ai_service: Optional[Any] = None
    ) -> DailyBriefingDTO:
        """
        Attempts Gemini natural language briefing if available, falling back
        instantly to deterministic briefing upon any error or if unconfigured.
        """
        fallback = cls.generate_deterministic_briefing(
            broker_name=broker_name,
            critical_count=critical_count,
            overdue_count=overdue_count,
            meetings_count=meetings_count,
            site_visits_count=site_visits_count,
            hot_leads_count=hot_leads_count,
            strong_matches_count=strong_matches_count,
            top_directive=top_directive,
            top_inventory_gap=top_inventory_gap
        )

        if not ai_service:
            return fallback

        # Attempt Gemini synthesis with verified facts ONLY
        try:
            facts_payload = {
                "agent_name": broker_name,
                "critical_actions": critical_count,
                "overdue_followups": overdue_count,
                "meetings_today": meetings_count,
                "site_visits_today": site_visits_count,
                "hot_leads": hot_leads_count,
                "strong_matches": strong_matches_count,
                "top_action": top_directive or "Review your pipeline",
                "top_inventory_gap": top_inventory_gap or "None"
            }

            system_instruction = (
                "You are an executive real-estate CRM operations assistant providing a 3-4 sentence morning briefing. "
                "CRITICAL SECURITY INVARIANT: Rely ONLY on the provided structured facts. "
                "DO NOT invent appointments, leads, inventory, phone numbers, or deadlines. "
                "Keep the tone sharp, professional, and action-oriented."
            )

            prompt = f"Summarize today's real estate workload based on these verified facts:\n{facts_payload}"

            # Invoke server-side ai_service if available
            if hasattr(ai_service, "generate_text"):
                resp = await ai_service.generate_text(prompt=prompt, system_instruction=system_instruction)
                if resp and len(resp.strip()) > 20:
                    fallback.briefing_text = resp.strip()
                    fallback.is_ai_generated = True
        except Exception as exc:
            logger.warning(f"[COMMAND_CENTER_BRIEFING] AI generation fallback used: {exc}")

        return fallback
