"""
Volume 2 PART 2 — Email Verification Provider
"""
import time
from typing import Dict, Any, Optional
from app.modules.enrichment.providers.base_provider import BaseEnrichmentProvider


class EmailVerifyProvider(BaseEnrichmentProvider):
    provider_name = "DefaultEmailVerify"
    provider_type = "email_verify"

    async def lookup(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        start = time.time()
        latency_ms = round((time.time() - start) * 1000, 2)

        if not query or "@" not in query:
            return {
                "provider": self.provider_name,
                "success": False,
                "latency_ms": latency_ms,
                "data": {"is_valid": False},
                "confidence": 0.0
            }

        domain = query.split("@")[-1].lower()
        is_free = domain in ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com"]

        return {
            "provider": self.provider_name,
            "success": True,
            "latency_ms": latency_ms,
            "data": {
                "email": query,
                "domain": domain,
                "is_deliverable": True,
                "is_disposable": False,
                "is_free_provider": is_free,
                "company": domain.split(".")[0].title() if not is_free else None
            },
            "confidence": 0.95
        }
