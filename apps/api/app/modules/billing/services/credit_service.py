"""
WefyLabs Canonical Append-Only Credit Ledger & Balance Service
==============================================================
Rules:
- Authoritative balance is computed from immutable CreditLedgerEntry records.
- Cached in CreditBalance table for accelerated reads.
- Balance can NEVER be negative.
- Entries: CREDIT_ISSUED, CREDIT_APPLIED, CREDIT_EXPIRED, CREDIT_REVERSED.
- Every entry records reason, actor, and source reference.
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing_models import (
    CreditBalance,
    CreditLedgerEntry,
    CreditEntryType,
)
from app.modules.billing.domain.money import Money

logger = logging.getLogger("wefylabs.billing.credits")


class InsufficientCreditError(ValueError):
    """Raised when an operation attempts to consume more credit than available."""
    pass


class CreditService:
    """
    Append-only credit ledger and balance service.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_balance(self, organization_id: uuid.UUID, currency: str = "INR") -> Money:
        """
        Retrieves authoritative credit balance for an organization.
        """
        curr = currency.upper()
        stmt = select(CreditBalance).where(
            and_(
                CreditBalance.organization_id == organization_id,
                CreditBalance.currency == curr,
            )
        )
        bal_row = (await self.db.execute(stmt)).scalars().first()
        if not bal_row:
            return Money(Decimal("0.0"), currency=curr)
        return Money(bal_row.balance, currency=curr)

    async def _update_cached_balance(
        self,
        organization_id: uuid.UUID,
        currency: str,
        new_balance: Decimal
    ) -> None:
        stmt = select(CreditBalance).where(
            and_(
                CreditBalance.organization_id == organization_id,
                CreditBalance.currency == currency,
            )
        )
        bal_row = (await self.db.execute(stmt)).scalars().first()
        if not bal_row:
            bal_row = CreditBalance(
                organization_id=organization_id,
                currency=currency,
                balance=new_balance,
            )
            self.db.add(bal_row)
        else:
            bal_row.balance = new_balance

    async def issue_credit(
        self,
        organization_id: uuid.UUID,
        amount: Money,
        reason: str,
        actor_id: Optional[str] = None,
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None,
    ) -> CreditLedgerEntry:
        """
        Issues new credit to organization account.
        """
        if amount.is_negative() or amount.is_zero():
            raise ValueError("Credit amount to issue must be strictly positive.")

        current_bal = await self.get_balance(organization_id, amount.currency)
        new_bal = current_bal + amount

        entry = CreditLedgerEntry(
            organization_id=organization_id,
            entry_type=CreditEntryType.CREDIT_ISSUED.value,
            amount=amount.amount,
            currency=amount.currency,
            balance_after=new_bal.amount,
            reason=reason,
            actor_id=actor_id,
            reference_type=reference_type,
            reference_id=reference_id,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(entry)
        await self._update_cached_balance(organization_id, amount.currency, new_bal.amount)
        await self.db.commit()
        await self.db.refresh(entry)

        logger.info(f"[CreditService] Issued {amount} to org {organization_id}. New balance: {new_bal}")
        return entry

    async def apply_credit(
        self,
        organization_id: uuid.UUID,
        amount: Money,
        invoice_id: Optional[uuid.UUID] = None,
        actor_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> CreditLedgerEntry:
        """
        Consumes credit against an invoice or adjustment.
        Raises InsufficientCreditError if requested amount exceeds balance.
        """
        if amount.is_negative() or amount.is_zero():
            raise ValueError("Credit amount to apply must be strictly positive.")

        current_bal = await self.get_balance(organization_id, amount.currency)
        if current_bal < amount:
            raise InsufficientCreditError(
                f"Requested credit consumption {amount} exceeds available balance {current_bal}."
            )

        new_bal = current_bal - amount

        entry = CreditLedgerEntry(
            organization_id=organization_id,
            entry_type=CreditEntryType.CREDIT_APPLIED.value,
            amount=amount.amount,
            currency=amount.currency,
            balance_after=new_bal.amount,
            reason=reason or f"Applied to invoice {invoice_id}",
            actor_id=actor_id,
            reference_type="INVOICE" if invoice_id else "ADJUSTMENT",
            reference_id=str(invoice_id) if invoice_id else None,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(entry)
        await self._update_cached_balance(organization_id, amount.currency, new_bal.amount)
        await self.db.commit()
        await self.db.refresh(entry)

        logger.info(f"[CreditService] Applied {amount} from org {organization_id}. New balance: {new_bal}")
        return entry

    async def reverse_credit(
        self,
        organization_id: uuid.UUID,
        amount: Money,
        reason: str,
        actor_id: Optional[str] = None,
    ) -> CreditLedgerEntry:
        """
        Reverses previously granted credit. Cannot result in negative balance.
        """
        if amount.is_negative() or amount.is_zero():
            raise ValueError("Credit amount to reverse must be strictly positive.")

        current_bal = await self.get_balance(organization_id, amount.currency)
        if current_bal < amount:
            raise InsufficientCreditError(
                f"Cannot reverse {amount}: exceeds current balance {current_bal}."
            )

        new_bal = current_bal - amount

        entry = CreditLedgerEntry(
            organization_id=organization_id,
            entry_type=CreditEntryType.CREDIT_REVERSED.value,
            amount=amount.amount,
            currency=amount.currency,
            balance_after=new_bal.amount,
            reason=reason,
            actor_id=actor_id,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(entry)
        await self._update_cached_balance(organization_id, amount.currency, new_bal.amount)
        await self.db.commit()
        await self.db.refresh(entry)

        return entry

    async def list_ledger(
        self,
        organization_id: uuid.UUID,
        limit: int = 50
    ) -> List[CreditLedgerEntry]:
        """
        Lists immutable credit entries for the tenant.
        """
        stmt = (
            select(CreditLedgerEntry)
            .where(CreditLedgerEntry.organization_id == organization_id)
            .order_by(CreditLedgerEntry.created_at.desc())
            .limit(limit)
        )
        return (await self.db.execute(stmt)).scalars().all()
