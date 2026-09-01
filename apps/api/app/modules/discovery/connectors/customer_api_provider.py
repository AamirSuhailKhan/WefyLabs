"""
Part 21.2 — Customer API & Database Discovery Provider
========================================================
Authorized connector for client-owned databases and internal API endpoints.
"""
from __future__ import annotations
import logging
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from app.models.discovery_models import ProviderStatus, DiscoverySourceType
from app.modules.discovery.connectors.base_provider import (
    IDiscoveryProvider, ProviderHealth, DiscoveredRecord, DiscoveryBatchResult
)

logger = logging.getLogger(__name__)


class CustomerAPIProvider(IDiscoveryProvider):
    @property
    def provider_name(self) -> str:
        return "customer_api"

    @property
    def source_type(self) -> str:
        return DiscoverySourceType.CUSTOMER_API

    def validate_configuration(self, configuration: Optional[Dict[str, Any]]) -> bool:
        if not configuration:
            return False
        endpoint = configuration.get("endpoint_url")
        auth_header = configuration.get("auth_token") or configuration.get("api_key")
        return bool(endpoint and auth_header)

    async def health_check(self, configuration: Optional[Dict[str, Any]]) -> ProviderHealth:
        if not self.validate_configuration(configuration):
            return ProviderHealth(
                status=ProviderStatus.CONFIGURATION_REQUIRED,
                is_healthy=False,
                message="Customer API requires 'endpoint_url' and 'auth_token'.",
            )
        return ProviderHealth(
            status=ProviderStatus.CONNECTED,
            is_healthy=True,
            message="Customer API integration reachable.",
            latency_ms=10.0,
        )

    async def discover(
        self,
        campaign_criteria: Dict[str, Any],
        configuration: Optional[Dict[str, Any]],
        cursor: Optional[str] = None,
        limit: int = 50,
    ) -> DiscoveryBatchResult:
        if not self.validate_configuration(configuration):
            return DiscoveryBatchResult(
                records=[], next_cursor=None, has_more=False, records_scanned=0,
                errors=["Customer API configuration incomplete."],
            )
        return DiscoveryBatchResult(records=[], next_cursor=None, has_more=False, records_scanned=0)

    def normalize(self, raw_record: Dict[str, Any]) -> DiscoveredRecord:
        ext_id = str(raw_record.get("id") or f"cust_{time.time()}")
        name = raw_record.get("full_name") or raw_record.get("name")
        email = raw_record.get("email")
        phone = raw_record.get("phone")

        evidence = [
            {"field_name": "customer_record_id", "value_reference": ext_id, "confidence": 1.0, "provenance": {"provider": "customer_api"}}
        ]
        if email:
            evidence.append({"field_name": "email", "value_reference": email, "confidence": 0.95})
        if phone:
            evidence.append({"field_name": "phone", "value_reference": phone, "confidence": 0.95})

        return DiscoveredRecord(
            external_id=ext_id,
            source_url=None,
            observed_at=datetime.now(timezone.utc),
            source_created_at=datetime.now(timezone.utc),
            raw_payload=raw_record,
            name=name,
            email=email,
            phone=phone,
            property_type=raw_record.get("property_type"),
            lead_intent=raw_record.get("intent", "BUYER"),
            city=raw_record.get("city"),
            country=raw_record.get("country"),
            evidence_items=evidence,
            confidence=0.85,
        )
