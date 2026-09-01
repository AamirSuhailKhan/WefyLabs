"""
Knowledge Document Storage Service
====================================
Abstracts document file storage.
Default: local filesystem (development / single-server).
Production: swap to S3StorageService by changing provider config.

Storage keys follow: {org_id}/{doc_id}/{version}/{filename}
Signed URLs are generated for time-limited access.
"""
from __future__ import annotations

import hashlib
import logging
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Default storage root (override via KNOWLEDGE_STORAGE_ROOT env var)
_DEFAULT_ROOT = os.getenv(
    "KNOWLEDGE_STORAGE_ROOT",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "storage", "knowledge"),
)


# ─── Abstract Interface ────────────────────────────────────────────────────────

class StorageProvider(ABC):
    """Abstract document storage provider."""
    provider_name: str = "abstract"

    @abstractmethod
    async def store(
        self,
        content: bytes,
        storage_key: str,
    ) -> str:
        """
        Store document bytes at storage_key.
        Returns the canonical storage key (may differ from input for normalization).
        """
        ...

    @abstractmethod
    async def retrieve(self, storage_key: str) -> bytes:
        """Retrieve document bytes by storage key."""
        ...

    @abstractmethod
    async def delete(self, storage_key: str) -> bool:
        """Delete stored document. Returns True if deleted."""
        ...

    @abstractmethod
    def generate_signed_url(
        self, storage_key: str, expires_in_seconds: int = 3600
    ) -> str:
        """Generate a time-limited access URL for the stored object."""
        ...

    @staticmethod
    def compute_checksum(content: bytes) -> str:
        """SHA-256 checksum for content integrity."""
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def make_storage_key(
        organization_id: str,
        document_id: str,
        version: int,
        filename: str,
    ) -> str:
        """Canonical storage key format."""
        safe_name = Path(filename).name  # strip any path components
        return f"knowledge/{organization_id}/{document_id}/v{version}/{safe_name}"


# ─── Local Filesystem Provider ────────────────────────────────────────────────

class LocalStorageProvider(StorageProvider):
    """
    Local filesystem storage.
    Suitable for single-server development and low-volume deployments.
    In production, replace with S3StorageProvider.
    """
    provider_name = "local"

    def __init__(self, root: str = _DEFAULT_ROOT):
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    async def store(self, content: bytes, storage_key: str) -> str:
        target = self._root / storage_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        logger.info(f"[STORAGE:local] Stored {len(content)} bytes at {storage_key}")
        return storage_key

    async def retrieve(self, storage_key: str) -> bytes:
        target = self._root / storage_key
        if not target.exists():
            raise FileNotFoundError(f"Storage key not found: {storage_key}")
        return target.read_bytes()

    async def delete(self, storage_key: str) -> bool:
        target = self._root / storage_key
        if target.exists():
            target.unlink()
            logger.info(f"[STORAGE:local] Deleted {storage_key}")
            return True
        return False

    def generate_signed_url(
        self, storage_key: str, expires_in_seconds: int = 3600
    ) -> str:
        # Local storage: return internal path reference (not a real signed URL)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
        return f"/internal/storage/{storage_key}?expires={expires_at.isoformat()}"


# ─── Mock Storage Provider (Tests) ────────────────────────────────────────────

class MockStorageProvider(StorageProvider):
    """In-memory storage for unit tests."""
    provider_name = "mock"

    def __init__(self):
        self._store: dict[str, bytes] = {}

    async def store(self, content: bytes, storage_key: str) -> str:
        self._store[storage_key] = content
        return storage_key

    async def retrieve(self, storage_key: str) -> bytes:
        if storage_key not in self._store:
            raise FileNotFoundError(f"Mock storage: key not found: {storage_key}")
        return self._store[storage_key]

    async def delete(self, storage_key: str) -> bool:
        if storage_key in self._store:
            del self._store[storage_key]
            return True
        return False

    def generate_signed_url(self, storage_key: str, expires_in_seconds: int = 3600) -> str:
        return f"mock://storage/{storage_key}"


# ─── S3 Storage Provider (Production) ────────────────────────────────────────

class S3StorageProvider(StorageProvider):
    """
    AWS S3 storage provider for production deployments.
    Requires: boto3, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY env vars.

    Supports: presigned URLs, bucket encryption, versioning.
    Storage key format: knowledge/{org_id}/{doc_id}/v{version}/{filename}
    """
    provider_name = "s3"

    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        prefix: str = "knowledge/",
    ):
        self._bucket = bucket
        self._region = region
        self._prefix = prefix

    def _client(self):
        try:
            import boto3
            return boto3.client("s3", region_name=self._region)
        except ImportError:
            raise RuntimeError("boto3 is required for S3StorageProvider. Install with: pip install boto3")

    async def store(self, content: bytes, storage_key: str) -> str:
        import asyncio
        s3 = self._client()
        full_key = storage_key  # Storage key already includes prefix from make_storage_key
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: s3.put_object(
                Bucket=self._bucket,
                Key=full_key,
                Body=content,
                ServerSideEncryption="AES256",
            ),
        )
        logger.info(
            f"[STORAGE:S3] Stored {len(content):,} bytes at s3://{self._bucket}/{full_key}"
        )
        return storage_key

    async def retrieve(self, storage_key: str) -> bytes:
        import asyncio
        s3 = self._client()
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: s3.get_object(Bucket=self._bucket, Key=storage_key),
            )
            return response["Body"].read()
        except Exception as exc:
            raise FileNotFoundError(
                f"S3 object not found: s3://{self._bucket}/{storage_key}: {exc}"
            ) from exc

    async def delete(self, storage_key: str) -> bool:
        import asyncio
        s3 = self._client()
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: s3.delete_object(Bucket=self._bucket, Key=storage_key),
            )
            logger.info(f"[STORAGE:S3] Deleted s3://{self._bucket}/{storage_key}")
            return True
        except Exception as exc:
            logger.error(f"[STORAGE:S3] Delete failed: {exc}")
            return False

    def generate_signed_url(
        self, storage_key: str, expires_in_seconds: int = 3600
    ) -> str:
        s3 = self._client()
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": storage_key},
            ExpiresIn=expires_in_seconds,
        )
        return url


# ─── Factory ──────────────────────────────────────────────────────────────────

def get_storage_provider(provider_name: str = "local") -> StorageProvider:
    """
    Resolve storage provider by name.
    Provider name comes from KNOWLEDGE_STORAGE_PROVIDER env var or per-org config.
    """
    if provider_name == "local":
        root = os.getenv("KNOWLEDGE_STORAGE_ROOT", _DEFAULT_ROOT)
        return LocalStorageProvider(root=root)
    if provider_name == "mock":
        return MockStorageProvider()
    if provider_name == "s3":
        import os as _os
        bucket = _os.getenv("KNOWLEDGE_S3_BUCKET", "beetlelabs-knowledge")
        region = _os.getenv("KNOWLEDGE_S3_REGION", "us-east-1")
        return S3StorageProvider(bucket=bucket, region=region)
    # Future: "gcs" (Google Cloud Storage), "azure_blob"
    logger.warning(
        f"[STORAGE FACTORY] Unknown provider '{provider_name}', falling back to local"
    )
    return LocalStorageProvider()
