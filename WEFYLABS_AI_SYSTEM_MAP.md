# WEFYLABS AI SYSTEM MAP

| System | Provider/path | Purpose | Status | Key gap |
|---|---|---|---|---|
| AI router | `modules/ai_agent/llm_router` Gemini/OpenAI/Anthropic/Azure adapters | abstraction/tool-capable calls | PARTIALLY IMPLEMENTED | optional providers not declared/verified |
| Qualification | `lead_qualification/extractor.py` | extract proposed buyer facts | CODE + fallback | direct calls / policy proof needed |
| Copilot | `modules/copilot/engine/copilot_agent.py` | internal agent/tool loop | PARTIALLY IMPLEMENTED | tool authorization audit incomplete |
| Legacy AI service | `services/ai_service.py` | lead scoring/conversation | CODE | bypasses gateway |
| Re-engagement | `follow_up/ai_reengagement` | draft outreach | CODE | deterministic fallback; delivery unverified |
| Command center | `command_center/briefing_service.py` | summary from structured facts | CODE | live LLM unverified |
| Knowledge/RAG | knowledge models/workers + pgvector SQL | retrieval/citations | PARTIALLY IMPLEMENTED | response effect unknown |
| Revenue autopilot | opportunity/outreach modules | action prioritization | CODE + selected tests | production outcome validation absent |

No system can be classified as a verified customer-facing autonomous agent yet. Required proof: one real channel, authoritative inventory retrieval, qualification, appointment booking, CRM mutation, human handoff, and audited consent/authorization in a staging environment.
