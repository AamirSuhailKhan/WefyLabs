from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.common.response import APIResponse, create_success_response
from app.modules.health.service.health_service import DeepHealthService

router = APIRouter(prefix="/v1/health-diag", tags=["Enterprise Observability & Health"])


@router.get("/liveness", response_model=APIResponse)
async def liveness_probe(db: AsyncSession = Depends(get_db)):
    svc = DeepHealthService(db)
    res = await svc.check_liveness()
    return create_success_response(data=res)


@router.get("/readiness", response_model=APIResponse)
async def readiness_probe(db: AsyncSession = Depends(get_db)):
    svc = DeepHealthService(db)
    res = await svc.check_readiness()
    return create_success_response(data=res)


@router.get("/database", response_model=APIResponse)
async def database_health(db: AsyncSession = Depends(get_db)):
    svc = DeepHealthService(db)
    res = await svc.check_database()
    return create_success_response(data=res)


@router.get("/redis", response_model=APIResponse)
async def redis_health(db: AsyncSession = Depends(get_db)):
    svc = DeepHealthService(db)
    res = await svc.check_redis()
    return create_success_response(data=res)


@router.get("/queues", response_model=APIResponse)
async def queues_health(db: AsyncSession = Depends(get_db)):
    svc = DeepHealthService(db)
    res = await svc.check_queues()
    return create_success_response(data=res)


@router.get("/search", response_model=APIResponse)
async def search_health(db: AsyncSession = Depends(get_db)):
    svc = DeepHealthService(db)
    res = await svc.check_search()
    return create_success_response(data=res)


@router.get("/ai", response_model=APIResponse)
async def ai_health(db: AsyncSession = Depends(get_db)):
    svc = DeepHealthService(db)
    res = await svc.check_ai()
    return create_success_response(data=res)


@router.get("/integrations", response_model=APIResponse)
async def integrations_health(db: AsyncSession = Depends(get_db)):
    svc = DeepHealthService(db)
    res = await svc.check_integrations()
    return create_success_response(data=res)


@router.get("/deep", response_model=APIResponse)
async def full_diagnostic(db: AsyncSession = Depends(get_db)):
    svc = DeepHealthService(db)
    res = await svc.full_diagnostic()
    return create_success_response(data=res)


@router.get("/capabilities")
async def system_capabilities():
    """
    Public endpoint — no authentication required.

    Returns a map of feature availability flags based on the actual
    runtime configuration. The frontend uses this to conditionally
    show or hide features (WhatsApp, Billing) that require external
    credentials that may not yet be configured.

    This endpoint NEVER reveals secret values — only boolean availability.
    """
    from app.config import settings

    _PLACEHOLDER_WA = {
        "wa_access_token_placeholder",
        "wa-placeholder",
        "placeholder",
        "",
    }
    _PLACEHOLDER_RZP = {
        "rzp_test_placeholder",
        "rzp_test_dummy",
        "",
        "placeholder",
    }

    wa_token = (settings.WHATSAPP_ACCESS_TOKEN or "").strip()
    wa_phone = (settings.PHONE_NUMBER_ID or "").strip()
    whatsapp_configured = (
        bool(wa_token)
        and wa_token not in _PLACEHOLDER_WA
        and "placeholder" not in wa_token.lower()
        and bool(wa_phone)
        and wa_phone not in _PLACEHOLDER_WA
    )

    rzp_key = (settings.RAZORPAY_KEY_ID or "").strip()
    rzp_secret = (settings.RAZORPAY_KEY_SECRET or "").strip()
    billing_configured = (
        bool(rzp_key)
        and rzp_key not in _PLACEHOLDER_RZP
        and not rzp_key.startswith("rzp_test_")
        and bool(rzp_secret)
        and rzp_secret not in _PLACEHOLDER_RZP
    )

    gemini_key = (settings.GEMINI_API_KEY or "").strip()
    ai_configured = (
        bool(gemini_key)
        and not gemini_key.startswith("placeholder")
        and not gemini_key.startswith("AIzaSy_placeholder")
    )

    google_oauth = (
        bool(settings.GOOGLE_CLIENT_ID)
        and (settings.GOOGLE_CLIENT_ID or "").endswith(".apps.googleusercontent.com")
        and bool(settings.GOOGLE_CLIENT_SECRET)
    )

    return {
        "whatsapp": {
            "enabled": whatsapp_configured,
            "reason": "configured" if whatsapp_configured else "credentials_not_configured",
        },
        "billing": {
            "enabled": billing_configured,
            "mode": "live" if billing_configured else (
                "test" if rzp_key.startswith("rzp_test_") else "disabled"
            ),
            "reason": "live_keys_configured" if billing_configured else "test_or_placeholder_keys",
        },
        "ai": {
            "enabled": ai_configured,
            "provider": "gemini",
        },
        "google_oauth": {
            "enabled": google_oauth,
        },
    }

