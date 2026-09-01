"""
Grounding Validator
=====================
Validates that LLM-generated answers are grounded in retrieved evidence.

A grounded answer is one where every factual claim can be traced to
a specific chunk from the knowledge retrieval step.

Validation steps:
  1. Extract factual claims from answer (price, area, availability)
  2. For each claim, check if evidence exists in retrieved chunks
  3. If a claim has no supporting evidence → UNGROUNDED CLAIM flagged
  4. If ungrounded claims exceed threshold → answer is BLOCKED

Integration:
  Called by SafetyGuard (existing) AFTER the existing checks,
  OR called directly in the AI agent loop before response delivery.

Design:
  - Never silently drops claims. Always flags or blocks.
  - Low-confidence retrieval → AI says "I don't have verified information"
  - Blocks hallucinated prices and availability (most critical)
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Patterns for factual claims that MUST be grounded
_PRICE_CLAIM_RE = re.compile(
    r"\b(?:AED|USD|GBP|INR|SGD|EUR|RM|SAR)\s*[\d,]+(?:\.\d+)?(?:\s*(?:M|K|L|Lac|Lakh|million))?\b",
    re.IGNORECASE,
)
_AVAILABILITY_CLAIM_RE = re.compile(
    r"\b(?:available|sold\s*out?|units?\s*left|only\s*\d+\s*units?|limited\s*units?)\b",
    re.IGNORECASE,
)
_AREA_CLAIM_RE = re.compile(
    r"\b[\d,]+(?:\.\d+)?\s*(?:sq\.?ft|sqft|sq\.?m|sqm|square\s*feet)\b",
    re.IGNORECASE,
)

# Safe fallback for ungrounded answers
INSUFFICIENT_EVIDENCE_RESPONSE = (
    "I don't have verified information on that specific detail. "
    "Let me connect you with our property specialist who can provide "
    "accurate and up-to-date information."
)


@dataclass
class GroundingViolation:
    """A specific claim that failed grounding validation."""
    claim_text: str
    claim_type: str           # PRICE | AVAILABILITY | AREA | OTHER
    evidence_found: bool = False
    supporting_chunk_id: Optional[str] = None


@dataclass
class GroundingResult:
    """Result of grounding validation for an LLM answer."""
    passed: bool
    answer_text: str              # Original or safe fallback
    violations: List[GroundingViolation] = field(default_factory=list)
    was_blocked: bool = False
    block_reason: Optional[str] = None
    grounding_score: float = 1.0  # 1.0 = fully grounded, 0.0 = no evidence


class GroundingValidator:
    """
    Validates that an LLM answer is grounded in retrieved knowledge.
    Called after hybrid search + context assembly, before final delivery.
    """

    # Threshold: if this fraction of claims are ungrounded, block the answer
    BLOCK_THRESHOLD = 0.5

    def validate(
        self,
        answer_text: str,
        retrieved_chunks: List[Dict[str, Any]],
        require_grounding: bool = True,
    ) -> GroundingResult:
        """
        Validate that factual claims in the answer are supported by evidence.

        Args:
            answer_text: LLM-generated answer to validate
            retrieved_chunks: list of chunks used in context construction
                              (from AssembledContext.knowledge_chunks)
            require_grounding: if False, skip grounding check (for general FAQ)

        Returns:
            GroundingResult — passed=False if critical claims are ungrounded.
        """
        if not require_grounding or not retrieved_chunks:
            # No evidence context → cannot ground → return insufficient evidence
            if require_grounding and not retrieved_chunks:
                return GroundingResult(
                    passed=False,
                    answer_text=INSUFFICIENT_EVIDENCE_RESPONSE,
                    was_blocked=True,
                    block_reason="No knowledge context available to ground the answer",
                    grounding_score=0.0,
                )
            return GroundingResult(
                passed=True,
                answer_text=answer_text,
                grounding_score=1.0,
            )

        # Build a combined text corpus from all retrieved chunks
        evidence_corpus = " ".join(
            chunk.get("text", "") for chunk in retrieved_chunks
        ).lower()

        violations: List[GroundingViolation] = []

        # ── 1. Check price claims ─────────────────────────────────────────────
        for match in _PRICE_CLAIM_RE.finditer(answer_text):
            claim = match.group(0)
            # Check if the claim appears in the evidence (normalized)
            evidence_found = self._claim_in_evidence(claim, evidence_corpus)
            if not evidence_found:
                violations.append(GroundingViolation(
                    claim_text=claim,
                    claim_type="PRICE",
                    evidence_found=False,
                ))
                logger.warning(
                    f"[GROUNDING] Ungrounded PRICE claim: '{claim}'"
                )

        # ── 2. Check availability claims ──────────────────────────────────────
        for match in _AVAILABILITY_CLAIM_RE.finditer(answer_text):
            claim = match.group(0)
            evidence_found = self._claim_in_evidence(claim, evidence_corpus)
            if not evidence_found:
                violations.append(GroundingViolation(
                    claim_text=claim,
                    claim_type="AVAILABILITY",
                    evidence_found=False,
                ))

        # ── 3. Check area claims ──────────────────────────────────────────────
        for match in _AREA_CLAIM_RE.finditer(answer_text):
            claim = match.group(0)
            evidence_found = self._claim_in_evidence(claim, evidence_corpus)
            if not evidence_found:
                violations.append(GroundingViolation(
                    claim_text=claim,
                    claim_type="AREA",
                    evidence_found=False,
                ))

        # Compute grounding score
        total_claims = len(violations) + (
            len(_PRICE_CLAIM_RE.findall(answer_text)) +
            len(_AVAILABILITY_CLAIM_RE.findall(answer_text)) +
            len(_AREA_CLAIM_RE.findall(answer_text))
        )
        ungrounded = len([v for v in violations if not v.evidence_found])
        grounding_score = (
            1.0 - (ungrounded / max(total_claims, 1))
            if total_claims > 0 else 1.0
        )

        # Should we block?
        should_block = (
            ungrounded > 0 and
            ungrounded / max(total_claims, 1) >= self.BLOCK_THRESHOLD
        )

        if should_block:
            logger.warning(
                f"[GROUNDING] Answer BLOCKED: {ungrounded}/{total_claims} "
                f"claims ungrounded. Score={grounding_score:.2f}"
            )
            return GroundingResult(
                passed=False,
                answer_text=INSUFFICIENT_EVIDENCE_RESPONSE,
                violations=violations,
                was_blocked=True,
                block_reason=f"{ungrounded} factual claims could not be verified in knowledge base",
                grounding_score=grounding_score,
            )

        return GroundingResult(
            passed=True,
            answer_text=answer_text,
            violations=violations,
            was_blocked=False,
            grounding_score=grounding_score,
        )

    def _claim_in_evidence(self, claim: str, corpus: str) -> bool:
        """Check if a claim text appears in the evidence corpus (case-insensitive)."""
        # Normalize: remove punctuation and extra spaces
        normalized_claim = re.sub(r"[,\s]+", " ", claim.lower()).strip()
        normalized_corpus = re.sub(r"[,\s]+", " ", corpus).strip()

        # Direct substring check
        if normalized_claim in normalized_corpus:
            return True

        # Numeric value check (for prices: "AED 1500000" vs "AED 1,500,000")
        digits_only = re.sub(r"\D", "", claim)
        if len(digits_only) >= 4 and digits_only in re.sub(r"\D", "", corpus):
            return True

        return False
