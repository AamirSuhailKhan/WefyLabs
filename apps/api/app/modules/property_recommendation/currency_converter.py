"""
Part 21.3 — Decimal-Safe Currency Normalizer
============================================
Decimal-safe currency normalization and FX rate engine.
NEVER uses floating point arithmetic for financial boundary checks.
"""
from decimal import Decimal
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, timezone
import logging

from app.modules.global_.currencies.money import Money

logger = logging.getLogger(__name__)

# Standard Central Bank Reference Rates (relative to 1 AED anchor)
DEFAULT_RATES_TO_AED_DECIMAL: Dict[str, Decimal] = {
    "AED": Decimal("1.0"),
    "USD": Decimal("3.6725"),
    "INR": Decimal("0.0442"),
    "EUR": Decimal("3.9850"),
    "GBP": Decimal("4.6500"),
    "SAR": Decimal("0.9790"),
    "QAR": Decimal("1.0080"),
    "OMR": Decimal("9.5400"),
    "KWD": Decimal("11.9600"),
    "BHD": Decimal("9.7400"),
}


class DecimalCurrencyConverter:
    """
    Decimal-safe financial conversion service for property recommendations.
    """

    def __init__(self, rates_override: Optional[Dict[str, Decimal]] = None):
        self.rates = rates_override or DEFAULT_RATES_TO_AED_DECIMAL.copy()

    def convert_to_aed(self, money: Money) -> Money:
        """Converts Money instance into AED with Decimal precision."""
        curr = money.currency_code.upper()
        if curr == "AED":
            return money

        rate = self.rates.get(curr, Decimal("1.0"))
        aed_amount = money.amount * rate
        return Money(aed_amount.quantize(Decimal("0.01")), "AED")

    def convert(self, money: Money, target_currency: str) -> Money:
        """Converts Money instance into target currency."""
        curr = money.currency_code.upper()
        target = target_currency.upper()

        if curr == target:
            return money

        aed_money = self.convert_to_aed(money)
        if target == "AED":
            return aed_money

        target_rate = self.rates.get(target, Decimal("1.0"))
        target_amount = aed_money.amount / target_rate
        return Money(target_amount.quantize(Decimal("0.01")), target)
