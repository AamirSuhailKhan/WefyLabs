import uuid
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.services.mobile_sync_service import MobileSyncService

router = APIRouter(prefix="/mobile", tags=["Uber-Grade Mobile App Engine & Offline Sync"])

class DeltaSyncRequest(BaseModel):
    device_id: str
    offline_mutations: List[Dict[str, Any]] = []

class BusinessCardOCRRequest(BaseModel):
    image_url_or_b64: str

@router.post("/sync")
async def process_delta_sync_endpoint(
    req: DeltaSyncRequest,
    current_broker: Broker = Depends(get_current_broker)
):
    """Processes offline queued mutations and returns delta sync payload."""
    res = MobileSyncService.execute_delta_sync(req.device_id, req.offline_mutations)
    return res

@router.post("/voice-note")
async def process_voice_note_endpoint(
    duration_sec: float = Query(18.5),
    current_broker: Broker = Depends(get_current_broker)
):
    """Processes audio voice dictation into speech-to-text and auto-extracts CRM tasks."""
    transcript = MobileSyncService.transcribe_voice_note(current_broker.id, duration_sec)
    return {
        "id": str(transcript.id),
        "duration_seconds": transcript.audio_duration_seconds,
        "transcript": transcript.raw_transcript,
        "ai_summary": transcript.ai_summary,
        "extracted_tasks": transcript.extracted_tasks
    }

@router.post("/business-card-ocr")
async def process_business_card_ocr_endpoint(
    req: BusinessCardOCRRequest,
    current_broker: Broker = Depends(get_current_broker)
):
    """AI OCR Scanner extracting Lead contact profile from business card image."""
    res = MobileSyncService.process_business_card_ocr(req.image_url_or_b64)
    return res
