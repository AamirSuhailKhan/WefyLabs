import json
import re
import logging
import httpx
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from app.config import settings
from app.services.lead_scorer import calculate_lead_score

logger = logging.getLogger(__name__)

LEAD_QUALIFICATION_PROMPT = """
You are a professional real estate lead qualification assistant working for a broker in India.
Your job is to analyze a conversation between a bot and a property lead, extract key information, and score the lead.

SCORING CRITERIA:
- HOT: Budget is clear and matches broker's market, timeline is < 1 month, location is specific, transaction type is clear (buy/rent), ready to view properties.
- WARM: Budget is approximate or slightly flexible, timeline is 1-3 months, location is known, interested but needs nurturing.
- COLD: No clear budget, timeline > 3 months or vague, location uncertain, just browsing.
- SPAM: Fake number, abusive, clearly not interested in real estate.

EXTRACTION RULES:
- budget_min / budget_max: Extract numeric values in INR. If range given (e.g. "40-50 lakhs"), min=4000000, max=5000000. If "around 1 crore", min=9000000, max=11000000. If not mentioned, set to null. NEVER fabricate a budget.
- property_type: Map to 1bhk, 2bhk, 3bhk, 4bhk_plus, villa, plot, commercial, or null.
- transaction_type: buy, rent, lease, or null.
- preferred_locations: Extract all mentioned areas/localities as a JSON array of strings. If none mentioned, return [].
- timeline: immediate, 1_month, 3_months, 6_months, flexible, or null.
- loan_status: pre_approved, in_process, not_started, not_needed, or null.
- reasoning: 1-2 sentence explanation of the score based strictly on actual conversation evidence.

RESPONSE FORMAT (strict JSON):
{
  "score": "hot|warm|cold|spam",
  "confidence": 0.0-1.0,
  "reasoning": "string",
  "extracted_data": {
    "budget_min": integer or null,
    "budget_max": integer or null,
    "property_type": "string" or null,
    "transaction_type": "string" or null,
    "preferred_locations": ["string"],
    "timeline": "string" or null,
    "loan_status": "string" or null
  },
  "recommended_action": "string",
  "follow_up_needed": true|false
}
"""

QUALIFICATION_SYSTEM_PROMPT_TEMPLATE = """You are BeetleLabs AI, a friendly real estate assistant helping {broker_name} from {agency_name} in {city}. 
You are chatting with a potential property buyer/renter on WhatsApp.

Your goals:
1. Qualify the lead by gathering: budget, location, property type, transaction type, timeline, loan status
2. Be conversational and brief (under 160 characters per message when possible)
3. Speak in English only (for MVP)
4. Never be pushy. If lead says "not interested", thank them and end.
5. After gathering sufficient info, say: "Thanks! {broker_name} will call you shortly."
6. NEVER fabricate property details or budgets. If the user did not specify a value, leave it null.

Current extracted data: {current_extracted_data}
Conversation history: {last_5_messages}
Lead message: {latest_message}

Respond ONLY with a valid JSON object:
{{
  "response_message": "string",
  "extracted_data": {{
    "budget_min": number|null,
    "budget_max": number|null,
    "preferred_locations": string[]|null,
    "property_type": string|null,
    "transaction_type": string|null,
    "timeline": string|null,
    "loan_status": string|null
  }},
  "qualification_complete": boolean,
  "end_conversation": boolean
}}"""


class ExtractedLeadData(BaseModel):
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    preferred_locations: Optional[List[str]] = None
    property_type: Optional[str] = None
    transaction_type: Optional[str] = None
    timeline: Optional[str] = None
    loan_status: Optional[str] = None


class AIQualificationResponseModel(BaseModel):
    response_message: str
    extracted_data: ExtractedLeadData
    qualification_complete: bool = False
    end_conversation: bool = False


def sanitize_user_input(text: str) -> str:
    """Sanitizes user input messages to prevent prompt injection and control character issues."""
    if not text:
        return ""
    clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    clean = clean.replace("```", "").strip()
    return clean[:1000]


async def generate_ai_qualification_response(
    broker_name: str,
    agency_name: str,
    city: str,
    current_extracted_data: Dict[str, Any],
    history: List[Dict[str, str]],
    latest_message: str
) -> Dict[str, Any]:
    """
    Generates conversational qualification response using Google Gemini API.
    If Gemini is unconfigured or encounters an error, falls back to a clean deterministic rule engine
    without fabricating any user information.
    """
    safe_latest_message = sanitize_user_input(latest_message)
    formatted_prompt = QUALIFICATION_SYSTEM_PROMPT_TEMPLATE.format(
        broker_name=broker_name or "our team",
        agency_name=agency_name or "Premier Realty",
        city=city or "Bengaluru",
        current_extracted_data=json.dumps(current_extracted_data or {}),
        last_5_messages=json.dumps(history[-5:] if history else []),
        latest_message=safe_latest_message
    )

    # 1. Primary: Google Gemini API (Configurable model, e.g. gemini-3.5-flash)
    if settings.GEMINI_API_KEY and not settings.GEMINI_API_KEY.startswith("AIzaSy_placeholder") and not settings.GEMINI_API_KEY.startswith("placeholder"):
        model_name = getattr(settings, "GEMINI_MODEL", "gemini-3.5-flash")
        try:
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={settings.GEMINI_API_KEY}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": formatted_prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    "response_mime_type": "application/json"
                }
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(gemini_url, json=payload)
                if res.status_code == 200:
                    res_json = res.json()
                    candidates = res_json.get("candidates", [])
                    if candidates:
                        raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        if "```json" in raw_text:
                            raw_text = raw_text.split("```json")[1].split("```")[0]
                        parsed = json.loads(raw_text.strip())
                        if "response_message" in parsed:
                            logger.info(f"[Gemini AI Success: {model_name}] Extracted & Qualified")
                            return parsed
                elif res.status_code == 429:
                    logger.warning("[Gemini AI Rate Limit / Quota Exceeded (429)] Using clean deterministic fallback.")
                else:
                    logger.warning(f"[Gemini AI API Error: {res.status_code}] {res.text}")
        except Exception as e:
            logger.warning(f"[Gemini AI Service Error] {e}. Falling back to clean deterministic rule engine.")

    # 2. Clean Deterministic Fallback (Never fabricates data)
    return fallback_qualification_response(broker_name, latest_message, current_extracted_data)


def fallback_qualification_response(
    broker_name: str,
    latest_message: str,
    current_extracted: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Deterministic rule engine for lead qualification when AI is unavailable.
    Strictly extracts ONLY what is present in the message. Never fabricates missing values.
    """
    msg = latest_message.lower()
    updated = dict(current_extracted or {})

    # Check for opt-out / not interested
    if any(term in msg for term in ["not interested", "stop", "no thanks", "don't call", "unsubscribe"]):
        return {
            "response_message": "Thank you for letting us know! Have a great day.",
            "extracted_data": updated,
            "qualification_complete": False,
            "end_conversation": True
        }

    # Extract property type if explicitly mentioned
    for ptype in ["1bhk", "2bhk", "3bhk", "4bhk", "villa", "plot", "commercial"]:
        if ptype in msg:
            updated["property_type"] = ptype
            break

    # Extract transaction type
    if "buy" in msg or "purchase" in msg:
        updated["transaction_type"] = "buy"
    elif "rent" in msg or "lease" in msg:
        updated["transaction_type"] = "rent"

    # Guide next question based on missing fields without fabricating data
    if not updated.get("property_type"):
        resp_msg = "Hi! Thanks for reaching out. What property configuration are you looking for (1BHK, 2BHK, 3BHK, Villa, Plot)?"
        complete = False
    elif not updated.get("transaction_type"):
        resp_msg = "Got it! Are you looking to buy or rent?"
        complete = False
    elif not updated.get("budget_max") and not updated.get("budget_min"):
        resp_msg = "Great! What is your approximate budget range?"
        complete = False
    elif not updated.get("preferred_locations"):
        resp_msg = "Which localities or areas do you prefer?"
        complete = False
    elif not updated.get("timeline"):
        resp_msg = "When are you planning to move or finalize the purchase?"
        complete = False
    else:
        resp_msg = f"Thanks! {broker_name} will call you shortly with matching options."
        complete = True

    return {
        "response_message": resp_msg,
        "extracted_data": updated,
        "qualification_complete": complete,
        "end_conversation": complete
    }


async def analyze_lead_conversation(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Analyzes full conversation transcript for final scoring using Google Gemini.
    If Gemini is unavailable, returns an honest error without fabricating lead data.
    """
    transcript_text = "\n".join([f"{msg.get('sender', 'USER').upper()}: {msg.get('text', '')}" for msg in messages])

    # Primary: Google Gemini API
    if settings.GEMINI_API_KEY and not settings.GEMINI_API_KEY.startswith("AIzaSy_placeholder") and not settings.GEMINI_API_KEY.startswith("placeholder"):
        model_name = getattr(settings, "GEMINI_MODEL", "gemini-3.5-flash")
        try:
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={settings.GEMINI_API_KEY}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": f"{LEAD_QUALIFICATION_PROMPT}\n\nTranscript:\n{transcript_text}"}
                        ]
                    }
                ],
                "generationConfig": {
                    "response_mime_type": "application/json"
                }
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(gemini_url, json=payload)
                if res.status_code == 200:
                    res_json = res.json()
                    candidates = res_json.get("candidates", [])
                    if candidates:
                        raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        if "```json" in raw_text:
                            raw_text = raw_text.split("```json")[1].split("```")[0]
                        parsed = json.loads(raw_text.strip())
                        if "score" in parsed:
                            logger.info(f"[Gemini AI Lead Analysis Success: {model_name}]")
                            return parsed
                elif res.status_code == 429:
                    logger.warning("[Gemini AI Rate Limit / Quota Exceeded (429)] during conversation analysis.")
                else:
                    logger.warning(f"[Gemini AI Analysis Error: {res.status_code}] {res.text}")
        except Exception as e:
            logger.warning(f"[Gemini AI Analysis Error] {e}.")

    # Honest error return when AI is unavailable — NEVER fabricate CRM information
    logger.warning("[AI Service] Gemini unavailable for transcript analysis. Returning honest unanalyzed status.")
    return {
        "score": "cold",
        "confidence": 0.0,
        "reasoning": "AI analysis service is currently unavailable. No lead facts fabricated.",
        "extracted_data": {
            "budget_min": None,
            "budget_max": None,
            "property_type": None,
            "transaction_type": None,
            "preferred_locations": [],
            "timeline": None,
            "loan_status": None
        },
        "recommended_action": "Review conversation transcript manually.",
        "follow_up_needed": False
    }
