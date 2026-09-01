"""
Volume 2 PART 1 — Universal Lead Ingestion Models
=================================================
SQLAlchemy 2.0 models for: ConnectorConfig, LeadImportBatch,
LeadImportItem, OriginalPayload, IngestionLog.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, BigInteger, Float, JSON, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

JSONBType = JSONB().with_variant(JSON(), "sqlite")


def _gen_uuid() -> str:
    return str(uuid.uuid4())


class ConnectorConfig(Base):
    """
    Configuration for an active source connector per organization.
    Stores encrypted connector credentials (e.g. Meta Lead Ads token, Twilio Auth Token).
    """
    __tablename__ = "connector_configs"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    connector_type = mapped_column(String(50), nullable=False, index=True) # website | whatsapp | telegram | email | csv | webhook | hubspot
    name = mapped_column(String(100), nullable=False)
    description = mapped_column(Text, nullable=True)
    credentials_encrypted = mapped_column(Text, nullable=True)
    settings_json = mapped_column(JSONBType, default=dict, nullable=False)
    is_active = mapped_column(Boolean, default=True, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class LeadImportBatch(Base):
    """
    Bulk File Import Batch metadata (CSV/Excel 100k+ records).
    Tracks batch processing progress, totals, failures, and execution times.
    """
    __tablename__ = "lead_import_batches"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    user_id = mapped_column(String(36), nullable=False, index=True)
    filename = mapped_column(String(255), nullable=False)
    file_size_bytes = mapped_column(BigInteger, default=0, nullable=False)
    total_records = mapped_column(Integer, default=0, nullable=False)
    processed_records = mapped_column(Integer, default=0, nullable=False)
    failed_records = mapped_column(Integer, default=0, nullable=False)
    duplicate_records = mapped_column(Integer, default=0, nullable=False)
    status = mapped_column(String(20), default="pending", nullable=False, index=True) # pending | processing | completed | failed
    error_summary = mapped_column(Text, nullable=True)
    started_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = mapped_column(DateTime(timezone=True), nullable=True)


class LeadImportItem(Base):
    """
    Individual item status record within a LeadImportBatch.
    Enables line-by-line failure inspection and Dead-Letter Queue replay.
    """
    __tablename__ = "lead_import_items"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    batch_id = mapped_column(String(36), nullable=False, index=True)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    row_index = mapped_column(Integer, nullable=False)
    raw_data = mapped_column(JSONBType, default=dict, nullable=False)
    status = mapped_column(String(20), default="pending", nullable=False, index=True) # pending | processed | failed | skipped_duplicate
    error_message = mapped_column(Text, nullable=True)
    lead_id = mapped_column(String(36), nullable=True)
    processed_at = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_import_item_batch_row", "batch_id", "row_index"),
    )


class OriginalPayload(Base):
    """
    Immutable raw payload store prior to normalization.
    Preserves exact source data for audit, compliance, and debugging.
    """
    __tablename__ = "original_payloads"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    ingestion_id = mapped_column(String(36), unique=True, nullable=False, index=True)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    source = mapped_column(String(50), nullable=False, index=True)
    raw_payload_json = mapped_column(JSONBType, default=dict, nullable=False)
    headers_json = mapped_column(JSONBType, default=dict, nullable=True)
    ip_address = mapped_column(String(45), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class IngestionLog(Base):
    """
    Audit log of every lead ingestion attempt.
    Tracks latency, validation status, idempotency keys, and routing decisions.
    """
    __tablename__ = "ingestion_logs"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    ingestion_id = mapped_column(String(36), nullable=False, index=True)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    source = mapped_column(String(50), nullable=False, index=True)
    idempotency_key = mapped_column(String(128), nullable=True, index=True)
    status = mapped_column(String(20), nullable=False, index=True) # success | rejected | duplicate | failed
    lead_id = mapped_column(String(36), nullable=True)
    latency_ms = mapped_column(Float, default=0.0, nullable=False)
    error_details = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index("ix_ingestion_log_org_status", "organization_id", "status"),
    )
