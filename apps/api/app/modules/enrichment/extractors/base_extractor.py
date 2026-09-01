"""
Volume 2 PART 2 — Base Extractor Interface
"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, text_content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts structured fields from raw lead text or payload.
        Returns a dictionary of extracted key-value pairs with confidence.
        """
        pass
