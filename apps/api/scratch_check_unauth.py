import json

with open("route_security_matrix.json") as f:
    matrix = json.load(f)

unauth_tenant = []
for m in matrix:
    if m["auth"] == "none":
        path = m["path"]
        # filter out docs, health, metrics, openapi, auth
        if not any(k in path.lower() for k in ["/docs", "/openapi", "/health", "/metrics", "/auth", "/redoc", "favicon"]):
            unauth_tenant.append(m)

print(f"Unauthenticated non-infrastructure routes: {len(unauth_tenant)}")
for u in unauth_tenant:
    methods_str = ",".join(u["methods"])
    print(f"  {methods_str:10} {u['path']} -> {u['endpoint']}")
