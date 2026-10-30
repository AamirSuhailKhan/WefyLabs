"""
Scratch Script: Authoritative API Authorization Inventory
Flattens all routes across FastAPI application, including _IncludedRouter and Mounts.
"""
import sys
sys.path.insert(0, "apps/api")

from app.main import app
from fastapi.routing import APIRoute

def get_all_routes(router_or_app, prefix=""):
    flat_routes = []
    routes = getattr(router_or_app, "routes", [])
    for r in routes:
        if hasattr(r, "router"):
            # _IncludedRouter or Mount
            sub_prefix = prefix + (getattr(r, "prefix", "") or "")
            flat_routes.extend(get_all_routes(r.router, sub_prefix))
        elif isinstance(r, APIRoute):
            full_path = prefix + r.path
            flat_routes.append((full_path, r))
        elif hasattr(r, "routes"):
            flat_routes.extend(get_all_routes(r, prefix))
    return flat_routes

all_routes = get_all_routes(app)
print(f"Total Flattened APIRoutes: {len(all_routes)}")

# Also compare with OpenAPI paths
openapi = app.openapi()
total_openapi_paths = len(openapi.get("paths", {}))
total_operations = sum(len(methods) for methods in openapi.get("paths", {}).values())
print(f"Total OpenAPI Unique Paths: {total_openapi_paths}")
print(f"Total OpenAPI Endpoint Operations: {total_operations}")

# Categorize
public_count = 0
protected_count = 0
public_samples = []

PUBLIC_PATHS = {
    "/docs", "/redoc", "/openapi.json",
    "/health", "/health/live", "/health/ready",
    "/api/v1/health",
    "/api/v1/auth/login", "/api/v1/auth/register",
    "/api/v1/auth/refresh", "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/api/v1/auth/google/login", "/api/v1/auth/google/callback",
    "/metrics", "/",
}

for path, r in all_routes:
    dep_names = [dep.call.__name__ for dep in r.dependencies if hasattr(dep, "call")]
    import inspect
    sig = inspect.signature(r.endpoint)
    for param in sig.parameters.values():
        if hasattr(param.default, "dependency") and param.default.dependency:
            dep_call = param.default.dependency
            dep_names.append(getattr(dep_call, "__name__", str(dep_call)))
            
    has_auth = any(
        d in ("get_current_broker", "get_current_user", "get_current_active_user",
              "get_current_superuser", "verify_api_key", "require_role",
              "get_revenue_org_id", "get_portal_lead", "verify_webhook_signature",
              "get_current_agent", "get_current_admin")
        for d in dep_names
    )
    
    is_public = (
        path in PUBLIC_PATHS 
        or "/webhooks" in path 
        or "/public" in path 
        or "/portal/auth" in path
        or not has_auth
    )
    
    if has_auth and not ("/webhooks" in path and not has_auth):
        is_public = False
        
    if is_public:
        public_count += 1
        public_samples.append((path, list(r.methods), dep_names))
    else:
        protected_count += 1

print(f"Classified Protected Routes: {protected_count}")
print(f"Classified Public/Unauthenticated Routes: {public_count}")
