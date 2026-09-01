"""
Lead Connector Base Interface
=============================
ILeadConnector is the single abstract interface that every source connector must implement.
No connector writes directly to the database. All connectors output CanonicalLeadDTO.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.modules.ingestion.dto.canonical_lead_dto import CanonicalLeadDTO


class RawLeadPayload(dict):
    """Container for raw source payload and metadata."""
    pass


class ILeadConnector(ABC):
    """
    Abstract Lead Connector.
    Source-agnostic interface for extracting, parsing, and normalizing
    incoming lead data into a CanonicalLeadDTO.
    """
    source_name: str = "base"

    @abstractmethod
    def validate_raw(self, payload: Dict[str, Any]) -> bool:
        """Validates that the raw payload contains minimal required fields."""
        pass

    @abstractmethod
    def parse_to_canonical(self, payload: Dict[str, Any]) -> CanonicalLeadDTO:
        """Parses raw source payload into a standard CanonicalLeadDTO."""
        pass
