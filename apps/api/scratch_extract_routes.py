import json
from app.main import app
from fastapi.routing import APIRoute

all_routes = []

def extract_routes(route_list, prefix=""):
    for r in route_list:
        if isinstance(r, APIRoute):
            all_routes.append({
                "path": r.path,
                "methods": sorted(list(r.methods)),
                "endpoint": r.endpoint.__name__,
                "module": r.endpoint.__module__,
                "dependencies": [getattr(d, "dependency", d).__name__ if hasattr(getattr(d, "dependency", d), "__name__") else str(d) for d in r.dependencies]
            })
        elif hasattr(r, "routes"):
            extract_routes(r.routes, prefix)
        elif hasattr(r, "app") and hasattr(r.app, "routes"):
            extract_routes(r.app.routes, prefix)
        elif hasattr(r, "include_context") and hasattr(r.include_context, "included_router"):
            extract_routes(r.include_context.included_router.routes, prefix)
        elif hasattr(r, "original_router"):
            extract_routes(r.original_router.routes, prefix)

extract_routes(app.routes)

# Deduplicate by path + methods
unique_routes = {}
for r in all_routes:
    key = (r["path"], tuple(r["methods"]))
    unique_routes[key] = r

routes_list = list(unique_routes.values())
print(f"Total Unique API Routes Extracted: {len(routes_list)}")

with open("all_extracted_routes.json", "w") as f:
    json.dump(routes_list, f, indent=2)

modules = {}
for r in routes_list:
    mod = r["module"]
    modules.setdefault(mod, []).append(r)

for mod, r_list in sorted(modules.items()):
    print(f"\n[{mod}] ({len(r_list)} routes)")
    for item in r_list:
        methods_str = ",".join(item["methods"])
        print(f"  {methods_str:12} {item['path']} -> {item['endpoint']}")
