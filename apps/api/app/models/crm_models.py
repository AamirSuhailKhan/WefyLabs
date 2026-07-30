import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

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
