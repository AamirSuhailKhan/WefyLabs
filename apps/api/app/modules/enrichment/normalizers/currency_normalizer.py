"""
Volume 2 PART 2 — Currency Normalizer (Canonical Currency in AED & USD)
"""
import re
from typing import Dict, Any, Optional

# Static FX rates to AED (Canonical Base: 1 USD = 3.6725 AED)
FX_RATES_TO_AED = {
    "AED": 1.0,
    "USD": 3.6725,
    "EUR": 3.98,
    "GBP": 4.65,
    "INR": 0.044,
    "SAR": 0.98,
    "QAR": 1.01,
    "KWD": 11.95,
    "EGP": 0.076,
    "CAD": 2.72,
    "AUD": 2.45,
}


class CurrencyNormalizer:
    @staticmethod
    def parse_amount(val_str: str) -> Optional[float]:
        """Parses numeric amount from strings like '1.5M', '500k', '2,500,000'."""
        if not val_str:
            return None
        
        s = val_str.lower().strip()
        multiplier = 1.0
        if "m" in s or "million" in s:
            multiplier = 1000000.0
            s = re.sub(r"[m|million]", "", s)
        elif "k" in s or "thousand" in s:
            multiplier = 1000.0
            s = re.sub(r"[k|thousand]", "", s)
        elif "b" in s or "billion" in s:
            multiplier = 1000000000.0
            s = re.sub(r"[b|billion]", "", s)

        s = re.sub(r"[^\d.]", "", s)
        try:
            val = float(s)
            return val * multiplier
        except ValueError:
            return None

    @classmethod
    def normalize(cls, val_str_or_num: Any, default_currency: str = "AED") -> Dict[str, Any]:
        """
        Converts budget / income amounts into canonical AED and USD.
        """
        if val_str_or_num is None:
            return {
                "raw": None,
                "amount_aed": None,
                "amount_usd": None,
                "currency": default_currency,
                "confidence": 0.0
            }

        if isinstance(val_str_or_num, (int, float)):
            amount = float(val_str_or_num)
            currency = default_currency.upper()
        else:
            s = str(val_str_or_num).upper()
            currency = default_currency.upper()

            # Detect currency symbols/codes
            if "USD" in s or "$" in s:
                currency = "USD"
            elif "EUR" in s or "€" in s:
                currency = "EUR"
            elif "GBP" in s or "£" in s:
                currency = "GBP"
            elif "INR" in s or "₹" in s:
                currency = "INR"
            elif "SAR" in s:
                currency = "SAR"
            elif "EGP" in s:
                currency = "EGP"
            elif "AED" in s or "DH" in s or "DIRHAM" in s:
                currency = "AED"

            amount = cls.parse_amount(str(val_str_or_num))

        if amount is None or amount <= 0:
            return {
                "raw": val_str_or_num,
                "amount_aed": None,
                "amount_usd": None,
                "currency": currency,
                "confidence": 0.1
            }

        fx_rate = FX_RATES_TO_AED.get(currency, 1.0)
        amount_aed = round(amount * fx_rate, 2)
        amount_usd = round(amount_aed / FX_RATES_TO_AED["USD"], 2)

        return {
            "raw": val_str_or_num,
            "amount": amount,
            "currency": currency,
            "amount_aed": amount_aed,
            "amount_usd": amount_usd,
            "confidence": 0.9
        }
