from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class OrganizationQuotaLimits:
    max_leads_per_month: int
    max_team_seats: int
    max_api_requests_per_min: int
    allow_custom_webhooks: bool
    allow_sso_saml: bool

PLAN_QUOTA_LIMITS: Dict[str, OrganizationQuotaLimits] = {
    "starter": OrganizationQuotaLimits(
        max_leads_per_month=100,
        max_team_seats=2,
        max_api_requests_per_min=60,
        allow_custom_webhooks=False,
        allow_sso_saml=False
    ),
    "pro": OrganizationQuotaLimits(
        max_leads_per_month=500,
        max_team_seats=10,
        max_api_requests_per_min=300,
        allow_custom_webhooks=True,
        allow_sso_saml=False
    ),
    "enterprise": OrganizationQuotaLimits(
        max_leads_per_month=10000,
        max_team_seats=500,
        max_api_requests_per_min=5000,
        allow_custom_webhooks=True,
        allow_sso_saml=True
    )
}

class EnterpriseQuotaService:
    """
    Enterprise Usage Quota and Feature Gating Monitor.
    Enforces plan limits for monthly leads, team seats, and API throughput.
    """

    @classmethod
    def get_quota_limits(cls, plan: str) -> OrganizationQuotaLimits:
        return PLAN_QUOTA_LIMITS.get(plan.lower(), PLAN_QUOTA_LIMITS["starter"])

    @classmethod
    def check_lead_qualification_allowed(cls, plan: str, current_monthly_leads_count: int) -> bool:
        limits = cls.get_quota_limits(plan)
        return current_monthly_leads_count < limits.max_leads_per_month

    @classmethod
    def check_seat_addition_allowed(cls, plan: str, current_active_seats: int) -> bool:
        limits = cls.get_quota_limits(plan)
        return current_active_seats < limits.max_team_seats
