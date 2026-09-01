"""
Volume 2 PART 2 — Dictionary Extractor
"""
from typing import Dict, Any
from app.modules.enrichment.extractors.base_extractor import BaseExtractor

LANGUAGES = {
    "english": "English", "en": "English",
    "arabic": "Arabic", "ar": "Arabic",
    "hindi": "Hindi", "hi": "Hindi",
    "french": "French", "fr": "French",
    "russian": "Russian", "ru": "Russian",
    "chinese": "Chinese", "zh": "Chinese",
    "german": "German", "de": "German",
    "spanish": "Spanish", "es": "Spanish",
}

OCCUPATIONS = [
    "doctor", "engineer", "software engineer", "pilot", "consultant",
    "lawyer", "banker", "executive", "ceo", "founder", "manager",
    "architect", "investor", "entrepreneur", "trader"
]


class DictionaryExtractor(BaseExtractor):
    def extract(self, text_content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        if not text_content:
            return {}

        text = text_content.lower()
        extracted = {}

        # Language detection
        for kw, lang_name in LANGUAGES.items():
            if f"speak {kw}" in text or f"language: {kw}" in text or f"in {kw}" in text:
                extracted["language"] = lang_name
                extracted["language_confidence"] = 0.85
                break

        # Occupation detection
        for occ in OCCUPATIONS:
            if occ in text:
                extracted["occupation"] = occ.title()
                extracted["occupation_confidence"] = 0.80
                break

        return extracted
