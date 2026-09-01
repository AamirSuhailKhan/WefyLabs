from app.modules.leads.service.lead_service import LeadService
from app.modules.leads.service.legacy_service import (
    list_leads, create_lead, get_lead_by_id, update_lead_status,
    update_lead_stage, add_lead_note, soft_delete_lead
)

__all__ = [
    "LeadService",
    "list_leads",
    "create_lead",
    "get_lead_by_id",
    "update_lead_status",
    "update_lead_stage",
    "add_lead_note",
    "soft_delete_lead",
]
