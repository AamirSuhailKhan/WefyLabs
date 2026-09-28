"""
WefyLabs AI Governance, Model Allowlist & Autonomy Guard Engine
===============================================================
Build 11 Enterprise AI Governance:
1. Model Allowlist Enforcement:
   - Approved production models: gemini-1.5-flash, gemini-1.5-pro, gemini-2.0-flash, gemini-2.5-flash, gemini-3.5-flash
   - Unapproved models fail closed.
2. AI Autonomy Governance:
   - 9 Governed Domains: FAQ, QUALIFICATION, PROPERTY_RECOMMENDATION, MESSAGE_DRAFTING,
     MESSAGE_SENDING, APPOINTMENT, NEGOTIATION, BOOKING, PAYMENT
   - 4 Autonomy Levels: DISABLED, SUGGEST, CONFIRM, AUTONOMOUS
   - Strict invariant: Financial actions (BOOKING, PAYMENT) require CONFIRM or DISABLED by default.
3. Prompt Injection & Jailbreak Defense:
   - Multi-layer regex and heuristic pattern neutralizing.
   - Enforces untrusted boundary delimiters for user and external data.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Dict, Any, Optional, Tuple, Set
from fastapi import HTTPException, status


APPROVED_AI_MODELS: set[str] = {
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-3.5-flash",
}


class ModelNotApprovedError(HTTPException):
    def __init__(self, model_name: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "MODEL_NOT_APPROVED",
                "message": f"Model '{model_name}' is not in the approved production allowlist.",
                "allowed_models": sorted(list(APPROVED_AI_MODELS)),
            }
        )


def validate_model_allowed(model_name: str) -> str:
    """Enforces that the requested LLM model is explicitly on the enterprise allowlist."""
    norm = (model_name or "").strip().lower()
    if norm not in APPROVED_AI_MODELS:
        raise ModelNotApprovedError(model_name)
    return norm


class AIAutonomyDomain(str, Enum):
    FAQ = "FAQ"
    QUALIFICATION = "QUALIFICATION"
    PROPERTY_RECOMMENDATION = "PROPERTY_RECOMMENDATION"
    MESSAGE_DRAFTING = "MESSAGE_DRAFTING"
    MESSAGE_SENDING = "MESSAGE_SENDING"
    APPOINTMENT = "APPOINTMENT"
    NEGOTIATION = "NEGOTIATION"
    BOOKING = "BOOKING"
    PAYMENT = "PAYMENT"


class AutonomyLevel(str, Enum):
    DISABLED = "DISABLED"      # Feature inactive
    SUGGEST = "SUGGEST"        # AI produces recommendation/draft for human
    CONFIRM = "CONFIRM"        # AI prepares action; human must approve prior to execution
    AUTONOMOUS = "AUTONOMOUS"  # AI executes automatically within business rules


# Default Enterprise Autonomy Baseline (Safe by Default)
DEFAULT_AUTONOMY_POLICY: dict[str, AutonomyLevel] = {
    AIAutonomyDomain.FAQ.value: AutonomyLevel.AUTONOMOUS,
    AIAutonomyDomain.QUALIFICATION.value: AutonomyLevel.AUTONOMOUS,
    AIAutonomyDomain.PROPERTY_RECOMMENDATION.value: AutonomyLevel.AUTONOMOUS,
    AIAutonomyDomain.MESSAGE_DRAFTING.value: AutonomyLevel.AUTONOMOUS,
    AIAutonomyDomain.MESSAGE_SENDING.value: AutonomyLevel.CONFIRM,
    AIAutonomyDomain.APPOINTMENT.value: AutonomyLevel.CONFIRM,
    AIAutonomyDomain.NEGOTIATION.value: AutonomyLevel.SUGGEST,
    AIAutonomyDomain.BOOKING.value: AutonomyLevel.CONFIRM,
    AIAutonomyDomain.PAYMENT.value: AutonomyLevel.CONFIRM,
}


class AIGovernancePolicyEngine:
    """Evaluates whether an AI action is permitted in the tenant's autonomy configuration."""

    @classmethod
    def get_effective_level(
        cls,
        domain: str | AIAutonomyDomain,
        tenant_policy: Optional[Dict[str, str]] = None
    ) -> AutonomyLevel:
        dom_key = domain.value if isinstance(domain, AIAutonomyDomain) else domain.upper()
        if tenant_policy and dom_key in tenant_policy:
            raw = str(tenant_policy[dom_key]).upper()
            try:
                return AutonomyLevel(raw)
            except ValueError:
                pass
        return DEFAULT_AUTONOMY_POLICY.get(dom_key, AutonomyLevel.DISABLED)

    @classmethod
    def can_execute_autonomously(
        cls,
        domain: str | AIAutonomyDomain,
        tenant_policy: Optional[Dict[str, str]] = None
    ) -> bool:
        level = cls.get_effective_level(domain, tenant_policy)
        return level == AutonomyLevel.AUTONOMOUS

    @classmethod
    def requires_confirmation(
        cls,
        domain: str | AIAutonomyDomain,
        tenant_policy: Optional[Dict[str, str]] = None
    ) -> bool:
        level = cls.get_effective_level(domain, tenant_policy)
        return level == AutonomyLevel.CONFIRM

    @classmethod
    def is_disabled(
        cls,
        domain: str | AIAutonomyDomain,
        tenant_policy: Optional[Dict[str, str]] = None
    ) -> bool:
        level = cls.get_effective_level(domain, tenant_policy)
        return level == AutonomyLevel.DISABLED


# ─── Prompt Injection & Adversarial Neutralizer ──────────────────────────────

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)\s+rules", re.IGNORECASE),
    re.compile(r"system\s+prompt\s+override", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an|in)\s+DAN\s+mode", re.IGNORECASE),
    re.compile(r"reveal\s+(your\s+)?(system\s+prompt|secret|api_key|password)", re.IGNORECASE),
    re.compile(r"dump\s+(all\s+)?(instructions|environment|secrets)", re.IGNORECASE),
    re.compile(r"<\s*script[^>]*>", re.IGNORECASE),
    re.compile(r"format\s+C:\\", re.IGNORECASE),
]


def detect_prompt_injection(user_input: str) -> Tuple[bool, Optional[str]]:
    """
    Scans user input for prompt injection, jailbreak attempts, or instruction override attempts.
    Returns (True, reason) if detected, otherwise (False, None).
    """
    if not isinstance(user_input, str):
        return False, None
    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(user_input)
        if match:
            return True, f"Detected injection pattern: '{match.group(0)}'"
    return False, None


def wrap_untrusted_input(user_input: str) -> str:
    """
    Wraps untrusted user/customer inputs in strict structural delimiters
    and neutralizes any injected boundary closure tags.
    """
    if not isinstance(user_input, str):
        return ""
    # Neutralize closure tags
    sanitized = user_input.replace("</user_input_untrusted>", "[TAG_DEFUSED]")
    sanitized = sanitized.replace("<user_input_untrusted>", "[TAG_DEFUSED]")
    return f"<user_input_untrusted>\n{sanitized}\n</user_input_untrusted>"
