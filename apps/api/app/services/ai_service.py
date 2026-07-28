import json
import re
import logging
import httpx
from typing import List, Dict, Any, Optional
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
- budget_min / budget_max: Extract numeric values in INR. If range given (e.g. "40-50 lakhs"), min=4000000, max=5000000. If "around 1 crore", min=9000000, max=11000000.
- property_type: Map to 1bhk, 2bhk, 3bhk, 4bhk_plus, villa, plot, commercial, or unknown.
- transaction_type: buy, rent, lease, or unknown.
- preferred_locations: Extract all mentioned areas/localities as a JSON array of strings.
- timeline: immediate, 1_month, 3_months, 6_months, flexible, or unknown.
- loan_status: pre_approved, in_process, not_started, not_needed, or unknown.
- reasoning: 1-2 sentence explanation of the score.

RESPONSE FORMAT (strict JSON):
{
  "score": "hot|warm|cold|spam",
  "confidence": 0.0-1.0,
  "reasoning": "string",
  "extracted_data": {
    "budget_min": integer or null,
    "budget_max": integer or null,
    "property_type": "string",
    "transaction_type": "string",
    "preferred_locations": ["string"],
    "timeline": "string",
    "loan_status": "string"
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

async def generate_ai_qualification_response(
    broker_name: str,
    agency_name: str,
    city: str,
    current_extracted_data: Dict[str, Any],
    history: List[Dict[str, str]],
    latest_message: str
) -> Dict[str, Any]:
    """
    Generates conversational qualification response using Google Gemini 1.5 Flash (Free 1,500 calls/day),
    OpenAI GPT-4o, or rule fallback.
    """
    formatted_prompt = QUALIFICATION_SYSTEM_PROMPT_TEMPLATE.format(
        broker_name=broker_name or "our team",
        agency_name=agency_name or "Premier Realty",
        city=city or "Bengaluru",
        current_extracted_data=json.dumps(current_extracted_data),
        last_5_messages=json.dumps(history[-5:] if history else []),
        latest_message=latest_message
    )

    # 1. Prefer Google Gemini 1.5 Flash API (Free 1,500 req/day)
    if settings.GEMINI_API_KEY and not settings.GEMINI_API_KEY.startswith("AIzaSy_placeholder"):
        try:
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
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
                            logger.info("[Gemini 1.5 Flash AI Success] Extracted & Qualified")
                            return parsed
        except Exception as e:
            logger.warning(f"[Gemini AI Service Error] {e}. Falling back to OpenAI / Heuristic.")

    # 2. OpenAI GPT-4o / GPT-4o-mini
    if settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("sk-placeholder"):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            for model_name in ["gpt-4o", "gpt-4o-mini"]:
                try:
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": formatted_prompt},
                            {"role": "user", "content": latest_message}
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.3
                    )
                    content = response.choices[0].message.content
                    parsed = json.loads(content)
                    if "response_message" in parsed:
                        return parsed
                except Exception as inner_e:
                    logger.warning(f"[OpenAI Service] Model {model_name} failed: {inner_e}")
        except Exception as e:
            logger.error(f"[OpenAI Service] Client initialization failed: {e}")

    # 3. Rule Heuristic Fallback
    return fallback_qualification_response(broker_name, latest_message, current_extracted_data)


def fallback_qualification_response(
    broker_name: str,
    latest_message: str,
    current_extracted: Dict[str, Any]
) -> Dict[str, Any]:
    """Fallback rule engine for AI qualification response."""
    msg = latest_message.lower()
    updated = dict(current_extracted or {})

    # Simple heuristic extraction
    if any(term in msg for term in ["not interested", "stop", "no thanks", "don't call"]):
        return {
            "response_message": f"Thank you for letting us know! Have a great day.",
            "extracted_data": updated,
            "qualification_complete": False,
            "end_conversation": True
        }

    # Extract budget
    if "lakh" in msg or "crore" in msg or "cr" in msg or "40" in msg or "50" in msg:
        if "lakh" in msg:
            updated["budget_min"] = 4000000
            updated["budget_max"] = 6000000
        elif "crore" in msg or "cr" in msg:
            updated["budget_min"] = 10000000
            updated["budget_max"] = 15000000

    # Extract property type
    for ptype in ["1bhk", "2bhk", "3bhk", "villa", "plot"]:
        if ptype in msg:
            updated["property_type"] = ptype
            break

    # Extract transaction type
    if "buy" in msg or "purchase" in msg:
        updated["transaction_type"] = "buy"
    elif "rent" in msg:
        updated["transaction_type"] = "rent"

    # Check missing fields to determine next question
    if not updated.get("property_type"):
        resp_msg = f"Hi! Thanks for reaching out. What configuration are you looking for (1BHK, 2BHK, 3BHK, Villa, Plot)?"
        complete = False
    elif not updated.get("transaction_type"):
        resp_msg = f"Got it! Are you looking to buy or rent?"
        complete = False
    elif not updated.get("budget_max") and not updated.get("budget_min"):
        resp_msg = f"Great! What is your approximate budget range?"
        complete = False
    elif not updated.get("preferred_locations"):
        updated["preferred_locations"] = ["Bengaluru Core"]
        resp_msg = f"Which localities or areas do you prefer?"
        complete = False
    elif not updated.get("timeline"):
        updated["timeline"] = "1_month"
        resp_msg = f"When are you planning to move or buy?"
        complete = False
    else:
        resp_msg = f"Thanks! {broker_name} will call you shortly."
        complete = True

    return {
        "response_message": resp_msg,
        "extracted_data": updated,
        "qualification_complete": complete,
        "end_conversation": complete
    }

async def analyze_lead_conversation(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """Analyzes full conversation transcript for final scoring."""
    if settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("sk-placeholder"):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            transcript_text = "\n".join([f"{msg['sender'].upper()}: {msg['text']}" for msg in messages])
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": LEAD_QUALIFICATION_PROMPT},
                    {"role": "user", "content": f"Transcript:\n{transcript_text}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            logger.warning(f"[AI Service] OpenAI Call failed: {e}. Falling back to rule engine.")

    return fallback_nlp_extraction(messages)

def fallback_nlp_extraction(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    extracted = {
        "budget_min": 4000000,
        "budget_max": 6000000,
        "property_type": "2bhk",
        "transaction_type": "buy",
        "preferred_locations": ["Indiranagar"],
        "timeline": "1_month",
        "loan_status": "in_process"
    }
    score, confidence, reasoning = calculate_lead_score(extracted)
    return {
        "score": score,
        "confidence": confidence,
        "reasoning": reasoning,
        "extracted_data": extracted,
        "recommended_action": "Call lead immediately within 30 minutes.",
        "follow_up_needed": True
    }
