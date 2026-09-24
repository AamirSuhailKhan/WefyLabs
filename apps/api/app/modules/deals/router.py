"""
Deals Router Export
===================
Re-exports the deal router from deal_controller for standardized module layout.
"""
from app.modules.deals.controller.deal_controller import router

__all__ = ["router"]
