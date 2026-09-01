from typing import Optional, List
from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.common.response import APIResponse, create_success_response
from app.modules.security.services.file_security import FileSecurityScanner
from app.modules.security.services.password_security import PasswordPolicyEnforcer
from app.modules.secrets.service.secrets_manager import secrets_manager
from app.modules.backup.service.backup_service import BackupService
from app.modules.recovery.service.disaster_recovery_service import DisasterRecoveryService
from app.modules.compliance.service.compliance_service import ComplianceService

router = APIRouter(prefix="/v1/security", tags=["Enterprise Security & DevSecOps"])


class SecretRotateDTO(BaseModel):
    secret_name: str
    new_value: str


@router.get("/auth-policy", response_model=APIResponse)
async def get_auth_policy():
    """Returns system password and token security policies."""
    return create_success_response(data={
        "password_policy": {
            "min_length": PasswordPolicyEnforcer.MIN_LENGTH,
            "require_uppercase": True,
            "require_lowercase": True,
            "require_digit": True,
            "require_special": True,
            "history_limit": PasswordPolicyEnforcer.HISTORY_LIMIT,
            "algorithm": "Argon2id / PBKDF2-sha256",
        },
        "token_policy": {
            "access_token_ttl_mins": 15,
            "refresh_token_ttl_days": 7,
            "device_binding": True,
            "revocation_method": "JTI Blacklist",
        }
    })


@router.post("/secrets/rotate", response_model=APIResponse)
async def rotate_secret(
    dto: SecretRotateDTO,
    current_broker=Depends(get_current_broker),
):
    """Zero-downtime secret rotation endpoint."""
    success = await secrets_manager.rotate_secret(dto.secret_name, dto.new_value)
    return create_success_response(data={"rotated": success, "secret_name": dto.secret_name})


@router.post("/file-scan", response_model=APIResponse)
async def scan_file_upload(
    file: UploadFile = File(...),
    current_broker=Depends(get_current_broker),
):
    """Scans uploaded file for MIME spoofing, prohibited extensions, and malware."""
    content = await file.read()
    valid, err_msg = FileSecurityScanner.scan_file(file.filename or "upload.tmp", content)
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
    return create_success_response(data={"filename": file.filename, "size_bytes": len(content), "status": "clean"})


@router.get("/backups", response_model=APIResponse)
async def list_backups(
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    svc = BackupService(db)
    items = await svc.list_backups()
    return create_success_response(data=[
        {
            "id": b.id,
            "file_name": b.file_name,
            "backup_type": b.backup_type,
            "status": b.status,
            "size_bytes": b.size_bytes,
            "checksum_sha256": b.checksum_sha256,
            "started_at": b.started_at,
            "completed_at": b.completed_at,
        } for b in items
    ])


@router.post("/backups/trigger", response_model=APIResponse)
async def trigger_backup(
    backup_type: str = Query(default="daily_full", pattern="^(daily_full|hourly_incremental|manual)$"),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    svc = BackupService(db)
    job = await svc.trigger_backup(backup_type=backup_type)
    return create_success_response(data={"id": job.id, "file_name": job.file_name, "checksum": job.checksum_sha256})


@router.post("/disaster-recovery/drill", response_model=APIResponse)
async def execute_dr_drill(
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    svc = DisasterRecoveryService(db)
    res = await svc.execute_dr_drill()
    return create_success_response(data=res)


@router.get("/compliance-report", response_model=APIResponse)
async def generate_compliance_report(
    framework: str = Query(default="SOC2", pattern="^(SOC2|GDPR|ISO27001|CCPA)$"),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    svc = ComplianceService(db)
    report = await svc.generate_report(framework=framework)
    return create_success_response(data={
        "id": report.id,
        "framework": report.framework,
        "status": report.status,
        "evidence": report.evidence_json,
        "generated_at": report.generated_at,
    })
