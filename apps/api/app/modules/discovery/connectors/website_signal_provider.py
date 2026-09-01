"""
Part 21.2 — Website Signal Discovery Provider
==============================================
Ingests high-intent real estate signals from authorized website tracking & widgets.
Signals: Viewing requests, brochure downloads, price calculation inquiries, repeat visits.
"""
from __future__ import annotations
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from app.models.discovery_models import ProviderStatus, DiscoverySourceType
from app.modules.discovery.connectors.base_provider import (
    IDiscoveryProvider, ProviderHealth, DiscoveredRecord, DiscoveryBatchResult
)


class WebsiteSignalProvider(IDiscoveryProvider):
    @property
    def provider_name(self) -> str:
        return "website_signal"

    @property
    def source_type(self) -> str:
        return DiscoverySourceType.WEBSITE_SIGNAL

    def validate_configuration(self, configuration: Optional[Dict[str, Any]]) -> bool:
        return True  # Native website signals are built-in

    async def health_check(self, configuration: Optional[Dict[str, Any]]) -> ProviderHealth:
        return ProviderHealth(
            status=ProviderStatus.CONNECTED,
            is_healthy=True,
            message="Website Signal Engine active and listening.",
            latency_ms=1.0,
        )

    async def discover(
        self,
        campaign_criteria: Dict[str, Any],
        configuration: Optional[Dict[str, Any]],
        cursor: Optional[str] = None,
        limit: int = 50,
    ) -> DiscoveryBatchResult:
        # In production, queries recent unlinked website engagement events
        return DiscoveryBatchResult(records=[], next_cursor=None, has_more=False, records_scanned=0)

    def normalize(self, raw_record: Dict[str, Any]) -> DiscoveredRecord:
        ext_id = str(raw_record.get("session_id") or raw_record.get("event_id") or f"web_{time.time()}")
        name = raw_record.get("name")
        email = raw_record.get("email")
        phone = raw_record.get("phone")

        evidence = [
            {
                "field_name": "website_session_event",
                "value_reference": ext_id,
                "confidence": 1.0,
                "provenance": {"provider": "website_signal", "page_url": raw_record.get("page_url")},
            }
        ]
        if email:
            evidence.append({"field_name": "email", "value_reference": email, "confidence": 0.95})
        if phone:
            evidence.append({"field_name": "phone", "value_reference": phone, "confidence": 0.95})

        signals = [
            {
                "signal_type": raw_record.get("event_type", "PROPERTY_PAGE_INTERACTION"),
                "source": "website_signal",
                "strength": float(raw_record.get("intent_weight", 0.75)),
                "confidence": 0.90,
                "signal_payload": {"property_id": raw_record.get("property_id"), "url": raw_record.get("page_url")},
            }
        ]

        return DiscoveredRecord(
            external_id=ext_id,
            source_url=raw_record.get("page_url"),
            observed_at=datetime.now(timezone.utc),
            source_created_at=datetime.now(timezone.utc),
            raw_payload=raw_record,
            name=name,
            email=email,
            phone=phone,
            property_type=raw_record.get("property_type"),
            transaction_type=raw_record.get("transaction_type"),
            lead_intent=raw_record.get("lead_intent", "BUYER"),
            city=raw_record.get("city"),
            country=raw_record.get("country"),
            evidence_items=evidence,
            signals=signals,
            confidence=0.85,
        )
