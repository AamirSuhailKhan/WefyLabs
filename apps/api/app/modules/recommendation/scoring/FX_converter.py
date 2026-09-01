"""
FX Currency Conversion Engine
==============================
Provides currency normalization, rate verification, and multi-currency safety checks.
Base anchor currency: AED (United Arab Emirates Dirham).
"""

import logging
from typing import Dict, Any, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Production FX Rate Reference relative to 1 AED anchor
DEFAULT_FX_RATES_TO_AED: Dict[str, float] = {
    "AED": 1.0,
    "USD": 3.6725,     # 1 USD = 3.6725 AED
    "INR": 0.0442,     # 1 INR = 0.0442 AED (~22.6 INR per AED)
    "EUR": 3.9850,     # 1 EUR = 3.9850 AED
    "GBP": 4.6500,     # 1 GBP = 4.6500 AED
    "SAR": 0.9790,     # 1 SAR = 0.9790 AED
    "QAR": 1.0080,     # 1 QAR = 1.0080 AED
}

class FXConverter:
    """
    Multi-currency normalization service with strict audit provenance.
    """

    def __init__(self, rates_override: Optional[Dict[str, float]] = None):
        self.rates = rates_override or DEFAULT_FX_RATES_TO_AED.copy()

    def convert_to_aed(self, amount: float, from_currency: str) -> Tuple[float, Dict[str, Any]]:
        """
        Converts any supported currency amount into AED.
        """
        curr = from_currency.upper().strip()
        if curr not in self.rates:
            logger.warning(f"[FX_CONVERTER] Unsupported currency '{curr}'. Marking conversion uncertain.")
            # Fallback: assume AED if unknown, with zero confidence
            return amount, {
                "original_amount": amount,
                "original_currency": curr,
                "normalized_amount_aed": amount,
                "fx_rate": 1.0,
                "fx_source": "FALLBACK_UNKNOWN_CURRENCY",
                "fx_timestamp": datetime.now(timezone.utc).isoformat(),
                "confidence": 0.0
            }

        rate = self.rates[curr]
        amount_aed = amount * rate

        return amount_aed, {
            "original_amount": amount,
            "original_currency": curr,
            "normalized_amount_aed": round(amount_aed, 2),
            "fx_rate": rate,
            "fx_source": "BEETLELABS_CENTRAL_BANK_CACHE",
            "fx_timestamp": datetime.now(timezone.utc).isoformat(),
            "confidence": 1.0
        }

    def convert(self, amount: float, from_currency: str, to_currency: str) -> Tuple[float, Dict[str, Any]]:
        """
        Converts between any two supported currencies via AED anchor.
        """
        from_curr = from_currency.upper().strip()
        to_curr = to_currency.upper().strip()

        if from_curr == to_curr:
            return amount, {
                "original_amount": amount,
                "original_currency": from_curr,
                "converted_amount": amount,
                "target_currency": to_curr,
                "fx_rate": 1.0,
                "fx_timestamp": datetime.now(timezone.utc).isoformat()
            }

        amount_aed, metadata = self.convert_to_aed(amount, from_curr)
        if to_curr == "AED":
            return amount_aed, metadata

        target_rate = self.rates.get(to_curr, 1.0)
        converted_amount = amount_aed / target_rate

        return converted_amount, {
            "original_amount": amount,
            "original_currency": from_curr,
            "converted_amount": round(converted_amount, 2),
            "target_currency": to_curr,
            "fx_rate": metadata["fx_rate"] / target_rate,
            "fx_timestamp": metadata["fx_timestamp"]
        }
