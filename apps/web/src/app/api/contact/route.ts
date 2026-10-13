import { NextRequest, NextResponse } from 'next/server';

/**
 * Server-Side Website Lead Ingestion Handler
 * ===========================================
 * Provides a secure intermediary between the public website client and
 * the production FastAPI Lead Capture Hub (`/api/v1/public/lead-capture/{token}`).
 *
 * Security Guarantees:
 * 1. Token Isolation: `WEBSITE_LEAD_SOURCE_TOKEN` is kept strictly server-side
 *    and NEVER exposed in client browser bundles or scripts.
 * 2. Honeypot Protection: Silently drops bot spam submissions.
 * 3. Validation: Enforces required contact parameters before dispatch.
 * 4. Error Handling: Normalizes backend responses for safe display to users.
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();

    // 1. Bot Honeypot Check
    if (body._hp_trap || body.website_url_hp) {
      return NextResponse.json({
        success: true,
        message: 'Request received successfully.',
        status: 'accepted',
      });
    }

    // 2. Validate Contact Fields
    const name = typeof body.name === 'string' ? body.name.trim() : '';
    const email = typeof body.email === 'string' ? body.email.trim() : '';
    const phone = typeof body.phone === 'string' ? body.phone.trim() : '';

    if (!name) {
      return NextResponse.json(
        { success: false, error: 'Full Name is required.' },
        { status: 422 }
      );
    }

    if (!email && !phone) {
      return NextResponse.json(
        { success: false, error: 'Please provide at least a phone number or email address.' },
        { status: 422 }
      );
    }

    // 3. Resolve Server-Side Source Token
    const sourceToken = process.env.WEBSITE_LEAD_SOURCE_TOKEN;
    if (!sourceToken) {
      return NextResponse.json(
        {
          success: false,
          error: 'Website lead source token is not configured on the server environment.',
        },
        { status: 503 }
      );
    }

    // 4. Resolve API Base URL
    const rawApiUrl =
      process.env.INTERNAL_API_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      'http://localhost:8000/api/v1';
    const apiBase = rawApiUrl.replace(/\/$/, '');
    const targetUrl = `${apiBase}/public/lead-capture/${encodeURIComponent(sourceToken)}`;

    // 5. Construct Normalized Payload
    const requirementSummary = [
      body.company ? `Agency: ${body.company}` : '',
      body.leadsPerMonth ? `Volume: ${body.leadsPerMonth}` : '',
      body.message ? `Notes: ${body.message}` : '',
    ]
      .filter(Boolean)
      .join(' | ') || 'Website Enterprise Pricing Inquiry';

    const capturePayload = {
      name,
      email: email || null,
      phone: phone || null,
      requirement: requirementSummary,
      message: body.message?.trim() || null,
      property_type: 'commercial',
      transaction_type: 'subscription',
      currency: 'INR',
      custom_fields: {
        company: body.company || null,
        leads_per_month: body.leadsPerMonth || null,
        inquiry_type: 'enterprise_custom_pricing',
      },
      utm_source: body.utm_source || 'website',
      utm_medium: body.utm_medium || 'pricing_modal',
      utm_campaign: body.utm_campaign || 'enterprise_quote',
      marketing_consent: true,
      email_consent: Boolean(email),
      whatsapp_consent: Boolean(phone),
      idempotency_key: body.idempotency_key || undefined,
    };

    // Forward client IP if available
    const clientIp =
      req.headers.get('x-forwarded-for')?.split(',')[0].trim() ||
      req.headers.get('x-real-ip') ||
      '127.0.0.1';

    // 6. Forward Request to Production Backend
    const backendResponse = await fetch(targetUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'X-Forwarded-For': clientIp,
      },
      body: JSON.stringify(capturePayload),
      cache: 'no-store',
    });

    const responseData = await backendResponse.json().catch(() => null);

    if (!backendResponse.ok) {
      const errorMessage =
        (responseData && (responseData.detail || responseData.message)) ||
        `Submission failed with status ${backendResponse.status}.`;

      return NextResponse.json(
        { success: false, error: errorMessage },
        { status: backendResponse.status }
      );
    }

    return NextResponse.json({
      success: true,
      status: 'accepted',
      data: responseData?.data || responseData,
    });
  } catch (error: any) {
    return NextResponse.json(
      {
        success: false,
        error: error?.message || 'An unexpected error occurred processing your submission.',
      },
      { status: 500 }
    );
  }
}
