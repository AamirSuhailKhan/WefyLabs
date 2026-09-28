"""
OCR Provider Architecture & Reliability Test Suite
==================================================
Tests:
- Abstract interface compliance
- Mock OCR provider (deterministic test output)
- Tesseract OCR provider (local open-source OCR)
- Low confidence score detection & UNVERIFIED field flagging
- OCR Factory resolution (Tesseract, Mock)
- Fail-fast production rejection of mock OCR
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.modules.knowledge.providers.ocr_provider import (
    OCRProvider, MockOCRProvider, TesseractOCRProvider,
    get_ocr_provider, OCRResult, OCRPage
)
from app.common.config.validated_settings import EnterpriseSettings


class TestOCRProviderInterfaceAndMock:
    """Tests basic OCR operations and confidence scoring."""

    @pytest.mark.asyncio
    async def test_mock_ocr_extraction_success(self):
        provider = MockOCRProvider(fixed_text="Floor Plan 3BHK 2400 sqft", confidence=0.98)
        result = await provider.extract(b"dummy_pdf_bytes", mime_type="application/pdf")

        assert isinstance(result, OCRResult)
        assert result.total_pages == 1
        assert result.full_text == "Floor Plan 3BHK 2400 sqft"
        assert result.average_confidence == 0.98
        assert OCRProvider.is_low_confidence(result.average_confidence, threshold=0.7) is False

    def test_low_confidence_detection(self):
        assert OCRProvider.is_low_confidence(0.45, threshold=0.7) is True
        assert OCRProvider.is_low_confidence(0.69, threshold=0.7) is True
        assert OCRProvider.is_low_confidence(0.70, threshold=0.7) is False
        assert OCRProvider.is_low_confidence(0.92, threshold=0.7) is False

    @pytest.mark.asyncio
    async def test_low_confidence_flagged_for_blurry_document(self):
        blurry_provider = MockOCRProvider(fixed_text="Unclear text", confidence=0.40)
        result = await blurry_provider.extract(b"blurry_image_bytes", mime_type="image/jpeg")

        assert result.average_confidence == 0.40
        assert OCRProvider.is_low_confidence(result.average_confidence, threshold=0.7) is True


class TestOCRFactoryResolution:
    """Tests factory resolution for all supported production and test providers."""

    def test_resolve_mock_provider(self):
        prov = get_ocr_provider("mock", {"fixed_text": "Custom", "confidence": 0.90})
        assert isinstance(prov, MockOCRProvider)
        assert prov.provider_name == "mock"

    def test_resolve_tesseract_provider(self):
        prov = get_ocr_provider("tesseract")
        assert isinstance(prov, TesseractOCRProvider)
        assert prov.provider_name == "tesseract"

    def test_resolve_local_provider(self):
        prov = get_ocr_provider("local")
        assert isinstance(prov, TesseractOCRProvider)
        assert prov.provider_name == "tesseract"

    def test_unknown_provider_falls_back_to_tesseract(self):
        prov = get_ocr_provider("unknown_legacy_engine")
        assert isinstance(prov, TesseractOCRProvider)


class TestProductionOCRPolicy:
    """Tests that production mode rejects MockOCRProvider unless explicitly bypassed."""

    def test_production_rejects_mock_ocr_provider(self):
        with pytest.raises(ValueError) as exc:
            EnterpriseSettings(
                ENV="production",
                DATABASE_URL="postgresql+asyncpg://prod_user:prod_pass@db.internal:5432/leadscore_prod",
                SECRET_KEY="c" * 32,
                SUPABASE_JWT_SECRET="s" * 32,
                GEMINI_API_KEY="valid_gemini_key_prod",
                WHATSAPP_VERIFY_TOKEN="w" * 32,
                RAZORPAY_KEY_ID="rzp_live_real_key_123456",
                RAZORPAY_KEY_SECRET="sec_live_key_" + "k" * 20,
                RAZORPAY_WEBHOOK_SECRET="whsec_" + "w" * 26,
                GOOGLE_CLIENT_ID="123456789-abcdef.apps.googleusercontent.com",
                GOOGLE_CLIENT_SECRET="google_prod_secret_123456789",
                KNOWLEDGE_OCR_PROVIDER="mock",  # Mock in production rejected
                EMERGENCY_ALLOW_MOCK_OCR=False,
            )
        assert "KNOWLEDGE_OCR_PROVIDER" in str(exc.value)

    def test_production_accepts_tesseract(self):
        s = EnterpriseSettings(
            ENV="production",
            DATABASE_URL="postgresql+asyncpg://prod_user:prod_pass@db.internal:5432/leadscore_prod",
            SECRET_KEY="c" * 32,
            SUPABASE_JWT_SECRET="s" * 32,
            GEMINI_API_KEY="valid_gemini_key_prod",
            WHATSAPP_VERIFY_TOKEN="w" * 32,
            RAZORPAY_KEY_ID="rzp_live_real_key_123456",
            RAZORPAY_KEY_SECRET="sec_live_key_" + "k" * 20,
            RAZORPAY_WEBHOOK_SECRET="whsec_" + "w" * 26,
            GOOGLE_CLIENT_ID="123456789-abcdef.apps.googleusercontent.com",
            GOOGLE_CLIENT_SECRET="google_prod_secret_123456789",
            KNOWLEDGE_OCR_PROVIDER="tesseract",
            STORAGE_BACKEND="s3",
        )
        assert s.KNOWLEDGE_OCR_PROVIDER == "tesseract"

    def test_production_accepts_local(self):
        s = EnterpriseSettings(
            ENV="production",
            DATABASE_URL="postgresql+asyncpg://prod_user:prod_pass@db.internal:5432/leadscore_prod",
            SECRET_KEY="c" * 32,
            SUPABASE_JWT_SECRET="s" * 32,
            GEMINI_API_KEY="valid_gemini_key_prod",
            WHATSAPP_VERIFY_TOKEN="w" * 32,
            RAZORPAY_KEY_ID="rzp_live_real_key_123456",
            RAZORPAY_KEY_SECRET="sec_live_key_" + "k" * 20,
            RAZORPAY_WEBHOOK_SECRET="whsec_" + "w" * 26,
            GOOGLE_CLIENT_ID="123456789-abcdef.apps.googleusercontent.com",
            GOOGLE_CLIENT_SECRET="google_prod_secret_123456789",
            KNOWLEDGE_OCR_PROVIDER="local",
            STORAGE_BACKEND="s3",
        )
        assert s.KNOWLEDGE_OCR_PROVIDER == "local"
