# PHASE 0 AUTHORIZATION MATRIX — RBAC & TENANCY ACCESS CONTROLS

**Version:** RC-1 Post-Hardening  
**Verification Target:** Core Routers & Security Dependencies  
**Enforcement Engine:** `apps/api/app/infrastructure/security/rbac.py` + `app/infrastructure/tenancy/scope.py`  

---

| Router | Endpoint | HTTP Method | Authentication Required | Organization Required | Permission | Role Restrictions | Tenant Source | Object-Level Check | Status | Test Reference |
|---|---|---|---|---|---|---|---|---|---|---|
| **Auth** | `/api/v1/auth/register` | `POST` | No | Created during register | None | Public | Request Body | Email unicity check | `VERIFIED` | `test_auth.py` |
| **Auth** | `/api/v1/auth/login` | `POST` | No | Resolved from broker | None | Public | Broker credentials | Active account verification | `VERIFIED` | `test_auth.py` |
| **Auth** | `/api/v1/auth/google/url` | `GET` | No | No | None | Public | Server generated | Cryptographic nonce | `VERIFIED` | `test_authentication_matrix.py` |
| **Auth** | `/api/v1/auth/google/exchange` | `POST` | No | Bound to Google account | None | Public | Verified Google Identity | State + Replay check | `VERIFIED` | `test_authentication_matrix.py` |
| **Auth** | `/api/v1/auth/me` | `GET` | Yes (`get_current_broker`) | No (returns status) | None | Authenticated Broker | JWT claims | Profile lookup | `VERIFIED` | `test_authentication_matrix.py` |
| **Leads** | `/api/v1/leads` | `GET` | Yes (`get_current_broker`) | Yes (`require_organization_id`) | `leads:read` | Agent, Manager, Admin, Owner | Tenant header / session | Tenant scoped query (`Lead.organization_id == org_id`) | `VERIFIED` | `test_tenant_matrix_security.py` |
| **Leads** | `/api/v1/leads` | `POST` | Yes (`get_current_broker`) | Yes (`require_organization_id`) | `leads:write` | Agent, Manager, Admin, Owner | Ambient tenant | Lead assigned to tenant org | `VERIFIED` | `test_tenant_matrix_security.py` |
| **Leads** | `/api/v1/leads/{id}` | `GET` | Yes (`get_current_broker`) | Yes (`require_organization_id`) | `leads:read` | Agent, Manager, Admin, Owner | Lead record org | IDOR check (`lead.organization_id == org_id`) | `VERIFIED` | `test_tenant_matrix_security.py` |
| **Leads** | `/api/v1/leads/{id}` | `PUT` | Yes (`get_current_broker`) | Yes (`require_organization_id`) | `leads:write` | Agent, Manager, Admin, Owner | Lead record org | IDOR check (`lead.organization_id == org_id`) | `VERIFIED` | `test_tenant_matrix_security.py` |
| **Leads** | `/api/v1/leads/{id}` | `DELETE` | Yes (`get_current_broker`) | Yes (`require_organization_id`) | `leads:delete` | Manager, Admin, Owner | Lead record org | IDOR check (`lead.organization_id == org_id`) | `VERIFIED` | `test_tenant_matrix_security.py` |
| **Properties** | `/api/v1/properties` | `GET` | Yes (`get_current_broker`) | Yes (`require_organization_id`) | `properties:read` | Agent, Manager, Admin, Owner | Ambient tenant | `PropertyListing.organization_id == org_id` | `VERIFIED` | `test_properties.py` |
| **Properties** | `/api/v1/properties` | `POST` | Yes (`get_current_broker`) | Yes (`require_organization_id`) | `properties:write` | Agent, Manager, Admin, Owner | Ambient tenant | Created with org foreign key | `VERIFIED` | `test_properties.py` |
| **Properties** | `/api/v1/properties/{id}` | `GET` | Yes (`get_current_broker`) | Yes (`require_organization_id`) | `properties:read` | Agent, Manager, Admin, Owner | Listing record org | IDOR check (`property.organization_id == org_id`) | `VERIFIED` | `test_properties.py` |
| **Deals** | `/api/v1/deals` | `GET` | Yes (`get_current_broker`) | Yes (`require_organization_id`) | `deals:read` | Agent, Manager, Admin, Owner | Ambient tenant | Scoped to organization | `VERIFIED` | `test_deals.py` |
| **Deals** | `/api/v1/deals` | `POST` | Yes (`get_current_broker`) | Yes (`require_organization_id`) | `deals:write` | Agent, Manager, Admin, Owner | Ambient tenant | Deal assigned to org & broker | `VERIFIED` | `test_deals.py` |
| **Billing** | `/api/v1/billing/plans` | `GET` | Yes (`get_current_broker`) | No | `billing:read` | All roles | Server catalog | Authoritative DB plans | `VERIFIED` | `test_razorpay_production.py` |
| **Billing** | `/api/v1/billing/orders` | `POST` | Yes (`get_current_broker`) | Yes (`require_organization_id`) | `billing:manage` | Admin, Owner | Organization record | Server-resolved catalog price | `VERIFIED` | `test_razorpay_production.py` |
| **Billing** | `/api/v1/billing/verify` | `POST` | Yes (`get_current_broker`) | Yes (`require_organization_id`) | `billing:manage` | Admin, Owner | Payment order org | HMAC signature + order matching | `VERIFIED` | `test_razorpay_production.py` |
| **Billing** | `/api/v1/billing/webhook` | `POST` | No (HMAC webhook) | Resolved from payment order | None | Razorpay Provider | Razorpay signature header | HMAC SHA-256 signature verification | `VERIFIED` | `test_razorpay_production.py` |
| **Calendar** | `/api/v1/calendar/meetings` | `GET` | Yes (`get_current_broker`) | Yes (`require_organization_id`) | `calendar:read` | Agent, Manager, Admin, Owner | Ambient tenant | `SchedulingMeeting.organization_id == org_id` | `VERIFIED` | `test_calendar.py` |
| **Super Admin** | `/api/v1/super-admin/*` | `ALL` | Yes (`get_current_broker`) | Global | `super_admin:manage` | Super Admin allowlist only | System root | Operator allowlist check | `VERIFIED` | `test_super_admin.py` |
