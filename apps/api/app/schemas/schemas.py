from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, EmailStr, Field

# Broker Schemas
class BrokerCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str
    agency_name: Optional[str] = None
    city: Optional[str] = "Bengaluru"
    whatsapp_number: Optional[str] = None

class BrokerLogin(BaseModel):
    email: EmailStr

class BrokerUpdate(BaseModel):
    name: Optional[str] = None
    agency_name: Optional[str] = None
    city: Optional[str] = None
    whatsapp_number: Optional[str] = None

class BrokerResponse(BaseModel):
    id: str
    email: str
    phone: str
    name: str
    agency_name: Optional[str] = None
    city: str
    whatsapp_number: Optional[str] = None
    subscription_status: str
    subscription_plan: Optional[str] = None
    trial_ends_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Conversation Schemas
class ConversationCreate(BaseModel):
    lead_id: str
    direction: str # inbound | outbound
    sender_type: str # bot | lead | broker
    message: str
    message_type: Optional[str] = "text"
    whatsapp_message_id: Optional[str] = None

class ConversationResponse(BaseModel):
    id: str
    lead_id: str
    direction: str
    sender_type: str
    message: str
    message_type: str
    whatsapp_message_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Lead Schemas
class LeadCreate(BaseModel):
    phone: str
    name: Optional[str] = None
    source: Optional[str] = "manual"
    notes: Optional[str] = None

class LeadUpdateStatus(BaseModel):
    status: str # pending | active | qualified | converted | lost | spam

class ExtractedDataSchema(BaseModel):
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    property_type: Optional[str] = None
    transaction_type: Optional[str] = None
    preferred_locations: List[str] = []
    timeline: Optional[str] = None
    loan_status: Optional[str] = None

class ScoreResponse(BaseModel):
    id: str
    lead_id: str
    score: str
    confidence: float
    reasoning: str
    extracted_data: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class LeadTagSchema(BaseModel):
    id: str
    name: str
    color: str

    class Config:
        from_attributes = True

class LeadNoteSchema(BaseModel):
    id: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

class TaskSchema(BaseModel):
    id: str
    title: str
    due_at: datetime
    status: str
    reminder_sent: str

    class Config:
        from_attributes = True

class LeadResponse(BaseModel):
    id: str
    broker_id: str
    phone: str
    name: Optional[str] = None
    source: str
    score: Optional[str] = "pending"
    score_confidence: float = 0.0
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    property_type: Optional[str] = None
    transaction_type: Optional[str] = None
    preferred_locations: List[str] = []
    timeline: Optional[str] = None
    loan_status: Optional[str] = None
    status: str
    stage_id: Optional[str] = None
    stage_name: str = "New"
    tags: List[LeadTagSchema] = []
    notes: List[LeadNoteSchema] = []
    tasks: List[TaskSchema] = []
    last_message_at: Optional[datetime] = None
    qualified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class LeadDetailResponse(LeadResponse):
    conversations: List[ConversationResponse] = []
    latest_score: Optional[ScoreResponse] = None

class LeadListResponse(BaseModel):
    total: int
    items: List[LeadResponse]

# AI Qualification Schemas
class AIQualifyResponse(BaseModel):
    score: str
    confidence: float
    reasoning: str
    extracted_data: ExtractedDataSchema
    recommended_action: str
    follow_up_needed: bool

# WhatsApp Webhook & Simulator Input
class SimulateMessageInput(BaseModel):
    broker_phone: str = "+919876543210"
    lead_phone: str
    lead_name: Optional[str] = "Rajesh Kumar"
    message: str

class SimulateResponse(BaseModel):
    lead_id: str
    reply_message: str
    lead_status: str
    score: Optional[str] = None
    score_card: Optional[Dict[str, Any]] = None

# Admin Stats Schema
class AdminStatsResponse(BaseModel):
    total_brokers: int
    active_brokers: int
    total_leads: int
    qualified_leads: int
    hot_leads: int
    mrr_inr: int
