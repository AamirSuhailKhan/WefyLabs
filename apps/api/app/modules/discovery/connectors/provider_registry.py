"""
Part 21.2 — Discovery Provider Registry
=========================================
Factory and registry mapping provider names to singleton provider instances.
"""
from __future__ import annotations
from typing import Dict, Optional, List

from app.modules.discovery.connectors.base_provider import IDiscoveryProvider
from app.modules.discovery.connectors.meta_provider import MetaDiscoveryProvider
from app.modules.discovery.connectors.google_provider import GoogleDiscoveryProvider
from app.modules.discovery.connectors.partner_provider import PartnerAPIProvider
from app.modules.discovery.connectors.customer_api_provider import CustomerAPIProvider
from app.modules.discovery.connectors.website_signal_provider import WebsiteSignalProvider
from app.modules.discovery.connectors.licensed_provider import LicensedProvider


class DiscoveryProviderRegistry:
    _providers: Dict[str, IDiscoveryProvider] = {}

    @classmethod
    def initialize(cls) -> None:
        if not cls._providers:
            providers = [
                MetaDiscoveryProvider(),
                GoogleDiscoveryProvider(),
                PartnerAPIProvider(),
                CustomerAPIProvider(),
                WebsiteSignalProvider(),
                LicensedProvider(),
            ]
            for p in providers:
                cls._providers[p.provider_name.lower()] = p

    @classmethod
    def get_provider(cls, provider_name: str) -> Optional[IDiscoveryProvider]:
        cls.initialize()
        return cls._providers.get(provider_name.lower())

    @classmethod
    def list_providers(cls) -> List[IDiscoveryProvider]:
        cls.initialize()
        return list(cls._providers.values())


def get_discovery_provider(provider_name: str) -> Optional[IDiscoveryProvider]:
    return DiscoveryProviderRegistry.get_provider(provider_name)
