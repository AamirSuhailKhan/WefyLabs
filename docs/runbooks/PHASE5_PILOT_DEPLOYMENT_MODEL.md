# WEFYLABS AUTONOMOUS REVENUE OS — PHASE 5 PILOT DEPLOYMENT MODEL

**Document Type**: Architectural Deployment Specification & Security Blueprint  
**Target Environment**: Staging / Controlled Pilot Infrastructure  
**Author**: DevOps Lead & Application Security Engineer  
**Status**: Proposal Pending Technical Owner Approval  

---

## 1. Operating Modes Evaluation

The WefyLabs CRM architecture supports two pilot deployment modes:

```
┌────────────────────────────────────────────────────────────────────────┐
│ MODE A: Internal Dry Run (Current Verified Baseline)                   │
│                                                                        │
│   Operator Workstation (127.0.0.1)                                     │
│     ├── API (:8000)                                                    │
│     ├── Postgres (:5432 - loopback)                                    │
│     └── Redis (:6379 - loopback)                                       │
│   Boundary: Zero external WAN network exposure.                        │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│ MODE B: Restricted Remote Pilot (Target for Customer Onboarding)        │
│                                                                        │
│   Remote Broker Users                                                  │
│     │ (HTTPS / TLS 1.3 on Port 443)                                    │
│     ▼                                                                  │
│   [Cloudflare / Edge Firewall]                                         │
│     │ (Origin Certificate / Strict SSL)                                │
│     ▼                                                                  │
│   [Nginx / Caddy Reverse Proxy] (Handles TLS & Rate Limiting)          │
│     │ (Internal Loopback / Docker Network)                             │
│     ├──► leadscore_api (:8000 with --proxy-headers)                    │
│     │     ├── Postgres (:5432 internal only, not exposed on WAN)       │
│     │     └── Redis (:6379 internal only, not exposed on WAN)          │
│     └──► leadscore_web (:3000 Next.js Frontend)                       │
│                                                                        │
│   Boundary: TLS encrypted, JWT authenticated, database strictly closed.│
└────────────────────────────────────────────────────────────────────────┘
```

### 1.1 Operating Mode Comparison

| Feature / Property | Mode A: Internal Dry Run | Mode B: Restricted Remote Pilot |
|---|---|---|
| **Access Boundary** | Local operator machine (`127.0.0.1`) | Whitelisted remote brokerage users |
| **Network Ingress** | None (Localhost only) | Secure HTTPS (Port 443) via Reverse Proxy |
| **TLS Encryption** | Not required (loopback memory) | Mandatory (TLS 1.3 with Let's Encrypt / Cloudflare) |
| **Database Exposure** | `127.0.0.1:5432` | Internal Docker network only (firewalled) |
| **Authentication** | Supabase JWT Bearer token | Supabase JWT Bearer token + Org Scoping |
| **Owner Action Needed** | None (Active now) | Requires DNS, Reverse Proxy, and Certificate approval |

---

## 2. Mode B Architectural Specification

For onboarding remote pilot brokerage users, the following architecture must be deployed:

### 2.1 Reverse Proxy & TLS Configuration (Nginx / Caddy)
1. **Reverse Proxy Role**: Fronts all external HTTP traffic; terminates TLS; enforces HSTS; forwards client headers.
2. **Nginx Configuration Template**:
   ```nginx
   server {
       listen 443 ssl http2;
       server_name pilot.wefylabs.com;

       ssl_certificate /etc/letsencrypt/live/pilot.wefylabs.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/pilot.wefylabs.com/privkey.pem;
       ssl_protocols TLSv1.2 TLSv1.3;
       ssl_ciphers HIGH:!aNULL:!MD5;

       # Security Headers
       add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
       add_header X-Content-Type-Options "nosniff" always;
       add_header X-Frame-Options "DENY" always;
       add_header X-XSS-Protection "1; mode=block" always;

       # API Reverse Proxy
       location /api/ {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_connect_timeout 10s;
           proxy_read_timeout 60s;
       }

       # Web App Frontend
       location / {
           proxy_pass http://127.0.0.1:3000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

### 2.2 Uvicorn Forwarded Header Trust
In `docker-compose.yml`, the API service command must be configured with:
```yaml
command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips "127.0.0.1,172.16.0.0/12"
```
This guarantees that `request.client.host` receives the genuine client IP address rather than the reverse proxy's internal address, enabling accurate IP rate limiting in `check_auth_rate_limit`.

### 2.3 Network Firewall Rules
- **Allow**: Port `80/tcp` (redirect to 443) and Port `443/tcp` (HTTPS).
- **Deny / Internal Only**: Port `5432` (PostgreSQL) and Port `6379` (Redis).
- In `docker-compose.yml`, remove host port publish mappings for database and cache:
  ```yaml
  # Replace "127.0.0.1:5432:5432" with internal network only:
  expose:
    - "5432"
  ```

### 2.4 Enterprise Secret Management
Before transitioning to Mode B:
1. Revoke the existing Google Gemini API key.
2. Store the new key in `.env.pilot` (excluded from git) or an external secrets vault (e.g., AWS Secrets Manager, HashiCorp Vault).
3. Do not hardcode placeholder or fallback credentials in `docker-compose.yml`.

---

## 3. Operational Sign-Off Protocol

The deployment of Mode B requires explicit written authorization from the **Responsible Technical Owner**:

| Step | Action Required | Status |
|---|---|---|
| 1 | Register pilot domain (`pilot.wefylabs.com`) & configure DNS | `[ ] PENDING OWNER ACTION` |
| 2 | Provision TLS certificate (Let's Encrypt / Certbot) | `[ ] PENDING OWNER ACTION` |
| 3 | Deploy Nginx / Caddy reverse proxy | `[ ] PENDING OWNER ACTION` |
| 4 | Remove public port mapping for PostgreSQL (`5432`) & Redis (`6379`) | `[ ] PENDING OWNER ACTION` |
| 5 | Rotate Google Gemini API credential | `[ ] PENDING OWNER ACTION` |

Until these actions are completed and approved, the pilot operates in **Mode A (Internal Dry Run)**.
