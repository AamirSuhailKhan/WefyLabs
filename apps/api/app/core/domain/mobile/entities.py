import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any

class SyncDirection(str, Enum):
    PUSH = "push"
    PULL = "pull"
    BIDIRECTIONAL = "bidirectional"

@dataclass
class OfflineQueueItemEntity:
    id: str
    action_type: str # create_lead | update_status | add_note
    payload: Dict[str, Any]
    queued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class VoiceNoteTranscriptEntity:
    id: uuid.UUID
    broker_id: uuid.UUID
    audio_duration_seconds: float
    raw_transcript: str
    ai_summary: str
    extracted_tasks: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class MobileSyncStateEntity:
    """Pure Domain Entity for Mobile Offline Delta Sync."""
    device_id: str
    last_synced_at: datetime
    pending_offline_items: List[OfflineQueueItemEntity] = field(default_factory=list)
    sync_status: str = "synced"
