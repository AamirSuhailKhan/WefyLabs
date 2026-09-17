"""
Part 35 — AI Real Estate Revenue Autopilot Module
==================================================
Exports router, engine, action handler, and outreach generator.
"""
from app.modules.revenue_autopilot.router import router as revenue_router
from app.modules.revenue_autopilot.engine import RevenueAutopilotEngine
from app.modules.revenue_autopilot.action_handler import RevenueActionHandler
from app.modules.revenue_autopilot.outreach_generator import RevenueOutreachGenerator

__all__ = [
    "revenue_router",
    "RevenueAutopilotEngine",
    "RevenueActionHandler",
    "RevenueOutreachGenerator",
]
