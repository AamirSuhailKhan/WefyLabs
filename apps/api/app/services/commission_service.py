from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

@dataclass
class CommissionBreakdown:
    property_sale_price: Decimal
    gross_commission_rate_pct: Decimal
    total_gci: Decimal
    brokerage_split_pct: Decimal
    agent_split_pct: Decimal
    brokerage_commission: Decimal
    agent_net_commission: Decimal

class CommissionCalculatorService:
    """
    Real Estate Commission & GCI Split Calculator surpassing Follow Up Boss & Salesforce Propertybase.
    Computes Gross Commission Income (GCI), Brokerage Splits, and Net Agent Payouts.
    """

    @classmethod
    def calculate_deal_commission(
        cls,
        property_sale_price: Decimal | int | str,
        gross_commission_rate_pct: Decimal | float | str = Decimal("2.0"),
        agent_split_pct: Decimal | float | str = Decimal("70.0"),
    ) -> CommissionBreakdown:
        """Return a display-only quote without binary floating-point rounding.

        The persisted commission workflow has its own 4-decimal accounting model.
        This calculator intentionally rounds only its final customer-facing amounts
        to currency minor units, with the brokerage share receiving the remainder.
        """
        try:
            sale_price = Decimal(str(property_sale_price))
            commission_rate = Decimal(str(gross_commission_rate_pct))
            agent_split = Decimal(str(agent_split_pct))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Commission inputs must be valid decimal values") from exc

        if sale_price <= 0:
            raise ValueError("Property sale price must be positive")
        if not Decimal("0") <= commission_rate <= Decimal("100"):
            raise ValueError("Gross commission rate must be between 0 and 100")
        if not Decimal("0") <= agent_split <= Decimal("100"):
            raise ValueError("Agent split must be between 0 and 100")

        minor_unit = Decimal("0.01")
        total_gci = (sale_price * commission_rate / Decimal("100")).quantize(
            minor_unit, rounding=ROUND_HALF_UP
        )
        agent_net = (total_gci * agent_split / Decimal("100")).quantize(
            minor_unit, rounding=ROUND_HALF_UP
        )
        brokerage_net = total_gci - agent_net

        return CommissionBreakdown(
            property_sale_price=sale_price,
            gross_commission_rate_pct=commission_rate,
            total_gci=total_gci,
            brokerage_split_pct=Decimal("100") - agent_split,
            agent_split_pct=agent_split,
            brokerage_commission=brokerage_net,
            agent_net_commission=agent_net
        )
