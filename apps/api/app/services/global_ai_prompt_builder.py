"""
Global AI Prompt Builder
========================
Generates dynamic AI qualification system prompts for any supported country.
Country context is resolved from the database — NEVER hardcoded in prompt strings.
"""
from __future__ import annotations

from typing import Optional
from app.infrastructure.plugins.global_country_config import GlobalCountryRegistry, CountryConfiguration


class GlobalAIPromptBuilder:
    """
    Generates dynamic AI qualification system prompts for any of the 100+ supported countries
    without relying on hardcoded country strings or prompt templates.

    For richer context (currency symbol, area unit, compliance framework, AI persona),
    use build_system_prompt_v2() which integrates GlobalContextBuilder.
    """

    @classmethod
    def build_system_prompt(cls, country_code: str, broker_name: str, city: str) -> str:
        config: CountryConfiguration = GlobalCountryRegistry.get(country_code)

        metrics_str = ", ".join(config.qualification_metrics) if config.qualification_metrics else "budget, location, property_type, timeline"
        portals_str = ", ".join(config.default_portals) if config.default_portals else "local property portals"

        flags_instructions = []
        if config.feature_flags.supports_lakhs_crores:
            flags_instructions.append("Format budget numbers in Lakhs or Crores (₹ INR).")
        if config.feature_flags.supports_hdb_logic:
            flags_instructions.append("Qualify if the buyer is looking for HDB public housing vs Private Condos, and verify citizenship status.")
        if config.feature_flags.supports_golden_visa:
            # UAE Golden Visa threshold is a policy — not hardcoded. Remind to mention qualifying properties.
            flags_instructions.append(
                "Check if the lead is interested in UAE Golden Visa qualifying properties "
                "(confirm current eligibility threshold from compliance policy)."
            )
        if config.feature_flags.requires_tcpa_optout:
            flags_instructions.append("Include TCPA compliance disclaimer if requested.")
        if config.feature_flags.requires_gdpr_consent:
            flags_instructions.append("Respect GDPR data privacy preferences.")

        flags_text = " ".join(flags_instructions)

        return (
            f"You are BeetleLabs AI assistant for {broker_name} operating in {city}, {config.name}. "
            f"Your job is to chat on WhatsApp and qualify leads arriving from {portals_str}. "
            f"Focus on gathering the following qualification metrics: {metrics_str}. "
            f"All financial calculations must use currency {config.currency} ({config.currency_symbol.strip()}). "
            f"{flags_text}"
        )

    @classmethod
    async def build_system_prompt_v2(
        cls,
        broker_name: str,
        country_code: Optional[str] = None,
        market_id: Optional[str] = None,
        locale: Optional[str] = None,
        db=None,  # AsyncSession — injected at call site
    ) -> str:
        """
        V2: Fully dynamic prompt using GlobalContextBuilder.
        All country/market/currency context resolved from DB — nothing hardcoded.
        Falls back to V1 if GlobalContextBuilder cannot resolve context.
        """
        if db and (country_code or market_id):
            try:
                from app.modules.global_.ai_context.global_context_builder import GlobalContextBuilder
                builder = GlobalContextBuilder(db)
                context = await builder.build(
                    country_code=country_code,
                    market_id=market_id,
                    locale=locale,
                )
                if context:
                    base = (
                        f"You are BeetleLabs AI assistant for {broker_name}. "
                        f"{context.ai_persona_hint} "
                        f"Always respond in {context.language_code}. "
                        f"Format all monetary values in {context.display_price_in}. "
                    )
                    context_block = context.to_system_prompt_fragment()
                    return f"{base}\n\n{context_block}"
            except Exception:
                pass

        # Fallback to V1 if no DB or context
        if country_code:
            return cls.build_system_prompt(country_code, broker_name, "")
        return f"You are BeetleLabs AI assistant for {broker_name}. Qualify leads professionally."
