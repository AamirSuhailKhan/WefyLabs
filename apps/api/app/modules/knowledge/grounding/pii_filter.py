"""
PII Detection & Redaction Filter
==================================
Detects and redacts Personally Identifiable Information (PII)
from knowledge chunks before they are served to customer-facing AI.

PII types detected:
  - Email addresses
  - Phone numbers (international formats)
  - UAE/Indian national ID patterns
  - Passport numbers
  - Credit/debit card numbers
  - Bank account numbers (IBAN)
  - Names in contact patterns (Name: John Smith)
  - Addresses with postal codes

Usage:
  - Applied during customer-facing retrieval (channel=customer_facing)
  - Applied during chunk content display in public/API responses
  - NOT applied for ADMIN/MANAGER retrieval of internal docs (they see raw)

Design:
  - Uses regex-only (no ML models required for baseline coverage)
  - Replacement: [REDACTED:TYPE] — enables auditability
  - PII-containing chunks can be flagged ai_not_allowed=True during ingestion
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# ─── PII Patterns ─────────────────────────────────────────────────────────────

_PII_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
        re.IGNORECASE,
    )),
    ("PHONE", re.compile(
        r"\b(?:\+?971|0)?[- ]?\(?(?:50|52|54|55|56|58|2|3|4|6|7|9)\)?[- ]?\d{3}[- ]?\d{4}\b"  # UAE
        r"|\b\+?(?:91|0)?[6789]\d{9}\b"  # India
        r"|\b\+?1[- ]?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b"  # US
        r"|\b\+?\d{1,3}[- ]?\d{6,12}\b",  # Generic international
        re.IGNORECASE,
    )),
    ("CREDIT_CARD", re.compile(
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}"
        r"|6(?:011|5[0-9]{2})[0-9]{12})\b",
    )),
    ("IBAN", re.compile(
        r"\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b",
    )),
    ("PASSPORT", re.compile(
        r"\b[A-Z]{1,2}\d{6,9}\b",
    )),
    ("EMIRATES_ID", re.compile(
        r"\b784[- ]?\d{4}[- ]?\d{7}[- ]?\d{1}\b",
    )),
    ("NAME_LABEL", re.compile(
        r"\b(?:Name|Contact|Client|Customer)\s*[:=]\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}",
        re.IGNORECASE,
    )),
    ("ADDRESS", re.compile(
        r"\b\d{1,5}\s+[A-Z][a-zA-Z\s]{5,50},\s*[A-Z][a-zA-Z\s]{2,30}(?:,\s*\d{5,10})?\b",
    )),
]


@dataclass
class PIIFilterResult:
    """Result of PII filtering on a text chunk."""
    original_text: str
    redacted_text: str
    pii_found: bool
    pii_types_detected: List[str] = field(default_factory=list)
    redaction_count: int = 0


class PIIFilter:
    """
    Regex-based PII detector and redactor for knowledge chunks.
    Used at retrieval time for customer-facing channels.
    """

    def filter_text(
        self,
        text: str,
        channel: str = "customer_facing",
        redact: bool = True,
    ) -> PIIFilterResult:
        """
        Detect and optionally redact PII from text.

        Args:
            text:    The raw chunk content.
            channel: If "internal" or "admin", PII is detected but NOT redacted.
            redact:  If True, replace PII with [REDACTED:TYPE] markers.

        Returns:
            PIIFilterResult with redacted text and detected types.
        """
        if not text:
            return PIIFilterResult(
                original_text=text,
                redacted_text=text,
                pii_found=False,
            )

        result_text = text
        detected_types: List[str] = []
        total_redactions = 0

        should_redact = redact and channel in (
            "customer_facing", "whatsapp", "telegram", "website", "public"
        )

        for pii_type, pattern in _PII_PATTERNS:
            matches = pattern.findall(result_text)
            if matches:
                detected_types.append(pii_type)
                total_redactions += len(matches)

                if should_redact:
                    result_text = pattern.sub(f"[REDACTED:{pii_type}]", result_text)

        if detected_types:
            logger.info(
                f"[PII FILTER] Detected {len(detected_types)} PII types "
                f"({', '.join(detected_types)}) in {len(text)} chars. "
                f"Redacted={should_redact}"
            )

        return PIIFilterResult(
            original_text=text,
            redacted_text=result_text,
            pii_found=bool(detected_types),
            pii_types_detected=detected_types,
            redaction_count=total_redactions,
        )

    def contains_pii(self, text: str) -> bool:
        """Quick check — returns True if any PII is detected in text."""
        for _, pattern in _PII_PATTERNS:
            if pattern.search(text):
                return True
        return False

    def scan_chunks(
        self,
        chunks: List[Dict[str, Any]],
        channel: str = "internal",
    ) -> List[Dict[str, Any]]:
        """
        Apply PII filtering to a list of retrieved chunk dicts.
        Used in the retrieval pipeline for customer-facing responses.

        Returns a new list with content redacted where appropriate.
        """
        filtered = []
        for chunk in chunks:
            text = chunk.get("text", "")
            result = self.filter_text(text, channel=channel, redact=True)
            filtered_chunk = {**chunk, "text": result.redacted_text}
            if result.pii_found:
                filtered_chunk["_pii_detected"] = result.pii_types_detected
            filtered.append(filtered_chunk)
        return filtered
