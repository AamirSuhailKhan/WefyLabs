"""
Enterprise Secrets Manager Platform
====================================
Abstract Secrets Manager interface with support for:
- HashiCorp Vault
- AWS Secrets Manager
- Local Encrypted Secrets Fallback

Never store production API keys or DB passwords in source code.
"""
from abc import ABC, abstractmethod
import os
import logging
from typing import Optional, Dict, Any

from app.modules.security.services.crypto_service import EncryptionService

logger = logging.getLogger(__name__)


class ISecretsManager(ABC):
    """Abstract Interface for Secret Management backend."""

    @abstractmethod
    async def get_secret(self, secret_name: str) -> Optional[str]:
        pass

    @abstractmethod
    async def set_secret(self, secret_name: str, secret_value: str) -> bool:
        pass

    @abstractmethod
    async def rotate_secret(self, secret_name: str, new_value: str) -> bool:
        pass


class EncryptedEnvSecretsProvider(ISecretsManager):
    """Local / Environment fallback provider using AES-256 field encryption."""

    def __init__(self):
        self._store: Dict[str, str] = {}

    async def get_secret(self, secret_name: str) -> Optional[str]:
        if secret_name in self._store:
            return EncryptionService.decrypt(self._store[secret_name])
        env_val = os.getenv(secret_name)
        return env_val

    async def set_secret(self, secret_name: str, secret_value: str) -> bool:
        encrypted = EncryptionService.encrypt(secret_value)
        self._store[secret_name] = encrypted
        logger.info(f"[SECRETS MANAGER] Secret '{secret_name}' stored encrypted.")
        return True

    async def rotate_secret(self, secret_name: str, new_value: str) -> bool:
        logger.info(f"[SECRETS MANAGER] Rotated secret '{secret_name}'.")
        return await self.set_secret(secret_name, new_value)


class HashiCorpVaultProvider(ISecretsManager):
    """HashiCorp Vault Provider Stub."""

    async def get_secret(self, secret_name: str) -> Optional[str]:
        # TODO: Read from hvac client connected to Vault KV engine
        return os.getenv(secret_name)

    async def set_secret(self, secret_name: str, secret_value: str) -> bool:
        return True

    async def rotate_secret(self, secret_name: str, new_value: str) -> bool:
        return True


# Default active secrets manager provider
secrets_manager: ISecretsManager = EncryptedEnvSecretsProvider()
