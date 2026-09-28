"""
WefyLabs Canonical Money & Financial Arithmetic Value Object
=============================================================
Enforces absolute financial invariants:
1. NEVER use float or binary floating-point arithmetic.
2. All monetary values are backed by exact Python `Decimal` or integer minor units.
3. Currency match is strictly checked before any addition/subtraction.
4. Rounding policy is deterministic (defaults to ROUND_HALF_UP).
5. Immutable value object semantics.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN, ROUND_FLOOR, ROUND_CEILING
from enum import Enum
from typing import Union, Optional, Tuple


class RoundingPolicy(str, Enum):
    HALF_UP = "HALF_UP"
    HALF_EVEN = "HALF_EVEN"
    FLOOR = "FLOOR"
    CEIL = "CEIL"


_ROUNDING_MAP = {
    RoundingPolicy.HALF_UP: ROUND_HALF_UP,
    RoundingPolicy.HALF_EVEN: ROUND_HALF_EVEN,
    RoundingPolicy.FLOOR: ROUND_FLOOR,
    RoundingPolicy.CEIL: ROUND_CEILING,
}

# ISO 4217 minor unit exponent mapping (default is 2 decimal places, e.g. cents/paise)
CURRENCY_EXPONENTS: dict[str, int] = {
    "USD": 2,
    "INR": 2,
    "AED": 2,
    "EUR": 2,
    "GBP": 2,
    "JPY": 0,
    "BHD": 3,
    "KWD": 3,
    "OMR": 3,
}


class CurrencyMismatchError(ValueError):
    """Raised when attempting arithmetic across distinct currencies."""
    pass


class NegativeAmountError(ValueError):
    """Raised when an operation results in an illegal negative amount where prohibited."""
    pass


class Money:
    """
    Immutable value object representing an exact monetary amount in a specific currency.
    """
    __slots__ = ("_amount", "_currency", "_precision")

    def __init__(
        self,
        amount: Union[Decimal, int, str, "Money"],
        currency: str = "INR",
        precision: int = 4
    ) -> None:
        if isinstance(amount, Money):
            self._amount = amount._amount
            self._currency = amount._currency.upper()
            self._precision = amount._precision
            return

        if isinstance(amount, float):
            raise TypeError(
                "Floating-point numbers are strictly forbidden in financial arithmetic. "
                "Use Decimal, integer minor units, or string representation."
            )

        if not isinstance(currency, str) or len(currency) != 3:
            raise ValueError(f"Invalid ISO 4217 currency code: {currency}")

        self._currency = currency.upper()
        self._precision = precision

        if isinstance(amount, Decimal):
            self._amount = amount.quantize(Decimal(10) ** -precision)
        else:
            self._amount = Decimal(str(amount)).quantize(Decimal(10) ** -precision)

    @property
    def amount(self) -> Decimal:
        return self._amount

    @property
    def currency(self) -> str:
        return self._currency

    @property
    def precision(self) -> int:
        return self._precision

    @classmethod
    def from_minor_units(cls, minor_units: int, currency: str = "INR") -> "Money":
        """
        Creates a Money instance from integer minor units (e.g. 299900 paise -> 2999.00 INR).
        """
        if not isinstance(minor_units, int):
            raise TypeError("Minor units must be an integer.")
        exp = CURRENCY_EXPONENTS.get(currency.upper(), 2)
        dec_amount = Decimal(minor_units) / (Decimal(10) ** exp)
        return cls(dec_amount, currency=currency)

    def to_minor_units(self) -> int:
        """
        Converts the monetary amount to integer minor units (e.g. 2999.00 INR -> 299900 paise).
        Uses ROUND_HALF_UP rounding.
        """
        exp = CURRENCY_EXPONENTS.get(self._currency, 2)
        quantizer = Decimal("1")
        minor = (self._amount * (Decimal(10) ** exp)).quantize(quantizer, rounding=ROUND_HALF_UP)
        return int(minor)

    def round(
        self,
        decimals: Optional[int] = None,
        policy: RoundingPolicy = RoundingPolicy.HALF_UP
    ) -> "Money":
        """
        Returns a new Money instance rounded to specified decimals using the given policy.
        """
        if decimals is None:
            decimals = CURRENCY_EXPONENTS.get(self._currency, 2)
        q = Decimal(10) ** -decimals
        rounded = self._amount.quantize(q, rounding=_ROUNDING_MAP[policy])
        return Money(rounded, currency=self._currency, precision=self._precision)

    def is_zero(self) -> bool:
        return self._amount == Decimal("0")

    def is_positive(self) -> bool:
        return self._amount > Decimal("0")

    def is_negative(self) -> bool:
        return self._amount < Decimal("0")

    # ─── Arithmetic Operators ──────────────────────────────────────────────────

    def __add__(self, other: Union["Money", int, Decimal]) -> "Money":
        if isinstance(other, Money):
            if self._currency != other._currency:
                raise CurrencyMismatchError(
                    f"Cannot add {self._currency} and {other._currency}"
                )
            return Money(self._amount + other._amount, currency=self._currency, precision=self._precision)
        if isinstance(other, (int, Decimal)):
            return Money(self._amount + Decimal(str(other)), currency=self._currency, precision=self._precision)
        return NotImplemented

    def __sub__(self, other: Union["Money", int, Decimal]) -> "Money":
        if isinstance(other, Money):
            if self._currency != other._currency:
                raise CurrencyMismatchError(
                    f"Cannot subtract {other._currency} from {self._currency}"
                )
            return Money(self._amount - other._amount, currency=self._currency, precision=self._precision)
        if isinstance(other, (int, Decimal)):
            return Money(self._amount - Decimal(str(other)), currency=self._currency, precision=self._precision)
        return NotImplemented

    def __mul__(self, factor: Union[int, Decimal, str]) -> "Money":
        if isinstance(factor, float):
            raise TypeError("Cannot multiply Money by float. Use Decimal or int.")
        dec_factor = Decimal(str(factor))
        return Money(self._amount * dec_factor, currency=self._currency, precision=self._precision)

    def __rmul__(self, factor: Union[int, Decimal, str]) -> "Money":
        return self.__mul__(factor)

    def __truediv__(self, divisor: Union[int, Decimal, str]) -> "Money":
        if isinstance(divisor, float):
            raise TypeError("Cannot divide Money by float. Use Decimal or int.")
        dec_divisor = Decimal(str(divisor))
        if dec_divisor == Decimal("0"):
            raise ZeroDivisionError("Cannot divide Money by zero.")
        return Money(self._amount / dec_divisor, currency=self._currency, precision=self._precision)

    def __neg__(self) -> "Money":
        return Money(-self._amount, currency=self._currency, precision=self._precision)

    def __abs__(self) -> "Money":
        return Money(abs(self._amount), currency=self._currency, precision=self._precision)

    # ─── Comparisons ──────────────────────────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Money):
            return self._currency == other._currency and self._amount == other._amount
        if other == 0 and self.is_zero():
            return True
        return False

    def __lt__(self, other: "Money") -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        if self._currency != other._currency:
            raise CurrencyMismatchError(f"Cannot compare {self._currency} and {other._currency}")
        return self._amount < other._amount

    def __le__(self, other: "Money") -> bool:
        return self < other or self == other

    def __gt__(self, other: "Money") -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        if self._currency != other._currency:
            raise CurrencyMismatchError(f"Cannot compare {self._currency} and {other._currency}")
        return self._amount > other._amount

    def __ge__(self, other: "Money") -> bool:
        return self > other or self == other

    def __hash__(self) -> int:
        return hash((self._amount, self._currency))

    def __repr__(self) -> str:
        return f"Money({self._amount}, '{self._currency}')"

    def __str__(self) -> str:
        exp = CURRENCY_EXPONENTS.get(self._currency, 2)
        q = Decimal(10) ** -exp
        return f"{self._currency} {self._amount.quantize(q, rounding=ROUND_HALF_UP):,}"


class MoneyCalculator:
    """
    Stateless financial calculation utilities for invoices, prorations, discounts, and taxes.
    """

    @staticmethod
    def calculate_line_total(
        unit_price: Money,
        quantity: Union[int, Decimal],
        discount: Optional[Money] = None,
        tax_rate_pct: Decimal = Decimal("0.0")
    ) -> Tuple[Money, Money, Money, Money]:
        """
        Returns: (subtotal, discount_amount, tax_amount, total)
        """
        if isinstance(quantity, int):
            qty = Decimal(quantity)
        elif isinstance(quantity, Decimal):
            qty = quantity
        else:
            qty = Decimal(str(quantity))

        subtotal = (unit_price * qty).round()
        disc = discount.round() if discount else Money(Decimal("0.0"), currency=unit_price.currency)
        if disc > subtotal:
            disc = subtotal

        taxable_base = subtotal - disc
        tax_factor = tax_rate_pct / Decimal("100.0")
        tax_amount = (taxable_base * tax_factor).round()
        total = taxable_base + tax_amount

        return subtotal, disc, tax_amount, total

    @staticmethod
    def calculate_proration(
        full_period_amount: Money,
        total_seconds_in_period: int,
        active_seconds: int
    ) -> Money:
        """
        Calculates exact proration for a subscription change.
        Formula: (full_period_amount * active_seconds) / total_seconds_in_period
        """
        if total_seconds_in_period <= 0:
            raise ValueError("total_seconds_in_period must be positive.")
        if active_seconds < 0:
            active_seconds = 0
        if active_seconds > total_seconds_in_period:
            active_seconds = total_seconds_in_period

        ratio = Decimal(active_seconds) / Decimal(total_seconds_in_period)
        return (full_period_amount * ratio).round()
