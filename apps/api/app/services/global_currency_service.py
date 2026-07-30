from typing import Dict
from app.infrastructure.plugins.global_country_config import GlobalCountryRegistry

# Static fallback exchange rates relative to 1 USD
STATIC_EXCHANGE_RATES_TO_USD: Dict[str, float] = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.78,
    "INR": 83.5,
    "AED": 3.67,
    "SGD": 1.35,
    "AUD": 1.52,
    "CAD": 1.36,
    "JPY": 155.0,
    "BRL": 5.15,
    "MXN": 16.8,
}

class GlobalCurrencyService:
    """
    Universal Currency Formatting and Multi-Currency Conversion Engine.
    Scales to 100+ countries with automatic symbol formatting and USD normalized reporting.
    """

    @classmethod
    def format_amount(cls, amount: int, country_code: str) -> str:
        config = GlobalCountryRegistry.get(country_code)
        symbol = config.currency_symbol.strip()

        if config.feature_flags.supports_lakhs_crores:
            if amount >= 10000000:
                return f"{symbol}{amount / 10000000:.2f} Cr"
            elif amount >= 100000:
                return f"{symbol}{amount / 100000:.0f} Lakhs"

        return f"{symbol}{amount:,}"

    @classmethod
    def convert_to_usd(cls, amount: float, currency_code: str) -> float:
        rate = STATIC_EXCHANGE_RATES_TO_USD.get(currency_code.upper(), 1.0)
        return round(amount / rate, 2)
