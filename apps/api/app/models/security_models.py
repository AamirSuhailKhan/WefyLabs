"""
PART 9 — Enterprise Security, Infrastructure, Backup & Disaster Recovery Models
=============================================================================
SQLAlchemy models for: TokenBlacklist, PasswordHistory, BackupJob,
DisasterRecoveryPlan, ComplianceAuditReport.
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


class TokenBlacklist(Base):
    """
    Revoked JWT token registry (JTI blacklist).
    Checked on every authenticated request for instant session termination.
    """
    __tablename__ = "token_blacklist"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    jti = mapped_column(String(255), unique=True, nullable=False, index=True)
    user_id = mapped_column(String(36), nullable=False, index=True)
    reason = mapped_column(String(100), default="logout", nullable=False) # logout | security_revocation | password_reset
    expires_at = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class PasswordHistory(Base):
    """Password history log to enforce password non-reuse policies."""
    __tablename__ = "password_history"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    user_id = mapped_column(String(36), nullable=False, index=True)
    password_hash = mapped_column(String(255), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_pwd_hist_user_time", "user_id", "created_at"),
    )


class BackupJob(Base):
    """Automated Database Backup execution log."""
    __tablename__ = "backup_jobs"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    backup_type = mapped_column(String(20), default="daily_full", nullable=False) # daily_full | hourly_incremental | manual
    status = mapped_column(String(20), default="pending", nullable=False, index=True) # pending | running | completed | failed
    file_name = mapped_column(String(255), nullable=False)
    storage_provider = mapped_column(String(30), default="s3", nullable=False) # s3 | r2 | local
    storage_path = mapped_column(String(500), nullable=False)
    size_bytes = mapped_column(BigInteger, default=0, nullable=False)
    checksum_sha256 = mapped_column(String(64), nullable=True)
    duration_seconds = mapped_column(Float, default=0.0, nullable=False)
    is_encrypted = mapped_column(Boolean, default=True, nullable=False)
    error_message = mapped_column(Text, nullable=True)
    started_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = mapped_column(DateTime(timezone=True), nullable=True)


class DisasterRecoveryPlan(Base):
    """Disaster recovery target configuration & drill log."""
    __tablename__ = "disaster_recovery_plans"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    name = mapped_column(String(100), nullable=False)
    target_rpo_minutes = mapped_column(Integer, default=15, nullable=False)
    target_rto_minutes = mapped_column(Integer, default=60, nullable=False)
    status = mapped_column(String(20), default="ready", nullable=False) # ready | testing | recovering | failed
    last_drill_at = mapped_column(DateTime(timezone=True), nullable=True)
    last_drill_status = mapped_column(String(20), nullable=True)
    recovery_playbook_json = mapped_column(JSONBType, default=dict, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ComplianceAuditReport(Base):
    """Automated compliance verification report (SOC2, GDPR, ISO27001)."""
    __tablename__ = "compliance_audit_reports"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    framework = mapped_column(String(30), nullable=False, index=True) # SOC2 | GDPR | ISO27001 | CCPA
    status = mapped_column(String(20), default="passed", nullable=False) # passed | warning | failed
    evidence_json = mapped_column(JSONBType, default=dict, nullable=False)
    generated_by = mapped_column(String(36), nullable=True)
    generated_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
