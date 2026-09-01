"""
Volume 2 PART 2 — Base Provider Interface
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import time


class BaseEnrichmentProvider(ABC):
    provider_name: str
    provider_type: str

    @abstractmethod
    async def lookup(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes external lookup and returns standardized dict.
        """
        pass
