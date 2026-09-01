import logging
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingestion_models import LeadImportItem, IngestionLog
from app.modules.ingestion.pipeline.ingestion_pipeline import LeadIngestionPipeline
from app.modules.ingestion.dto.canonical_lead_dto import IngestionResponseDTO

logger = logging.getLogger(__name__)


class DeadLetterQueueService:
    """
    Dead-Letter Queue (DLQ) & Replay Engine.
    Inspects failed ingestion attempts and replays payloads without duplication.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.pipeline = LeadIngestionPipeline(db)

    async def list_failed_items(self, organization_id: str, limit: int = 50) -> List[LeadImportItem]:
        stmt = (
            select(LeadImportItem)
            .where(LeadImportItem.organization_id == organization_id, LeadImportItem.status == "failed")
            .order_by(LeadImportItem.row_index.asc())
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def replay_failed_item(self, item_id: str) -> IngestionResponseDTO:
        stmt = select(LeadImportItem).where(LeadImportItem.id == item_id)
        item = (await self.db.execute(stmt)).scalars().first()
        if not item:
            raise ValueError(f"DLQ item '{item_id}' not found.")

        logger.info(f"[DLQ REPLAY] Replaying failed item {item_id} (Batch: {item.batch_id})")

        res = await self.pipeline.ingest_lead(
            source="csv_import_replay",
            raw_payload=item.raw_data,
            organization_id=item.organization_id,
        )

        if res.status in ("ingested", "updated", "duplicate"):
            item.status = "processed" if res.status != "duplicate" else "skipped_duplicate"
            item.lead_id = res.lead_id
            item.error_message = None
            await self.db.commit()

        return res
