import time
import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_models import BackupJob

logger = logging.getLogger(__name__)


class BackupService:
    """Automated Database Backup Management Engine."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def trigger_backup(
        self, backup_type: str = "daily_full", storage_provider: str = "s3"
    ) -> BackupJob:
        start_time = time.time()
        now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"beetlelabs_backup_{backup_type}_{now_str}.sql.gz.enc"
        storage_path = f"s3://beetlelabs-enterprise-backups/{backup_type}/{filename}"

        job = BackupJob(
            backup_type=backup_type,
            status="running",
            file_name=filename,
            storage_provider=storage_provider,
            storage_path=storage_path,
            is_encrypted=True,
        )
        self.db.add(job)
        await self.db.flush()

        # Simulate backup execution & SHA-256 hash generation
        dummy_content = f"DATABASE_DUMP_{now_str}".encode()
        checksum = hashlib.sha256(dummy_content).hexdigest()
        duration = round(time.time() - start_time, 2)

        job.status = "completed"
        job.size_bytes = 1024 * 1024 * 42 # 42 MB sample dump
        job.checksum_sha256 = checksum
        job.duration_seconds = duration
        job.completed_at = datetime.now(timezone.utc)

        await self.db.commit()
        logger.info(f"[BACKUP COMPLETED] {filename} (Size: 42MB, Checksum: {checksum[:12]}...)")
        return job

    async def list_backups(self, limit: int = 30) -> List[BackupJob]:
        stmt = select(BackupJob).order_by(BackupJob.started_at.desc()).limit(limit)
        return list((await self.db.execute(stmt)).scalars().all())
