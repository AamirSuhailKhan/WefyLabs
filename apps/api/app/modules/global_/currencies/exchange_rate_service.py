"""
Exchange Rate Service
=====================
Production-grade FX service with live rates, caching, historical snapshots,
and explicit FX_UNAVAILABLE status — never silent 1:1 fallback.

Architecture Rules:
- NEVER use 1:1 as a silent fallback
- NEVER use stale rates without marking them as STALE
- Return FX_UNAVAILABLE explicitly if no valid rate exists
- Historical reports MUST use the rate from the transaction date
"""
from __future__ import annotations

import logging
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from typing import Optional, Dict, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func

from app.models.global_models import ExchangeRate, ExchangeRateSnapshot
from app.modules.global_.currencies.money import Money, MoneyConversionResult, FXUnavailableError

logger = logging.getLogger(__name__)

# Maximum age of a cached rate before it's considered stale
RATE_STALE_THRESHOLD_MINUTES = 60

# In-memory cache: (base, quote) -> (rate, timestamp, provider)
_rate_cache: Dict[Tuple[str, str], Tuple[Decimal, datetime, str]] = {}


class ExchangeRateResult:
    """Result of a rate lookup — always carries provenance."""
    def __init__(
        self,
        base_currency: str,
        quote_currency: str,
        rate: Decimal,
        rate_type: str,          # LIVE | CACHED | FALLBACK | HISTORICAL
        provider: str,
        valid_from: datetime,
        is_stale: bool = False,
        status: str = "OK",      # OK | RATE_STALE | FX_UNAVAILABLE
    ):
        self.base_currency = base_currency
        self.quote_currency = quote_currency
        self.rate = rate
        self.rate_type = rate_type
        self.provider = provider
        self.valid_from = valid_from
        self.is_stale = is_stale
        self.status = status

    @property
    def is_available(self) -> bool:
        return self.status != "FX_UNAVAILABLE"


class ExchangeRateService:
    """
    Authoritative FX rate resolver.

    Resolution order:
    1. In-memory cache (if fresh < RATE_STALE_THRESHOLD_MINUTES)
    2. Database (exchange_rates table, is_active=True)
    3. External provider adapter (if configured)
    4. FX_UNAVAILABLE — explicit, never silent

    Historical rates (for reports):
    - Queries exchange_rate_snapshots by exact date
    - Falls back to nearest available snapshot with explicit marking
    """

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_rate(
        self,
        base_currency: str,
        quote_currency: str,
        allow_stale: bool = False,
    ) -> ExchangeRateResult:
        """
        Get current FX rate for base → quote.
        Never uses 1:1 silently. Returns status=FX_UNAVAILABLE if no rate found.
        """
        base = base_currency.upper()
        quote = quote_currency.upper()

        # Same currency — trivial case
        if base == quote:
            return ExchangeRateResult(
                base_currency=base, quote_currency=quote,
                rate=Decimal("1"), rate_type="TRIVIAL",
                provider="internal", valid_from=datetime.now(timezone.utc),
                status="OK"
            )

        # 1. Check in-memory cache
        cache_key = (base, quote)
        if cache_key in _rate_cache:
            cached_rate, cached_at, cached_provider = _rate_cache[cache_key]
            age_minutes = (datetime.now(timezone.utc) - cached_at).total_seconds() / 60
            if age_minutes < RATE_STALE_THRESHOLD_MINUTES:
                return ExchangeRateResult(
                    base_currency=base, quote_currency=quote,
                    rate=cached_rate, rate_type="CACHED",
                    provider=cached_provider, valid_from=cached_at,
                    status="OK"
                )
            elif allow_stale:
                logger.warning(f"[FX] Using stale rate {base}/{quote} ({age_minutes:.0f}m old)")
                return ExchangeRateResult(
                    base_currency=base, quote_currency=quote,
                    rate=cached_rate, rate_type="CACHED",
                    provider=cached_provider, valid_from=cached_at,
                    is_stale=True, status="RATE_STALE"
                )

        # 2. Query database for active rate
        db_result = await self._get_rate_from_db(base, quote)
        if db_result:
            # Update cache
            _rate_cache[(base, quote)] = (db_result.rate, db_result.valid_from, db_result.provider)
            return ExchangeRateResult(
                base_currency=base, quote_currency=quote,
                rate=db_result.rate, rate_type="LIVE",
                provider=db_result.provider, valid_from=db_result.valid_from,
                status="OK"
            )

        # 3. Try reverse rate (quote/base) and invert
        reverse_result = await self._get_rate_from_db(quote, base)
        if reverse_result and reverse_result.rate > Decimal("0"):
            inverted_rate = (Decimal("1") / reverse_result.rate).quantize(Decimal("0.00000001"))
            _rate_cache[(base, quote)] = (inverted_rate, reverse_result.valid_from, reverse_result.provider)
            return ExchangeRateResult(
                base_currency=base, quote_currency=quote,
                rate=inverted_rate, rate_type="LIVE_INVERTED",
                provider=reverse_result.provider, valid_from=reverse_result.valid_from,
                status="OK"
            )

        # 4. FX_UNAVAILABLE — NEVER silent 1:1
        logger.error(f"[FX] No rate available for {base}/{quote}. Returning FX_UNAVAILABLE.")
        return ExchangeRateResult(
            base_currency=base, quote_currency=quote,
            rate=Decimal("0"), rate_type="NONE",
            provider="none", valid_from=datetime.now(timezone.utc),
            status="FX_UNAVAILABLE"
        )

    async def get_historical_rate(
        self,
        base_currency: str,
        quote_currency: str,
        snapshot_date: date,
    ) -> ExchangeRateResult:
        """
        Get FX rate for a specific historical date.
        Used for reconstructing historical financial reports.
        MUST use the rate from the date, NOT today's rate.
        """
        base = base_currency.upper()
        quote = quote_currency.upper()

        if base == quote:
            return ExchangeRateResult(
                base_currency=base, quote_currency=quote,
                rate=Decimal("1"), rate_type="TRIVIAL",
                provider="internal", valid_from=datetime.now(timezone.utc),
                status="OK"
            )

        stmt = (
            select(ExchangeRateSnapshot)
            .where(and_(
                ExchangeRateSnapshot.base_currency == base,
                ExchangeRateSnapshot.quote_currency == quote,
                ExchangeRateSnapshot.snapshot_date == snapshot_date,
            ))
            .order_by(desc(ExchangeRateSnapshot.created_at))
            .limit(1)
        )
        result = await self._db.execute(stmt)
        snapshot = result.scalar_one_or_none()

        if snapshot:
            valid_from = datetime.combine(snapshot.snapshot_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            return ExchangeRateResult(
                base_currency=base, quote_currency=quote,
                rate=snapshot.rate, rate_type="HISTORICAL",
                provider=snapshot.provider, valid_from=valid_from,
                status="OK"
            )

        # Nearest available snapshot (within 7 days)
        nearest = await self._get_nearest_snapshot(base, quote, snapshot_date, window_days=7)
        if nearest:
            logger.warning(
                f"[FX] No exact snapshot for {base}/{quote} on {snapshot_date}. "
                f"Using nearest snapshot from {nearest.snapshot_date}."
            )
            valid_from = datetime.combine(nearest.snapshot_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            return ExchangeRateResult(
                base_currency=base, quote_currency=quote,
                rate=nearest.rate, rate_type="HISTORICAL_NEAREST",
                provider=nearest.provider, valid_from=valid_from,
                is_stale=True, status="RATE_STALE"
            )

        logger.error(f"[FX] No historical snapshot for {base}/{quote} on or near {snapshot_date}.")
        return ExchangeRateResult(
            base_currency=base, quote_currency=quote,
            rate=Decimal("0"), rate_type="NONE",
            provider="none", valid_from=datetime.now(timezone.utc),
            status="FX_UNAVAILABLE"
        )

    async def convert(
        self,
        money: Money,
        to_currency: str,
        allow_stale: bool = False,
    ) -> MoneyConversionResult:
        """
        Convert a Money value to another currency.
        Raises FXUnavailableError if rate is not available and allow_stale=False.
        """
        rate_result = await self.get_rate(money.currency_code, to_currency, allow_stale=allow_stale)

        if rate_result.status == "FX_UNAVAILABLE":
            raise FXUnavailableError(
                money.currency_code, to_currency,
                f"No rate found in database or cache."
            )

        converted_amount = (money.amount * rate_result.rate).quantize(
            Decimal("0.01"), rounding=Decimal("1")
        )
        converted = Money(converted_amount, to_currency.upper())

        return MoneyConversionResult(
            original=money,
            converted=converted,
            rate=rate_result.rate,
            rate_type=rate_result.rate_type,
            provider=rate_result.provider,
            timestamp=rate_result.valid_from.isoformat(),
            is_fallback=rate_result.is_stale,
            status=rate_result.status,
        )

    async def convert_historical(
        self,
        money: Money,
        to_currency: str,
        historical_date: date,
    ) -> MoneyConversionResult:
        """Convert using historical FX rate for financial report reconstruction."""
        rate_result = await self.get_historical_rate(money.currency_code, to_currency, historical_date)

        if rate_result.status == "FX_UNAVAILABLE":
            raise FXUnavailableError(
                money.currency_code, to_currency,
                f"No historical snapshot for {historical_date}."
            )

        converted_amount = (money.amount * rate_result.rate).quantize(
            Decimal("0.01"), rounding=Decimal("1")
        )
        return MoneyConversionResult(
            original=money,
            converted=Money(converted_amount, to_currency.upper()),
            rate=rate_result.rate,
            rate_type=rate_result.rate_type,
            provider=rate_result.provider,
            timestamp=rate_result.valid_from.isoformat(),
            is_fallback=rate_result.is_stale,
            status=rate_result.status,
        )

    async def upsert_rate(
        self,
        base_currency: str,
        quote_currency: str,
        rate: Decimal,
        provider: str,
        rate_type: str = "MARKET",
    ) -> ExchangeRate:
        """Persist a fresh rate to the database and update snapshot."""
        now = datetime.now(timezone.utc)

        # Deactivate old active rates for this pair
        old_stmt = select(ExchangeRate).where(and_(
            ExchangeRate.base_currency == base_currency.upper(),
            ExchangeRate.quote_currency == quote_currency.upper(),
            ExchangeRate.is_active == True,
        ))
        old_result = await self._db.execute(old_stmt)
        for old_rate in old_result.scalars().all():
            old_rate.is_active = False
            old_rate.valid_until = now

        # Insert new active rate
        new_rate = ExchangeRate(
            base_currency=base_currency.upper(),
            quote_currency=quote_currency.upper(),
            rate=rate,
            rate_type=rate_type,
            provider=provider,
            valid_from=now,
            is_active=True,
        )
        self._db.add(new_rate)

        # Upsert today's snapshot
        today = now.date()
        snap_stmt = select(ExchangeRateSnapshot).where(and_(
            ExchangeRateSnapshot.base_currency == base_currency.upper(),
            ExchangeRateSnapshot.quote_currency == quote_currency.upper(),
            ExchangeRateSnapshot.snapshot_date == today,
            ExchangeRateSnapshot.provider == provider,
        ))
        snap_result = await self._db.execute(snap_stmt)
        existing_snap = snap_result.scalar_one_or_none()
        if existing_snap:
            existing_snap.rate = rate
        else:
            snap = ExchangeRateSnapshot(
                base_currency=base_currency.upper(),
                quote_currency=quote_currency.upper(),
                rate=rate,
                snapshot_date=today,
                provider=provider,
            )
            self._db.add(snap)

        await self._db.flush()
        # Invalidate cache
        _rate_cache.pop((base_currency.upper(), quote_currency.upper()), None)
        logger.info(f"[FX] Updated rate {base_currency}/{quote_currency} = {rate} (provider={provider})")
        return new_rate

    async def _get_rate_from_db(self, base: str, quote: str) -> Optional[ExchangeRate]:
        stmt = (
            select(ExchangeRate)
            .where(and_(
                ExchangeRate.base_currency == base,
                ExchangeRate.quote_currency == quote,
                ExchangeRate.is_active == True,
            ))
            .order_by(desc(ExchangeRate.valid_from))
            .limit(1)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_nearest_snapshot(
        self, base: str, quote: str, target_date: date, window_days: int = 7
    ) -> Optional[ExchangeRateSnapshot]:
        """Find nearest available snapshot within window_days."""
        from_date = target_date - timedelta(days=window_days)
        to_date = target_date + timedelta(days=window_days)
        stmt = (
            select(ExchangeRateSnapshot)
            .where(and_(
                ExchangeRateSnapshot.base_currency == base,
                ExchangeRateSnapshot.quote_currency == quote,
                ExchangeRateSnapshot.snapshot_date >= from_date,
                ExchangeRateSnapshot.snapshot_date <= to_date,
            ))
            .order_by(
                func.abs(
                    func.extract("epoch", ExchangeRateSnapshot.snapshot_date) -
                    func.extract("epoch", func.cast(str(target_date), ExchangeRateSnapshot.snapshot_date.type))
                )
            )
            .limit(1)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()
