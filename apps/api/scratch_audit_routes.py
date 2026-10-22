import json
from app.main import app

route_data = []
for r in app.routes:
    methods = list(getattr(r, "methods", []))
    path = getattr(r, "path", str(r))
    endpoint = getattr(r, "endpoint", None)
    endpoint_name = endpoint.__name__ if endpoint else ""
    endpoint_module = endpoint.__module__ if endpoint else ""
    
    # check dependencies on endpoint
    deps = []
    if hasattr(endpoint, "__annotations__"):
        for param, typ in endpoint.__annotations__.items():
            deps.append(f"{param}: {str(typ)}")
    
    route_data.append({
        "path": path,
        "methods": sorted(methods),
        "endpoint": endpoint_name,
        "module": endpoint_module,
    })

print(f"Total Routes: {len(route_data)}")

modules = {}
for r in route_data:
    mod = r["module"]
    modules.setdefault(mod, []).append(r)

for mod, r_list in sorted(modules.items()):
    print(f"\n[{mod}] ({len(r_list)} routes)")
    for item in r_list:
        methods_str = ",".join(item["methods"])
        print(f"  {methods_str:10} {item['path']} -> {item['endpoint']}")
