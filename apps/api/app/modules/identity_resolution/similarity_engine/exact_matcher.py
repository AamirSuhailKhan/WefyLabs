"""
Exact Matcher — Deterministic first-pass matcher.
Handles: E.164 phone, lowercased email, normalized strings.
Fastest algorithm — O(1) comparison. Confidence = 1.0 on match.
"""
import re
from typing import Optional
from .base_algorithm import BaseSimilarityAlgorithm


class ExactMatcher(BaseSimilarityAlgorithm):
    name = "exact"

    def score(self, value_a: Optional[str], value_b: Optional[str]) -> float:
        if not value_a or not value_b:
            return 0.0
        return 1.0 if self._normalize(value_a) == self._normalize(value_b) else 0.0

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().lower()


class NormalizedPhoneMatcher(BaseSimilarityAlgorithm):
    """
    Normalized phone matcher for E.164 format comparison.
    Strips non-digit characters, compares last 9 digits (handles country code variations).
    """
    name = "normalized_phone"
    supports_fields = ["phone", "whatsapp", "telegram_phone"]

    def score(self, value_a: Optional[str], value_b: Optional[str]) -> float:
        if not value_a or not value_b:
            return 0.0
        digits_a = self._digits_only(value_a)
        digits_b = self._digits_only(value_b)
        if not digits_a or not digits_b:
            return 0.0
        # Full digit match
        if digits_a == digits_b:
            return 1.0
        # Last 9 digits match (handles different country code representations)
        if len(digits_a) >= 9 and len(digits_b) >= 9:
            if digits_a[-9:] == digits_b[-9:]:
                return 0.95
        return 0.0

    @staticmethod
    def _digits_only(value: str) -> str:
        return re.sub(r"\D", "", value)


class NormalizedEmailMatcher(BaseSimilarityAlgorithm):
    """
    Normalized email matcher. Strips dots from Gmail local part, handles + aliases.
    """
    name = "normalized_email"
    supports_fields = ["email"]

    def score(self, value_a: Optional[str], value_b: Optional[str]) -> float:
        if not value_a or not value_b:
            return 0.0
        norm_a = self._normalize_email(value_a)
        norm_b = self._normalize_email(value_b)
        if norm_a == norm_b:
            return 1.0
        # Check without + aliases (user+alias@domain.com → user@domain.com)
        if self._strip_alias(norm_a) == self._strip_alias(norm_b):
            return 0.95
        return 0.0

    @staticmethod
    def _normalize_email(email: str) -> str:
        email = email.strip().lower()
        if "@" not in email:
            return email
        local, domain = email.split("@", 1)
        # Gmail: dots in local part are ignored
        if "gmail.com" in domain:
            local = local.replace(".", "")
        return f"{local}@{domain}"

    @staticmethod
    def _strip_alias(email: str) -> str:
        if "+" in email and "@" in email:
            local, domain = email.split("@", 1)
            local = local.split("+")[0]
            return f"{local}@{domain}"
        return email
