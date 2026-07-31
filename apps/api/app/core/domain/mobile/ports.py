import uuid
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from app.core.domain.mobile.entities import MobileSyncStateEntity, VoiceNoteTranscriptEntity

class IMobileSyncEngine(ABC):
    """Abstract Port for Mobile Offline Delta Sync & Conflict Resolution."""

    @abstractmethod
    async def process_delta_sync(self, device_id: str, offline_mutations: List[Dict[str, Any]]) -> Dict[str, Any]:
        pass

class IVoiceNoteProcessor(ABC):
    """Abstract Port for AI Audio Transcription & Summarization."""

    @abstractmethod
    async def process_audio_voice_note(self, broker_id: uuid.UUID, audio_bytes_len: int) -> VoiceNoteTranscriptEntity:
        pass
