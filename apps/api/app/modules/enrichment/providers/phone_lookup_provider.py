"""
Volume 2 PART 2 — Phone Lookup Provider
"""
import time
from typing import Dict, Any, Optional
from app.modules.enrichment.providers.base_provider import BaseEnrichmentProvider
from app.modules.enrichment.normalizers.phone_normalizer import PhoneNormalizer


class PhoneLookupProvider(BaseEnrichmentProvider):
    provider_name = "DefaultPhoneLookup"
    provider_type = "phone_lookup"

    async def lookup(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        start = time.time()
        norm = PhoneNormalizer.normalize(query)
        latency_ms = round((time.time() - start) * 1000, 2)

        return {
            "provider": self.provider_name,
            "success": norm["is_valid"],
            "latency_ms": latency_ms,
            "data": {
                "e164": norm["e164"],
                "carrier": "Etisalat / Du" if norm["iso2"] == "AE" else "Global Carrier",
                "line_type": "mobile",
                "country": norm["country"],
                "iso2": norm["iso2"],
                "timezone": norm["timezone"]
            },
            "confidence": norm["confidence"]
        }
