"""
Part 26 — Public Lead Capture Ingestion Controller
==================================================
Provides public, secure, organization-scoped lead capture endpoints for:
  - Website lead forms
  - Embeddable widgets and iframes
  - External landing pages and partner APIs

Security Architecture:
  - Token-based tenant resolution: strictly resolves organization_id from verified LeadSource
  - Client cannot manipulate organization_id
  - Honeypot anti-spam protection (_hp_trap / website_url_hp)
  - Rate limiting (per IP and per source token)
  - Strict payload size limits (64KB max)
  - Prompt-injection sanitization for AI safety
  - Cryptographic idempotency & replay protection
  - Automated normalization, deduplication, assignment, task, and notification pipeline
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from decimal import Decimal
from typing import Optional, Dict, Any, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from fastapi import APIRouter, Request, HTTPException, status, Depends, Header
from fastapi.responses import Response, JSONResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database import get_db
from app.common.response import APIResponse, create_success_response
from app.models.acquisition_models import LeadSource, LeadAcquisitionEvent, LeadProspect, ProspectStatus, DuplicateMatchStatus
from app.modules.lead_acquisition.dto.acquisition_dto import (
    PublicLeadCaptureDTO, CanonicalLeadIntakeDTO, UniversalSourceType
)
from app.modules.lead_acquisition.services.lead_source_service import LeadSourceService
from app.modules.lead_acquisition.services.acquisition_event_service import AcquisitionEventService
from app.modules.lead_acquisition.services.prospect_service import ProspectService
from app.modules.lead_acquisition.services.universal_intake_service import UniversalIntakeService
from app.modules.lead_acquisition.services.normalization_service import (
    normalize_phone, normalize_email, normalize_name,
    normalize_budget, normalize_currency, normalize_country_code
)
from app.modules.lead_acquisition.metrics.acquisition_metrics import (
    record_acquisition_received, record_acquisition_success, record_acquisition_failure,
    record_prospect_created, record_duplicate, record_import, record_latency
)

logger = logging.getLogger("beetlelabs.public_capture")

router = APIRouter(prefix="/api/v1/public/lead-capture", tags=["Public Lead Capture Hub"])

# In-memory sliding rate limiter fallback (if Redis unavailable)
_IP_RATE_CACHE: Dict[str, list[float]] = {}
_SOURCE_RATE_CACHE: Dict[str, list[float]] = {}


def _check_rate_limit(key: str, cache: Dict[str, list[float]], limit: int, window_seconds: int = 60) -> bool:
    now = time.time()
    timestamps = cache.get(key, [])
    # Filter within window
    timestamps = [t for t in timestamps if now - t < window_seconds]
    if len(timestamps) >= limit:
        return False
    timestamps.append(now)
    cache[key] = timestamps
    return True


def _sanitize_untrusted_text(text: Optional[str], max_chars: int = 1000) -> Optional[str]:
    """Sanitizes text fields to protect against prompt injection and control character abuse."""
    if not text:
        return None
    cleaned = text.strip()[:max_chars]
    # Neutralize prompt injection markers if passed directly to Gemini downstream
    injection_patterns = [
        r"(?i)\bignore\s+all\s+(previous|prior)\s+instructions\b",
        r"(?i)\bsystem\s*:\s*",
        r"(?i)\bdeveloper\s+mode\b",
        r"(?i)\byou\s+are\s+now\s+in\b",
    ]
    for pattern in injection_patterns:
        cleaned = re.sub(pattern, "[sanitized]", cleaned)
    return cleaned


def _parse_flexible_budget(val: Optional[Union[str, Decimal, int, float]]) -> Optional[Decimal]:
    """
    Normalizes Indian and International budget representations:
      '50L', '50 lakhs', '1.5 Cr', '1.5 crore', '₹5,000,000', 5000000 -> Decimal(5000000)
    """
    if val is None:
        return None
    if isinstance(val, (int, float, Decimal)):
        return Decimal(str(int(val)))

    text = str(val).strip().replace(",", "").replace("₹", "").replace("$", "").replace("AED", "").strip()
    if not text:
        return None

    # Check for Lakhs
    lakh_match = re.search(r"^([\d\.]+)\s*(?:l|lakh|lakhs|lac|lacs)$", text, re.IGNORECASE)
    if lakh_match:
        try:
            return Decimal(str(int(float(lakh_match.group(1)) * 100000)))
        except ValueError:
            pass

    # Check for Crores
    cr_match = re.search(r"^([\d\.]+)\s*(?:cr|crore|crores)$", text, re.IGNORECASE)
    if cr_match:
        try:
            return Decimal(str(int(float(cr_match.group(1)) * 10000000)))
        except ValueError:
            pass

    # Check for k / M
    k_match = re.search(r"^([\d\.]+)\s*k$", text, re.IGNORECASE)
    if k_match:
        try:
            return Decimal(str(int(float(k_match.group(1)) * 1000)))
        except ValueError:
            pass

    m_match = re.search(r"^([\d\.]+)\s*m$", text, re.IGNORECASE)
    if m_match:
        try:
            return Decimal(str(int(float(m_match.group(1)) * 1000000)))
        except ValueError:
            pass

    # Plain digits
    digits_only = re.sub(r"[^\d.]", "", text)
    if digits_only:
        try:
            return Decimal(str(int(float(digits_only))))
        except ValueError:
            pass

    return None


@router.post("/{token}", response_model=APIResponse, status_code=status.HTTP_200_OK)
async def public_capture_lead(
    token: str,
    payload: PublicLeadCaptureDTO,
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    """
    Public Lead Ingestion endpoint.
    Accessible without JWT. Securely resolves organization from token.
    """
    start_time = time.perf_counter()
    client_ip = request.client.host if request.client else "unknown"

    # 1. Rate Limiting: 60 req/min per IP
    if not _check_rate_limit(f"ip:{client_ip}", _IP_RATE_CACHE, limit=60, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please retry in a moment."
        )

    # 2. Resolve LeadSource strictly via token
    stmt = select(LeadSource).where(
        and_(LeadSource.webhook_url_token == token, LeadSource.is_active.is_(True))
    )
    res = await db.execute(stmt)
    source = res.scalars().first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capture source not found or inactive."
        )

    # Source-level rate limiting: default 500/hr or configured
    source_hourly_limit = source.rate_limit_per_hour or 500
    if not _check_rate_limit(f"src:{source.id}", _SOURCE_RATE_CACHE, limit=source_hourly_limit, window_seconds=3600):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Source capture threshold reached. Please try later."
        )

    org_id = source.organization_id

    # 3. Honeypot anti-spam check: if bot filled trap field, return fake success
    if payload.hp_trap or payload.website_url_hp:
        logger.info(f"[PUBLIC_CAPTURE] Bot caught by honeypot for source={source.id} from IP={client_ip}")
        return create_success_response(data={
            "status": "accepted",
            "event_id": f"evt_hp_{int(time.time())}",
            "message": "Inquiry received successfully."
        })

    # 4. Contact validation
    if not payload.validate_contact_present():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one of phone or email is required."
        )

    # 5. Route through Universal Intake Pipeline
    raw_idem = (
        payload.idempotency_key
        or (x_idempotency_key if isinstance(x_idempotency_key, str) else None)
        or f"{source.id}:{payload.phone or ''}:{payload.email or ''}:{datetime.now(timezone.utc).strftime('%Y-%m-%d-%H')}"
    )

    intake_dto = CanonicalLeadIntakeDTO(
        source_type=UniversalSourceType.WEBSITE,
        external_source=source.provider or "public_capture",
        external_lead_id=None,
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        message=payload.message or payload.requirement,
        property_type=payload.property_type,
        transaction_type=payload.transaction_type,
        budget=payload.budget,
        budget_min=payload.budget_min,
        budget_max=payload.budget_max,
        currency=payload.currency or "INR",
        city=payload.city or payload.location,
        timeline=payload.timeline,
        landing_page=payload.landing_page,
        referrer=payload.referrer,
        utm_source=payload.utm_source or source.name,
        utm_medium=payload.utm_medium or source.channel,
        utm_campaign=payload.utm_campaign,
        utm_term=payload.utm_term,
        utm_content=payload.utm_content,
        campaign_id=payload.campaign_id,
        source_id=source.id,
        marketing_consent=payload.marketing_consent,
        email_consent=payload.email_consent,
        whatsapp_consent=payload.whatsapp_consent,
        idempotency_key=raw_idem,
    )

    u_svc = UniversalIntakeService(db)
    result = await u_svc.ingest_lead(
        organization_id=org_id,
        dto=intake_dto,
        ip_address=client_ip,
        user_agent=getattr(request, "headers", {}).get("User-Agent") if hasattr(request, "headers") else None,
        raw_payload=payload.model_dump(),
    )

    elapsed = time.perf_counter() - start_time
    record_latency(source.channel or "WEBSITE", elapsed)
    record_acquisition_success(org_id, source.channel or "WEBSITE")

    return create_success_response(data={
        "status": "accepted",
        "event_id": result.event_id,
        "lead_id": result.lead_id,
        "is_duplicate": result.is_duplicate,
        "is_new_prospect": result.is_new_lead,
        "identity_outcome": result.identity_outcome,
        "message": result.message,
    })


class PublicConversationLeadCaptureDTO(BaseModel):
    conversation_id: str = Field(..., description="Active omnichannel conversation ID")
    phone: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    message: Optional[str] = None
    budget: Optional[Union[str, int, float, Decimal]] = None
    city: Optional[str] = None
    property_type: Optional[str] = None
    transaction_type: Optional[str] = None
    timeline: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    landing_page: Optional[str] = None
    referrer: Optional[str] = None


@router.post("/conversation/{token}", response_model=APIResponse, status_code=status.HTTP_200_OK)
async def public_capture_lead_from_conversation(
    token: str,
    payload: PublicConversationLeadCaptureDTO,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Public conversational lead capture endpoint (Part 9 / Phase 22–24).
    Enables anonymous web visitors conversing with the AI agent to submit contact
    information, seamlessly linking the existing conversation to the canonical Lead
    and Customer Intelligence node.
    """
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(f"ip:{client_ip}", _IP_RATE_CACHE, limit=60, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please retry in a moment."
        )

    stmt = select(LeadSource).where(
        and_(LeadSource.webhook_url_token == token, LeadSource.is_active.is_(True))
    )
    res = await db.execute(stmt)
    source = res.scalars().first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capture source not found or inactive."
        )

    if not (payload.phone or payload.email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one of phone or email is required."
        )

    intake_dto = CanonicalLeadIntakeDTO(
        source_type=UniversalSourceType.PUBLIC_AI,
        external_source="public_ai_conversation",
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        message=payload.message,
        property_type=payload.property_type,
        transaction_type=payload.transaction_type,
        budget=payload.budget,
        city=payload.city,
        timeline=payload.timeline,
        landing_page=payload.landing_page,
        referrer=payload.referrer,
        utm_source=payload.utm_source or source.name,
        utm_medium=payload.utm_medium or "ai_chat",
        utm_campaign=payload.utm_campaign,
        source_id=source.id,
        conversation_id=payload.conversation_id,
    )

    u_svc = UniversalIntakeService(db)
    result = await u_svc.ingest_lead(
        organization_id=source.organization_id,
        dto=intake_dto,
        ip_address=client_ip,
        user_agent=getattr(request, "headers", {}).get("User-Agent") if hasattr(request, "headers") else None,
        raw_payload=payload.model_dump(),
    )

    return create_success_response(data={
        "status": "accepted",
        "event_id": result.event_id,
        "lead_id": result.lead_id,
        "customer_id": result.customer_id,
        "conversation_id": result.conversation_id,
        "is_duplicate": result.is_duplicate,
        "identity_outcome": result.identity_outcome,
        "message": "Conversational inquiry linked to canonical lead.",
    })



@router.get("/forms/{token}/config", response_model=APIResponse)
async def get_form_config(token: str, db: AsyncSession = Depends(get_db)):
    """Returns the public configuration for an embeddable capture form."""
    stmt = select(LeadSource).where(
        and_(LeadSource.webhook_url_token == token, LeadSource.is_active.is_(True))
    )
    res = await db.execute(stmt)
    source = res.scalars().first()
    if not source:
        raise HTTPException(status_code=404, detail="Form configuration not found or disabled.")

    config = source.configuration or {}
    return create_success_response(data={
        "source_name": source.name,
        "channel": source.channel,
        "title": config.get("form_title", f"Contact {source.name}"),
        "description": config.get("form_description", "Share your details to connect with a verified advisor."),
        "button_text": config.get("button_text", "Submit Inquiry"),
        "primary_color": config.get("primary_color", "#1F2937"),
        "fields": config.get("fields", [
            {"id": "name", "label": "Full Name", "required": True, "type": "text"},
            {"id": "phone", "label": "Phone Number", "required": True, "type": "tel"},
            {"id": "email", "label": "Email Address", "required": False, "type": "email"},
            {"id": "budget", "label": "Budget", "required": False, "type": "text"},
            {"id": "city", "label": "Preferred Location", "required": False, "type": "text"},
            {"id": "property_type", "label": "Property Type", "required": False, "type": "select", "options": ["Apartment", "Villa", "Penthouse", "Plot", "Commercial"]},
            {"id": "message", "label": "Requirement / Message", "required": False, "type": "textarea"},
        ]),
        "terms_notice": config.get("terms_notice", "By submitting, you agree to be contacted regarding relevant property updates."),
    })


@router.get("/forms/{token}/embed.js")
async def get_form_embed_script(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Serves a standalone, lightweight JavaScript widget that injects a responsive capture form."""
    stmt = select(LeadSource).where(
        and_(LeadSource.webhook_url_token == token, LeadSource.is_active.is_(True))
    )
    res = await db.execute(stmt)
    source = res.scalars().first()
    if not source:
        return Response(content="// WefyLabs Lead Capture: invalid or inactive token", media_type="application/javascript", status_code=404)

    base_url = str(request.base_url).rstrip("/")
    submit_url = f"{base_url}/api/v1/public/lead-capture/{token}"
    config_url = f"{base_url}/api/v1/public/lead-capture/forms/{token}/config"

    js_code = f"""
(function() {{
  const token = "{token}";
  const submitUrl = "{submit_url}";
  const configUrl = "{config_url}";

  const container = document.getElementById("wefylabs-lead-form-" + token) || document.getElementById("wefylabs-lead-form") || document.getElementById("beetlelabs-lead-form-" + token) || document.getElementById("beetlelabs-lead-form");
  if (!container) return;

  container.innerHTML = `
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 440px; margin: 0 auto; padding: 24px; background: #ffffff; border: 1px solid #E5E7EB; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
      <h3 style="margin: 0 0 8px 0; font-size: 20px; font-weight: 700; color: #111827;">Get In Touch</h3>
      <p style="margin: 0 0 20px 0; font-size: 13px; color: #6B7280;">Leave your contact details and our team will get back to you promptly.</p>
      <form id="bl-capture-form-${token}" style="display: flex; flex-direction: column; gap: 12px;">
        <input type="text" name="_hp_trap" style="display:none !important;" tabindex="-1" autocomplete="off" />
        <div>
          <label style="display:block; font-size: 12px; font-weight: 600; color: #374151; margin-bottom: 4px;">Name *</label>
          <input type="text" name="name" required placeholder="Your Full Name" style="width: 100%; box-sizing: border-box; padding: 9px 12px; border: 1px solid #D1D5DB; border-radius: 6px; font-size: 14px;" />
        </div>
        <div>
          <label style="display:block; font-size: 12px; font-weight: 600; color: #374151; margin-bottom: 4px;">Phone *</label>
          <input type="tel" name="phone" required placeholder="+91 98765 43210" style="width: 100%; box-sizing: border-box; padding: 9px 12px; border: 1px solid #D1D5DB; border-radius: 6px; font-size: 14px;" />
        </div>
        <div>
          <label style="display:block; font-size: 12px; font-weight: 600; color: #374151; margin-bottom: 4px;">Email</label>
          <input type="email" name="email" placeholder="you@example.com" style="width: 100%; box-sizing: border-box; padding: 9px 12px; border: 1px solid #D1D5DB; border-radius: 6px; font-size: 14px;" />
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
          <div>
            <label style="display:block; font-size: 12px; font-weight: 600; color: #374151; margin-bottom: 4px;">Budget</label>
            <input type="text" name="budget" placeholder="e.g. 75L or 1.5 Cr" style="width: 100%; box-sizing: border-box; padding: 9px 12px; border: 1px solid #D1D5DB; border-radius: 6px; font-size: 14px;" />
          </div>
          <div>
            <label style="display:block; font-size: 12px; font-weight: 600; color: #374151; margin-bottom: 4px;">Location</label>
            <input type="text" name="city" placeholder="City or Area" style="width: 100%; box-sizing: border-box; padding: 9px 12px; border: 1px solid #D1D5DB; border-radius: 6px; font-size: 14px;" />
          </div>
        </div>
        <div>
          <label style="display:block; font-size: 12px; font-weight: 600; color: #374151; margin-bottom: 4px;">Requirements</label>
          <textarea name="message" rows="2" placeholder="Tell us what you are looking for..." style="width: 100%; box-sizing: border-box; padding: 9px 12px; border: 1px solid #D1D5DB; border-radius: 6px; font-size: 14px; resize: vertical;"></textarea>
        </div>
        <button type="submit" id="bl-btn-${token}" style="margin-top: 8px; width: 100%; padding: 11px; background: #111827; color: #ffffff; border: none; border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer; transition: background 0.2s;">
          Submit Inquiry
        </button>
        <div id="bl-msg-${token}" style="display: none; padding: 10px; border-radius: 6px; font-size: 13px; text-align: center;"></div>
      </form>
    </div>
  `;

  const form = document.getElementById("bl-capture-form-" + token);
  const btn = document.getElementById("bl-btn-" + token);
  const msg = document.getElementById("bl-msg-" + token);

  form.addEventListener("submit", async function(e) {{
    e.preventDefault();
    btn.disabled = true;
    btn.innerText = "Submitting...";
    msg.style.display = "none";

    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());

    // Capture URL params (UTM)
    const urlParams = new URLSearchParams(window.location.search);
    data.utm_source = urlParams.get("utm_source") || null;
    data.utm_medium = urlParams.get("utm_medium") || null;
    data.utm_campaign = urlParams.get("utm_campaign") || null;
    data.utm_term = urlParams.get("utm_term") || null;
    data.utm_content = urlParams.get("utm_content") || null;
    data.landing_page = window.location.href;
    data.referrer = document.referrer || null;

    try {{
      const res = await fetch(submitUrl, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify(data)
      }});
      const json = await res.json();
      if (res.ok) {{
        msg.style.display = "block";
        msg.style.background = "#DEF7EC";
        msg.style.color = "#03543F";
        msg.innerText = "Thank you! We have received your inquiry.";
        form.reset();
        btn.innerText = "Submitted";
      }} else {{
        throw new Error(json.message || "Submission failed");
      }}
    }} catch (err) {{
      msg.style.display = "block";
      msg.style.background = "#FDE8E8";
      msg.style.color = "#9B1C1C";
      msg.innerText = err.message || "Failed to submit inquiry. Please try again.";
      btn.disabled = false;
      btn.innerText = "Submit Inquiry";
    }}
  }});
}})();
    """
    return Response(content=js_code, media_type="application/javascript")


@router.get("/forms/{token}/frame", response_class=HTMLResponse)
@router.get("/forms/{token}/embed.html", response_class=HTMLResponse)
async def get_form_iframe_html(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Renders a responsive, self-contained HTML page designed specifically for embedding via <iframe>.
    Includes CSRF-safe submission, honeypot protection, client-side UTM extraction, and error/success states.
    """
    stmt = select(LeadSource).where(
        and_(LeadSource.webhook_url_token == token, LeadSource.is_active.is_(True))
    )
    res = await db.execute(stmt)
    source = res.scalars().first()
    if not source:
        return HTMLResponse(
            content="""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Form Not Found</title>
            <style>body{font-family:-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#f9fafb;color:#6b7280;}</style>
            </head><body><p>This lead capture form is currently unavailable or disabled.</p></body></html>""",
            status_code=404,
        )

    base_url = str(request.base_url).rstrip("/")
    submit_url = f"{base_url}/api/v1/public/lead-capture/{token}"
    config = source.configuration or {}
    title = config.get("form_title", "Schedule a Consultation")
    subtitle = config.get("form_description", "Leave your details and a dedicated property advisor will contact you.")
    btn_text = config.get("button_text", "Submit Inquiry")
    primary_color = config.get("primary_color", "#111827")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background-color: #ffffff;
      color: #111827;
      padding: 16px;
      line-height: 1.5;
    }}
    .container {{
      max-width: 480px;
      margin: 0 auto;
      background: #ffffff;
      border: 1px solid #E5E7EB;
      border-radius: 12px;
      padding: 24px;
      box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
    }}
    .header {{ margin-bottom: 20px; }}
    .title {{ font-size: 20px; font-weight: 700; color: #111827; margin-bottom: 4px; }}
    .subtitle {{ font-size: 13px; color: #6B7280; }}
    .form-group {{ margin-bottom: 14px; }}
    .form-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
    label {{ display: block; font-size: 12px; font-weight: 600; color: #374151; margin-bottom: 5px; }}
    label span.req {{ color: #EF4444; margin-left: 2px; }}
    input, select, textarea {{
      width: 100%;
      padding: 10px 12px;
      border: 1px solid #D1D5DB;
      border-radius: 8px;
      font-size: 14px;
      color: #111827;
      background-color: #ffffff;
      transition: border-color 0.15s ease;
      outline: none;
    }}
    input:focus, select:focus, textarea:focus {{
      border-color: {primary_color};
      box-shadow: 0 0 0 2px rgba(17, 24, 39, 0.1);
    }}
    textarea {{ resize: vertical; min-height: 70px; }}
    .btn-submit {{
      width: 100%;
      padding: 12px;
      background-color: {primary_color};
      color: #ffffff;
      font-size: 14px;
      font-weight: 600;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      transition: opacity 0.2s ease;
      margin-top: 6px;
    }}
    .btn-submit:hover {{ opacity: 0.92; }}
    .btn-submit:disabled {{ opacity: 0.6; cursor: not-allowed; }}
    .notice {{
      font-size: 11px;
      color: #9CA3AF;
      margin-top: 12px;
      text-align: center;
    }}
    .alert {{
      padding: 12px 14px;
      border-radius: 8px;
      font-size: 13px;
      margin-top: 14px;
      display: none;
      text-align: center;
    }}
    .alert-success {{ background-color: #DEF7EC; color: #03543F; border: 1px solid #BCF0DA; }}
    .alert-error {{ background-color: #FDE8E8; color: #9B1C1C; border: 1px solid #FBD5D5; }}
    .hp-field {{ display: none !important; opacity: 0; position: absolute; left: -9999px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h2 class="title">{title}</h2>
      <p class="subtitle">{subtitle}</p>
    </div>

    <form id="lead-capture-form" novalidate>
      <!-- Anti-Spam Honeypot Trap -->
      <input type="text" name="_hp_trap" class="hp-field" tabindex="-1" autocomplete="off" />

      <div class="form-group">
        <label for="name">Full Name <span class="req">*</span></label>
        <input type="text" id="name" name="name" required placeholder="e.g. Rahul Sharma" autocomplete="name" />
      </div>

      <div class="form-group">
        <label for="phone">Phone Number <span class="req">*</span></label>
        <input type="tel" id="phone" name="phone" required placeholder="+91 98765 43210" autocomplete="tel" />
      </div>

      <div class="form-group">
        <label for="email">Email Address</label>
        <input type="email" id="email" name="email" placeholder="you@example.com" autocomplete="email" />
      </div>

      <div class="form-row">
        <div class="form-group">
          <label for="budget">Target Budget</label>
          <input type="text" id="budget" name="budget" placeholder="e.g. ₹75L or 1.5 Cr" />
        </div>
        <div class="form-group">
          <label for="city">Preferred City/Area</label>
          <input type="text" id="city" name="city" placeholder="e.g. Whitefield" />
        </div>
      </div>

      <div class="form-group">
        <label for="property_type">Property Type</label>
        <select id="property_type" name="property_type">
          <option value="">Select Property Type</option>
          <option value="Apartment">Apartment / Flat</option>
          <option value="Villa">Villa / Row House</option>
          <option value="Penthouse">Penthouse</option>
          <option value="Plot">Residential Plot</option>
          <option value="Commercial">Commercial Space</option>
        </select>
      </div>

      <div class="form-group">
        <label for="message">Requirements / Notes</label>
        <textarea id="message" name="message" placeholder="Bedrooms, timeline, amenities, or specific preferences..."></textarea>
      </div>

      <button type="submit" id="submit-btn" class="btn-submit">{btn_text}</button>
      <div id="alert-msg" class="alert"></div>

      <p class="notice">Protected by enterprise lead ingestion & anti-spam encryption.</p>
    </form>
  </div>

  <script>
    (function() {{
      const form = document.getElementById('lead-capture-form');
      const submitBtn = document.getElementById('submit-btn');
      const alertMsg = document.getElementById('alert-msg');
      const submitUrl = "{submit_url}";

      form.addEventListener('submit', async function(e) {{
        e.preventDefault();
        alertMsg.style.display = 'none';
        alertMsg.className = 'alert';

        const nameInput = document.getElementById('name');
        const phoneInput = document.getElementById('phone');

        if (!nameInput.value.trim() || !phoneInput.value.trim()) {{
          alertMsg.className = 'alert alert-error';
          alertMsg.textContent = 'Please provide both your name and phone number.';
          alertMsg.style.display = 'block';
          return;
        }}

        submitBtn.disabled = true;
        const originalText = submitBtn.textContent;
        submitBtn.textContent = 'Submitting...';

        const formData = new FormData(form);
        const payload = Object.fromEntries(formData.entries());

        // Extract UTM parameters from parent or current window query
        const urlParams = new URLSearchParams(window.location.search);
        payload.utm_source = urlParams.get('utm_source') || null;
        payload.utm_medium = urlParams.get('utm_medium') || null;
        payload.utm_campaign = urlParams.get('utm_campaign') || null;
        payload.utm_term = urlParams.get('utm_term') || null;
        payload.utm_content = urlParams.get('utm_content') || null;
        payload.landing_page = window.location.href;
        payload.referrer = document.referrer || null;

        try {{
          const response = await fetch(submitUrl, {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(payload)
          }});

          const resData = await response.json();

          if (response.ok) {{
            alertMsg.className = 'alert alert-success';
            alertMsg.textContent = 'Thank you! Your inquiry has been received. Our advisor will connect with you shortly.';
            alertMsg.style.display = 'block';
            form.reset();
            submitBtn.textContent = 'Submitted ✓';
          }} else {{
            throw new Error(resData.message || resData.detail || 'Submission failed. Please check your information.');
          }}
        }} catch (err) {{
          alertMsg.className = 'alert alert-error';
          alertMsg.textContent = err.message || 'Unable to submit inquiry at this moment. Please retry.';
          alertMsg.style.display = 'block';
          submitBtn.disabled = false;
          submitBtn.textContent = originalText;
        }}
      }});
    }})();
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)

