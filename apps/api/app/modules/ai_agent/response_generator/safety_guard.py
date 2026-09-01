"""
Response Safety Guard — validates every LLM response before it reaches the buyer.

Checks (in order):
  1. Hallucination check: any price/availability claim must be tagged with a tool source
  2. Policy check: no financial advice, legal guarantees, or competitor mentions
  3. PII filter: no unmasked phone numbers or email addresses in outbound messages
  4. Tone check: detect aggressive or unprofessional language
  5. Length check: enforce channel-appropriate response length

If any check fails, the response is blocked and a safe fallback is returned.
All violations are logged for monitoring (hallucination_incidents counter).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.modules.ai_agent.tool_executor.executor import ToolResult


# ─── Safety Result ────────────────────────────────────────────────────────────

@dataclass
class SafetyResult:
    approved: bool
    final_content: str              # Approved or replaced content
    violations: List[str]           # List of violation codes
    was_modified: bool = False      # True if content was sanitized (not fully blocked)
    was_blocked: bool = False       # True if blocked and replaced with safe fallback


# ─── Patterns ─────────────────────────────────────────────────────────────────

# Price/number patterns that could be hallucinated
_PRICE_PATTERN = re.compile(
    r"\b(?:AED|USD|GBP|INR|SGD|AUD|CAD|EUR|RM)\s*[\d,]+(?:\.\d{2})?\b"
    r"|\b[\d,]+(?:\.\d{2})?\s*(?:dirhams?|dollars?|pounds?|rupees?)\b",
    re.IGNORECASE,
)

# PII patterns
_PHONE_PATTERN = re.compile(r"\+?\d[\d\s\-().]{8,}\d")
_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Policy violation patterns
_FINANCIAL_ADVICE_PATTERNS = [
    r"guaranteed return", r"will definitely appreciate", r"price will go up",
    r"safe investment", r"can't lose", r"risk.?free", r"certain profit",
]
_LEGAL_GUARANTEE_PATTERNS = [
    r"legally guarantee", r"i guarantee", r"we guarantee", r"100% legal",
    r"no legal issues", r"legally binding",
]
_COMPETITOR_PATTERNS = [
    r"\bsalesforce\b", r"\bhubspot\b", r"\bzoho\b", r"\bproppilot\b",
    r"\bproptiger\b", r"\bmagicbricks\b",
]
_AGGRESSIVE_PATTERNS = [
    r"\bstupid\b", r"\bidiot\b", r"\bfool\b", r"\bliar\b", r"\bworthless\b",
]

# Channel max response lengths (chars)
_CHANNEL_MAX_LENGTHS: Dict[str, int] = {
    "whatsapp": 1000,
    "telegram": 1500,
    "web": 3000,
    "email": 5000,
    "default": 1500,
}

_SAFE_FALLBACK = (
    "I want to make sure I give you accurate information. "
    "Let me connect you with a specialist who can confirm the exact details for you."
)


class ResponseSafetyGuard:
    """
    Validates and optionally sanitizes LLM responses before delivery.
    """

    def __init__(self, require_tool_grounding: bool = True):
        self.require_tool_grounding = require_tool_grounding

    def validate(
        self,
        content: str,
        tool_results: List[ToolResult],
        channel: str = "web",
    ) -> SafetyResult:
        """
        Run all safety checks on the response content.
        Returns SafetyResult with approved content or safe fallback.
        """
        violations: List[str] = []
        modified = content

        # ── 1. Hallucination check ──────────────────────────────────────────
        if self.require_tool_grounding:
            price_mentions = _PRICE_PATTERN.findall(content)
            if price_mentions:
                # Check if any tool_result has verified price data
                verified_sources = {r.data_source for r in tool_results if r.success and r.source_verified}
                has_verified_source = bool(verified_sources & {"property_service", "crm_service"})
                if not has_verified_source:
                    violations.append("HALLUCINATION_PRICE_UNVERIFIED")
                    return SafetyResult(
                        approved=False,
                        final_content=_SAFE_FALLBACK,
                        violations=violations,
                        was_blocked=True,
                    )

        # ── 2. Financial advice check ───────────────────────────────────────
        content_lower = content.lower()
        for pattern in _FINANCIAL_ADVICE_PATTERNS:
            if re.search(pattern, content_lower):
                violations.append("POLICY_FINANCIAL_ADVICE")
                return SafetyResult(
                    approved=False,
                    final_content=(
                        "I appreciate your question. For investment projections and financial advice, "
                        "I'd recommend consulting with a certified financial advisor. "
                        "I can share verified market data — would that help?"
                    ),
                    violations=violations,
                    was_blocked=True,
                )

        # ── 3. Legal guarantee check ────────────────────────────────────────
        for pattern in _LEGAL_GUARANTEE_PATTERNS:
            if re.search(pattern, content_lower):
                violations.append("POLICY_LEGAL_GUARANTEE")
                return SafetyResult(
                    approved=False,
                    final_content=_SAFE_FALLBACK,
                    violations=violations,
                    was_blocked=True,
                )

        # ── 4. Competitor mention check ─────────────────────────────────────
        for pattern in _COMPETITOR_PATTERNS:
            if re.search(pattern, content_lower):
                violations.append("POLICY_COMPETITOR_MENTION")
                # Sanitize by removing the sentence containing the competitor name
                modified = re.sub(r"[^.!?]*" + pattern + r"[^.!?]*[.!?]", "", modified, flags=re.IGNORECASE)
                if not modified.strip():
                    modified = "We focus on providing the best solution for your needs!"

        # ── 5. PII filter ───────────────────────────────────────────────────
        if _PHONE_PATTERN.search(modified):
            violations.append("PII_PHONE_DETECTED")
            modified = _PHONE_PATTERN.sub("[contact details withheld]", modified)

        if _EMAIL_PATTERN.search(modified):
            violations.append("PII_EMAIL_DETECTED")
            modified = _EMAIL_PATTERN.sub("[email withheld]", modified)

        # ── 6. Aggressive language check ────────────────────────────────────
        for pattern in _AGGRESSIVE_PATTERNS:
            if re.search(pattern, modified, re.IGNORECASE):
                violations.append("TONE_AGGRESSIVE_LANGUAGE")
                return SafetyResult(
                    approved=False,
                    final_content=_SAFE_FALLBACK,
                    violations=violations,
                    was_blocked=True,
                )

        # ── 7. Length enforcement ───────────────────────────────────────────
        max_len = _CHANNEL_MAX_LENGTHS.get(channel, _CHANNEL_MAX_LENGTHS["default"])
        if len(modified) > max_len:
            violations.append(f"LENGTH_EXCEEDED_{channel.upper()}")
            # Truncate at last sentence boundary within limit
            truncated = modified[:max_len]
            last_sentence = max(
                truncated.rfind("."),
                truncated.rfind("!"),
                truncated.rfind("?"),
            )
            if last_sentence > max_len // 2:
                modified = truncated[:last_sentence + 1]
            else:
                modified = truncated + "..."

        was_modified = modified != content
        return SafetyResult(
            approved=True,
            final_content=modified,
            violations=violations,
            was_modified=was_modified,
            was_blocked=False,
        )
