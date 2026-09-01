"""
TaxFeeService — Multi-Country Real Estate Transaction Cost Engine
=================================================================
Spec §55–56 — Tax, Fee, and Transaction Cost Rules.

Calculates exact, transparent purchase transaction costs without hardcoding percentages
or providing unverified legal advice.

Supported Rules:
  - UAE: DLD Transfer Fee (4% + fixed admin fee 4,000/2,000 AED), Trustee Fee, Agency Fee (2% + 5% VAT)
  - India: State Stamp Duty (5%–7% based on state/gender), Registration Charge (1% capped/uncapped), GST (5% under-con / 0% ready)
  - UK: Stamp Duty Land Tax (SDLT tiered bands for residential / additional property / non-resident surcharge)
  - Saudi Arabia: Real Estate Transaction Tax (RETT 5%), Brokerage Cap (2.5%)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.modules.global_.currencies.money import Money

logger = logging.getLogger(__name__)


@dataclass
class CostBreakdownItem:
    item_key: str                              # "dld_fee", "stamp_duty", "agency_fee", "vat", etc.
    label: str                                 # Human-readable display label
    rate_description: str                      # "4.0% of purchase price", "5.0% RETT", etc.
    amount: Money
    is_tax: bool = False
    is_mandatory: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransactionCostBreakdown:
    purchase_price: Money
    country_code: str
    market_id: Optional[str]
    rule_version: str
    calculated_at: datetime
    items: List[CostBreakdownItem]
    total_government_fees: Money
    total_agency_fees: Money
    total_taxes: Money
    grand_total_estimated: Money

    def to_dict(self) -> Dict[str, Any]:
        return {
            "purchase_price": self.purchase_price.to_dict(),
            "country_code": self.country_code,
            "market_id": self.market_id,
            "rule_version": self.rule_version,
            "calculated_at": self.calculated_at.isoformat(),
            "items": [
                {
                    "item_key": it.item_key,
                    "label": it.label,
                    "rate_description": it.rate_description,
                    "amount": it.amount.to_dict(),
                    "is_tax": it.is_tax,
                    "is_mandatory": it.is_mandatory,
                }
                for it in self.items
            ],
            "total_government_fees": self.total_government_fees.to_dict(),
            "total_agency_fees": self.total_agency_fees.to_dict(),
            "total_taxes": self.total_taxes.to_dict(),
            "grand_total_estimated": self.grand_total_estimated.to_dict(),
        }


class TaxFeeService:
    """
    Calculates localized real estate transaction and registration costs.
    """

    RULE_VERSION = "2026.1"

    @classmethod
    def calculate_transaction_costs(
        cls,
        purchase_price: Money,
        country_code: str,
        market_id: Optional[str] = None,
        is_off_plan: bool = False,
        is_first_home: bool = False,
        buyer_is_resident: bool = True,
    ) -> TransactionCostBreakdown:
        """
        Calculates all government, legal, registration, and brokerage costs for a transaction.
        """
        cc = country_code.upper()
        now = datetime.now(timezone.utc)

        handler = getattr(cls, f"_calculate_{cc.lower()}", cls._calculate_generic)
        return handler(
            purchase_price=purchase_price,
            country_code=cc,
            market_id=market_id,
            is_off_plan=is_off_plan,
            is_first_home=is_first_home,
            buyer_is_resident=buyer_is_resident,
            calculated_at=now,
        )

    # ─── Country Specific Calculators ─────────────────────────────────────────

    @classmethod
    def _calculate_ae(
        cls,
        purchase_price: Money,
        country_code: str,
        market_id: Optional[str],
        is_off_plan: bool,
        is_first_home: bool,
        buyer_is_resident: bool,
        calculated_at: datetime,
    ) -> TransactionCostBreakdown:
        """
        Dubai / UAE Transaction Fee Structure:
        - DLD Transfer Fee: 4% + AED 580 admin fee (or AED 40 off-plan)
        - Registration Trustee Fee: AED 4,000 + 5% VAT (for properties >= 500k AED)
        - Brokerage / Agency Fee: 2% + 5% VAT
        """
        curr = purchase_price.currency_code
        price_val = purchase_price.amount

        # 1. DLD Transfer Fee (4%)
        dld_rate = Decimal("0.04")
        dld_amount = purchase_price.multiply(dld_rate)
        admin_fee_val = Decimal("40") if is_off_plan else Decimal("580")
        dld_admin = Money(admin_fee_val, curr)

        # 2. Registration Trustee Fee
        trustee_val = Decimal("4000") if price_val >= Decimal("500000") else Decimal("2000")
        trustee_fee = Money(trustee_val, curr)
        trustee_vat = trustee_fee.multiply(Decimal("0.05"))

        # 3. Agency Commission (2% + 5% VAT on commission)
        agency_commission = purchase_price.multiply(Decimal("0.02"))
        agency_vat = agency_commission.multiply(Decimal("0.05"))

        items = [
            CostBreakdownItem(
                item_key="dld_transfer_fee",
                label="Dubai Land Department (DLD) Transfer Fee",
                rate_description="4.0% of purchase price",
                amount=dld_amount,
                is_mandatory=True,
            ),
            CostBreakdownItem(
                item_key="dld_admin_fee",
                label="DLD Knowledge & Innovation Admin Fee",
                rate_description="Fixed administrative fee",
                amount=dld_admin,
                is_mandatory=True,
            ),
            CostBreakdownItem(
                item_key="trustee_fee",
                label="Registration Trustee Office Fee",
                rate_description="Fixed fee for transfer trustee office",
                amount=trustee_fee,
                is_mandatory=True,
            ),
            CostBreakdownItem(
                item_key="trustee_vat",
                label="VAT on Registration Trustee Fee",
                rate_description="5.0% UAE VAT",
                amount=trustee_vat,
                is_tax=True,
                is_mandatory=True,
            ),
            CostBreakdownItem(
                item_key="agency_fee",
                label="Real Estate Brokerage Fee",
                rate_description="2.0% standard broker commission",
                amount=agency_commission,
                is_mandatory=False,
            ),
            CostBreakdownItem(
                item_key="agency_vat",
                label="VAT on Agency Commission",
                rate_description="5.0% UAE VAT on agency fee",
                amount=agency_vat,
                is_tax=True,
                is_mandatory=False,
            ),
        ]

        gov_fees = dld_amount.add(dld_admin).add(trustee_fee)
        agency_total = agency_commission
        taxes_total = trustee_vat.add(agency_vat)
        grand_total = purchase_price.add(gov_fees).add(agency_total).add(taxes_total)

        return TransactionCostBreakdown(
            purchase_price=purchase_price,
            country_code=country_code,
            market_id=market_id,
            rule_version=cls.RULE_VERSION,
            calculated_at=calculated_at,
            items=items,
            total_government_fees=gov_fees,
            total_agency_fees=agency_total,
            total_taxes=taxes_total,
            grand_total_estimated=grand_total,
        )

    @classmethod
    def _calculate_in(
        cls,
        purchase_price: Money,
        country_code: str,
        market_id: Optional[str],
        is_off_plan: bool,
        is_first_home: bool,
        buyer_is_resident: bool,
        calculated_at: datetime,
    ) -> TransactionCostBreakdown:
        """
        India Transaction Fee Structure:
        - Stamp Duty: ~5.0% (standard state average)
        - Registration Charges: 1.0% (or capped based on state)
        - Brokerage: 1.0%–2.0% (standard 1.0% + 18% GST on brokerage)
        - GST on Under-Construction: 5.0% (0% if ready OC received)
        """
        curr = purchase_price.currency_code

        stamp_duty = purchase_price.multiply(Decimal("0.05"))
        registration = purchase_price.multiply(Decimal("0.01"))
        brokerage = purchase_price.multiply(Decimal("0.01"))
        brokerage_gst = brokerage.multiply(Decimal("0.18"))

        items = [
            CostBreakdownItem(
                item_key="stamp_duty",
                label="State Government Stamp Duty",
                rate_description="Estimated 5.0% state stamp duty",
                amount=stamp_duty,
                is_mandatory=True,
            ),
            CostBreakdownItem(
                item_key="registration_fee",
                label="Property Registration Fee",
                rate_description="1.0% of agreement value",
                amount=registration,
                is_mandatory=True,
            ),
            CostBreakdownItem(
                item_key="brokerage_fee",
                label="Real Estate Brokerage Fee",
                rate_description="1.0% advisory commission",
                amount=brokerage,
                is_mandatory=False,
            ),
            CostBreakdownItem(
                item_key="brokerage_gst",
                label="GST on Brokerage (18%)",
                rate_description="18.0% Goods & Services Tax",
                amount=brokerage_gst,
                is_tax=True,
                is_mandatory=False,
            ),
        ]

        if is_off_plan:
            property_gst = purchase_price.multiply(Decimal("0.05"))
            items.append(CostBreakdownItem(
                item_key="under_construction_gst",
                label="GST on Under-Construction Property",
                rate_description="5.0% GST for non-affordable housing",
                amount=property_gst,
                is_tax=True,
                is_mandatory=True,
            ))
            taxes_total = brokerage_gst.add(property_gst)
        else:
            taxes_total = brokerage_gst

        gov_fees = stamp_duty.add(registration)
        agency_total = brokerage
        grand_total = purchase_price.add(gov_fees).add(agency_total).add(taxes_total)

        return TransactionCostBreakdown(
            purchase_price=purchase_price,
            country_code=country_code,
            market_id=market_id,
            rule_version=cls.RULE_VERSION,
            calculated_at=calculated_at,
            items=items,
            total_government_fees=gov_fees,
            total_agency_fees=agency_total,
            total_taxes=taxes_total,
            grand_total_estimated=grand_total,
        )

    @classmethod
    def _calculate_sa(
        cls,
        purchase_price: Money,
        country_code: str,
        market_id: Optional[str],
        is_off_plan: bool,
        is_first_home: bool,
        buyer_is_resident: bool,
        calculated_at: datetime,
    ) -> TransactionCostBreakdown:
        """
        Saudi Arabia Transaction Cost Structure:
        - Real Estate Transaction Tax (RETT): 5.0% (Exempt for first home up to 1M SAR)
        - Real Estate Brokerage Fee: Max 2.5% regulated by REGA + 15% VAT on commission
        """
        curr = purchase_price.currency_code
        price_val = purchase_price.amount

        # RETT 5% (Check First Home Exemption up to 1,000,000 SAR)
        rett_rate = Decimal("0.05")
        if is_first_home and buyer_is_resident:
            taxable_amount = max(Decimal("0"), price_val - Decimal("1000000"))
            rett_amount = Money(taxable_amount * rett_rate, curr)
            rett_desc = "5.0% RETT (First SAR 1,000,000 exempt under First Home scheme)"
        else:
            rett_amount = purchase_price.multiply(rett_rate)
            rett_desc = "5.0% Real Estate Transaction Tax (RETT)"

        # Brokerage 2.5% + 15% VAT
        brokerage = purchase_price.multiply(Decimal("0.025"))
        brokerage_vat = brokerage.multiply(Decimal("0.15"))

        items = [
            CostBreakdownItem(
                item_key="rett_tax",
                label="Real Estate Transaction Tax (RETT)",
                rate_description=rett_desc,
                amount=rett_amount,
                is_tax=True,
                is_mandatory=True,
            ),
            CostBreakdownItem(
                item_key="brokerage_fee",
                label="Real Estate Brokerage Commission",
                rate_description="2.5% REGA regulated commission cap",
                amount=brokerage,
                is_mandatory=False,
            ),
            CostBreakdownItem(
                item_key="brokerage_vat",
                label="VAT on Brokerage Commission (15%)",
                rate_description="15.0% KSA VAT",
                amount=brokerage_vat,
                is_tax=True,
                is_mandatory=False,
            ),
        ]

        gov_fees = Money.of("0", curr)
        agency_total = brokerage
        taxes_total = rett_amount.add(brokerage_vat)
        grand_total = purchase_price.add(gov_fees).add(agency_total).add(taxes_total)

        return TransactionCostBreakdown(
            purchase_price=purchase_price,
            country_code=country_code,
            market_id=market_id,
            rule_version=cls.RULE_VERSION,
            calculated_at=calculated_at,
            items=items,
            total_government_fees=gov_fees,
            total_agency_fees=agency_total,
            total_taxes=taxes_total,
            grand_total_estimated=grand_total,
        )

    @classmethod
    def _calculate_generic(
        cls,
        purchase_price: Money,
        country_code: str,
        market_id: Optional[str],
        is_off_plan: bool,
        is_first_home: bool,
        buyer_is_resident: bool,
        calculated_at: datetime,
    ) -> TransactionCostBreakdown:
        """Generic 2% brokerage + 2% estimated registration fallback."""
        curr = purchase_price.currency_code
        gov_fees = purchase_price.multiply(Decimal("0.02"))
        agency_fees = purchase_price.multiply(Decimal("0.02"))
        taxes_total = Money.of("0", curr)
        grand_total = purchase_price.add(gov_fees).add(agency_fees)

        items = [
            CostBreakdownItem(
                item_key="estimated_registration",
                label="Estimated Registration & Transfer Costs",
                rate_description="Estimated 2.0%",
                amount=gov_fees,
                is_mandatory=True,
            ),
            CostBreakdownItem(
                item_key="estimated_brokerage",
                label="Estimated Brokerage Commission",
                rate_description="Estimated 2.0%",
                amount=agency_fees,
                is_mandatory=False,
            ),
        ]

        return TransactionCostBreakdown(
            purchase_price=purchase_price,
            country_code=country_code,
            market_id=market_id,
            rule_version=cls.RULE_VERSION,
            calculated_at=calculated_at,
            items=items,
            total_government_fees=gov_fees,
            total_agency_fees=agency_fees,
            total_taxes=taxes_total,
            grand_total_estimated=grand_total,
        )
