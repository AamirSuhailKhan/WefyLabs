"""
Volume 2 PART 25 — Copilot Agent Engine
========================================
Core reasoning, tool orchestration, multi-turn conversation memory,
and security guardrails for the product-native AI Copilot.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.config import settings
from app.models.broker import Broker
from app.models.copilot_models import CopilotConversation, CopilotMessage
from app.modules.copilot.tools.tool_registry import (
    COPILOT_TOOL_REGISTRY,
    ToolRiskLevel,
    get_all_tool_declarations
)
from app.modules.copilot.knowledge.product_knowledge import search_product_knowledge

logger = logging.getLogger("beetlelabs.copilot.agent")

MAX_AGENT_ITERATIONS = 5

INJECTION_KEYWORDS = [
    "ignore previous instructions",
    "ignore all previous",
    "system prompt",
    "drop table",
    "override rules",
    "developer mode",
    "jailbreak",
    "reveal internal instructions",
    "disregard all guardrails",
    "execute arbitrary sql"
]


import inspect

async def _safe_add(db: AsyncSession, item: Any):
    res = db.add(item)
    if inspect.isawaitable(res):
        await res

async def _safe_commit(db: AsyncSession):
    res = db.commit()
    if inspect.isawaitable(res):
        await res

async def _safe_refresh(db: AsyncSession, item: Any):
    try:
        res = db.refresh(item)
        if inspect.isawaitable(res):
            await res
    except Exception:
        pass


class CopilotAgentEngine:
    @classmethod
    def check_prompt_injection(cls, query: str) -> bool:
        lowered = query.lower()
        return any(k in lowered for k in INJECTION_KEYWORDS)

    @classmethod
    async def get_or_create_conversation(
        cls,
        db: AsyncSession,
        broker: Broker,
        conversation_id: Optional[str] = None,
        route_path: str = "/dashboard"
    ) -> CopilotConversation:
        conv = None
        if conversation_id:
            try:
                c_uuid = uuid.UUID(str(conversation_id))
                conv = await db.get(CopilotConversation, c_uuid)
                if conv and conv.broker_id != broker.id:
                    conv = None  # Tenant isolation enforcement
            except Exception:
                conv = None

        if not conv:
            org_id = getattr(broker, "organization_id", None) or str(broker.id)
            conv = CopilotConversation(
                id=uuid.uuid4(),
                organization_id=str(org_id),
                broker_id=broker.id,
                title="New Conversation",
                route_context=route_path,
                is_active=True
            )
            await _safe_add(db, conv)
            await _safe_commit(db)
            await _safe_refresh(db, conv)

        return conv

    @classmethod
    async def run_copilot_turn(
        cls,
        db: AsyncSession,
        broker: Broker,
        query: str,
        route_path: str = "/dashboard",
        conversation_id: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        active_entity_id: Optional[str] = None,
        confirmed_action: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes a complete AI Copilot turn:
        1. Guardrails & Prompt Injection Protection
        2. Persistent Conversation Resolution
        3. Tool Calling Loop (up to 5 iterations)
        4. Confirmation & Preview Handling
        5. Citation Grounding & Response Persistence
        """
        start_time = time.time()

        # 1. Prompt Injection Defense
        if cls.check_prompt_injection(query):
            return {
                "query": query,
                "answer_markdown": "⚠️ **Security Alert:** Your query contains prohibited system override instructions. Prompt injection defenses are active.",
                "summary": "Security Guardrail Triggered",
                "reasoning": "Blocked potential prompt injection attempt.",
                "confidence_score": 1.0,
                "citations": ["Security Engine → Input Validation"],
                "action_buttons": [],
                "rich_cards": [],
                "suggested_followups": ["Ask a standard CRM question"],
                "executed_tools": [],
                "action_preview": None
            }

        # 2. Conversation Persistence Setup
        conv = await cls.get_or_create_conversation(db, broker, conversation_id, route_path)

        # Update conversation title from first meaningful query if title is default
        if conv.title == "New Conversation" and len(query.strip()) > 3:
            conv.title = query.strip()[:60]
            conv.route_context = route_path
            await db.commit()

        # 3. Check for WhatsApp intent (Prohibited/Disabled)
        q_lower = query.lower()
        if "whatsapp" in q_lower and any(w in q_lower for w in ["send", "message", "dispatch", "chat"]):
            answer = "WhatsApp messaging is not currently enabled in your workspace. You can communicate via Brevo Email or record internal notes."
            citations = ["Product Documentation → System Limitations"]
            await cls._save_messages(db, conv, query, answer, citations=citations)
            return {
                "query": query,
                "answer_markdown": answer,
                "summary": "WhatsApp is disabled in workspace.",
                "reasoning": "Detected request for WhatsApp dispatch; returned explicit disabled notice.",
                "confidence_score": 1.0,
                "citations": citations,
                "action_buttons": [
                    {"label": "📧 Draft Email Instead", "action_type": "DRAFT_EMAIL", "payload": {}},
                    {"label": "📋 View Leads", "action_type": "OPEN_PAGE", "payload": {"url": "/dashboard/leads"}}
                ],
                "rich_cards": [],
                "suggested_followups": ["Draft follow-up email", "Create follow-up task"],
                "executed_tools": [],
                "action_preview": None
            }

        # 4. Handle Confirmed Action Execution if provided
        if confirmed_action:
            action_tool_name = confirmed_action.get("tool_name")
            action_args = confirmed_action.get("arguments", {})
            if action_tool_name in COPILOT_TOOL_REGISTRY:
                tool = COPILOT_TOOL_REGISTRY[action_tool_name]
                exec_result = await tool.handler(db, broker, action_args)
                msg_text = exec_result.get("message", f"Successfully executed action: {action_tool_name}.")
                citations = [exec_result.get("_citation", f"Executed {action_tool_name}")]
                await cls._save_messages(db, conv, f"[Confirmed: {action_tool_name}]", msg_text, citations=citations)
                return {
                    "query": query,
                    "answer_markdown": f"**Action Confirmed & Executed:**\n\n{msg_text}",
                    "summary": f"Executed confirmed action: {action_tool_name}",
                    "reasoning": "User confirmed action preview. Executed backend handler safely.",
                    "confidence_score": 1.0,
                    "citations": citations,
                    "action_buttons": [],
                    "rich_cards": [],
                    "suggested_followups": ["View updated records", "Show my pipeline"],
                    "executed_tools": [{"tool_name": action_tool_name, "arguments": action_args}],
                    "action_preview": None
                }

        # 5. Build Agent System Instruction & Context
        system_instruction = (
            f"You are the enterprise AI Copilot for WefyLabs Real Estate CRM.\n"
            f"Authenticated User: {broker.name} (Email: {broker.email}, Role: Broker/Agent, City: {broker.city or 'Bengaluru'}).\n"
            f"Active Workspace Route: {route_path}\n\n"
            f"RULES:\n"
            f"1. You have access to authorized tools for the user's workspace. ALWAYS call tools to retrieve live CRM facts.\n"
            f"2. Never guess or invent CRM data, lead names, counts, or dates.\n"
            f"3. Clearly distinguish FACT (actual database information), ANALYSIS (AI interpretation), and RECOMMENDATION (suggested next action).\n"
            f"4. For destructive actions (e.g. deleting leads) or high-risk writes (e.g. sending client emails, scheduling calendar meetings), explain what will happen and request confirmation.\n"
            f"5. WhatsApp messaging is DISABLED. If the user asks for WhatsApp, clearly state it is not currently enabled.\n"
            f"6. Indicative pricing (not yet finalized): Starter Plan is approximately ₹2,999/month, Pro Plan is approximately ₹4,999/month. Always qualify pricing as 'indicative' or 'subject to change'. Never invent other currencies or rates.\n"
            f"7. Use clean Markdown formatting (bullet points, bold text, headings)."
        )

        executed_tools_log = []
        citations = []
        action_preview = None
        final_answer = ""
        reasoning_text = ""

        # Fast deterministic tool invocation for tests or when Gemini is mocked
        is_test_env = settings.ENV in ("testing", "test")
        has_gemini_key = bool(settings.GEMINI_API_KEY and not settings.GEMINI_API_KEY.startswith("AIzaSy_placeholder"))

        if is_test_env or not has_gemini_key:
            # Deterministic Semantic Tool Dispatch
            final_answer, executed_tools_log, citations, action_preview = await cls._dispatch_deterministic_tools(
                db, broker, query, route_path
            )
            reasoning_text = f"Analyzed intent from route '{route_path}'. Retrieved live CRM facts via tool calling."
        else:
            # Full Live Gemini Function Calling Loop
            final_answer, executed_tools_log, citations, action_preview, reasoning_text = await cls._run_gemini_loop(
                db, broker, query, route_path, system_instruction, history
            )

        # Generate Action Buttons & Dynamic Suggested Followups
        action_buttons, suggested_followups = cls._generate_suggestions(query, route_path, executed_tools_log)

        # 6. Persist Conversation Messages
        await cls._save_messages(
            db, conv, query, final_answer,
            reasoning=reasoning_text,
            tool_calls=executed_tools_log,
            citations=citations,
            action_preview=action_preview
        )

        latency_ms = round((time.time() - start_time) * 1000, 2)
        summary = f"Processed CRM request via {len(executed_tools_log)} tool(s) in {latency_ms}ms."

        return {
            "query": query,
            "conversation_id": str(conv.id),
            "answer_markdown": final_answer,
            "summary": summary,
            "reasoning": reasoning_text,
            "confidence_score": 0.98,
            "citations": citations,
            "action_buttons": action_buttons,
            "rich_cards": [],
            "suggested_followups": suggested_followups,
            "executed_tools": executed_tools_log,
            "action_preview": action_preview
        }

    @classmethod
    async def _dispatch_deterministic_tools(
        cls,
        db: AsyncSession,
        broker: Broker,
        query: str,
        route_path: str
    ) -> Tuple[str, List[Dict[str, Any]], List[str], Optional[Dict[str, Any]]]:
        """Dispatches matching tools deterministically for fast and reliable execution."""
        q_lower = query.lower()
        executed_tools = []
        citations = []
        action_preview = None

        # 1. Profile Queries
        if any(w in q_lower for w in ["who am i", "my profile", "my role", "my account", "give me my profile"]):
            tool = COPILOT_TOOL_REGISTRY["read_profile"]
            res = await tool.handler(db, broker, {})
            executed_tools.append({"tool_name": "read_profile", "arguments": {}})
            citations.append(res.get("_citation", "Live CRM Profile"))
            answer = (
                f"You are **{res['name']}**.\n"
                f"- **Role**: {res['role']}\n"
                f"- **Email**: {res['email']}\n"
                f"- **Agency**: {res['agency_name']}\n"
                f"- **Location**: {res['city']}\n"
                f"- **Subscription Plan**: {res['subscription_status'].upper()} ({res['trial_days_remaining']} days remaining)"
            )
            return answer, executed_tools, citations, None

        # 2. Deletion Queries (Destructive with preview)
        if ("delete" in q_lower or "remove" in q_lower) and "lead" in q_lower:
            tool = COPILOT_TOOL_REGISTRY["list_leads"]
            leads_data = await tool.handler(db, broker, {"limit": 10})
            total = leads_data.get("total_matching", 0)
            lead_ids = [l["id"] for l in leads_data.get("leads", [])]
            token = f"confirm-del-{uuid.uuid4()}"
            action_preview = {
                "tool_name": "delete_lead",
                "title": "Confirm Deletion of Leads",
                "summary": f"Permanently remove {total} lead(s) from your workspace.",
                "impacted_records": total,
                "is_destructive": True,
                "confirmation_token": token,
                "arguments": {"lead_ids": lead_ids}
            }
            citations.append("Live CRM Leads Database")
            answer = (
                f"⚠️ **Action Confirmation Required:**\n\n"
                f"I found **{total} lead(s)** in your workspace matching this request. "
                f"Deleting them is permanent and cannot be undone.\n\n"
                f"Shall I proceed with deleting these records?"
            )
            return answer, executed_tools, citations, action_preview

        # 3. Create Task Queries
        if any(w in q_lower for w in ["create task", "create a task", "create follow-up", "create a follow-up"]):
            tool = COPILOT_TOOL_REGISTRY["create_task"]
            title = query.replace("create a task", "").replace("create task", "").replace("create follow-up for", "").strip() or "Client Follow-up"
            res = await tool.handler(db, broker, {"title": title, "due_in_hours": 24, "priority": "high"})
            executed_tools.append({"tool_name": "create_task", "arguments": {"title": title}})
            citations.append(res.get("_citation", "CRM Task Database"))
            answer = f"Done. I created the task: **'{res['title']}'** (Priority: {res['priority']}) due on {res['due_at']}."
            return answer, executed_tools, citations, None

        # 4. Task Listing
        if any(w in q_lower for w in ["task", "tasks", "overdue", "todo"]):
            filter_type = "overdue" if "overdue" in q_lower else ("today" if "today" in q_lower else "all")
            tool = COPILOT_TOOL_REGISTRY["list_tasks"]
            res = await tool.handler(db, broker, {"filter_type": filter_type, "limit": 5})
            executed_tools.append({"tool_name": "list_tasks", "arguments": {"filter_type": filter_type}})
            citations.append(res.get("_citation", "CRM Task Database"))
            task_list = res.get("tasks", [])
            if not task_list:
                answer = f"You have no {filter_type if filter_type != 'all' else 'pending'} tasks right now."
            else:
                lines = [f"- **{t['title']}** (Due: {t['due_at']}, Priority: {t['priority']})" for t in task_list]
                answer = f"I found **{res['total']}** task(s):\n\n" + "\n".join(lines)
            return answer, executed_tools, citations, None

        # 5. Calendar Queries
        if any(w in q_lower for w in ["meeting", "calendar", "free", "available slot"]):
            if any(w in q_lower for w in ["free", "availability", "slot"]):
                tool = COPILOT_TOOL_REGISTRY["check_calendar_availability"]
                res = await tool.handler(db, broker, {})
                executed_tools.append({"tool_name": "check_calendar_availability", "arguments": {}})
                citations.append(res.get("_citation", "Google Calendar Integration"))
                answer = f"Here are your available Google Calendar slots for {res['date']}:\n\n" + "\n".join([f"- {s}" for s in res['available_slots']])
                return answer, executed_tools, citations, None
            else:
                tool = COPILOT_TOOL_REGISTRY["list_calendar_events"]
                res = await tool.handler(db, broker, {})
                executed_tools.append({"tool_name": "list_calendar_events", "arguments": {}})
                citations.append(res.get("_citation", "Google Calendar Integration"))
                meetings = res.get("meetings", [])
                if not meetings:
                    answer = "You have no upcoming calendar meetings scheduled for this week."
                else:
                    lines = [f"- **{m['title']}** at {m['scheduled_at']}" for m in meetings]
                    answer = f"You have **{len(meetings)}** meeting(s) scheduled:\n\n" + "\n".join(lines)
                return answer, executed_tools, citations, None

        # 6. Billing / Plans Queries
        if any(w in q_lower for w in ["plan", "billing", "pricing", "cost", "how much", "upgrade", "starter", "pro"]):
            tool = COPILOT_TOOL_REGISTRY["get_billing_info"]
            res = await tool.handler(db, broker, {})
            executed_tools.append({"tool_name": "get_billing_info", "arguments": {}})
            citations.append(res.get("_citation", "Billing & Subscriptions Service"))
            answer = (
                f"Here are the official subscription plans for WefyLabs CRM:\n\n"
                f"- **Starter Plan**: {res['starter_plan_price']}\n"
                f"- **Pro Plan**: {res['pro_plan_price']}\n\n"
                f"Your workspace is currently on **{res['current_plan']}** with **{res['trial_days_remaining']} days remaining**. "
                f"You can upgrade your plan in [Settings](/dashboard/settings)."
            )
            return answer, executed_tools, citations, None

        # 7. Product Help / How-To
        if any(w in q_lower for w in ["how do i", "how to", "what can", "explain", "features", "documentation", "how does"]):
            tool = COPILOT_TOOL_REGISTRY["get_product_help"]
            res = await tool.handler(db, broker, {"query": query})
            executed_tools.append({"tool_name": "get_product_help", "arguments": {"query": query}})
            citations.append(res.get("_citation", "Product Documentation"))
            article = res.get("results", [{}])[0]
            answer = f"### {article.get('title', 'Product Guide')}\n\n{article.get('content', '')}"
            return answer, executed_tools, citations, None

        # 8. Leads Queries (Default / Fallback)
        score_filter = "hot" if "hot" in q_lower else ("warm" if "warm" in q_lower else None)
        uncontacted = 7 if "7 days" in q_lower else (3 if "3 days" in q_lower else None)

        tool = COPILOT_TOOL_REGISTRY["list_leads"]
        res = await tool.handler(db, broker, {
            "score": score_filter,
            "uncontacted_days": uncontacted,
            "limit": 5
        })
        executed_tools.append({"tool_name": "list_leads", "arguments": {"score": score_filter, "uncontacted_days": uncontacted}})
        citations.append(res.get("_citation", "Live CRM Leads Database"))

        total = res.get("total_matching", 0)
        leads = res.get("leads", [])

        if "how many" in q_lower:
            filter_desc = f" {score_filter.upper()}" if score_filter else ""
            answer = f"You currently have **{total}**{filter_desc} lead(s) in your workspace."
        elif not leads:
            answer = "I searched your CRM database but couldn't find any leads matching those criteria."
        else:
            lines = [
                f"- **{l['name']}** ({l['phone']}) — Score: **{l['score']}**, Stage: *{l['stage'].title()}*, Budget: ₹{l['budget_min']:,.0f}-₹{l['budget_max']:,.0f}"
                for l in leads
            ]
            filter_label = f"**{score_filter.upper()}** " if score_filter else ""
            answer = f"I found **{total}** {filter_label}lead(s) in your CRM:\n\n" + "\n".join(lines)

        return answer, executed_tools, citations, None

    @classmethod
    async def _run_gemini_loop(
        cls,
        db: AsyncSession,
        broker: Broker,
        query: str,
        route_path: str,
        system_instruction: str,
        history: Optional[List[Dict[str, str]]] = None
    ) -> Tuple[str, List[Dict[str, Any]], List[str], Optional[Dict[str, Any]], str]:
        """Executes full Gemini function calling loop with up to MAX_AGENT_ITERATIONS turns."""
        configured_model = getattr(settings, "GEMINI_MODEL", "gemini-3.5-flash")
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{configured_model}:generateContent?key={settings.GEMINI_API_KEY}"

        tools_declarations = get_all_tool_declarations()
        gemini_tools = [{"function_declarations": tools_declarations}]

        # Prepare messages
        contents = []
        if history:
            for h in history[-6:]:
                role = "user" if h.get("sender") == "user" or h.get("role") == "user" else "model"
                text_content = h.get("text") or h.get("content") or ""
                if text_content:
                    contents.append({"role": role, "parts": [{"text": text_content}]})

        contents.append({
            "role": "user",
            "parts": [{"text": f"System Guidelines:\n{system_instruction}\n\nUser Request: {query}"}]
        })

        executed_tools_log = []
        citations = []
        action_preview = None
        final_answer = ""
        reasoning_text = f"Processed request using {configured_model} with function calling."

        async with httpx.AsyncClient(timeout=20.0) as client:
            for iteration in range(MAX_AGENT_ITERATIONS):
                payload = {
                    "contents": contents,
                    "tools": gemini_tools,
                    "generationConfig": {
                        "temperature": 0.2,
                        "maxOutputTokens": 1200
                    }
                }

                try:
                    resp = await client.post(gemini_url, json=payload)
                    if resp.status_code != 200:
                        logger.warning(f"[Copilot Gemini HTTP {resp.status_code}]: {resp.text[:300]}")
                        # Fallback to deterministic tools
                        answer, ex_tools, cits, preview = await cls._dispatch_deterministic_tools(db, broker, query, route_path)
                        return answer, ex_tools, cits, preview, reasoning_text

                    resp_data = resp.json()
                    candidates = resp_data.get("candidates", [])
                    if not candidates:
                        break

                    candidate_part = candidates[0].get("content", {}).get("parts", [{}])[0]

                    # 1. Did Gemini emit a functionCall?
                    function_call = candidate_part.get("functionCall")
                    if function_call:
                        tool_name = function_call.get("name")
                        tool_args = function_call.get("args") or {}

                        if tool_name not in COPILOT_TOOL_REGISTRY:
                            tool_result = {"error": f"Tool '{tool_name}' is not recognized."}
                        else:
                            tool = COPILOT_TOOL_REGISTRY[tool_name]

                            # Check if tool requires confirmation preview
                            if tool.requires_confirmation:
                                token = f"confirm-{uuid.uuid4()}"
                                action_preview = {
                                    "tool_name": tool_name,
                                    "title": f"Confirmation Required: {tool.name.replace('_', ' ').title()}",
                                    "summary": f"Please confirm execution of {tool.name}.",
                                    "impacted_records": 1,
                                    "is_destructive": tool.risk_level == ToolRiskLevel.DESTRUCTIVE,
                                    "confirmation_token": token,
                                    "arguments": tool_args
                                }
                                citations.append(f"Action Guardrail ({tool_name})")
                                final_answer = (
                                    f"⚠️ **Action Confirmation Required:**\n\n"
                                    f"I am ready to execute **{tool_name.replace('_', ' ').title()}** with the provided details. "
                                    f"Would you like me to proceed?"
                                )
                                executed_tools_log.append({"tool_name": tool_name, "arguments": tool_args})
                                return final_answer, executed_tools_log, citations, action_preview, reasoning_text

                            # Execute read / low-risk tool
                            tool_result = await tool.handler(db, broker, tool_args)
                            if "_citation" in tool_result:
                                citations.append(tool_result["_citation"])

                        executed_tools_log.append({"tool_name": tool_name, "arguments": tool_args})

                        # Feed function response back to Gemini for the next turn
                        contents.append({
                            "role": "model",
                            "parts": [{"functionCall": function_call}]
                        })
                        contents.append({
                            "role": "function",
                            "parts": [{
                                "functionResponse": {
                                    "name": tool_name,
                                    "response": {"output": tool_result}
                                }
                            }]
                        })
                        continue

                    # 2. Gemini emitted final text answer
                    text_ans = candidate_part.get("text", "")
                    if text_ans:
                        final_answer = text_ans.strip()
                        break

                except Exception as exc:
                    logger.error(f"[Copilot Gemini Loop Exception]: {exc}")
                    answer, ex_tools, cits, preview = await cls._dispatch_deterministic_tools(db, broker, query, route_path)
                    return answer, ex_tools, cits, preview, reasoning_text

        if not final_answer:
            answer, ex_tools, cits, preview = await cls._dispatch_deterministic_tools(db, broker, query, route_path)
            return answer, ex_tools, cits, preview, reasoning_text

        return final_answer, executed_tools_log, citations, action_preview, reasoning_text

    @classmethod
    def _generate_suggestions(
        cls,
        query: str,
        route_path: str,
        executed_tools: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        q_lower = query.lower()
        action_buttons = []
        suggested_followups = []

        if any(w in q_lower for w in ["lead", "client", "hot"]):
            action_buttons.append({"label": "📋 View Leads Directory", "action_type": "OPEN_PAGE", "payload": {"url": "/dashboard/leads"}})
            action_buttons.append({"label": "⚡ Create Follow-up Task", "action_type": "CREATE_TASK", "payload": {"title": "Follow up with leads", "due_in_hours": 24}})
            suggested_followups = ["Show my hottest leads", "Which leads haven't been contacted in 7 days?", "Create tasks for top leads"]
        elif any(w in q_lower for w in ["plan", "billing", "pricing"]):
            action_buttons.append({"label": "💳 Open Billing Settings", "action_type": "OPEN_PAGE", "payload": {"url": "/dashboard/settings"}})
            suggested_followups = ["Compare Starter and Pro plans", "Explain 7-day trial policy"]
        elif any(w in q_lower for w in ["meeting", "calendar", "viewing"]):
            action_buttons.append({"label": "📅 View Calendar", "action_type": "OPEN_PAGE", "payload": {"url": "/dashboard"}})
            suggested_followups = ["Find an available slot tomorrow", "List all meetings this week"]
        else:
            action_buttons.append({"label": "📋 View Leads", "action_type": "OPEN_PAGE", "payload": {"url": "/dashboard/leads"}})
            action_buttons.append({"label": "📊 Open Pipeline", "action_type": "OPEN_PAGE", "payload": {"url": "/dashboard/pipeline"}})
            suggested_followups = ["How many leads do I have?", "What tasks do I have today?", "Show my hottest leads"]

        return action_buttons, suggested_followups

    @classmethod
    async def _save_messages(
        cls,
        db: AsyncSession,
        conv: CopilotConversation,
        user_content: str,
        copilot_content: str,
        reasoning: Optional[str] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        citations: Optional[List[str]] = None,
        action_preview: Optional[Dict[str, Any]] = None
    ) -> None:
        try:
            user_msg = CopilotMessage(
                id=uuid.uuid4(),
                conversation_id=conv.id,
                sender="user",
                content=user_content
            )
            await _safe_add(db, user_msg)

            copilot_msg = CopilotMessage(
                id=uuid.uuid4(),
                conversation_id=conv.id,
                sender="copilot",
                content=copilot_content,
                thought_reasoning=reasoning,
                tool_calls=tool_calls,
                citations=[{"source": c} for c in (citations or [])],
                action_preview=action_preview
            )
            await _safe_add(db, copilot_msg)
            conv.updated_at = datetime.now(timezone.utc)
            await _safe_commit(db)
        except Exception as exc:
            logger.warning(f"[Copilot Message Persistence Error]: {exc}")
            try:
                res = db.rollback()
                if inspect.isawaitable(res):
                    await res
            except Exception:
                pass
