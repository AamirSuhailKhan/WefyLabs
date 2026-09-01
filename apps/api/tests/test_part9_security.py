"""
PART 9 — Enterprise Security, DevSecOps, Backup & Disaster Recovery Tests
==========================================================================
Comprehensive tests for:
  - AES-256 Field Level Encryption & Decryption
  - Argon2id / PBKDF2 Password Hashing & NIST Policy Enforcement
  - Encrypted Secrets Manager Provider
  - File Upload Security & MIME Magic Bytes Scanner
  - Token Revocation & JTI Blacklist Models
  - Backup & Disaster Recovery SLA Verification
"""
import pytest
from datetime import datetime, timezone

from app.modules.security.services.crypto_service import EncryptionService
from app.modules.security.services.password_security import PasswordPolicyEnforcer
from app.modules.secrets.service.secrets_manager import EncryptedEnvSecretsProvider
from app.modules.security.services.file_security import FileSecurityScanner
from app.models.security_models import TokenBlacklist, BackupJob, DisasterRecoveryPlan, ComplianceAuditReport


# ─── AES-256 Encryption Tests ──────────────────────────────────────────────────

def test_crypto_encryption_decryption():
    plaintext = "super_secret_oauth_access_token_12345"
    ciphertext = EncryptionService.encrypt(plaintext)

    assert ciphertext != plaintext
    assert len(ciphertext) > 20

    decrypted = EncryptionService.decrypt(ciphertext)
    assert decrypted == plaintext


# ─── Argon2id Password Security Tests ─────────────────────────────────────────

def test_password_policy_validation():
    # Weak password
    valid, errors = PasswordPolicyEnforcer.validate_strength("weak")
    assert valid is False
    assert len(errors) >= 3

    # Strong password
    valid, errors = PasswordPolicyEnforcer.validate_strength("BeetleLabs#2026_Secure!")
    assert valid is True
    assert len(errors) == 0


def test_password_hashing_and_verification():
    raw_pwd = "BeetleLabs#2026_Secure!"
    hashed = PasswordPolicyEnforcer.hash_password(raw_pwd)

    assert hashed != raw_pwd
    assert PasswordPolicyEnforcer.verify_password(raw_pwd, hashed) is True
    assert PasswordPolicyEnforcer.verify_password("WrongPassword!", hashed) is False


def test_password_history_detection():
    pwd1 = "BeetleLabs#2026_v1"
    pwd2 = "BeetleLabs#2026_v2"
    hash1 = PasswordPolicyEnforcer.hash_password(pwd1)

    history = [hash1]
    assert PasswordPolicyEnforcer.check_history(pwd1, history) is True
    assert PasswordPolicyEnforcer.check_history(pwd2, history) is False


# ─── Secrets Manager Tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_encrypted_secrets_manager_provider():
    provider = EncryptedEnvSecretsProvider()

    await provider.set_secret("DATABASE_PASSWORD", "SuperSecretDBPass123!")
    val = await provider.get_secret("DATABASE_PASSWORD")
    assert val == "SuperSecretDBPass123!"

    await provider.rotate_secret("DATABASE_PASSWORD", "NewRotatedDBPass456!")
    new_val = await provider.get_secret("DATABASE_PASSWORD")
    assert new_val == "NewRotatedDBPass456!"


# ─── File Upload Security Scanner Tests ────────────────────────────────────────

def test_file_security_mime_and_extension_scanner():
    # Executable extension should fail
    valid, err = FileSecurityScanner.scan_file("malicious.exe", b"MZ_binary_content")
    assert valid is False
    assert "prohibited" in err

    # Path traversal should fail
    valid, err = FileSecurityScanner.scan_file("../../../etc/passwd", b"root:x:0:0")
    assert valid is False
    assert "Invalid filename" in err

    # Valid PDF file header magic bytes
    pdf_content = b"%PDF-1.5 header content..."
    valid, err = FileSecurityScanner.scan_file("proposal.pdf", pdf_content)
    assert valid is True
    assert err is None


# ─── Security Models Tests ────────────────────────────────────────────────────

def test_security_models_instantiation():
    tbl = TokenBlacklist(
        jti="jti-uuid-12345",
        user_id="user-123",
        reason="logout",
        expires_at=datetime.now(timezone.utc),
    )
    assert tbl.jti == "jti-uuid-12345"

    job = BackupJob(
        file_name="backup.sql.gz.enc",
        backup_type="daily_full",
        storage_path="s3://backups/backup.sql.gz.enc",
    )
    assert job.backup_type == "daily_full"

    dr = DisasterRecoveryPlan(
        name="Main DR Plan",
        target_rpo_minutes=15,
        target_rto_minutes=60,
    )
    assert dr.target_rpo_minutes == 15
    assert dr.target_rto_minutes == 60

    report = ComplianceAuditReport(
        framework="SOC2",
        status="passed",
    )
    assert report.framework == "SOC2"
