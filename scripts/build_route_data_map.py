import os
import re
import json

app_dir = r"apps/web/src/app"

routes = []

for root, dirs, files in os.walk(app_dir):
    for f in files:
        if f == "page.tsx":
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, app_dir).replace("\\", "/")
            route_path = "/" + rel_path.replace("/page.tsx", "")
            if route_path == "/page":
                route_path = "/"
            elif route_path.endswith("/page"):
                route_path = route_path[:-5]

            with open(full_path, "r", encoding="utf-8") as fp:
                content = fp.read()

            # Find API calls
            api_calls = set()
            for m in re.finditer(r'api\.([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)?)', content):
                api_calls.add(m.group(0))
            for m in re.finditer(r'fetcher<[^>]+>\([\'"`]([^\'"`]+)[\'"`]', content):
                api_calls.add(f"fetcher({m.group(1)})")
            for m in re.finditer(r'fetch\([\'"`]([^\'"`]+)[\'"`]', content):
                api_calls.add(f"fetch({m.group(1)})")

            # Check states
            has_loading = bool(re.search(r'loading|isLoading|Skeleton', content, re.I))
            has_empty = bool(re.search(r'empty|EmptyState|no \w+ found|length === 0', content, re.I))
            has_error = bool(re.search(r'error|isError|setError|catch', content, re.I))

            # Shell
            layout = "Canonical AppShell (DashboardLayoutClient)" if route_path.startswith("/dashboard") else "Root Layout"

            routes.append({
                "route": route_path,
                "file": rel_path,
                "api_calls": sorted(list(api_calls)),
                "has_loading": has_loading,
                "has_empty": has_empty,
                "has_error": has_error,
                "layout": layout
            })

routes.sort(key=lambda x: x["route"])
print(f"Total routes analyzed: {len(routes)}")
with open("scripts/route_analysis.json", "w", encoding="utf-8") as out:
    json.dump(routes, out, indent=2)

print("Saved scripts/route_analysis.json")
