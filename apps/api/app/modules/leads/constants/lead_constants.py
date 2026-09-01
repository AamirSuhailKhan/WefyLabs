from enum import Enum

class LeadStatus(str, Enum):
    PENDING = "pending"
    QUALIFIED = "qualified"
    UNQUALIFIED = "unqualified"
    CONVERTED = "converted"
    LOST = "lost"
    ARCHIVED = "archived"

class PipelineStage(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    ENGAGED = "engaged"
    OFFER_MADE = "offer_made"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"

class LeadSource(str, Enum):
    MANUAL = "manual"
    WEBSITE = "website"
    WHATSAPP = "whatsapp"
    FACEBOOK = "facebook"
    TELEGRAM = "telegram"
    ZAPIER = "zapier"
    AI_DISCOVERY = "ai_discovery"
