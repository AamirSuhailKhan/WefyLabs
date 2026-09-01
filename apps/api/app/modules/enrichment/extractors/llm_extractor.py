"""
Volume 2 PART 2 — LLM Extractor (Via Google Gemini API)
"""
import os
import json
import logging
from typing import Dict, Any, Optional
import httpx
from app.modules.enrichment.extractors.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)


class LLMExtractor(BaseExtractor):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

    def extract(self, text_content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Uses Google Gemini JSON mode for unstructured note extractions.
        """
        if not text_content or not self.api_key:
            logger.info("[LLMExtractor] Skipping LLM extraction: No text or API key.")
            return {"token_cost": 0.0}

        prompt = f"""
        Extract real estate lead parameters from the text below as strict JSON.
        Fields to infer:
        - full_name (string or null)
        - occupation (string or null)
        - company (string or null)
        - budget_min (number or null)
        - budget_max (number or null)
        - property_type (one of: '1bhk', '2bhk', '3bhk', 'villa', 'plot' or null)
        - bedrooms (number or null)
        - preferred_locations (array of strings)
        - purpose (one of: 'investment', 'end_user' or null)
        - timeline (one of: 'immediate', '1_month', '3_months', '6_months' or null)
        - financing_required (boolean or null)
        - ai_summary (short 1-2 sentence executive summary of buyer intent)
        - ai_recommendations (array of 2-3 sales action items for real estate broker)

        Text: "{text_content}"
        """

        try:
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
            payload = {
                "contents": [
                    {
                        "parts": [{"text": prompt}]
                    }
                ],
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "temperature": 0.1,
                    "maxOutputTokens": 600
                }
            }

            with httpx.Client(timeout=10.0) as client:
                res = client.post(gemini_url, json=payload)

                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        if "```json" in raw_text:
                            raw_text = raw_text.split("```json")[1].split("```")[0]
                        parsed = json.loads(raw_text.strip())
                        parsed["token_cost"] = 0.0  # Free tier / low cost
                        parsed["llm_confidence"] = 0.90
                        return parsed
        except Exception as e:
            logger.warning(f"[LLMExtractor] Gemini extraction failed: {e}")

        return {"token_cost": 0.0}
