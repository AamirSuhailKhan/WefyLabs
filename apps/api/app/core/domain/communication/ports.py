import uuid
from abc import ABC, abstractmethod
from typing import Optional, List, Tuple, Dict, Any
from app.core.domain.communication.entities import UnifiedConversationEntity, UnifiedMessageEntity, ChannelType

class IChannelAdapter(ABC):
    """Abstract Hexagonal Channel Adapter Interface (WhatsApp, Email, SMS, Voice Calls)."""

    @property
    @abstractmethod
    def channel_type(self) -> ChannelType:
        pass

    @abstractmethod
    async def send_message(
        self,
        recipient_identifier: str, # phone / email
        content: str,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        pass

class ICommunicationRepository(ABC):
    """Abstract Hexagonal Port for Communication Data Storage."""

    @abstractmethod
    async def get_conversation_by_lead(self, lead_id: uuid.UUID, broker_id: uuid.UUID) -> Optional[UnifiedConversationEntity]:
        pass

    @abstractmethod
    async def save_conversation(self, conversation: UnifiedConversationEntity) -> UnifiedConversationEntity:
        pass

    @abstractmethod
    async def save_message(self, message: UnifiedMessageEntity) -> UnifiedMessageEntity:
        pass

    @abstractmethod
    async def list_messages(self, conversation_id: uuid.UUID, limit: int = 50) -> List[UnifiedMessageEntity]:
        pass

    @abstractmethod
    async def list_inbox_conversations(
        self,
        broker_id: uuid.UUID,
        channel: Optional[ChannelType] = None,
        search: Optional[str] = None,
        is_unassigned: bool = False,
        page: int = 1,
        limit: int = 20
    ) -> Tuple[List[UnifiedConversationEntity], int]:
        pass
