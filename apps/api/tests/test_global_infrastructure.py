"""
Test Suite — Global Multi-Country Infrastructure Engine
=======================================================
Tests: Money, ExchangeRateService, TimezoneService,
       PolicyService, PropertySchemaRegistry, ConsentService,
       MarketActivationService, GlobalContextBuilder,
       PhoneService, AddressService, TaxFeeService,
       TranslationService, ConfigurationHierarchyResolver,
       RegionalPipelineService, MarketFlagService,
       CrossCountryAnalyticsEngine, CrossCountryIdentityResolver,
       GlobalEventBus

Run: pytest apps/api/tests/test_global_infrastructure.py -v
"""
import pytest
from decimal import Decimal
from datetime import datetime, timezone, date
from unittest.mock import AsyncMock, MagicMock, patch


# ─────────────────────────────────────────────────────────────────────────────
# MONEY TYPE TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestMoney:
    """Core financial arithmetic — must NEVER use floats."""

    def test_money_creation_with_decimal(self):
        from app.modules.global_.currencies.money import Money
        m = Money(Decimal("1500000"), "AED")
        assert m.amount == Decimal("1500000")
        assert m.currency_code == "AED"

    def test_money_of_factory_accepts_string(self):
        from app.modules.global_.currencies.money import Money
        m = Money.of("1500000", "AED")
        assert m.amount == Decimal("1500000")

    def test_money_of_factory_accepts_int(self):
        from app.modules.global_.currencies.money import Money
        m = Money.of(8500000, "INR")
        assert m.amount == Decimal("8500000")
        assert m.currency_code == "INR"

    def test_money_requires_decimal_type(self):
        from app.modules.global_.currencies.money import Money
        with pytest.raises(TypeError, match="must be Decimal"):
            Money(1500000.0, "AED")  # float rejected

    def test_money_requires_valid_currency_code(self):
        from app.modules.global_.currencies.money import Money
        with pytest.raises(ValueError):
            Money(Decimal("100"), "D")  # 1-char code rejected
        with pytest.raises(ValueError):
            Money(Decimal("100"), "")   # empty rejected

    def test_money_add_same_currency(self):
        from app.modules.global_.currencies.money import Money
        a = Money.of("1000000", "AED")
        b = Money.of("500000", "AED")
        result = a.add(b)
        assert result.amount == Decimal("1500000")
        assert result.currency_code == "AED"

    def test_money_add_different_currency_raises(self):
        from app.modules.global_.currencies.money import Money
        a = Money.of("1000000", "AED")
        b = Money.of("1000000", "INR")
        with pytest.raises(ValueError, match="Cannot add"):
            a.add(b)

    def test_money_multiply_dld_fee(self):
        """UAE DLD fee = 4% of property value."""
        from app.modules.global_.currencies.money import Money
        price = Money.of("2000000", "AED")
        dld_fee = price.multiply(Decimal("0.04"))
        assert dld_fee.amount == Decimal("80000.00000000")
        assert dld_fee.currency_code == "AED"

    def test_money_inr_format_lakhs(self):
        from app.modules.global_.currencies.money import Money
        m = Money.of("8500000", "INR")
        formatted = m.format("en-IN")
        assert "Cr" in formatted or "L" in formatted

    def test_money_to_dict(self):
        from app.modules.global_.currencies.money import Money
        m = Money.of("250000", "GBP")
        d = m.to_dict()
        assert d["amount"] == "250000"
        assert d["currency_code"] == "GBP"

    def test_money_is_positive(self):
        from app.modules.global_.currencies.money import Money
        assert Money.of("100", "USD").is_positive()
        assert not Money.of("0", "USD").is_positive()

    def test_money_rounded_to_display_precision(self):
        from app.modules.global_.currencies.money import Money
        m = Money(Decimal("1999.999"), "USD")
        rounded = m.rounded()
        assert rounded.amount == Decimal("2000.00")


# ─────────────────────────────────────────────────────────────────────────────
# EXCHANGE RATE SERVICE TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestExchangeRateService:
    """FX service must NEVER return 1:1 silently — explicit FX_UNAVAILABLE."""

    @pytest.mark.asyncio
    async def test_same_currency_returns_trivial(self):
        from app.modules.global_.currencies.exchange_rate_service import ExchangeRateService
        db = AsyncMock()
        service = ExchangeRateService(db)
        result = await service.get_rate("AED", "AED")
        assert result.rate == Decimal("1")
        assert result.rate_type == "TRIVIAL"
        assert result.status == "OK"

    @pytest.mark.asyncio
    async def test_fx_unavailable_never_returns_one_to_one(self):
        """The critical test: must return FX_UNAVAILABLE, not 1:1 silently."""
        from app.modules.global_.currencies.exchange_rate_service import ExchangeRateService
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None))
        service = ExchangeRateService(db)
        result = await service.get_rate("XYZ", "ABC")
        assert result.status == "FX_UNAVAILABLE"
        assert result.rate == Decimal("0")  # NOT 1.0

    @pytest.mark.asyncio
    async def test_convert_raises_on_unavailable(self):
        from app.modules.global_.currencies.exchange_rate_service import ExchangeRateService
        from app.modules.global_.currencies.money import Money, FXUnavailableError
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None))
        service = ExchangeRateService(db)
        money = Money.of("1000000", "AED")
        with pytest.raises(FXUnavailableError):
            await service.convert(money, "XYZ")


# ─────────────────────────────────────────────────────────────────────────────
# TIMEZONE SERVICE TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestTimezoneService:
    """Timezone must NEVER default to Asia/Dubai or any country-specific TZ."""

    def test_resolves_user_timezone_first(self):
        from app.modules.global_.timezones.timezone_service import TimezoneService, TimezoneContext
        ctx = TimezoneContext(
            user_timezone="Asia/Kolkata",
            org_timezone="Asia/Dubai",
        )
        result = TimezoneService.resolve(ctx)
        assert result == "Asia/Kolkata"  # User wins

    def test_resolves_org_timezone_when_no_user(self):
        from app.modules.global_.timezones.timezone_service import TimezoneService, TimezoneContext
        ctx = TimezoneContext(org_timezone="America/New_York")
        result = TimezoneService.resolve(ctx)
        assert result == "America/New_York"

    def test_falls_back_to_utc_not_dubai(self):
        """Critical: empty context MUST fall back to UTC, never Asia/Dubai."""
        from app.modules.global_.timezones.timezone_service import TimezoneService, TimezoneContext
        ctx = TimezoneContext()  # All None
        result = TimezoneService.resolve(ctx)
        assert result == "UTC"
        assert result != "Asia/Dubai"  # Explicit check

    def test_invalid_timezone_skipped(self):
        from app.modules.global_.timezones.timezone_service import TimezoneService, TimezoneContext
        ctx = TimezoneContext(
            user_timezone="Invalid/Timezone",
            org_timezone="Europe/London",
        )
        result = TimezoneService.resolve(ctx)
        assert result == "Europe/London"

    def test_converts_utc_to_local(self):
        from app.modules.global_.timezones.timezone_service import TimezoneService
        utc_dt = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        local = TimezoneService.convert_to_local(utc_dt, "Asia/Dubai")
        assert local.hour == 16  # UAE is UTC+4

    def test_converts_utc_to_local_kolkata(self):
        from app.modules.global_.timezones.timezone_service import TimezoneService
        utc_dt = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        local = TimezoneService.convert_to_local(utc_dt, "Asia/Kolkata")
        assert local.hour == 17  # IST is UTC+5:30
        assert local.minute == 30

    def test_invalid_tz_falls_back_to_utc(self):
        from app.modules.global_.timezones.timezone_service import TimezoneService
        utc_dt = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        local = TimezoneService.convert_to_local(utc_dt, "Not/Valid")
        assert local.tzname() == "UTC"

    def test_phone_inference_uae(self):
        from app.modules.global_.timezones.timezone_service import TimezoneService
        tz = TimezoneService._infer_from_phone("+971501234567")
        assert tz == "Asia/Dubai"

    def test_phone_inference_india(self):
        from app.modules.global_.timezones.timezone_service import TimezoneService
        tz = TimezoneService._infer_from_phone("+919876543210")
        assert tz == "Asia/Kolkata"

    def test_phone_inference_unknown_returns_none(self):
        from app.modules.global_.timezones.timezone_service import TimezoneService
        tz = TimezoneService._infer_from_phone("+999000000000")
        assert tz is None


# ─────────────────────────────────────────────────────────────────────────────
# PROPERTY SCHEMA REGISTRY TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestPropertySchemaRegistry:
    """Property types must come from market schema, not hardcoded BHK/villa list."""

    @pytest.mark.asyncio
    async def test_no_schema_returns_none_allows_any_type(self):
        from app.modules.global_.property_schema.schema_registry import PropertySchemaRegistry
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None))
        registry = PropertySchemaRegistry(db)
        is_valid = await registry.validate_property_type("anything", market_id="some-market-id")
        assert is_valid is True  # permissive when no schema

    @pytest.mark.asyncio
    async def test_schema_restricts_property_types(self):
        from app.modules.global_.property_schema.schema_registry import PropertySchemaRegistry
        mock_schema = MagicMock()
        mock_schema.property_type_codes = ["1bhk", "2bhk", "3bhk", "villa", "plot"]
        mock_schema.id = "schema-123"

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: mock_schema))
        registry = PropertySchemaRegistry(db)

        # Valid type
        is_valid = await registry.validate_property_type("1bhk", market_id="india-market")
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_bhk_not_valid_for_uae_market(self):
        """1bhk is an India type — should be invalid for UAE market."""
        from app.modules.global_.property_schema.schema_registry import PropertySchemaRegistry
        mock_schema = MagicMock()
        mock_schema.property_type_codes = ["studio", "1_bed", "2_bed", "luxury_villa", "penthouse"]
        mock_schema.id = "uae-schema"

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: mock_schema))
        registry = PropertySchemaRegistry(db)

        is_valid = await registry.validate_property_type("1bhk", market_id="dubai-market")
        assert is_valid is False


# ─────────────────────────────────────────────────────────────────────────────
# UNIT CONVERSION TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestUnitConversionService:

    def test_sqft_to_sqm(self):
        from app.modules.global_.property_schema.schema_registry import UnitConversionService
        result = UnitConversionService.to_sqft(100, "sqm")
        assert abs(result.canonical_value - 1076.39) < 1.0  # 100 sqm ≈ 1076 sqft

    def test_sqft_to_sqft_identity(self):
        from app.modules.global_.property_schema.schema_registry import UnitConversionService
        result = UnitConversionService.to_sqft(1000, "sqft")
        assert result.canonical_value == 1000.0

    def test_marla_to_sqft(self):
        from app.modules.global_.property_schema.schema_registry import UnitConversionService
        result = UnitConversionService.to_sqft(5, "marla")
        assert abs(result.canonical_value - 1361.25) < 1.0  # 5 marla = 1361.25 sqft

    def test_kanal_to_sqft(self):
        from app.modules.global_.property_schema.schema_registry import UnitConversionService
        result = UnitConversionService.to_sqft(1, "kanal")
        assert result.canonical_value == 5445.0

    def test_round_trip_sqm(self):
        from app.modules.global_.property_schema.schema_registry import UnitConversionService
        sqft = UnitConversionService.to_sqft(200, "sqm").canonical_value
        back = UnitConversionService.from_sqft(sqft, "sqm")
        assert abs(back - 200.0) < 0.1

    def test_unknown_unit_treated_as_sqft(self):
        from app.modules.global_.property_schema.schema_registry import UnitConversionService
        result = UnitConversionService.to_sqft(500, "unknown_unit")
        assert result.canonical_value == 500.0  # passes through as sqft


# ─────────────────────────────────────────────────────────────────────────────
# CONSENT SERVICE TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestConsentService:

    @pytest.mark.asyncio
    async def test_has_consent_false_when_no_record(self):
        from app.modules.global_.consent.consent_service import ConsentService
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None))
        service = ConsentService(db)
        result = await service.has_consent("lead-1", "org-1", "WHATSAPP")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_consent_status_unknown_when_no_record(self):
        from app.modules.global_.consent.consent_service import ConsentService
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None))
        service = ConsentService(db)
        status = await service.get_consent_status("lead-1", "org-1", "SMS")
        assert status == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_granted_consent_is_detected(self):
        from app.modules.global_.consent.consent_service import ConsentService
        mock_record = MagicMock()
        mock_record.status = "GRANTED"
        mock_record.expires_at = None
        mock_record.withdrawn_at = None

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: mock_record))
        service = ConsentService(db)
        result = await service.has_consent("lead-1", "org-1", "EMAIL")
        assert result is True

    @pytest.mark.asyncio
    async def test_expired_consent_not_active(self):
        from app.modules.global_.consent.consent_service import ConsentService
        from datetime import timedelta
        mock_record = MagicMock()
        mock_record.status = "GRANTED"
        mock_record.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)  # expired 1 hour ago
        mock_record.withdrawn_at = None

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: mock_record))
        service = ConsentService(db)
        result = await service.has_consent("lead-1", "org-1", "WHATSAPP")
        assert result is False


# ─────────────────────────────────────────────────────────────────────────────
# POLICY SERVICE TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestPolicyService:

    @pytest.mark.asyncio
    async def test_no_policy_returns_unknown(self):
        from app.modules.global_.policies.policy_service import PolicyService, PolicyContext
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: [])))
        service = PolicyService(db)
        ctx = PolicyContext(organization_id="org-1", market_id="market-1")
        result = await service.evaluate("COMMUNICATION", "send_whatsapp", ctx)
        assert result.decision == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_allowed_policy_returns_allowed(self):
        from app.modules.global_.policies.policy_service import PolicyService, PolicyContext
        mock_policy = MagicMock()
        mock_policy.policy_key = "whatsapp_allowed"
        mock_policy.category = "COMMUNICATION"
        mock_policy.version = 1
        mock_policy.id = "policy-1"
        mock_policy.rule_json = {
            "actions": ["send_whatsapp"],
            "decision": "ALLOWED",
            "reason": "WhatsApp communication permitted in UAE."
        }

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: [mock_policy])))
        service = PolicyService(db)
        ctx = PolicyContext(organization_id="org-1", market_id="market-uae")
        result = await service.evaluate("COMMUNICATION", "send_whatsapp", ctx)
        assert result.decision == "ALLOWED"

    def test_quiet_hours_local_hour_calculation(self):
        from app.modules.global_.policies.policy_service import PolicyService
        # Midnight UTC = 4am Dubai (UTC+4)
        utc_midnight = datetime(2026, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        local_hour = PolicyService._get_local_hour(utc_midnight, "Asia/Dubai")
        assert local_hour == 4


# ─────────────────────────────────────────────────────────────────────────────
# MARKET ACTIVATION SERVICE TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestMarketActivationService:

    @pytest.mark.asyncio
    async def test_cannot_go_general_without_checklist(self):
        from app.modules.global_.markets.service import MarketActivationService, ACTIVATION_CHECKLIST_KEYS
        mock_rollout = MagicMock()
        mock_rollout.rollout_status = "LIMITED"
        mock_rollout.checklist_completed = {k: False for k in ACTIVATION_CHECKLIST_KEYS}

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: mock_rollout))
        service = MarketActivationService(db)
        success, msg = await service.advance_status("org-1", "market-1", "GENERAL")
        assert success is False
        assert "incomplete" in msg.lower() or "checklist" in msg.lower()

    @pytest.mark.asyncio
    async def test_valid_transition_internal_to_beta(self):
        from app.modules.global_.markets.service import MarketActivationService
        mock_rollout = MagicMock()
        mock_rollout.rollout_status = "INTERNAL"

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: mock_rollout))
        service = MarketActivationService(db)
        success, msg = await service.advance_status("org-1", "market-1", "BETA")
        assert success is True

    def test_invalid_transition_raises_blocked(self):
        from app.modules.global_.markets.service import MarketActivationService
        allowed = MarketActivationService.VALID_TRANSITIONS.get("GENERAL", [])
        assert "INTERNAL" not in allowed  # Cannot go back to INTERNAL from GENERAL
        assert "BETA" not in allowed


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CONTEXT BUILDER TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestGlobalContextBuilder:

    @pytest.mark.asyncio
    async def test_returns_none_with_no_context(self):
        from app.modules.global_.ai_context.global_context_builder import GlobalContextBuilder
        db = AsyncMock()
        builder = GlobalContextBuilder(db)
        result = await builder.build()
        assert result is None

    @pytest.mark.asyncio
    async def test_currency_symbol_lookup(self):
        from app.modules.global_.ai_context.global_context_builder import GlobalContextBuilder
        assert GlobalContextBuilder._get_currency_symbol("INR") == "₹"
        assert GlobalContextBuilder._get_currency_symbol("AED") == "AED"
        assert GlobalContextBuilder._get_currency_symbol("GBP") == "£"
        assert GlobalContextBuilder._get_currency_symbol("USD") == "$"

    @pytest.mark.asyncio
    async def test_display_price_hints(self):
        from app.modules.global_.ai_context.global_context_builder import GlobalContextBuilder
        assert "lakhs" in GlobalContextBuilder._build_display_price_hint("INR").lower()
        assert "AED" in GlobalContextBuilder._build_display_price_hint("AED")
        assert "£" in GlobalContextBuilder._build_display_price_hint("GBP")

    @pytest.mark.asyncio
    async def test_system_prompt_fragment_contains_country(self):
        from app.modules.global_.ai_context.global_context_builder import GlobalAIContext
        ctx = GlobalAIContext(
            country_code="AE",
            country_name="United Arab Emirates",
            market_name="Dubai",
            currency_code="AED",
            currency_symbol="AED",
            timezone="Asia/Dubai",
            language_code="en",
            is_rtl=False,
            date_format="DD/MM/YYYY",
            property_types=["studio", "1_bed", "2_bed"],
            compliance_framework="DLD & RERA Dubai",
            phone_code="+971",
            ai_persona_hint="High-end Dubai specialist.",
            golden_visa_eligible=True,
            rera_compliance_required=True,
            area_unit="sqft",
            display_price_in="AED (e.g., AED 1,500,000)",
        )
        fragment = ctx.to_system_prompt_fragment()
        assert "United Arab Emirates" in fragment
        assert "Dubai" in fragment
        assert "AED" in fragment
        assert "Golden Visa" in fragment
        assert "RERA" in fragment


# ─────────────────────────────────────────────────────────────────────────────
# PHONE SERVICE TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestPhoneService:

    def test_normalize_india_phone(self):
        from app.modules.global_.phone.phone_service import PhoneService
        e164 = PhoneService.normalize_to_e164("9084399304", default_region="IN")
        assert e164 == "+919084399304"

    def test_normalize_uae_phone(self):
        from app.modules.global_.phone.phone_service import PhoneService
        e164 = PhoneService.normalize_to_e164("+971 50 123 4567")
        assert e164 == "+971501234567"

    def test_extract_country_code(self):
        from app.modules.global_.phone.phone_service import PhoneService
        assert PhoneService.extract_country_code("+919084399304") == "IN"
        assert PhoneService.extract_country_code("+971501234567") == "AE"
        assert PhoneService.extract_country_code("+447911123456") == "GB"

    def test_mask_phone_number(self):
        from app.modules.global_.phone.phone_service import PhoneService
        masked = PhoneService.mask("+919084399304")
        assert masked.endswith("9304")
        assert "X" in masked


# ─────────────────────────────────────────────────────────────────────────────
# ADDRESS SERVICE TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestAddressService:

    def test_uae_address_formatting(self):
        from app.modules.global_.addresses.address_service import AddressService
        addr = AddressService.format_address("AE", {
            "building": "Burj Crown",
            "area": "Downtown Dubai",
            "emirate": "Dubai",
            "makani": "12345 67890"
        })
        assert addr.country_code == "AE"
        assert "Burj Crown" in addr.formatted_address
        assert "Downtown Dubai" in addr.formatted_address
        assert "United Arab Emirates" in addr.formatted_address

    def test_india_address_formatting(self):
        from app.modules.global_.addresses.address_service import AddressService
        addr = AddressService.format_address("IN", {
            "line1": "Flat 402, Prestige Tower",
            "locality": "Koramangala",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560034"
        })
        assert addr.country_code == "IN"
        assert "560034" in addr.formatted_address
        assert "Bengaluru" in addr.formatted_address


# ─────────────────────────────────────────────────────────────────────────────
# TAX & FEE SERVICE TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestTaxFeeService:

    def test_dubai_transaction_costs(self):
        from app.modules.global_.tax.tax_fee_service import TaxFeeService
        from app.modules.global_.currencies.money import Money

        price = Money.of("2000000", "AED")
        costs = TaxFeeService.calculate_transaction_costs(price, "AE")
        
        # 4% DLD fee = 80,000 AED
        dld_item = next(it for it in costs.items if it.item_key == "dld_transfer_fee")
        assert dld_item.amount.amount == Decimal("80000")
        assert costs.grand_total_estimated.amount > Decimal("2000000")

    def test_saudi_rett_tax_calculation(self):
        from app.modules.global_.tax.tax_fee_service import TaxFeeService
        from app.modules.global_.currencies.money import Money

        price = Money.of("3000000", "SAR")
        costs = TaxFeeService.calculate_transaction_costs(price, "SA")
        
        # 5% RETT = 150,000 SAR
        rett_item = next(it for it in costs.items if it.item_key == "rett_tax")
        assert rett_item.amount.amount == Decimal("150000")


# ─────────────────────────────────────────────────────────────────────────────
# TRANSLATION SERVICE TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestTranslationService:

    @pytest.mark.asyncio
    async def test_fallback_chain_returns_key_if_missing(self):
        from app.modules.global_.localization.translation_service import TranslationService
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None))
        service = TranslationService(db)
        
        # Returns key safely instead of crashing or returning undefined
        res = await service.t("crm.lead.status.new", "ar-AE")
        assert res == "lead.status.new" or res == "crm.lead.status.new"

    def test_rtl_detection(self):
        from app.modules.global_.localization.translation_service import TranslationService
        assert TranslationService.is_rtl("ar-AE") is True
        assert TranslationService.is_rtl("ar-SA") is True
        assert TranslationService.is_rtl("en-US") is False
        assert TranslationService.is_rtl("hi-IN") is False


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION HIERARCHY RESOLVER TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestConfigurationHierarchyResolver:

    @pytest.mark.asyncio
    async def test_system_default_fallback(self):
        from app.modules.global_.configuration.hierarchy_resolver import ConfigurationHierarchyResolver
        db = AsyncMock()
        resolver = ConfigurationHierarchyResolver(db)
        res = await resolver.resolve("timezone")
        assert res.value == "UTC"
        assert res.resolved_from == "system"
        assert res.is_default is True


# ─────────────────────────────────────────────────────────────────────────────
# REGIONAL PIPELINE SERVICE TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestRegionalPipelineService:

    @pytest.mark.asyncio
    async def test_validate_transition_same_stage(self):
        from app.modules.global_.pipelines.regional_pipeline_service import RegionalPipelineService
        db = AsyncMock()
        service = RegionalPipelineService(db)
        res = await service.validate_transition("new", "new")
        assert res.success is True


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE FLAGS TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestMarketFlagService:

    @pytest.mark.asyncio
    async def test_system_default_flag_is_off(self):
        from app.modules.global_.feature_flags.market_flag_service import MarketFlagService
        db = AsyncMock()
        service = MarketFlagService(db)
        enabled = await service.is_enabled("communication.whatsapp")
        assert enabled is False


# ─────────────────────────────────────────────────────────────────────────────
# CROSS COUNTRY REVENUE ANALYTICS TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestCrossCountryAnalytics:

    @pytest.mark.asyncio
    async def test_consolidated_revenue_report(self):
        from app.modules.global_.analytics.cross_country_analytics import CrossCountryAnalyticsEngine
        db = AsyncMock()
        mock_rate = MagicMock()
        mock_rate.rate = Decimal("0.272")
        mock_rate.rate_type = "MARKET"
        mock_rate.status = "OK"
        mock_rate.provider = "test"
        
        engine = CrossCountryAnalyticsEngine(db)
        with patch.object(engine._fx_service, "convert", AsyncMock(return_value=MagicMock(
            converted=MagicMock(amount=Decimal("4080000"), currency_code="USD", to_dict=lambda: {"amount": "4080000", "currency_code": "USD"}),
            rate=Decimal("0.272"),
            status="OK"
        ))):
            report = await engine.generate_global_revenue_report("org-1", "USD", [
                {"market_id": "dubai", "market_name": "Dubai", "country_code": "AE", "native_currency": "AED", "amount": Decimal("15000000"), "deals": 5}
            ])
            assert report.reporting_currency == "USD"
            assert len(report.markets) == 1
            assert report.markets[0].country_code == "AE"


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL EVENT BUS TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestGlobalEventBus:

    @pytest.mark.asyncio
    async def test_event_publishing(self):
        from app.modules.global_.events.domain_events import GlobalEventBus, MarketEnabledEvent
        received = []

        async def handler(evt):
            received.append(evt)

        GlobalEventBus.subscribe("MarketEnabled", handler)
        evt = MarketEnabledEvent(market_id="dubai", country_code="AE")
        await GlobalEventBus.publish(evt)

        assert len(received) == 1
        assert received[0].market_id == "dubai"
