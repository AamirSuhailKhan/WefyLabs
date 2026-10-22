import json
import inspect
from app.main import app
from fastapi.routing import APIRoute

with open("all_extracted_routes.json") as f:
    routes = json.load(f)

print(f"Loaded {len(routes)} routes.")

audit_results = []

for r in routes:
    path = r["path"]
    methods = r["methods"]
    mod_name = r["module"]
    ep_name = r["endpoint"]
    
    # Try importing module and endpoint
    try:
        mod = __import__(mod_name, fromlist=[ep_name])
        ep = getattr(mod, ep_name)
        sig = inspect.signature(ep)
        src = inspect.getsource(ep)
        
        # Check auth dependency
        auth_dep = "none"
        if "get_current_broker" in src:
            auth_dep = "get_current_broker"
        elif "get_current_active_broker" in src:
            auth_dep = "get_current_active_broker"
        elif "get_current_super_admin" in src:
            auth_dep = "get_current_super_admin"
        elif "verify_webhook_signature" in src or "webhook" in path.lower():
            auth_dep = "webhook_signature"
        elif "public" in path.lower() or "health" in path.lower() or "auth" in path.lower():
            auth_dep = "public_or_auth"
            
        # Check tenant isolation mechanism
        tenancy_mechanism = "none"
        if "resolve_organization_id_for_broker" in src:
            tenancy_mechanism = "resolve_organization_id_for_broker"
        elif "organization_id" in src:
            tenancy_mechanism = "scoped_by_organization_id"
        elif "broker_id" in src or "current_broker.id" in src:
            tenancy_mechanism = "scoped_by_broker_id"
            
        audit_results.append({
            "path": path,
            "methods": methods,
            "endpoint": f"{mod_name}.{ep_name}",
            "auth": auth_dep,
            "tenancy": tenancy_mechanism,
            "has_org_scope": "organization_id" in src or "resolve_organization_id_for_broker" in src,
            "has_broker_scope": "broker_id" in src or "current_broker.id" in src,
        })
    except Exception as e:
        audit_results.append({
            "path": path,
            "methods": methods,
            "endpoint": f"{mod_name}.{ep_name}",
            "auth": "error",
            "tenancy": "error",
            "error": str(e)
        })

with open("route_security_matrix.json", "w") as f:
    json.dump(audit_results, f, indent=2)

print(f"Successfully audited {len(audit_results)} endpoints.")

# Summary statistics
auth_counts = {}
tenancy_counts = {}
for a in audit_results:
    auth_counts[a.get("auth", "unknown")] = auth_counts.get(a.get("auth", "unknown"), 0) + 1
    tenancy_counts[a.get("tenancy", "unknown")] = tenancy_counts.get(a.get("tenancy", "unknown"), 0) + 1

print("\n--- Authentication Breakdown ---")
for k, v in sorted(auth_counts.items()):
    print(f"  {k}: {v}")

print("\n--- Tenancy Isolation Breakdown ---")
for k, v in sorted(tenancy_counts.items()):
    print(f"  {k}: {v}")
