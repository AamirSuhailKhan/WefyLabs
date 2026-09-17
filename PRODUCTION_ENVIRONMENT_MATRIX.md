# ==============================================================================
# BEETLELABS PRODUCTION ENVIRONMENT MATRIX
# ==============================================================================
# Security Policy: Real credentials and secret keys are NEVER documented here.
# Columns:
#   - Variable: Name of the environment variable
#   - Target: Frontend / Backend / Worker / Beat
#   - Required: YES (Mandatory) / NO (Optional)
#   - Secret: YES (Confidential) / NO (Public)
#   - Staging: Expected value pattern in staging
#   - Production: Expected value pattern in production
#   - Source: Origin system providing the value
# ==============================================================================

| Variable | Target | Required | Secret | Staging | Production | Source |
|---|---|---|---|---|---|---|
| `ENV` | Backend, Worker, Beat | YES | NO | `staging` | `production` | Platform Env Config |
| `API_URL` | Backend, Worker | YES | NO | `https://api-staging.${DOMAIN}` | `https://api.${DOMAIN}` | Hosting Provider URL |
| `FRONTEND_URL` | Backend, Worker | YES | NO | `https://app-staging.${DOMAIN}` | `https://app.${DOMAIN}` | Frontend Domain |
| `CORS_ORIGINS` | Backend | YES | NO | `https://app-staging.${DOMAIN}` | `https://app.${DOMAIN},https://${DOMAIN}` | DNS / Domain Policy |
| `SECRET_KEY` | Backend, Worker | YES | YES | [64-char crypto token] | [64-char crypto token] | Secrets Manager / Vault |
| `DATABASE_URL` | Backend, Worker | YES | YES | `postgresql+asyncpg://...staging` | `postgresql+asyncpg://...prod?ssl=require` | Supabase Settings |
| `SUPABASE_URL` | Backend, Frontend | YES | NO | `https://[project-stg].supabase.co` | `https://[project-prod].supabase.co` | Supabase Settings |
| `SUPABASE_JWT_SECRET` | Backend | YES | YES | [staging-jwt-secret] | [production-jwt-secret] | Supabase API Settings |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Frontend | NO | NO | [staging-anon-key] | [production-anon-key] | Supabase API Settings |
| `REDIS_URL` | Backend, Worker, Beat | YES | YES | `rediss://...staging.upstash.io` | `rediss://...prod.upstash.io:6379` | Upstash Redis Console |
| `CELERY_BROKER_URL` | Backend, Worker, Beat | NO | YES | Defaults to `REDIS_URL` | Defaults to `REDIS_URL` | Upstash Redis Console |
| `CELERY_RESULT_BACKEND` | Backend, Worker, Beat | NO | YES | Defaults to `REDIS_URL` | Defaults to `REDIS_URL` | Upstash Redis Console |
| `GEMINI_API_KEY` | Backend, Worker | YES | YES | [Google AI API Key] | [Google AI API Key] | Google Cloud AI Studio |
| `GEMINI_MODEL` | Backend, Worker | NO | NO | `gemini-2.5-flash` | `gemini-2.5-flash` | System Default |
| `SMTP_HOST` | Backend, Worker | YES | NO | `smtp-relay.brevo.com` | `smtp-relay.brevo.com` | Brevo SMTP Console |
| `SMTP_PORT` | Backend, Worker | YES | NO | `587` | `587` | Brevo SMTP Console |
| `SMTP_USERNAME` | Backend, Worker | YES | YES | [Brevo SMTP login] | [Brevo SMTP login] | Brevo SMTP Keys |
| `SMTP_PASSWORD` | Backend, Worker | YES | YES | [Brevo SMTP master key] | [Brevo SMTP master key] | Brevo SMTP Keys |
| `SMTP_FROM_EMAIL` | Backend, Worker | YES | NO | `staging@${DOMAIN}` | `notifications@${DOMAIN}` | Verified Brevo Sender |
| `SMTP_FROM_NAME` | Backend, Worker | NO | NO | `BeetleLabs Staging` | `Real Estate CRM` | Platform Branding |
| `SMTP_USE_TLS` | Backend, Worker | NO | NO | `true` | `true` | System Config |
| `GOOGLE_CLIENT_ID` | Backend | YES | NO | `[stg].apps.googleusercontent.com` | `[prod].apps.googleusercontent.com` | Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | Backend | YES | YES | [Google OAuth Secret] | [Google OAuth Secret] | Google Cloud Console |
| `GOOGLE_OAUTH_REDIRECT_URI` | Backend | YES | NO | `https://app-stg.${DOMAIN}/auth/callback` | `https://app.${DOMAIN}/auth/callback` | Google Cloud Console |
| `RAZORPAY_KEY_ID` | Backend | YES | NO | `rzp_test_[staging_key]` | `rzp_test_[prod_test_key]` | Razorpay Dashboard |
| `RAZORPAY_KEY_SECRET` | Backend | YES | YES | [Razorpay Secret] | [Razorpay Secret] | Razorpay Dashboard |
| `RAZORPAY_WEBHOOK_SECRET` | Backend | YES | YES | [Razorpay Webhook Secret] | [Razorpay Webhook Secret] | Razorpay Dashboard |
| `RAZORPAY_ENVIRONMENT` | Backend | YES | NO | `test` | `test` | STRICT SAFETY POLICY |
| `WHATSAPP_ENABLED` | Backend, Worker | YES | NO | `false` | `false` | STRICT SAFETY POLICY |
| `WHATSAPP_ACCESS_TOKEN` | Backend, Worker | NO | YES | [ABSENT / DISABLED] | [ABSENT / DISABLED] | Meta Cloud API |
| `PHONE_NUMBER_ID` | Backend, Worker | NO | NO | [ABSENT / DISABLED] | [ABSENT / DISABLED] | Meta Cloud API |
| `WABA_ID` | Backend, Worker | NO | NO | [ABSENT / DISABLED] | [ABSENT / DISABLED] | Meta Cloud API |
| `WHATSAPP_VERIFY_TOKEN` | Backend | NO | YES | [ABSENT / DISABLED] | [ABSENT / DISABLED] | Meta Cloud API |
| `ALERT_SLACK_WEBHOOK_URL` | Backend, Worker | NO | YES | [Staging Slack Webhook] | [Production Slack Webhook] | Slack App Settings |
| `ALERT_PAGERDUTY_ROUTING_KEY` | Backend, Worker | NO | YES | [Staging Routing Key] | [Production Routing Key] | PagerDuty Integration |
| `NEXT_PUBLIC_API_URL` | Frontend | YES | NO | `https://api-staging.${DOMAIN}/api/v1` | `https://api.${DOMAIN}/api/v1` | Vercel Project Settings |
| `NEXT_PUBLIC_FRONTEND_URL` | Frontend | NO | NO | `https://app-staging.${DOMAIN}` | `https://app.${DOMAIN}` | Vercel Project Settings |
