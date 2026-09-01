"""
Part 21.5 — AI Sales Action & Follow-Up Engine
==============================================
"""
from app.modules.sales_action.taxonomies import (
    SalesActionType,
    SalesActionStatus,
    CommunicationChannel,
    ConsentStatus,
    HandoffReason,
)
from app.modules.sales_action.dto import (
    SalesActionDecisionDTO,
    SalesBriefDTO,
    SalesActionExecutionResultDTO,
    FollowUpStateDTO,
    EvaluateSalesActionRequestDTO,
    ApproveSalesActionRequestDTO,
)
from app.modules.sales_action.service import SalesActionDomainService
from app.modules.sales_action.policy_engine import SalesActionPolicyEngine
from app.modules.sales_action.message_generator import SalesActionMessageGenerator
from app.modules.sales_action.action_executor import SalesActionExecutor
from app.modules.sales_action.router import router as sales_action_router

__all__ = [
    "SalesActionType",
    "SalesActionStatus",
    "CommunicationChannel",
    "ConsentStatus",
    "HandoffReason",
    "SalesActionDecisionDTO",
    "SalesBriefDTO",
    "SalesActionExecutionResultDTO",
    "FollowUpStateDTO",
    "EvaluateSalesActionRequestDTO",
    "ApproveSalesActionRequestDTO",
    "SalesActionDomainService",
    "SalesActionPolicyEngine",
    "SalesActionMessageGenerator",
    "SalesActionExecutor",
    "sales_action_router",
]
