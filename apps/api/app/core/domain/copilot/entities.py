import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any

class PageContextType(str, Enum):
    DASHBOARD = "dashboard"
    LEAD_DETAIL = "lead_detail"
    INBOX = "inbox"
    PROPERTIES = "properties"
    DEALS = "deals"
    ANALYTICS = "analytics"
    SETTINGS = "settings"
    UNKNOWN = "unknown"

@dataclass
class CopilotContextEntity:
    """Captures current broker environment context."""
    route_path: str
    context_type: PageContextType
    active_entity_id: Optional[str] = None
    broker_id: Optional[str] = None
    broker_role: str = "agent"
    locality: str = "Dubai"

@dataclass
class CopilotToolCallEntity:
    tool_name: str
    arguments: Dict[str, Any]
    result: Optional[Any] = None

@dataclass
class CopilotResponseEntity:
    query: str
    context_type: PageContextType
    summary: str
    answer_markdown: str
    confidence_score: float = 0.95
    reasoning: Optional[str] = None
    rich_cards: List[Dict[str, Any]] = field(default_factory=list)
    action_buttons: List[Dict[str, Any]] = field(default_factory=list)
    citations: List[str] = field(default_factory=list)
    suggested_followups: List[str] = field(default_factory=list)
    executed_tools: List[CopilotToolCallEntity] = field(default_factory=list)
