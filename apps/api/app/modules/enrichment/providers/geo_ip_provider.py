"""
Volume 2 PART 2 — GeoIP Location Provider
"""
import time
from typing import Dict, Any, Optional
from app.modules.enrichment.providers.base_provider import BaseEnrichmentProvider


class GeoIPProvider(BaseEnrichmentProvider):
    provider_name = "DefaultGeoIP"
    provider_type = "geo_ip"

    async def lookup(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        start = time.time()
        # Mock/Pluggable IP lookup (handles local or IPv4 addresses)
        latency_ms = round((time.time() - start) * 1000, 2)
        
        is_local = query in ["127.0.0.1", "localhost", "::1"] or query.startswith("192.168.")
        if is_local or not query:
            return {
                "provider": self.provider_name,
                "success": False,
                "latency_ms": latency_ms,
                "data": {},
                "confidence": 0.0
            }

        return {
            "provider": self.provider_name,
            "success": True,
            "latency_ms": latency_ms,
            "data": {
                "ip": query,
                "city": "Dubai",
                "country": "United Arab Emirates",
                "iso2": "AE",
                "timezone": "Asia/Dubai"
            },
            "confidence": 0.80
        }
