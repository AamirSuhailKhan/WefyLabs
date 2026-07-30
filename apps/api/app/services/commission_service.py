from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class CommissionBreakdown:
    property_sale_price: int
    gross_commission_rate_pct: float
    total_gci: float
    brokerage_split_pct: float
    agent_split_pct: float
    brokerage_commission: float
    agent_net_commission: float

class CommissionCalculatorService:
    """
    Real Estate Commission & GCI Split Calculator surpassing Follow Up Boss & Salesforce Propertybase.
    Computes Gross Commission Income (GCI), Brokerage Splits, and Net Agent Payouts.
    """

    @classmethod
    def calculate_deal_commission(
        cls,
        property_sale_price: int,
        gross_commission_rate_pct: float = 2.0, # e.g. 2.0%
        agent_split_pct: float = 70.0 # 70% to agent, 30% to brokerage
    ) -> CommissionBreakdown:
        total_gci = round(property_sale_price * (gross_commission_rate_pct / 100.0), 2)
        agent_net = round(total_gci * (agent_split_pct / 100.0), 2)
        brokerage_net = round(total_gci - agent_net, 2)

        return CommissionBreakdown(
            property_sale_price=property_sale_price,
            gross_commission_rate_pct=gross_commission_rate_pct,
            total_gci=total_gci,
            brokerage_split_pct=round(100.0 - agent_split_pct, 2),
            agent_split_pct=agent_split_pct,
            brokerage_commission=brokerage_net,
            agent_net_commission=agent_net
        )
