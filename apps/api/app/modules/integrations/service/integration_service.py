import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.infrastructure_models import Integration
from app.modules.integrations.interfaces.provider_interface import get_provider, INTEGRATION_PROVIDER_REGISTRY

logger = logging.getLogger(__name__)


class IntegrationService:
    """
    Integration Framework Service.
    Delegates all provider-specific logic to IIntegrationProvider adapters.
    CRM business services never import provider-specific code.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    def list_available_providers(self) -> List[dict]:
        """List all registered integration providers."""
        return [
            {"provider": name, "display_name": p.provider_display_name}
            for name, p in INTEGRATION_PROVIDER_REGISTRY.items()
        ]

    async def list_connected(self, organization_id: str) -> List[Integration]:
        stmt = select(Integration).where(Integration.organization_id == organization_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def connect(
        self,
        organization_id: str,
        provider_name: str,
        credentials: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
    ) -> Integration:
        provider = get_provider(provider_name)
        if not provider:
            raise ValueError(f"Unknown integration provider: '{provider_name}'")

        success = await provider.connect(credentials, config)
        status = "connected" if success else "error"

        # Upsert the integration record
        stmt = select(Integration).where(
            Integration.organization_id == organization_id,
            Integration.provider == provider_name,
        )
        existing = (await self.db.execute(stmt)).scalars().first()

        if existing:
            existing.status = status
            existing.updated_at = datetime.now(timezone.utc)
            integration = existing
        else:
            integration = Integration(
                organization_id=organization_id,
                provider=provider_name,
                display_name=provider.provider_display_name,
                status=status,
                config=config or {},
            )
            self.db.add(integration)

        await self.db.commit()
        logger.info(f"[INTEGRATION] Connected '{provider_name}' for org={organization_id} status={status}")
        return integration

    async def disconnect(self, organization_id: str, provider_name: str) -> bool:
        provider = get_provider(provider_name)
        if not provider:
            raise ValueError(f"Unknown provider: '{provider_name}'")

        stmt = select(Integration).where(
            Integration.organization_id == organization_id,
            Integration.provider == provider_name,
        )
        integration = (await self.db.execute(stmt)).scalars().first()
        if integration:
            await provider.disconnect(str(integration.id))
            integration.status = "disconnected"
            integration.is_active = False
            await self.db.commit()
        return True
