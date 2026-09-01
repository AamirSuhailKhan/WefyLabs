"""
Part 21.2 — Discovery Provider Base Interface
===============================================
Abstract foundation for all authorized discovery source providers.

Rules:
  - Providers ONLY connect via official/authorized APIs or customer data.
  - NEVER implement unauthorized scraping or CAPTCHA bypass.
  - If credentials missing: return CONFIGURATION_REQUIRED (never claim connected).
  - All records must contain concrete provenance evidence.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.models.discovery_models import ProviderStatus, DiscoverySourceType


@dataclass
class ProviderHealth:
    status: str  # CONNECTED, CONFIGURATION_REQUIRED, DISABLED, RATE_LIMITED, ERROR, UNAVAILABLE
    is_healthy: bool
    message: str
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: Optional[float] = None


@dataclass
class DiscoveredRecord:
    external_id: str
    source_url: Optional[str]
    observed_at: datetime
    source_created_at: Optional[datetime]
    raw_payload: Dict[str, Any]
    # Extracted raw contact details (as supplied by provider)
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    # Real estate interest signals
    property_interest: Optional[str] = None
    property_type: Optional[str] = None
    transaction_type: Optional[str] = None
    lead_intent: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    currency: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    language: Optional[str] = None
    timeline: Optional[str] = None
    message: Optional[str] = None
    # Concrete factual evidence pointers
    evidence_items: List[Dict[str, Any]] = field(default_factory=list)
    # Signal metadata
    signals: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class DiscoveryBatchResult:
    records: List[DiscoveredRecord]
    next_cursor: Optional[str]
    has_more: bool
    records_scanned: int
    errors: List[str] = field(default_factory=list)


class IDiscoveryProvider(ABC):
    """Abstract interface that all authorized discovery providers must implement."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique provider identifier (e.g. 'meta_lead_ads', 'google_lead_form')."""
        pass

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Taxonomy source type from DiscoverySourceType."""
        pass

    @abstractmethod
    def validate_configuration(self, configuration: Optional[Dict[str, Any]]) -> bool:
        """Check if provider configuration contains required credentials."""
        pass

    @abstractmethod
    async def health_check(self, configuration: Optional[Dict[str, Any]]) -> ProviderHealth:
        """Perform live connectivity check if credentials exist."""
        pass

    @abstractmethod
    async def discover(
        self,
        campaign_criteria: Dict[str, Any],
        configuration: Optional[Dict[str, Any]],
        cursor: Optional[str] = None,
        limit: int = 50,
    ) -> DiscoveryBatchResult:
        """
        Execute discovery query against authorized provider.
        Returns ONLY real records with concrete evidence.
        """
        pass

    @abstractmethod
    def normalize(self, raw_record: Dict[str, Any]) -> DiscoveredRecord:
        """Normalize raw provider record into standard DiscoveredRecord."""
        pass

    def get_rate_limit(self) -> int:
        """Default requests per minute limit."""
        return 60

    def get_usage(self) -> Dict[str, Any]:
        """Return provider usage stats."""
        return {}

    def close(self) -> None:
        """Clean up connections."""
        pass
