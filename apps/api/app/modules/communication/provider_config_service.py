"""
Part 21.6 — Provider Configuration & Health Service
====================================================
Inspects provider readiness and health status across channels (WhatsApp, Email, SMS,
WebChat, Telegram) without leaking credentials or secrets.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.communication.channel_manager.manager import ChannelManager, get_channel_manager
from app.modules.communication.provider_adapters.base_provider import (
    ProviderStatusEnum,
    CommunicationCapabilities,
)
from app.models.communication_models import ProviderCredential

logger = logging.getLogger("wefylabs.communication.config")


@dataclass
class ChannelProviderHealthDTO:
    """Safe, non-secret operational health report for a channel provider."""
    channel: str
    provider_name: str
    status: ProviderStatusEnum
    is_configured: bool
    is_active: bool = True
    capabilities: Dict[str, Any] = field(default_factory=dict)
    last_verified_at: Optional[datetime] = None
    safe_metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


class ProviderConfigurationService:
    """
    Service reporting provider operational readiness and connectivity.
    """

    def __init__(self, channel_manager: Optional[ChannelManager] = None):
        self.channel_manager = channel_manager or get_channel_manager()

    async def get_all_provider_health(
        self,
        organization_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> List[ChannelProviderHealthDTO]:
        """
        Returns health and readiness status for all supported channels.
        Checks both ChannelManager provider instances and database ProviderCredentials.
        """
        results: List[ChannelProviderHealthDTO] = []
        channels = self.channel_manager.supported_channels()

        # Fetch org-specific DB credentials if DB session provided
        db_creds_map: Dict[str, ProviderCredential] = {}
        if db and organization_id:
            stmt = select(ProviderCredential).where(
                ProviderCredential.organization_id == organization_id,
                ProviderCredential.is_active == True,
            )
            res = await db.execute(stmt)
            for cred in res.scalars().all():
                db_creds_map[cred.channel.lower()] = cred

        for ch in channels:
            providers = self.channel_manager.get_all_providers(ch)
            for p in providers:
                try:
                    status = await p.verify_configuration()
                    is_conf = getattr(p, "is_configured", lambda: status == ProviderStatusEnum.READY)()
                    caps = p.capabilities()

                    db_cred = db_creds_map.get(ch.lower())
                    last_verified = db_cred.last_verified_at if db_cred else datetime.now(timezone.utc)

                    safe_meta: Dict[str, Any] = {}
                    if ch == "whatsapp":
                        pid = getattr(p, "_phone_number_id", "") or ""
                        safe_meta["phone_number_id_configured"] = bool(pid and pid not in ("mock_phone_number_id", "placeholder"))
                        if pid and len(pid) > 4:
                            safe_meta["phone_number_id_preview"] = f"***{pid[-4:]}"
                    elif ch == "email":
                        from_em = getattr(p, "_from_email", "") or ""
                        safe_meta["from_email"] = from_em
                        safe_meta["smtp_host_configured"] = bool(getattr(p, "_smtp_host", ""))
                    elif ch == "sms":
                        from_num = getattr(p, "_from_number", "") or ""
                        if from_num and len(from_num) > 4:
                            safe_meta["from_number_preview"] = f"***{from_num[-4:]}"

                    results.append(
                        ChannelProviderHealthDTO(
                            channel=ch,
                            provider_name=p.provider_name,
                            status=status,
                            is_configured=is_conf,
                            capabilities={
                                "supports_text": caps.supports_text,
                                "supports_templates": caps.supports_templates,
                                "supports_media": caps.supports_media,
                                "supports_read_receipts": caps.supports_read_receipts,
                                "supports_webhooks": caps.supports_webhooks,
                            },
                            last_verified_at=last_verified,
                            safe_metadata=safe_meta,
                        )
                    )
                except Exception as e:
                    logger.error(f"[ProviderConfigService] Error checking provider={p.provider_name}: {e}")
                    results.append(
                        ChannelProviderHealthDTO(
                            channel=ch,
                            provider_name=p.provider_name,
                            status=ProviderStatusEnum.CONFIGURATION_REQUIRED,
                            is_configured=False,
                            error_message=str(e),
                        )
                    )

        return results

    async def get_channel_health(self, channel: str) -> Optional[ChannelProviderHealthDTO]:
        """Returns health status for a single channel."""
        all_health = await self.get_all_provider_health()
        for h in all_health:
            if h.channel.lower() == channel.lower():
                return h
        return None
