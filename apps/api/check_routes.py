import sys
sys.path.insert(0, '.')
from app.main import app

def collect_routes(router, prefix=""):
    routes = []
    for route in getattr(router, 'routes', []):
        path = getattr(route, 'path', '')
        if hasattr(route, 'routes'):
            routes.extend(collect_routes(route, prefix + path))
        else:
            routes.append(prefix + path)
    return routes

all_routes = collect_routes(app.router)
sales_routes = [r for r in all_routes if 'sales' in r.lower() or 'follow' in r.lower()]
print(f"\nTotal routes collected: {len(all_routes)}")
print(f"\nSales-action routes ({len(sales_routes)}):")
for r in sales_routes:
    print(f"  {r}")
