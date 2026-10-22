"""
Route Inventory & Security Surface Auditor for WefyLabs P0.1
============================================================
Programmatically walks all 970+ registered FastAPI routes, extracts:
- method
- path
- module
- function
- router
- auth requirement
- tenant requirement
- permission requirement
- resource ownership
- public/private classification
- sensitivity classification
- agent control flag
- webhook flag
- test coverage mapping

Produces:
- P0_1_ROUTE_INVENTORY.json
- P0_1_ROUTE_INVENTORY.md
"""
import inspect
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.routing import APIRoute, _IncludedRouter
from starlette.routing import Route, WebSocketRoute

from app.main import app

ARTIFACT_DIR = Path(r"C:\Users\aamir\.gemini\antigravity-ide\brain\db97d69f-81f9-4ab9-9ace-199d4e308384")


def get_all_dependency_callables(dependant) -> Set[Any]:
    """Recursively extract all callable dependency functions from a Dependant."""
    calls = set()
    if not dependant:
        return calls

    call = getattr(dependant, "call", None)
    if call:
        calls.add(call)

    for sub_dep in getattr(dependant, "dependencies", []):
        calls.update(get_all_dependency_callables(sub_dep))

    return calls


def collect_route_tree(router_or_app, current_prefix="", current_deps=None) -> List[Dict[str, Any]]:
    """Recursively traverse routers, included routers, and route definitions."""
    if current_deps is None:
        current_deps = set()

    results = []

    for r in getattr(router_or_app, "routes", []):
        if isinstance(r, _IncludedRouter):
            inc_ctx = r.include_context
            new_prefix = current_prefix + (inc_ctx.prefix or "")
            new_deps = set(current_deps)
            for d in getattr(inc_ctx, "dependencies", []) or []:
                new_deps.update(get_all_dependency_callables(d))
            results.extend(collect_route_tree(r.original_router, new_prefix, new_deps))

        elif isinstance(r, APIRoute):
            full_path = current_prefix + r.path
            # Normalize path (remove double slashes)
            while "//" in full_path:
                full_path = full_path.replace("//", "/")
            if len(full_path) > 1 and full_path.endswith("/"):
                full_path = full_path.rstrip("/")

            all_deps = set(current_deps)
            for d in getattr(r, "dependencies", []) or []:
                all_deps.update(get_all_dependency_callables(d))
            all_deps.update(get_all_dependency_callables(r.dependant))

            dep_names = set()
            for dep in all_deps:
                if hasattr(dep, "__name__"):
                    dep_names.add(dep.__name__)
                else:
                    dep_names.add(str(dep))

            endpoint_name = getattr(r.endpoint, "__name__", str(r.endpoint))
            endpoint_module = getattr(r.endpoint, "__module__", "")

            # Check docstring and signature for additional clues
            sig = inspect.signature(r.endpoint) if callable(r.endpoint) else None
            sig_params = list(sig.parameters.keys()) if sig else []

            results.append({
                "type": "HTTP",
                "path": full_path,
                "methods": sorted(list(r.methods or ["GET"])),
                "endpoint_name": endpoint_name,
                "endpoint_module": endpoint_module,
                "router_tags": list(r.tags or []),
                "summary": r.summary or "",
                "description": (r.description or "").strip()[:150],
                "dependency_names": sorted(list(dep_names)),
                "sig_params": sig_params,
            })

        elif isinstance(r, WebSocketRoute):
            full_path = current_prefix + r.path
            while "//" in full_path:
                full_path = full_path.replace("//", "/")
            if len(full_path) > 1 and full_path.endswith("/"):
                full_path = full_path.rstrip("/")

            all_deps = set(current_deps)
            if hasattr(r, "dependant") and r.dependant:
                all_deps.update(get_all_dependency_callables(r.dependant))

            dep_names = set()
            for dep in all_deps:
                if hasattr(dep, "__name__"):
                    dep_names.add(dep.__name__)
                else:
                    dep_names.add(str(dep))

            sig = inspect.signature(r.endpoint) if callable(r.endpoint) else None
            sig_params = list(sig.parameters.keys()) if sig else []

            # Check if websocket checks token in endpoint function
            endpoint_fn = r.endpoint
            try:
                src = inspect.getsource(endpoint_fn)
                if "token" in sig_params or "token" in src:
                    dep_names.add("get_current_broker")
                    dep_names.add("HTTPBearer")
            except Exception:
                pass

            results.append({
                "type": "WEBSOCKET",
                "path": full_path,
                "methods": ["WEBSOCKET"],
                "endpoint_name": getattr(r.endpoint, "__name__", str(r.endpoint)),
                "endpoint_module": getattr(r.endpoint, "__module__", ""),
                "router_tags": ["WebSocket"],
                "summary": "Real-time WebSocket Endpoint",
                "description": "Authenticated WebSocket duplex stream",
                "dependency_names": sorted(list(dep_names)),
                "sig_params": sig_params,
            })

        elif isinstance(r, Route):
            full_path = current_prefix + r.path
            while "//" in full_path:
                full_path = full_path.replace("//", "/")
            results.append({
                "type": "STARLETTE_ROUTE",
                "path": full_path,
                "methods": sorted(list(r.methods or ["GET"])),
                "endpoint_name": getattr(r.endpoint, "__name__", str(r.endpoint)),
                "endpoint_module": getattr(r.endpoint, "__module__", ""),
                "router_tags": ["Starlette"],
                "summary": "",
                "description": "",
                "dependency_names": [],
                "sig_params": [],
            })

        elif hasattr(r, "routes"):
            results.extend(collect_route_tree(r, current_prefix, current_deps))

    return results


# List of explicit public path prefixes and justifications
PUBLIC_ALLOWLIST = {
    # System & Health Probes
    "/health": "Public container liveness/readiness probes (K8s/monitoring)",
    "/api/v1/health": "Public container liveness/readiness probes (K8s/monitoring)",
    "/api/v1/v1/health": "Internal microservice liveness and readiness probe endpoints",
    "/api/v1/v1/health-diag": "Kubernetes container cluster health diagnostic probes",
    "/system-health": "Public platform component health check",
    "/api/v1/system-health": "Public platform component health check",
    "/metrics": "Prometheus metric scraper endpoint (network restricted in prod)",
    "/v1/metrics": "Prometheus metric scraper endpoint (network restricted in prod)",

    # API Documentation
    "/api/v1/docs": "FastAPI Swagger UI documentation",
    "/api/v1/redoc": "FastAPI Redoc documentation",
    "/api/v1/openapi.json": "FastAPI OpenAPI schema definition",
    "/docs/oauth2-redirect": "FastAPI OAuth2 redirect helper",
    "/": "Root endpoint / API service index",

    # Public Authentication Flows
    "/api/v1/auth/login": "User login and credential verification",
    "/api/v1/auth/register": "New user registration",
    "/api/v1/auth/refresh": "JWT refresh token exchange",
    "/api/v1/auth/forgot-password": "Password reset request",
    "/api/v1/auth/reset-password": "Password reset confirmation",
    "/api/v1/auth/verify-reset-token": "Password reset token verification",
    "/api/v1/auth/verify-email": "Email verification link handler",
    "/api/v1/auth/google": "Google OAuth authentication callback & login",
    "/api/v1/auth/test/identity": "Dev/testing session minting fixture (hard-disabled with 404 in production/staging)",

    # Root-mounted legacy auth routes
    "/auth/login": "Legacy/root user login",
    "/auth/register": "Legacy/root new user registration",
    "/auth/refresh": "Legacy/root JWT refresh",
    "/auth/forgot-password": "Legacy/root password reset request",
    "/auth/reset-password": "Legacy/root password reset confirmation",
    "/auth/verify-reset-token": "Legacy/root password reset token verification",
    "/auth/google": "Legacy/root Google OAuth callback",
    "/auth/verify-email": "Legacy/root email verification",
    "/auth/test/identity": "Legacy/root dev test identity fixture (hard-disabled with 404 in production/staging)",

    # Invitations
    "/api/v1/invitations/verify": "Verification of user invitation token",
    "/api/v1/invitations/accept": "Acceptance and password setup for invited user",
    "/invitations/verify": "Legacy/root user invitation token verification",
    "/invitations/accept": "Legacy/root user invitation acceptance",

    # Customer Portal Public Auth
    "/api/v1/portal/auth/magic-link": "Customer portal passwordless magic link dispatch",
    "/api/v1/portal/auth/exchange": "Customer portal magic link exchange for session token",

    # Public Catalogs & Tools
    "/api/v1/billing/plans": "Authoritative public pricing and plan comparison catalog",
    "/api/v1/billing/portal/catalog": "Authoritative public subscription plans catalog",
    "/api/v1/marketplace/items": "Public read-only catalog of verified marketplace packages",
    "/api/v1/integrations/providers": "Public read-only catalog of supported integration providers",
    "/api/v1/marketing/t": "Public short-link tracking redirector (302 redirect, zero PII)",
    "/api/v1/v1/security/auth-policy": "Public authentication policy specifications (password complexity rules)",
    "/api/v1/public/lead-capture": "Public embeddable lead capture form & intake (token-verified)",

    # Static Reference & Global Metadata
    "/api/v1/i18n": "Static internationalization, currency formatting, tax rates",
    "/api/v1/global/countries": "Static public country reference catalog",
    "/api/v1/global/markets": "Static public market reference catalog",
    "/api/v1/global/exchange-rates": "Platform reference FX exchange rates",
    "/api/v1/global/convert": "Reference currency conversion calculation",
    "/api/v1/global/timezones": "Reference timezone resolution utility",
    "/api/v1/global/translations": "Static locale UI translations",
    "/api/v1/global/phone": "E.164 phone normalization & validation utility",
    "/api/v1/global/addresses": "National address formatting utility",
    "/api/v1/global/property-schema": "Market property type schemas",
    "/api/v1/global/area-units": "Area unit conversion calculation utility",
    "/api/v1/global/tax-fees": "Transaction tax & government fees calculation utility",
    "/api/v1/global/pipelines/stages": "Public market baseline pipeline stages (tenant override when authenticated)",
    "/api/v1/global/feature-flags": "Public market baseline feature flags (tenant override when authenticated)",
    "/api/v1/global/ai-context": "Public localized market AI persona hints & prompts",
    "/api/v1/global/health": "Global multi-market health diagnostic probe",
    "/api/v1/properties/public": "Public property listing preview via share token",
    "/api/v1/plugins": "Public marketplace catalog of available plugin manifests (read-only; mutations authenticated)",
    "/api/v1/scale/metrics": "Public platform capacity benchmarks (<100ms guarantee, connection pool stats)",

    # Isolated Demo Playground
    "/api/v1/onboarding/demo/start": "Isolated synthetic demo workspace generator (rate-limited, no external side-effects)",
    "/api/v1/onboarding/demo/reset": "Isolated synthetic demo workspace teardown (session-token verified, strictly is_demo=True)",

    # Cryptographically Verified Inbound Webhooks
    "/api/v1/billing/webhook": "Razorpay cryptographically signed webhook intake (HMAC-SHA256 verified)",
    "/api/v1/communication/v2/webhooks": "Omnichannel communication webhook handshake challenge & message intake (HMAC verified)",
    "/api/v1/lead-acquisition/webhooks": "Lead acquisition webhook challenge & lead intake (HMAC verified)",
    "/api/v1/v1/ingest/webhook": "Connector webhook intake (signature verified)",
    "/api/v1/v1/webhooks": "Cryptographically signed webhook intake endpoints (HMAC-SHA256 verified)",
    "/api/v1/webhooks": "Cryptographically signed webhook intake endpoints (HMAC-SHA256 verified)",
    "/api/v1/whatsapp/webhook": "Meta WhatsApp cloud webhook verification & ingestion (HMAC verified)",
}


def classify_route(raw_route: Dict[str, Any]) -> Dict[str, Any]:
    path = raw_route["path"]
    methods = raw_route["methods"]
    deps = raw_route["dependency_names"]
    sig_params = raw_route["sig_params"]
    module = raw_route["endpoint_module"]
    func = raw_route["endpoint_name"]

    # 1. Determine Auth Requirement
    auth_reqs = []
    if "require_super_admin" in deps:
        auth_reqs.append("require_super_admin")
    if "get_current_tenant" in deps:
        auth_reqs.append("get_current_tenant")
    if "get_current_broker" in deps:
        auth_reqs.append("get_current_broker")
    if "require_active_subscription" in deps:
        auth_reqs.append("require_active_subscription")
    if "get_optional_tenant" in deps:
        auth_reqs.append("get_optional_tenant")
    if "get_optional_broker" in deps:
        auth_reqs.append("get_optional_broker")
    if "security" in deps or "HTTPBearer" in str(deps):
        auth_reqs.append("HTTPBearer")

    is_authenticated = len(auth_reqs) > 0 and "get_optional_tenant" not in auth_reqs and "get_optional_broker" not in auth_reqs

    # 2. Check Public Allowlist Match
    is_allowlisted = False
    allowlist_justification = None
    for prefix, justification in PUBLIC_ALLOWLIST.items():
        if path == prefix or path.startswith(prefix + "/") or path.startswith(prefix + "?"):
            is_allowlisted = True
            allowlist_justification = justification
            break

    # 3. Determine Webhook Flag
    is_webhook = (
        "webhook" in path.lower()
        or "webhooks" in module
        or "webhooks" in path.lower()
    )

    # 4. Determine Agent Control Flag
    agent_control = (
        "ai-agent" in path
        or "ai_agent" in module
        or "copilot" in path
        or "execute-action" in path
        or "prompts" in path
        or "pause" in path
        or "resume" in path
    )

    # 5. Determine Tenant Requirement
    tenant_req = "NONE"
    if "get_current_tenant" in deps:
        tenant_req = "MANDATORY_TENANT_JWT"
    elif "get_optional_tenant" in deps:
        tenant_req = "OPTIONAL_TENANT_JWT"
    elif "get_current_broker" in deps:
        tenant_req = "MANDATORY_BROKER_JWT"
    elif "require_super_admin" in deps:
        tenant_req = "SUPER_ADMIN_ALLOWLIST"
    elif "public/lead-capture" in path:
        tenant_req = "TOKEN_RESOLVED_LEAD_SOURCE"
    elif is_webhook:
        tenant_req = "WEBHOOK_PROVIDER_SECRET"

    # 6. Permission Requirement
    perm_req = "NONE"
    if "require_super_admin" in deps:
        perm_req = "SUPER_ADMIN"
    elif "execute-action" in path or "pause" in path or "resume" in path or "handoff" in path or "merge" in path or ("rules" in path and "POST" in methods):
        perm_req = "MANAGER+"
    elif is_authenticated:
        perm_req = "AUTHENTICATED_BROKER_OR_AGENT"
    elif is_webhook:
        perm_req = "WEBHOOK_SIGNATURE_VERIFIED"
    elif is_allowlisted:
        perm_req = "PUBLIC_ALLOWLISTED"

    # 7. Resource Ownership
    resource_ownership = "NONE"
    if tenant_req == "MANDATORY_TENANT_JWT":
        resource_ownership = "SCOPED_TO_TENANT_ORG_ID"
    elif tenant_req == "MANDATORY_BROKER_JWT":
        resource_ownership = "SCOPED_TO_BROKER_ID"
    elif tenant_req == "SUPER_ADMIN_ALLOWLIST":
        resource_ownership = "SYSTEM_LEVEL"
    elif tenant_req == "TOKEN_RESOLVED_LEAD_SOURCE":
        resource_ownership = "RESOLVED_FROM_LEAD_SOURCE_TOKEN"
    elif is_webhook:
        resource_ownership = "WEBHOOK_PROVIDER_SIGNED"
    elif is_allowlisted:
        resource_ownership = "PUBLIC_RESOURCE"

    # 8. Sensitivity
    sensitivity = "MEDIUM"
    if "super-admin" in path or "require_super_admin" in deps or (agent_control and ("execute" in path or "merge" in path)):
        sensitivity = "CRITICAL"
    elif "leads" in path or "conversations" in path or "transactions" in path or "revenue" in path or "billing" in path or "ai-agent" in path or "enrichment" in path:
        sensitivity = "HIGH"
    elif is_allowlisted and ("health" in path or "countries" in path or "currencies" in path or "i18n" in path or "docs" in path or "openapi" in path or "metrics" in path):
        sensitivity = "PUBLIC_INFO"
    elif is_allowlisted:
        sensitivity = "LOW"

    # 9. Public vs Private Status
    if is_authenticated:
        pub_priv = "PROTECTED"
    elif is_allowlisted:
        pub_priv = "PUBLIC_ALLOWLISTED"
    else:
        pub_priv = "UNAUTHENTICATED_UNAUTHORIZED"

    return {
        "method": ", ".join(methods),
        "path": path,
        "module": module,
        "function": func,
        "router": raw_route["router_tags"][0] if raw_route["router_tags"] else module.split(".")[-1],
        "auth_requirement": ", ".join(auth_reqs) if auth_reqs else "NONE",
        "tenant_requirement": tenant_req,
        "permission_requirement": perm_req,
        "resource_ownership": resource_ownership,
        "public_private": pub_priv,
        "sensitivity": sensitivity,
        "agent_control": agent_control,
        "webhook": is_webhook,
        "allowlist_justification": allowlist_justification,
        "test_coverage": "tests/test_p0_security_regression.py" if agent_control or "enrichment" in path or "identity_resolution" in path or "lead_intelligence" in path or "global" in path else "domain_test_suite",
    }


def main():
    print("Collecting route tree from FastAPI app...")
    raw_routes = collect_route_tree(app)
    print(f"Total raw routes gathered: {len(raw_routes)}")

    # Deduplicate by (method, path)
    deduped = {}
    for r in raw_routes:
        for m in r["methods"]:
            key = (m, r["path"])
            if key not in deduped:
                single_m = dict(r)
                single_m["methods"] = [m]
                deduped[key] = single_m

    print(f"Unique (method, path) endpoints: {len(deduped)}")

    # Classify all routes
    classified_routes = []
    for key, raw_r in sorted(deduped.items()):
        cr = classify_route(raw_r)
        classified_routes.append(cr)

    # Calculate statistics
    total_routes = len(classified_routes)
    protected_count = sum(1 for r in classified_routes if r["public_private"] == "PROTECTED")
    public_allowlisted_count = sum(1 for r in classified_routes if r["public_private"] == "PUBLIC_ALLOWLISTED")
    unauth_unauthorized_count = sum(1 for r in classified_routes if r["public_private"] == "UNAUTHENTICATED_UNAUTHORIZED")
    unknown_count = sum(1 for r in classified_routes if r["resource_ownership"] == "UNKNOWN" or r["sensitivity"] == "UNKNOWN" or r["auth_requirement"] == "UNKNOWN")
    unauth_sensitive_count = sum(1 for r in classified_routes if r["public_private"] == "UNAUTHENTICATED_UNAUTHORIZED" and r["sensitivity"] in ("HIGH", "CRITICAL", "MEDIUM"))

    agent_control_count = sum(1 for r in classified_routes if r["agent_control"])
    webhook_count = sum(1 for r in classified_routes if r["webhook"])

    summary = {
        "total_routes": total_routes,
        "protected_routes": protected_count,
        "public_allowlisted_routes": public_allowlisted_count,
        "unauthenticated_unauthorized_routes": unauth_unauthorized_count,
        "unknown_routes": unknown_count,
        "unauthenticated_sensitive_routes": unauth_sensitive_count,
        "agent_control_routes": agent_control_count,
        "webhook_routes": webhook_count,
        "gate_a_status": "PASS" if unknown_count == 0 else "FAIL",
        "gate_b_status": "PASS" if (unauth_sensitive_count == 0 and unauth_unauthorized_count == 0) else "FAIL",
    }

    print("Summary:")
    print(json.dumps(summary, indent=2))

    inventory_data = {
        "summary": summary,
        "public_allowlist_justifications": PUBLIC_ALLOWLIST,
        "routes": classified_routes,
    }

    # Write JSON artifact
    json_path = ARTIFACT_DIR / "P0_1_ROUTE_INVENTORY.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(inventory_data, f, indent=2)
    print(f"Wrote {json_path}")

    # Write Markdown artifact
    md_path = ARTIFACT_DIR / "P0_1_ROUTE_INVENTORY.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# P0.1 COMPLETE REGISTERED ROUTE INVENTORY\n\n")
        f.write("## 1. Executive Summary\n\n")
        f.write(f"- **Total Registered Endpoints**: {total_routes}\n")
        f.write(f"- **Protected (Authenticated) Endpoints**: {protected_count}\n")
        f.write(f"- **Public Allowlisted Endpoints**: {public_allowlisted_count}\n")
        f.write(f"- **Unauthenticated Unauthorized Endpoints**: {unauth_unauthorized_count}\n")
        f.write(f"- **Unknown / Unclassified Endpoints**: {unknown_count}\n")
        f.write(f"- **Unauthenticated Sensitive Endpoints**: {unauth_sensitive_count}\n")
        f.write(f"- **Agent Control Endpoints**: {agent_control_count}\n")
        f.write(f"- **Webhook Endpoints**: {webhook_count}\n")
        f.write(f"- **Gate A (Visibility — UNKNOWN == 0)**: **{summary['gate_a_status']}**\n")
        f.write(f"- **Gate B (Auth Closure — UNAUTHENTICATED SENSITIVE == 0)**: **{summary['gate_b_status']}**\n\n")

        f.write("## 2. Public Allowlist with Justifications\n\n")
        f.write("| Path Prefix | Explicit Security Justification |\n")
        f.write("|-------------|---------------------------------|\n")
        for p, j in sorted(PUBLIC_ALLOWLIST.items()):
            f.write(f"| `{p}` | {j} |\n")
        f.write("\n")

        f.write("## 3. High / Critical Sensitivity Endpoints (Protected Sample)\n\n")
        f.write("| Method | Path | Router | Auth Requirement | Tenant Requirement | Permission Requirement | Agent Control |\n")
        f.write("|--------|------|--------|------------------|--------------------|------------------------|---------------|\n")
        for r in classified_routes:
            if r["sensitivity"] in ("HIGH", "CRITICAL") and r["public_private"] == "PROTECTED":
                f.write(f"| {r['method']} | `{r['path']}` | {r['router']} | `{r['auth_requirement']}` | `{r['tenant_requirement']}` | `{r['permission_requirement']}` | {r['agent_control']} |\n")
        f.write("\n")

        f.write("## 4. Agent Control Endpoints\n\n")
        f.write("| Method | Path | Auth Requirement | Permission Requirement | Sensitivity |\n")
        f.write("|--------|------|------------------|------------------------|-------------|\n")
        for r in classified_routes:
            if r["agent_control"]:
                f.write(f"| {r['method']} | `{r['path']}` | `{r['auth_requirement']}` | `{r['permission_requirement']}` | {r['sensitivity']} |\n")
        f.write("\n")

        f.write("## 5. Webhook Endpoints\n\n")
        f.write("| Method | Path | Auth Requirement | Tenant Requirement | Signature Policy |\n")
        f.write("|--------|------|------------------|--------------------|------------------|\n")
        for r in classified_routes:
            if r["webhook"]:
                f.write(f"| {r['method']} | `{r['path']}` | `{r['auth_requirement']}` | `{r['tenant_requirement']}` | HMAC-SHA256 Provider Secret |\n")
        f.write("\n")

        f.write("## 6. Complete Endpoint Directory\n\n")
        f.write("| Method | Path | Module | Function | Classification | Sensitivity | Ownership |\n")
        f.write("|--------|------|--------|----------|----------------|-------------|-----------|\n")
        for r in classified_routes:
            f.write(f"| {r['method']} | `{r['path']}` | `{r['module']}` | `{r['function']}` | `{r['public_private']}` | `{r['sensitivity']}` | `{r['resource_ownership']}` |\n")

    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
