import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, BigInteger, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Broker(Base):
    __tablename__ = "brokers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    agency_name = Column(String(255), nullable=True)
    city = Column(String(100), default="Bengaluru", nullable=False)
    whatsapp_number = Column(String(20), nullable=True)
    subscription_status = Column(String(20), default="trial", nullable=False) # trial | active | cancelled | expired
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    subscription_plan = Column(String(50), default="monthly", nullable=True) # monthly | annual
    razorpay_customer_id = Column(String(255), nullable=True)
    razorpay_subscription_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    leads = relationship("Lead", back_populates="broker", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="broker", cascade="all, delete-orphan")


class Lead(Base):
    __tablename__ = "leads"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    broker_id = Column(String(36), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    phone = Column(String(20), nullable=False, index=True)
    name = Column(String(255), nullable=True)
    source = Column(String(50), default="whatsapp_forward", nullable=False) # whatsapp_forward | facebook | google | manual
    score = Column(String(20), default="pending", index=True) # hot | warm | cold | unqualified | pending | spam
    score_confidence = Column(Float, default=0.0) # 0.0 - 1.0
    budget_min = Column(BigInteger, nullable=True)
    budget_max = Column(BigInteger, nullable=True)
    property_type = Column(String(50), nullable=True) # 1bhk | 2bhk | 3bhk | 4bhk_plus | villa | plot | commercial
    transaction_type = Column(String(20), nullable=True) # buy | rent | lease
    preferred_locations = Column(JSON, default=list) # Array of strings
    timeline = Column(String(50), nullable=True) # immediate | 1_month | 3_months | 6_months | flexible
    loan_status = Column(String(50), nullable=True) # pre_approved | in_process | not_started | not_needed
    status = Column(String(20), default="pending", nullable=False, index=True) # pending | active | qualified | converted | lost | spam
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    qualified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    stage_id = Column(String(36), ForeignKey("pipeline_stages.id", ondelete="SET NULL"), nullable=True, index=True)
    stage_name = Column(String(50), default="New", nullable=False) # Fallback stage name

    broker = relationship("Broker", back_populates="leads")
    conversations = relationship("Conversation", back_populates="lead", cascade="all, delete-orphan", order_by="Conversation.created_at")
    scores = relationship("Score", back_populates="lead", cascade="all, delete-orphan")
    follow_ups = relationship("FollowUp", back_populates="lead", cascade="all, delete-orphan")
    notes = relationship("LeadNote", back_populates="lead", cascade="all, delete-orphan", order_by="LeadNote.created_at.desc()")
    tasks = relationship("Task", back_populates="lead", cascade="all, delete-orphan", order_by="Task.due_at.asc()")
    tags = relationship("LeadTag", secondary="lead_tag_assignments", back_populates="leads")
    stage = relationship("PipelineStage", back_populates="leads")


class PipelineStage(Base):
    __tablename__ = "pipeline_stages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    broker_id = Column(String(36), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    order_index = Column(Integer, default=0, nullable=False)
    color = Column(String(7), default="#3B82F6", nullable=False)
    is_default = Column(String(20), default="false") # 'true' | 'false'
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    leads = relationship("Lead", back_populates="stage")


class LeadNote(Base):
    __tablename__ = "lead_notes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    lead_id = Column(String(36), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_id = Column(String(36), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    lead = relationship("Lead", back_populates="notes")


class LeadTag(Base):
    __tablename__ = "lead_tags"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    broker_id = Column(String(36), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    color = Column(String(7), default="#6B7280", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    leads = relationship("Lead", secondary="lead_tag_assignments", back_populates="tags")


class LeadTagAssignment(Base):
    __tablename__ = "lead_tag_assignments"

    lead_id = Column(String(36), ForeignKey("leads.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(String(36), ForeignKey("lead_tags.id", ondelete="CASCADE"), primary_key=True)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    broker_id = Column(String(36), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(String(36), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    due_at = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(String(20), default="pending", nullable=False) # pending | completed | cancelled
    reminder_sent = Column(String(10), default="false") # 'true' | 'false'
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    lead = relationship("Lead", back_populates="tasks")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    lead_id = Column(String(36), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    direction = Column(String(10), nullable=False) # inbound | outbound
    sender_type = Column(String(20), nullable=False) # bot | lead | broker
    message = Column(Text, nullable=False)
    message_type = Column(String(20), default="text", nullable=False) # text | image | template
    whatsapp_message_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    lead = relationship("Lead", back_populates="conversations")


class Score(Base):
    __tablename__ = "scores"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    lead_id = Column(String(36), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    score = Column(String(20), nullable=False)
    confidence = Column(Float, nullable=False)
    reasoning = Column(Text, nullable=False)
    extracted_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    lead = relationship("Lead", back_populates="scores")


class FollowUp(Base):
    __tablename__ = "follow_ups"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    lead_id = Column(String(36), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence_number = Column(Integer, nullable=False) # 1, 2, 3
    scheduled_at = Column(DateTime(timezone=True), nullable=False, index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), default="scheduled", nullable=False) # scheduled | sent | cancelled | failed
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    lead = relationship("Lead", back_populates="follow_ups")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    broker_id = Column(String(36), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    razorpay_payment_id = Column(String(255), nullable=True)
    razorpay_subscription_id = Column(String(255), nullable=True)
    amount = Column(Integer, nullable=False) # in paise
    currency = Column(String(3), default="INR", nullable=False)
    status = Column(String(20), nullable=False) # created | active | cancelled | completed
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    broker = relationship("Broker", back_populates="subscriptions")

