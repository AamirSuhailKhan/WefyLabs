from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from app.core.domain.copilot.entities import CopilotContextEntity, CopilotResponseEntity

class ICopilotContextBuilder(ABC):
    """Abstract Port for resolving page route context into domain objects."""

    @abstractmethod
    def resolve_context(self, route_path: str, active_entity_id: Optional[str] = None) -> CopilotContextEntity:
        pass

class ICopilotOrchestrator(ABC):
    """Abstract Port for execution of Copilot queries with tool calling."""

    @abstractmethod
    async def process_query(self, query: str, context: CopilotContextEntity) -> CopilotResponseEntity:
        pass
