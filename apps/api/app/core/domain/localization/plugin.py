from abc import ABC, abstractmethod
from typing import Dict, Any, List

class ICountryPlugin(ABC):
    """
    Abstract Plugin Interface for Multi-Country Architecture.
    Every supported region implements this plugin to provide localized portals,
    qualification rules, and currency formatting abstractions.
    """

    @property
    @abstractmethod
    def country_code(self) -> str:
        """Returns 2-letter ISO Country Code (e.g. IN, AE, SG, US, GB, AU, CA)."""
        pass

    @property
    @abstractmethod
    def country_name(self) -> str:
        pass

    @property
    @abstractmethod
    def currency(self) -> str:
        pass

    @property
    @abstractmethod
    def default_portals(self) -> List[str]:
        pass

    @abstractmethod
    def format_currency_amount(self, amount: int) -> str:
        pass

    @abstractmethod
    def get_qualification_system_prompt(self, broker_name: str, city: str) -> str:
        pass

    @abstractmethod
    def parse_budget_input(self, text: str) -> Dict[str, Any]:
        pass
