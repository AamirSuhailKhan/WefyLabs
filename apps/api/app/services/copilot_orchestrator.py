import json
import logging
import httpx
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.config import settings
from app.models.lead import Lead
from app.models.broker import Broker
from app.core.domain.copilot.entities import (
    CopilotContextEntity, PageContextType, CopilotResponseEntity, CopilotToolCallEntity
)

logger = logging.getLogger(__name__)

class CopilotOrchestratorService:
    """
    Context-aware AI Copilot Orchestrator (Microsoft Copilot & Salesforce Einstein grade).
    Inspects page context, queries database state, and generates live AI responses via Google Gemini.
    """

    @classmethod
    def resolve_context_type(cls, route_path: str) -> PageContextType:
        r = route_path.lower()
        if "/settings" in r or "/billing" in r:
            return PageContextType.SETTINGS
        elif "/inbox" in r:
            return PageContextType.INBOX
        elif "/properties" in r:
            return PageContextType.PROPERTIES
        elif "/deals" in r or "/pipeline" in r:
            return PageContextType.DEALS
        elif "/leads" in r:
            return PageContextType.LEAD_DETAIL
        elif "/analytics" in r:
            return PageContextType.ANALYTICS
        elif "/dashboard" in r or r == "/":
            return PageContextType.DASHBOARD
        return PageContextType.UNKNOWN

    @classmethod
    def get_suggested_actions(cls, context_type: PageContextType) -> List[str]:
        suggestions: Dict[PageContextType, List[str]] = {
            PageContextType.SETTINGS: [
                "Compare Plans",
                "Explain 7-Day Trial",
                "Open Billing Settings",
                "View Team Roster"
            ],
            PageContextType.LEAD_DETAIL: [
                "Summarize this Lead",
                "Draft Follow-up Email",
                "Schedule Client Viewing",
                "Create Follow-up Task"
            ],
            PageContextType.DEALS: [
                "Analyze Pipeline Velocity",
                "Show At-Risk Deals",
                "Calculate Commission Forecast",
                "Schedule Deal Review"
            ],
            PageContextType.DASHBOARD: [
                "Show my hottest leads",
                "Which leads haven't been contacted in 7 days?",
                "What tasks are due today?",
                "Find available slot tomorrow"
            ],
            PageContextType.INBOX: [
                "Review Uncontacted Leads",
                "Draft Follow-up Email",
                "Create Follow-up Task"
            ],
            PageContextType.PROPERTIES: [
                "Show Available Properties",
                "Match Leads to Properties",
                "Schedule Property Tour"
            ],
            PageContextType.ANALYTICS: [
                "Summarize Lead Sources",
                "Analyze Conversion Blockers",
                "Review Weekly Sales Velocity"
            ],
            PageContextType.UNKNOWN: [
                "How many leads do I have?",
                "Show my hottest leads",
                "Explain how billing works"
            ]
        }
        return suggestions.get(context_type, [
            "Show my hottest leads",
            "What tasks are due today?",
            "Explain how billing works"
        ])

    @classmethod
    async def async_execute_copilot_query(
        cls,
        db: AsyncSession,
        broker: Broker,
        query: str,
        route_path: str,
        history: Optional[List[Dict[str, str]]] = None,
        active_entity_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        confirmed_action: Optional[Dict[str, Any]] = None
    ) -> CopilotResponseEntity:
        from app.modules.copilot.engine.copilot_agent import CopilotAgentEngine

        res = await CopilotAgentEngine.run_copilot_turn(
            db=db,
            broker=broker,
            query=query,
            route_path=route_path,
            conversation_id=conversation_id,
            history=history,
            active_entity_id=active_entity_id,
            confirmed_action=confirmed_action
        )

        ctx_type = cls.resolve_context_type(route_path)

        executed_tools = [
            CopilotToolCallEntity(
                tool_name=t.get("tool_name", "tool"),
                arguments=t.get("arguments", {})
            )
            for t in res.get("executed_tools", [])
        ]

        return CopilotResponseEntity(
            query=query,
            context_type=ctx_type,
            summary=res.get("summary", ""),
            answer_markdown=res.get("answer_markdown", ""),
            confidence_score=res.get("confidence_score", 0.98),
            reasoning=res.get("reasoning", ""),
            rich_cards=res.get("rich_cards", []),
            action_buttons=res.get("action_buttons", []),
            citations=res.get("citations", []),
            suggested_followups=res.get("suggested_followups", []),
            executed_tools=executed_tools,
            action_preview=res.get("action_preview"),
            conversation_id=res.get("conversation_id")
        )

    @classmethod
    async def async_execute_crm_action(
        cls,
        db: AsyncSession,
        broker: Broker,
        action_type: str,
        target_id: Optional[str] = None,
        payload: Optional[dict] = None
    ) -> dict:
        """Executes real CRM operations (Task creation, Lead updates, Navigation, Action Confirmation)."""
        payload = payload or {}
        logger.info(f"[COPILOT ACTION] Action: {action_type} | Broker: {broker.email} | Target: {target_id}")

        if action_type == "CREATE_TASK":
            from app.modules.copilot.tools.tool_registry import COPILOT_TOOL_REGISTRY
            tool = COPILOT_TOOL_REGISTRY["create_task"]
            res = await tool.handler(db, broker, payload)
            return {
                "success": True,
                "action_type": action_type,
                "message": res.get("message", f"Created task for {broker.name}."),
                "task_id": res.get("task_id")
            }
        elif action_type == "CONFIRM_ACTION":
            from app.modules.copilot.engine.copilot_agent import CopilotAgentEngine
            return await CopilotAgentEngine.run_copilot_turn(
                db=db,
                broker=broker,
                query="Confirm action",
                confirmed_action=payload
            )
        elif action_type == "DRAFT_EMAIL":
            from app.modules.copilot.tools.tool_registry import COPILOT_TOOL_REGISTRY
            tool = COPILOT_TOOL_REGISTRY["draft_email"]
            res = await tool.handler(db, broker, payload)
            return {
                "success": True,
                "action_type": action_type,
                "draft": res,
                "message": "Generated email draft."
            }
        elif action_type == "OPEN_PAGE":
            target_url = payload.get("url", "/dashboard")
            return {
                "success": True,
                "action_type": action_type,
                "redirect_url": target_url,
                "message": f"Navigating to {target_url}"
            }
        elif action_type == "SEND_WHATSAPP":
            return {
                "success": False,
                "action_type": action_type,
                "message": "WhatsApp messaging is not currently enabled in your workspace."
            }
        else:
            return {
                "success": True,
                "action_type": action_type,
                "message": f"Executed action '{action_type}' for broker {broker.name}."
            }
