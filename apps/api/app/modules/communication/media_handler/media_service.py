"""
Media Handler — Secure Attachment Processing
=============================================
Handles upload, download, validation, and storage of message attachments.

Current storage: Mock (returns deterministic URLs, no real storage).
Future storage: S3-compatible (AWS S3, Cloudflare R2, MinIO).
The storage abstraction is defined here; implementation is swappable.
"""
from __future__ import annotations

import hashlib
import logging
import mimetypes
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.communication_models import MessageAttachment

logger = logging.getLogger(__name__)

# Allowed MIME types per category
_ALLOWED_MIME_TYPES = {
    "image": {"image/jpeg", "image/png", "image/gif", "image/webp"},
    "video": {"video/mp4", "video/quicktime", "video/x-msvideo"},
    "audio": {"audio/mpeg", "audio/ogg", "audio/wav", "audio/aac"},
    "voice_note": {"audio/ogg", "audio/aac", "audio/mpeg"},
    "document": {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
        "text/plain",
    },
    "floor_plan": {"application/pdf", "image/png", "image/jpeg"},
    "brochure": {"application/pdf"},
}

# Max file sizes in bytes
_MAX_FILE_SIZES = {
    "image": 10 * 1024 * 1024,      # 10 MB
    "video": 100 * 1024 * 1024,     # 100 MB
    "audio": 25 * 1024 * 1024,      # 25 MB
    "voice_note": 5 * 1024 * 1024,  # 5 MB
    "document": 50 * 1024 * 1024,   # 50 MB
    "floor_plan": 50 * 1024 * 1024,
    "brochure": 50 * 1024 * 1024,
}


class MediaHandler:
    """
    Secure media upload/download/validation service.

    Storage is abstracted — swap mock → S3 by changing _storage_backend
    without touching any business logic.
    """

    def __init__(self, storage_backend: str = "mock"):
        self._storage_backend = storage_backend
        logger.info(f"[MediaHandler] Initialized with storage_backend={storage_backend}")

    async def upload(
        self,
        file_bytes: bytes,
        mime_type: str,
        file_name: str,
        organization_id: str,
        message_id: str,
        db: AsyncSession,
        file_type: Optional[str] = None,
    ) -> MessageAttachment:
        """
        Upload a file and create a MessageAttachment record.

        1. Validate MIME type and size
        2. Detect file_type from mime_type if not provided
        3. Upload to storage backend
        4. Create and persist MessageAttachment
        5. Return attachment
        """
        # Detect file type
        detected_type = file_type or self._detect_file_type(mime_type)

        # Validate
        self._validate(file_bytes, mime_type, detected_type)

        # Upload to storage
        storage_key, public_url = await self._upload_to_storage(
            file_bytes, mime_type, file_name, organization_id
        )

        # Create attachment record
        attachment = MessageAttachment(
            message_id=message_id,
            organization_id=organization_id,
            file_name=file_name,
            mime_type=mime_type,
            file_size_bytes=len(file_bytes),
            file_type=detected_type,
            storage_provider=self._storage_backend,
            storage_key=storage_key,
            public_url=public_url,
            is_virus_scanned=False,  # Async virus scan queued separately
            is_safe=None,
        )
        db.add(attachment)
        await db.flush()

        logger.info(
            f"[MediaHandler] Uploaded attachment={attachment.id} "
            f"type={detected_type} size={len(file_bytes)} bytes"
        )
        return attachment

    async def download(self, storage_key: str) -> bytes:
        """Download a file from storage by key."""
        if self._storage_backend == "mock":
            return b""  # Mock: return empty bytes

        # Production: download from S3/R2
        # async with s3_client.get_object(Bucket=bucket, Key=storage_key) as response:
        #     return await response["Body"].read()
        return b""

    async def get_public_url(self, storage_key: str, expires_seconds: int = 3600) -> str:
        """Generate a (optionally pre-signed) URL for a stored file."""
        if self._storage_backend == "mock":
            return f"https://mock-cdn.wefylabs.com/{storage_key}"
        # Production: generate pre-signed URL from S3
        return f"https://cdn.wefylabs.com/{storage_key}"

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _validate(self, file_bytes: bytes, mime_type: str, file_type: str) -> None:
        """Validate file size and MIME type."""
        allowed = _ALLOWED_MIME_TYPES.get(file_type, set())
        if allowed and mime_type not in allowed:
            raise ValueError(
                f"MIME type {mime_type!r} not allowed for file_type={file_type}. "
                f"Allowed: {allowed}"
            )

        max_size = _MAX_FILE_SIZES.get(file_type, 50 * 1024 * 1024)
        if len(file_bytes) > max_size:
            raise ValueError(
                f"File too large: {len(file_bytes)} bytes > max {max_size} bytes for {file_type}"
            )

    def _detect_file_type(self, mime_type: str) -> str:
        """Detect file_type category from MIME type."""
        if mime_type.startswith("image/"):
            return "image"
        if mime_type.startswith("video/"):
            return "video"
        if "pdf" in mime_type:
            return "document"
        if mime_type.startswith("audio/"):
            return "audio"
        if "zip" in mime_type:
            return "document"
        if "word" in mime_type or "excel" in mime_type or "sheet" in mime_type:
            return "document"
        return "document"

    async def _upload_to_storage(
        self, file_bytes: bytes, mime_type: str,
        file_name: str, organization_id: str
    ) -> Tuple[str, str]:
        """
        Upload to storage backend.
        Returns (storage_key, public_url).
        """
        file_hash = hashlib.sha256(file_bytes).hexdigest()[:32]
        ext = mimetypes.guess_extension(mime_type) or ""
        storage_key = f"{organization_id}/media/{file_hash}{ext}"

        if self._storage_backend == "mock":
            public_url = f"https://mock-cdn.wefylabs.com/{storage_key}"
            return storage_key, public_url

        # Production (S3-compatible):
        # async with s3_client.put_object(
        #     Bucket=settings.S3_BUCKET,
        #     Key=storage_key,
        #     Body=file_bytes,
        #     ContentType=mime_type,
        # ) as _:
        #     pass
        # public_url = f"https://{settings.CDN_DOMAIN}/{storage_key}"

        public_url = f"https://cdn.wefylabs.com/{storage_key}"
        return storage_key, public_url
