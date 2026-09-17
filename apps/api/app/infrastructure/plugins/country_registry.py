from typing import Dict, List, Any
from app.core.domain.localization.plugin import ICountryPlugin

class IndiaCountryPlugin(ICountryPlugin):
    @property
    def country_code(self) -> str: return "IN"
    @property
    def country_name(self) -> str: return "India"
    @property
    def currency(self) -> str: return "INR"
    @property
    def default_portals(self) -> List[str]: return ["Housing.com", "MagicBricks", "99acres", "Meta Ads"]

    def format_currency_amount(self, amount: int) -> str:
        if amount >= 10000000:
            return f"₹{amount / 10000000:.2f} Cr"
        elif amount >= 100000:
            return f"₹{amount / 100000:.0f} Lakhs"
        return f"₹{amount:,}"

    def get_qualification_system_prompt(self, broker_name: str, city: str) -> str:
        return f"You are WefyLabs AI assistant for {broker_name} in {city}, India. Qualify budget in Lakhs/Crores (₹ INR), configuration (1BHK/2BHK/3BHK), and ready vs under-construction."

    def parse_budget_input(self, text: str) -> Dict[str, Any]:
        msg = text.lower()
        if "lakh" in msg:
            return {"budget_min": 4000000, "budget_max": 7000000}
        elif "crore" in msg or "cr" in msg:
            return {"budget_min": 10000000, "budget_max": 20000000}
        return {}


class UAECountryPlugin(ICountryPlugin):
    @property
    def country_code(self) -> str: return "AE"
    @property
    def country_name(self) -> str: return "UAE"
    @property
    def currency(self) -> str: return "AED"
    @property
    def default_portals(self) -> List[str]: return ["Property Finder", "Bayut", "Dubizzle"]

    def format_currency_amount(self, amount: int) -> str:
        return f"AED {amount:,}"

    def get_qualification_system_prompt(self, broker_name: str, city: str) -> str:
        return f"You are WefyLabs AI assistant for {broker_name} in Dubai/UAE. Qualify budget in AED, off-plan vs secondary market, and Golden Visa interest."

    def parse_budget_input(self, text: str) -> Dict[str, Any]:
        return {"budget_min": 1000000, "budget_max": 2500000}


class SingaporeCountryPlugin(ICountryPlugin):
    @property
    def country_code(self) -> str: return "SG"
    @property
    def country_name(self) -> str: return "Singapore"
    @property
    def currency(self) -> str: return "SGD"
    @property
    def default_portals(self) -> List[str]: return ["PropertyGuru", "99.co"]

    def format_currency_amount(self, amount: int) -> str:
        return f"S${amount:,}"

    def get_qualification_system_prompt(self, broker_name: str, city: str) -> str:
        return f"You are WefyLabs AI assistant for {broker_name} in Singapore. Qualify HDB vs Private Condos, citizenship/ABSD status, and budget in SGD."

    def parse_budget_input(self, text: str) -> Dict[str, Any]:
        return {"budget_min": 800000, "budget_max": 1800000}


class USCountryPlugin(ICountryPlugin):
    @property
    def country_code(self) -> str: return "US"
    @property
    def country_name(self) -> str: return "United States"
    @property
    def currency(self) -> str: return "USD"
    @property
    def default_portals(self) -> List[str]: return ["Zillow", "Realtor.com", "Trulia"]

    def format_currency_amount(self, amount: int) -> str:
        return f"${amount:,}"

    def get_qualification_system_prompt(self, broker_name: str, city: str) -> str:
        return f"You are WefyLabs AI assistant for {broker_name} in the US. Qualify mortgage pre-approval status, desired neighborhood, and budget in USD."

    def parse_budget_input(self, text: str) -> Dict[str, Any]:
        return {"budget_min": 350000, "budget_max": 750000}


class UKCountryPlugin(ICountryPlugin):
    @property
    def country_code(self) -> str: return "GB"
    @property
    def country_name(self) -> str: return "United Kingdom"
    @property
    def currency(self) -> str: return "GBP"
    @property
    def default_portals(self) -> List[str]: return ["Rightmove", "Zoopla", "PrimeLocation"]

    def format_currency_amount(self, amount: int) -> str:
        return f"£{amount:,}"

    def get_qualification_system_prompt(self, broker_name: str, city: str) -> str:
        return f"You are WefyLabs AI assistant for {broker_name} in the UK. Qualify buyer chain status, mortgage in principle, and budget in GBP (£)."

    def parse_budget_input(self, text: str) -> Dict[str, Any]:
        return {"budget_min": 250000, "budget_max": 500000}


class AustraliaCountryPlugin(ICountryPlugin):
    @property
    def country_code(self) -> str: return "AU"
    @property
    def country_name(self) -> str: return "Australia"
    @property
    def currency(self) -> str: return "AUD"
    @property
    def default_portals(self) -> List[str]: return ["REA Group (realestate.com.au)", "Domain"]

    def format_currency_amount(self, amount: int) -> str:
        return f"A${amount:,}"

    def get_qualification_system_prompt(self, broker_name: str, city: str) -> str:
        return f"You are WefyLabs AI assistant for {broker_name} in Australia. Qualify finance approval, auction readiness, and budget in AUD."

    def parse_budget_input(self, text: str) -> Dict[str, Any]:
        return {"budget_min": 600000, "budget_max": 1200000}


class CanadaCountryPlugin(ICountryPlugin):
    @property
    def country_code(self) -> str: return "CA"
    @property
    def country_name(self) -> str: return "Canada"
    @property
    def currency(self) -> str: return "CAD"
    @property
    def default_portals(self) -> List[str]: return ["Realtor.ca", "HouseSigma"]

    def format_currency_amount(self, amount: int) -> str:
        return f"C${amount:,}"

    def get_qualification_system_prompt(self, broker_name: str, city: str) -> str:
        return f"You are WefyLabs AI assistant for {broker_name} in Canada. Qualify mortgage pre-approval, first-time buyer status, and budget in CAD."

    def parse_budget_input(self, text: str) -> Dict[str, Any]:
        return {"budget_min": 500000, "budget_max": 950000}


class CountryPluginRegistry:
    """Central Plugin Registry for Country Localization Adapters."""
    _plugins: Dict[str, ICountryPlugin] = {
        "IN": IndiaCountryPlugin(),
        "AE": UAECountryPlugin(),
        "SG": SingaporeCountryPlugin(),
        "US": USCountryPlugin(),
        "GB": UKCountryPlugin(),
        "AU": AustraliaCountryPlugin(),
        "CA": CanadaCountryPlugin(),
    }

    @classmethod
    def get_plugin(cls, code: str) -> ICountryPlugin:
        return cls._plugins.get(code.upper(), cls._plugins["IN"])
