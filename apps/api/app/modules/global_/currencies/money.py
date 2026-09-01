"""
Global Money Type — Decimal-Safe Financial Arithmetic
=====================================================
Architecture Rule: NEVER use Python float for authoritative financial calculations.
Always use Decimal / NUMERIC.

All monetary values must carry: amount, currency_code.
Never store: price = 2000000 without currency.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.global_.currencies.exchange_rate_service import ExchangeRateService

logger = logging.getLogger(__name__)

# Canonical rounding mode for all financial calculations
FINANCIAL_ROUNDING = ROUND_HALF_UP

# Precision for display vs. computation
COMPUTATION_PRECISION = Decimal("0.00000001")   # 8 decimal places
DISPLAY_PRECISION     = Decimal("0.01")          # 2 decimal places (configurable per currency)


@dataclass(frozen=True)
class Money:
    """
    Immutable Decimal-safe monetary value.
    Carries both amount and currency_code — they are inseparable.
    All arithmetic returns new Money instances.

    Usage:
        price = Money(Decimal("2000000"), "AED")
        dld_fee = price.multiply(Decimal("0.04"))         # DLD 4% fee
        total = price.add(dld_fee)
        formatted = price.format("en-AE")                 # "AED 2,000,000"
    """
    amount: Decimal
    currency_code: str  # ISO 4217: "AED", "INR", "USD"
    decimal_digits: int = field(default=2, compare=False)

    def __post_init__(self):
        if not isinstance(self.amount, Decimal):
            raise TypeError(
                f"Money.amount must be Decimal, not {type(self.amount).__name__}. "
                f"Convert before constructing: Money(Decimal('{self.amount}'), '{self.currency_code}')"
            )
        if not self.currency_code or len(self.currency_code) != 3:
            raise ValueError(f"currency_code must be a 3-character ISO 4217 code, got: '{self.currency_code}'")

    @classmethod
    def of(cls, amount: int | float | str | Decimal, currency_code: str, decimal_digits: int = 2) -> "Money":
        """Convenience factory that accepts int/float/str and converts safely."""
        try:
            decimal_amount = Decimal(str(amount))
        except InvalidOperation as e:
            raise ValueError(f"Cannot convert {amount!r} to Decimal: {e}") from e
        return cls(decimal_amount, currency_code.upper(), decimal_digits)

    def add(self, other: "Money") -> "Money":
        """Add two Money values — must share the same currency_code."""
        if self.currency_code != other.currency_code:
            raise ValueError(
                f"Cannot add {self.currency_code} and {other.currency_code}. "
                "Convert to a common currency first via ExchangeRateService."
            )
        return Money(self.amount + other.amount, self.currency_code, self.decimal_digits)

    def subtract(self, other: "Money") -> "Money":
        if self.currency_code != other.currency_code:
            raise ValueError(f"Cannot subtract {self.currency_code} from {other.currency_code}.")
        return Money(self.amount - other.amount, self.currency_code, self.decimal_digits)

    def multiply(self, factor: Decimal | int | str) -> "Money":
        """Multiply by a factor (e.g. tax rate). Returns new Money."""
        d_factor = Decimal(str(factor))
        return Money(
            (self.amount * d_factor).quantize(COMPUTATION_PRECISION, rounding=FINANCIAL_ROUNDING),
            self.currency_code,
            self.decimal_digits
        )

    def rounded(self) -> "Money":
        """Round to display precision (decimal_digits)."""
        precision = Decimal(10) ** -self.decimal_digits
        return Money(
            self.amount.quantize(precision, rounding=FINANCIAL_ROUNDING),
            self.currency_code,
            self.decimal_digits
        )

    def is_positive(self) -> bool:
        return self.amount > Decimal("0")

    def is_zero(self) -> bool:
        return self.amount == Decimal("0")

    def format(self, locale: str = "en-US") -> str:
        """
        Locale-aware formatting.
        For production use, integrate with babel or the frontend's Intl.NumberFormat.
        """
        rounded = self.rounded()
        amount_str = f"{rounded.amount:,.{self.decimal_digits}f}"
        # Basic locale formatting — extend with proper i18n library
        if locale.startswith("ar"):
            return f"{self.currency_code} {amount_str}"
        elif self.currency_code == "INR":
            # Indian numbering: lakhs/crores formatting
            return self._format_inr(rounded.amount)
        return f"{self.currency_code} {amount_str}"

    def _format_inr(self, amount: Decimal) -> str:
        """Indian numbering system (lakhs/crores)."""
        amt = float(amount)
        if amt >= 10_000_000:
            return f"₹{amt / 10_000_000:.2f} Cr"
        elif amt >= 100_000:
            return f"₹{amt / 100_000:.1f} L"
        return f"₹{amount:,.2f}"

    def to_dict(self) -> dict:
        return {
            "amount": str(self.amount),
            "currency_code": self.currency_code,
            "decimal_digits": self.decimal_digits,
        }

    def __repr__(self) -> str:
        return f"Money({self.amount}, '{self.currency_code}')"

    def __str__(self) -> str:
        return self.format()


@dataclass(frozen=True)
class MoneyConversionResult:
    """
    Result of a currency conversion via ExchangeRateService.
    Carries the full provenance of the conversion.
    """
    original: Money
    converted: Money
    rate: Decimal
    rate_type: str          # LIVE | CACHED | FALLBACK | HISTORICAL
    provider: str
    timestamp: str          # ISO8601 UTC
    is_fallback: bool
    status: str             # OK | FX_UNAVAILABLE | RATE_STALE

    @property
    def is_ok(self) -> bool:
        return self.status == "OK"


class FXUnavailableError(Exception):
    """
    Raised when FX rate is not available and no fallback is configured.
    NEVER silently use 1:1 or stale rate without marking it explicitly.
    """
    def __init__(self, base: str, quote: str, reason: str = ""):
        self.base = base
        self.quote = quote
        super().__init__(
            f"FX rate unavailable for {base}/{quote}. "
            f"Reason: {reason or 'No provider returned a valid rate.'} "
            "Do NOT use 1:1 silently. Return FX_UNAVAILABLE status to caller."
        )
