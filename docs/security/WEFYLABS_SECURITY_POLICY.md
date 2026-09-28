# WEFYLABS — ENTERPRISE INFORMATION SECURITY POLICY

**Document Reference:** SEC-POL-001  
**Classification:** PUBLIC / INTERNAL  
**Authority:** Chief Security Officer + Chief Technology Officer  
**Last Updated:** 2026-09-27 (Master Build 11)  
**Status:** ACTIVE — PRODUCTION TRUTH  

---

## 1. OBJECTIVE & SCOPE

This policy defines the high-level information security principles, governance structure, and defense-in-depth controls mandated across the WefyLabs real estate CRM and AI operating platform. It applies to all infrastructure, microservices, databases, caching tiers, worker clusters, web applications, mobile interfaces, and AI agent workloads operated by WefyLabs.

---

## 2. CORE SECURITY PRINCIPLES

1. **Zero-Trust Tenancy:** Every request must establish identity, authenticate cryptographically, resolve a verified tenant organization, and authorize permissions at the object boundary. No component may rely solely on network location or upstream trust.
2. **Fail-Closed Tenancy:** `UNKNOWN TENANT = REJECT`. If a tenant organization cannot be resolved or is invalid, the request must fail with HTTP 400, 403, or 409. The platform must never fall back to a default, global, or inferred organization.
3. **Defense in Depth:** Security controls are enforced independently across web clients, API gateways, dependency middleware, domain services, database queries, and asynchronous worker queues.
4. **Least Privilege:** Users, services, background workers, and AI agents possess only the minimal privileges required to complete their designated business functions.
5. **Continuous Auditability:** Every security-sensitive transaction, authentication attempt, permission mutation, export, deletion, and administrative action is written to an immutable, append-only audit trail.

---

## 3. IDENTITY & AUTHENTICATION STANDARDS

- **Token Validation:** Supabase JWT tokens are cryptographically verified using HS256/RS256 algorithms. Token expiration (`exp`), issuance (`iat`), and subject (`sub`/`email`) claims are validated server-side.
- **Session Revocation:** Revoked tokens are registered in an immediate `TokenBlacklist` (JTI registry) for zero-latency session termination.
- **Password Hygiene:** Managed according to NIST SP 800-63B standards (12-character minimum, mixed casing, numeric digits, special symbols, and PBKDF2-HMAC-SHA256 with 100,000 iterations and salt).

---

## 4. TENANT ISOLATION & OBJECT-LEVEL AUTHORIZATION

- **Organization Scoping:** Every CRM record (`Lead`, `Deal`, `Task`, `Meeting`, `Booking`, `Payment`, `AuditLog`) is strictly scoped by `organization_id` or authenticated `broker_id`.
- **IDOR Protection:** Object lookups using UUIDs or sequential identifiers enforce composite ownership queries (`WHERE id = :id AND organization_id = :org_id`). Attempting to access foreign tenant records returns HTTP 404 or 403 without data leakage.

---

## 5. NETWORK & WEB SECURITY

- **CORS:** Restricted to verified production origins. Wildcard `*` origins are strictly prohibited on authenticated API endpoints.
- **Security Headers:** Injected by `SecurityHeadersMiddleware`:
  - `Content-Security-Policy`: Default-src 'self', script-src 'self', frame-ancestors 'none'.
  - `Strict-Transport-Security`: `max-age=31536000; includeSubDomains; preload`.
  - `X-Frame-Options`: `DENY` (clickjacking defense).
  - `X-Content-Type-Options`: `nosniff`.
  - `Permissions-Policy`: Camera, microphone, and geolocation disabled by default.

---

## 6. COMPLIANCE & GOVERNANCE COMMITMENT

WefyLabs operates in alignment with SOC 2 Type II, ISO/IEC 27001, and GDPR Article 15/17 standards. All operational procedures, incident response timelines, data retention schedules, and vendor reviews are formally codified in accompanying policy documents.
