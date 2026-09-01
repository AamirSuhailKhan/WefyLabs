"""
Part 21.2 — Meta Lead Ads Discovery Provider
==============================================
Official Meta Lead Ads integration for real estate lead discovery.

Rules:
  - Connects strictly through official Meta Graph API v19.0+
  - NEVER scrapes Facebook/Instagram web pages.
  - If access_token or page_id missing: returns CONFIGURATION_REQUIRED.
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


class MetaDiscoveryProvider(IDiscoveryProvider):
    @property
    def provider_name(self) -> str:
        return "meta_lead_ads"

    @property
    def source_type(self) -> str:
        return DiscoverySourceType.META

    def validate_configuration(self, configuration: Optional[Dict[str, Any]]) -> bool:
        if not configuration:
            return False
        # Page ID and access token required for official Graph API access
        page_id = configuration.get("page_id")
        access_token = configuration.get("access_token") or configuration.get("access_token_encrypted")
        return bool(page_id and access_token)

    async def health_check(self, configuration: Optional[Dict[str, Any]]) -> ProviderHealth:
        if not self.validate_configuration(configuration):
            return ProviderHealth(
                status=ProviderStatus.CONFIGURATION_REQUIRED,
                is_healthy=False,
                message="Meta Lead Ads requires 'page_id' and 'access_token' in source configuration.",
            )

        start = time.perf_counter()
        try:
            import httpx
            page_id = configuration.get("page_id")
            token = configuration.get("access_token")
            # Verify page access via Graph API
            url = f"https://graph.facebook.com/v19.0/{page_id}"
            params = {"access_token": token, "fields": "id,name,category"}
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.get(url, params=params)
                latency = round((time.perf_counter() - start) * 1000, 2)
                if res.status_code == 200:
                    data = res.json()
                    return ProviderHealth(
                        status=ProviderStatus.CONNECTED,
                        is_healthy=True,
                        message=f"Connected to Meta Page '{data.get('name', page_id)}'.",
                        latency_ms=latency,
                    )
                else:
                    return ProviderHealth(
                        status=ProviderStatus.ERROR,
                        is_healthy=False,
                        message=f"Meta API responded with status {res.status_code}: {res.text[:200]}",
                        latency_ms=latency,
                    )
        except Exception as exc:
            latency = round((time.perf_counter() - start) * 1000, 2)
            logger.warning(f"[META_DISCOVERY] Health check failed: {exc}")
            return ProviderHealth(
                status=ProviderStatus.ERROR,
                is_healthy=False,
                message=f"Connection error: {str(exc)}",
                latency_ms=latency,
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
                records=[],
                next_cursor=None,
                has_more=False,
                records_scanned=0,
                errors=["Meta provider configuration is missing required credentials."],
            )

        page_id = configuration.get("page_id")
        token = configuration.get("access_token")
        form_id = configuration.get("form_id")

        try:
            import httpx
            # If form_id is provided, retrieve leads from form; else retrieve from page leadgen
            endpoint = form_id if form_id else page_id
            url = f"https://graph.facebook.com/v19.0/{endpoint}/leads"
            params: Dict[str, Any] = {
                "access_token": token,
                "fields": "id,created_time,field_data,ad_id,form_id,campaign_id,adset_id",
                "limit": limit,
            }
            if cursor:
                params["after"] = cursor

            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.get(url, params=params)
                if res.status_code != 200:
                    return DiscoveryBatchResult(
                        records=[],
                        next_cursor=None,
                        has_more=False,
                        records_scanned=0,
                        errors=[f"Meta Graph API error {res.status_code}: {res.text[:200]}"],
                    )

                data = res.json()
                raw_leads = data.get("data", [])
                paging = data.get("paging", {})
                next_cursor = paging.get("cursors", {}).get("after")
                has_more = bool(next_cursor)

                records = []
                for item in raw_leads:
                    record = self.normalize(item)
                    records.append(record)

                return DiscoveryBatchResult(
                    records=records,
                    next_cursor=next_cursor,
                    has_more=has_more,
                    records_scanned=len(raw_leads),
                )
        except Exception as exc:
            logger.error(f"[META_DISCOVERY] Discovery failed: {exc}")
            return DiscoveryBatchResult(
                records=[],
                next_cursor=None,
                has_more=False,
                records_scanned=0,
                errors=[str(exc)],
            )

    def normalize(self, raw_record: Dict[str, Any]) -> DiscoveredRecord:
        field_data = raw_record.get("field_data", [])
        field_map = {}
        for f in field_data:
            key = f.get("name", "")
            vals = f.get("values", [])
            val = vals[0] if vals else None
            field_map[key.lower()] = val

        created_str = raw_record.get("created_time")
        created_dt = None
        if created_str:
            try:
                created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            except Exception:
                pass

        external_id = raw_record.get("id", f"meta_{time.time()}")
        name = field_map.get("full_name") or field_map.get("name") or field_map.get("first_name")
        email = field_map.get("email")
        phone = field_map.get("phone_number") or field_map.get("phone")

        evidence_items = [
            {
                "field_name": "leadgen_id",
                "value_reference": external_id,
                "confidence": 1.0,
                "provenance": {"provider": "meta_lead_ads", "form_id": raw_record.get("form_id")},
            }
        ]
        if email:
            evidence_items.append({
                "field_name": "email",
                "value_reference": email,
                "confidence": 0.95,
                "provenance": {"provider": "meta_lead_ads"},
            })
        if phone:
            evidence_items.append({
                "field_name": "phone",
                "value_reference": phone,
                "confidence": 0.95,
                "provenance": {"provider": "meta_lead_ads"},
            })

        signals = [
            {
                "signal_type": "CAMPAIGN_RESPONSE",
                "source": "meta_lead_ads",
                "strength": 0.90,
                "confidence": 0.95,
                "signal_payload": {"form_id": raw_record.get("form_id"), "ad_id": raw_record.get("ad_id")},
            }
        ]

        return DiscoveredRecord(
            external_id=external_id,
            source_url=f"https://facebook.com/ads/leadgen/{external_id}",
            observed_at=datetime.now(timezone.utc),
            source_created_at=created_dt or datetime.now(timezone.utc),
            raw_payload=raw_record,
            name=name,
            email=email,
            phone=phone,
            property_type=field_map.get("property_type") or field_map.get("interest"),
            city=field_map.get("city") or field_map.get("location"),
            country=field_map.get("country"),
            timeline=field_map.get("timeline") or field_map.get("purchase_timeline"),
            message=field_map.get("message") or field_map.get("notes"),
            evidence_items=evidence_items,
            signals=signals,
            confidence=0.92,
        )
