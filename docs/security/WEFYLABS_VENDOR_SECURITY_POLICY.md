# WEFYLABS — THIRD-PARTY VENDOR SECURITY & INTEGRATION POLICY

**Document Reference:** SEC-POL-006  
**Classification:** INTERNAL  
**Authority:** DevSecOps Lead + Cloud Security Engineer  
**Last Updated:** 2026-09-27 (Master Build 11)  
**Status:** ACTIVE — PRODUCTION TRUTH  

---

## 1. VENDOR RISK INVENTORY & DATA MINIMIZATION

All third-party services integrated into WefyLabs are evaluated for data minimization, security posture, and failover capabilities:

| Vendor / Provider | Service Category | Data Accessed | Security Controls | Fallback / Redundancy |
| :--- | :--- | :--- | :--- | :--- |
| **Google Vertex / Gemini** | AI Inference & RAG | Redacted conversation context & property listings | TLS 1.3, zero training retention, approved model allowlist | In-memory cached responses, rule-based fallback |
| **Meta / WhatsApp Cloud** | Omnichannel Messaging | Customer phone, inbound/outbound chat text | HMAC-SHA256 signature verification, webhook replay defense | SMS gateway, SMTP Email channel |
| **Supabase / PostgreSQL** | Primary Database & Auth | Tenant CRM records, memberships, credentials | Managed TLS, connection pooling, automated backups, JTI blacklist | Standby read-replica promotion (RTO < 3m) |
| **Redis** | Distributed Cache & Rate Limiting | Session counters, rate limit buckets | Redis AUTH, non-exposed network plane | In-memory sliding window fallback |
| **Cloudflare / CDN** | Ingress, DDoS, WAF | Public HTTP headers, request paths | Anycast DDoS mitigation, automatic TLS termination | Direct load balancer failover |
| **Stripe / Payment Gateway** | Transaction Processing | Card tokens, payment intents | PCI-DSS Level 1 compliance; no raw PAN stored | Offline bank transfer / invoice workflow |

---

## 2. INTEGRATION CREDENTIAL HYGIENE

1. **Hashed Storage:** Provider API secrets are encrypted at rest using AES-256-GCM via `SecretsManager`. Plaintext secrets are never committed to git repositories or displayed in UI forms after creation.
2. **Zero-Downtime Rotation:** Secrets can be rotated on-the-fly via `/v1/security/secrets/rotate`.
3. **Webhook Verification:** Inbound webhooks from all providers must submit cryptographically verified HMAC signatures. Replay skew exceeding 300 seconds is strictly rejected.
4. **Periodic Review:** Third-party integrations are reviewed quarterly for SOC 2 Type II compliance reports and minimal OAuth permission scopes.
