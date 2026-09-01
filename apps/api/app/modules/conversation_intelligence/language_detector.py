"""
Part 21.7 — Multilingual Language Detector
=========================================
Determines the language of an inbound customer communication.
Supports:
- English ('en')
- Arabic ('ar') via Unicode script detection (0x0600 - 0x06FF)
- Hindi ('hi') via Devanagari Unicode (0x0900 - 0x097F) and romanized conversational cues
"""
from __future__ import annotations
import re


ARABIC_PATTERN = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+")
DEVANAGARI_HINDI_PATTERN = re.compile(r"[\u0900-\u097F]+")

ROMANIZED_HINDI_CUES = {
    "namaste", "chahiye", "hai", "kya", "shukriya", "bhai", "kitna", "dekho",
    "bataye", "karo", "acha", "theek", "paiso", "makan", "ghar", "kiraya", "kharidna"
}

ARABIC_TRANSLITERATED_CUES = {
    "marhaba", "shukran", "salam", "kam", "ayn", "uridu", "mumkin", "habibi"
}


class LanguageDetector:
    """Accurate, zero-network language detector for real-estate interactions."""

    @staticmethod
    def detect_language(text: str) -> str:
        if not text or not text.strip():
            return "en"

        cleaned = text.strip()

        # 1. Check Arabic Unicode Script
        if ARABIC_PATTERN.search(cleaned):
            return "ar"

        # 2. Check Hindi / Devanagari Script
        if DEVANAGARI_HINDI_PATTERN.search(cleaned):
            return "hi"

        # 3. Check Romanized / Transliterated keywords
        words = set(re.findall(r"\b\w+\b", cleaned.lower()))
        if words & ROMANIZED_HINDI_CUES:
            return "hi"
        if words & ARABIC_TRANSLITERATED_CUES:
            return "ar"

        return "en"
