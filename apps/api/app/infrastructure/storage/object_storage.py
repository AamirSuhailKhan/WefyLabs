"""
Canonical Enterprise Object Storage Service
============================================
Enforces:
1. Tenant Isolation: Every object key starts with `organizations/{organization_id}/...`.
2. Secure Object Key Standard: `organizations/{org_id}/{resource_type}/{resource_id}/{file_id}_{safe_filename}`.
3. Strict File Security: MIME verification, magic-byte inspection, extension allowlists, size limits via FileSecurityScanner.
4. Signed URLs: Time-limited, HMAC-signed download URLs for private customer documents.
5. Zero Fake Success: Failed storage operations raise or return truthful error contracts, never silent success.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from app.config import settings
from app.infrastructure.tenancy.scope import require_organization_id
from app.modules.security.services.file_security import FileSecurityScanner

logger = logging.getLogger("wefylabs.storage.object_storage")


@dataclass
class StorageObjectMetadata:
    object_key: str
    organization_id: uuid.UUID
    resource_type: str
    resource_id: str
    filename: str
    content_type: str
    size_bytes: int
    etag: str
    created_at: datetime
    is_private: bool = True
    signed_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "object_key": self.object_key,
            "organization_id": str(self.organization_id),
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "filename": self.filename,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "etag": self.etag,
            "created_at": self.created_at.isoformat(),
            "is_private": self.is_private,
            "signed_url": self.signed_url,
        }


class ObjectStorageService:
    """
    Canonical multi-tenant object storage service with built-in security gates.
    """

    def __init__(
        self,
        base_dir: Optional[str] = None,
        signing_secret: Optional[str] = None,
    ):
        self.base_dir = Path(base_dir or getattr(settings, "STORAGE_LOCAL_DIR", "storage_data"))
        self.signing_secret = (signing_secret or getattr(settings, "STORAGE_SIGNING_SECRET", "") or getattr(settings, "SECRET_KEY", "wefylabs_storage_secret")).encode("utf-8")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename against path traversal and special characters."""
        clean = Path(filename).name
        clean = re.sub(r"[^\w\.-]", "_", clean)
        return clean[:128] or "unnamed_file"

    def build_object_key(
        self,
        organization_id: Union[str, uuid.UUID],
        resource_type: str,
        resource_id: str,
        filename: str,
    ) -> str:
        """
        Enforces Section 18: File Object Key Standard.
        Format: organizations/{org_id}/{resource_type}/{resource_id}/{file_id}_{filename}
        """
        org_uuid = require_organization_id(organization_id)
        clean_resource_type = re.sub(r"[^\w-]", "", resource_type.strip().lower()) or "documents"
        clean_resource_id = re.sub(r"[^\w-]", "", str(resource_id).strip()) or "general"
        safe_name = self.sanitize_filename(filename)
        file_uuid = uuid.uuid4().hex[:12]
        return f"organizations/{org_uuid}/{clean_resource_type}/{clean_resource_id}/{file_uuid}_{safe_name}"

    def _resolve_physical_path(self, organization_id: Union[str, uuid.UUID], object_key: str) -> Path:
        """Resolves local path ensuring strict tenant directory containment."""
        org_uuid = require_organization_id(organization_id)
        expected_prefix = f"organizations/{org_uuid}/"
        if not object_key.startswith(expected_prefix):
            raise PermissionError(f"Cross-tenant access violation: key '{object_key}' does not belong to tenant '{org_uuid}'")

        relative_path = Path(object_key)
        full_path = (self.base_dir / relative_path).resolve()
        # Path traversal guard
        if not str(full_path).startswith(str(self.base_dir.resolve())):
            raise PermissionError("Path traversal violation detected in storage key.")
        return full_path

    async def upload(
        self,
        *,
        organization_id: Union[str, uuid.UUID],
        resource_type: str,
        resource_id: str,
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        is_private: bool = True,
    ) -> StorageObjectMetadata:
        """
        Uploads an object after running file security scans (magic-byte validation, extension whitelist, size check).
        """
        org_uuid = require_organization_id(organization_id)

        # 1. Security Gate: Validate MIME, extension, magic bytes, size
        valid, err = FileSecurityScanner.scan_file(filename, content)
        if not valid:
            logger.warning(f"[ObjectStorage:UploadRejected] Tenant: {org_uuid} | File: {filename} | Reason: {err}")
            raise ValueError(f"File upload security check failed: {err}")

        # 2. Build canonical tenant-scoped key
        object_key = self.build_object_key(org_uuid, resource_type, resource_id, filename)
        target_path = self._resolve_physical_path(org_uuid, object_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # 3. Write bytes to disk / storage
        target_path.write_bytes(content)
        size_bytes = len(content)
        etag = hashlib.sha256(content).hexdigest()
        now = datetime.now(timezone.utc)

        signed = self.generate_signed_url(org_uuid, object_key, expires_in_seconds=3600) if is_private else None

        logger.info(f"[ObjectStorage:Uploaded] Key: {object_key} | Size: {size_bytes} bytes | Tenant: {org_uuid}")

        return StorageObjectMetadata(
            object_key=object_key,
            organization_id=org_uuid,
            resource_type=resource_type,
            resource_id=resource_id,
            filename=self.sanitize_filename(filename),
            content_type=content_type,
            size_bytes=size_bytes,
            etag=etag,
            created_at=now,
            is_private=is_private,
            signed_url=signed,
        )

    async def download(
        self,
        *,
        organization_id: Union[str, uuid.UUID],
        object_key: str,
    ) -> Tuple[bytes, StorageObjectMetadata]:
        """Downloads an object belonging strictly to the requested tenant."""
        org_uuid = require_organization_id(organization_id)
        path = self._resolve_physical_path(org_uuid, object_key)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Storage object '{object_key}' not found.")

        content = path.read_bytes()
        meta = await self.metadata(organization_id=org_uuid, object_key=object_key)
        return content, meta

    async def delete(
        self,
        *,
        organization_id: Union[str, uuid.UUID],
        object_key: str,
    ) -> bool:
        """Deletes an object belonging strictly to the requested tenant."""
        org_uuid = require_organization_id(organization_id)
        path = self._resolve_physical_path(org_uuid, object_key)
        if path.exists() and path.is_file():
            path.unlink()
            logger.info(f"[ObjectStorage:Deleted] Key: {object_key} | Tenant: {org_uuid}")
            return True
        return False

    async def exists(
        self,
        *,
        organization_id: Union[str, uuid.UUID],
        object_key: str,
    ) -> bool:
        """Checks if an object exists strictly within tenant boundaries."""
        org_uuid = require_organization_id(organization_id)
        try:
            path = self._resolve_physical_path(org_uuid, object_key)
            return path.exists() and path.is_file()
        except PermissionError:
            return False

    async def metadata(
        self,
        *,
        organization_id: Union[str, uuid.UUID],
        object_key: str,
    ) -> StorageObjectMetadata:
        """Retrieves metadata of a tenant-scoped object."""
        org_uuid = require_organization_id(organization_id)
        path = self._resolve_physical_path(org_uuid, object_key)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Storage object '{object_key}' not found.")

        stat = path.stat()
        parts = object_key.split("/")
        resource_type = parts[2] if len(parts) > 2 else "general"
        resource_id = parts[3] if len(parts) > 3 else "unknown"
        filename = parts[-1] if len(parts) > 4 else path.name

        return StorageObjectMetadata(
            object_key=object_key,
            organization_id=org_uuid,
            resource_type=resource_type,
            resource_id=resource_id,
            filename=filename,
            content_type="application/octet-stream",
            size_bytes=stat.st_size,
            etag=hashlib.md5(f"{object_key}:{stat.st_mtime}".encode("utf-8")).hexdigest(),
            created_at=datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc),
            is_private=True,
        )

    def generate_signed_url(
        self,
        organization_id: Union[str, uuid.UUID],
        object_key: str,
        expires_in_seconds: int = 3600,
    ) -> str:
        """
        Generates a secure HMAC time-limited signed URL for private documents.
        Never exposes permanent public URLs for private customer data.
        """
        org_uuid = require_organization_id(organization_id)
        if not object_key.startswith(f"organizations/{org_uuid}/"):
            raise PermissionError("Cross-tenant signing prohibited.")

        expires_at = int(time.time()) + expires_in_seconds
        message = f"{org_uuid}:{object_key}:{expires_at}".encode("utf-8")
        signature = hmac.new(self.signing_secret, message, hashlib.sha256).hexdigest()

        return f"/api/v1/storage/download?key={object_key}&org={org_uuid}&expires={expires_at}&sig={signature}"

    def verify_signed_url(
        self,
        organization_id: Union[str, uuid.UUID],
        object_key: str,
        expires_at: int,
        signature: str,
    ) -> bool:
        """Verifies signature authenticity and timestamp liveness."""
        org_uuid = require_organization_id(organization_id)
        if int(time.time()) > expires_at:
            logger.warning(f"[ObjectStorage:ExpiredUrl] Key: {object_key} expired at {expires_at}")
            return False

        message = f"{org_uuid}:{object_key}:{expires_at}".encode("utf-8")
        expected_sig = hmac.new(self.signing_secret, message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_sig, signature)
